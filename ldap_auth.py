import os
import ssl
import logging

try:
    import ldap3
    from ldap3 import (Server, Connection, ALL, Tls,
                       AUTO_BIND_TLS_BEFORE_BIND)
    from ldap3.utils.conv import escape_filter_chars
    from ldap3.utils.dn import escape_rdn
    LDAP3_AVAILABLE = True
except ImportError:
    LDAP3_AVAILABLE = False

logger = logging.getLogger(__name__)

def is_ldap_enabled():
    """Prüft, ob LDAP in den Umgebungsvariablen aktiviert ist."""
    if not LDAP3_AVAILABLE:
        return False
    enabled = os.environ.get('LDAP_ENABLED', 'false').lower() in ('true', '1', 'yes')
    host = os.environ.get('LDAP_HOST', '').strip()
    return enabled and bool(host)

def get_ldap_config():
    """Liest die LDAP/LDAPs Konfigurationswerte aus den Umgebungsvariablen."""
    host = os.environ.get('LDAP_HOST', '').strip()
    port = int(os.environ.get('LDAP_PORT', '636'))
    use_ssl = os.environ.get('LDAP_USE_SSL', 'true').lower() in ('true', '1', 'yes')
    # StartTLS ist der sichere Standard fuer unverschluesseltes LDAP auf Port
    # 389: Die Verbindung wird vor dem Bind auf TLS hochgezogen. Ist auch das
    # aus, wird der Login verweigert, statt das Passwort im Klartext zu senden
    # (F-08).
    start_tls = os.environ.get('LDAP_START_TLS', 'true').lower() in ('true', '1', 'yes')
    base_dn = os.environ.get('LDAP_BASE_DN', '').strip()
    bind_dn = os.environ.get('LDAP_BIND_DN', '').strip()
    bind_password = os.environ.get('LDAP_BIND_PASSWORD', '')
    user_search_filter = os.environ.get('LDAP_USER_SEARCH_FILTER', '(sAMAccountName={username})')
    user_dn_template = os.environ.get('LDAP_USER_DN_TEMPLATE', '').strip()
    default_role = os.environ.get('LDAP_DEFAULT_ROLE', 'lesen').strip().lower()
    # Default an: ohne Pruefung akzeptiert der Client jedes Zertifikat, und die
    # Anwendung schickt Klartext-Anmeldedaten an den Verzeichnisdienst. Wer
    # selbstsignierte Zertifikate nutzt, hinterlegt sie ueber
    # LDAP_CA_CERT_FILE, statt die Pruefung abzuschalten.
    require_cert = os.environ.get('LDAP_REQUIRE_CERT', 'true').lower() in ('true', '1', 'yes')

    if default_role not in ('admin', 'moderator', 'benutzer', 'lesen'):
        default_role = 'lesen'

    return {
        'host': host,
        'port': port,
        'use_ssl': use_ssl,
        'start_tls': start_tls,
        'base_dn': base_dn,
        'bind_dn': bind_dn,
        'bind_password': bind_password,
        'user_search_filter': user_search_filter,
        'user_dn_template': user_dn_template,
        'default_role': default_role,
        'require_cert': require_cert,
        'ca_cert_file': os.environ.get('LDAP_CA_CERT_FILE', '').strip()
    }

def _transportart(cfg):
    """Effektive Transportverschluesselung: 'ssl', 'starttls' oder None."""
    if cfg['use_ssl'] or cfg['port'] == 636:
        return 'ssl'
    if cfg['start_tls']:
        return 'starttls'
    return None


def _verbindung(server, user, password, transport):
    """Baut die Verbindung; bei StartTLS wird TLS vor dem Bind hochgezogen."""
    auto_bind = (AUTO_BIND_TLS_BEFORE_BIND
                 if transport == 'starttls' else True)
    return Connection(server, user=user, password=password,
                      auto_bind=auto_bind)


def pruefe_transport_konfiguration():
    """Warnt beim Start, wenn LDAP ohne TLS konfiguriert ist."""
    if not is_ldap_enabled():
        return
    cfg = get_ldap_config()
    if _transportart(cfg) is None:
        logger.warning(
            'LDAP ist ohne Transportverschluesselung konfiguriert '
            '(LDAP_USE_SSL=false, LDAP_START_TLS=false). Anmeldedaten '
            'wuerden im Klartext uebertragen; Login-Versuche werden '
            'verweigert. LDAP_START_TLS=true setzen oder Port 636 mit '
            'LDAP_USE_SSL=true verwenden.'
        )


def authenticate_ldap(username, password):
    """
    Versucht, einen Benutzer via LDAPs/LDAP zu authentifizieren.
    
    Gibt (success: bool, info_dict: dict_or_str) zurück.
    Bei Erfolg: (True, {'username': username, 'default_role': role})
    Bei Fehler: (False, error_message_str)
    """
    if not is_ldap_enabled():
        return False, "LDAP ist nicht aktiviert oder nicht installiert."
    
    if not username or not password:
        return False, "Benutzername und Passwort erforderlich."

    cfg = get_ldap_config()

    # Ohne SSL und ohne StartTLS gingen Benutzername, Passwort und ggf. das
    # Service-Account-Passwort im Klartext ueber das Netz. Der Login wird
    # deshalb verweigert, statt die unsichere Konfiguration stillschweigend
    # zu akzeptieren (F-08).
    transport = _transportart(cfg)
    if transport is None:
        logger.error(
            "LDAP-Login verweigert: weder SSL noch StartTLS aktiv "
            "(LDAP_USE_SSL=false, LDAP_START_TLS=false). Bitte "
            "LDAP_START_TLS=true setzen oder LDAP_USE_SSL=true mit Port 636 "
            "verwenden."
        )
        return False, ("LDAP ist ohne Transportverschluesselung konfiguriert. "
                       "Der Login wird verweigert; bitte LDAP_START_TLS=true "
                       "setzen oder LDAP_USE_SSL=true mit Port 636 verwenden.")

    try:
        # TLS / SSL Zertifikatskonfiguration. Bei StartTLS gilt dieselbe
        # Zertifikatspruefung wie bei SSL.
        tls_ctx = None
        validate = ssl.CERT_REQUIRED if cfg['require_cert'] else ssl.CERT_NONE
        # Eigenes CA-Bundle (z.B. Unternehmens-PKI) statt abgeschalteter
        # Pruefung. Ohne die Datei greift der System-Speicher.
        if cfg['ca_cert_file']:
            tls_ctx = Tls(validate=validate, ca_certs_file=cfg['ca_cert_file'])
        else:
            tls_ctx = Tls(validate=validate)
        if not cfg['require_cert']:
            logger.warning(
                'LDAP_REQUIRE_CERT ist deaktiviert: das Server-Zertifikat '
                'wird nicht geprueft. LDAP_CA_CERT_FILE hinterlegen statt '
                'die Pruefung abzuschalten.'
            )

        # Server-Objekt erstellen. Bei StartTLS beginnt die Verbindung auf
        # ldap:// und wird vom Client hochgezogen.
        host_str = cfg['host']
        if not (host_str.startswith('ldap://') or host_str.startswith('ldaps://')):
            prefix = 'ldaps://' if transport == 'ssl' else 'ldap://'
            host_str = f"{prefix}{host_str}"

        server = Server(
            host_str,
            port=cfg['port'],
            use_ssl=(transport == 'ssl'),
            tls=tls_ctx,
            get_info=ALL,
            connect_timeout=5
        )

        user_dn = None

        # Methode A: Direct DN Template (z.B. uid={username},ou=users,dc=example,dc=com)
        if cfg['user_dn_template']:
            # escape_rdn maskiert ',', '=', '+' usw., mit denen sich sonst ein
            # anderer DN zusammenbauen liesse.
            user_dn = cfg['user_dn_template'].format(username=escape_rdn(username))
            conn = _verbindung(server, user_dn, password, transport)
            conn.unbind()
            return True, {'username': username, 'default_role': cfg['default_role']}

        # Methode B: Service Account Search Bind -> User Direct Bind
        elif cfg['bind_dn'] and cfg['base_dn']:
            # 1. Mit Service Account binden
            admin_conn = _verbindung(server, cfg['bind_dn'],
                                     cfg['bind_password'], transport)
            
            # 2. Nach dem User DN suchen
            # Ohne Maskierung hebt ein '*)(|(objectClass=*)' den Filter aus.
            search_filter = cfg['user_search_filter'].format(
                username=escape_filter_chars(username))
            admin_conn.search(
                search_base=cfg['base_dn'],
                search_filter=search_filter,
                attributes=['dn', 'cn', 'mail']
            )

            if not admin_conn.entries:
                admin_conn.unbind()
                return False, f"Benutzer '{username}' im LDAP-Verzeichnis nicht gefunden."

            user_dn = admin_conn.entries[0].entry_dn
            admin_conn.unbind()

            # 3. Mit gefundenem User DN & eingegebenem Passwort binden
            user_conn = _verbindung(server, user_dn, password, transport)
            user_conn.unbind()
            return True, {'username': username, 'default_role': cfg['default_role']}

        # Methode C: Direkte Authentifizierung mit Base DN
        elif cfg['base_dn']:
            user_dn = f"cn={escape_rdn(username)},{cfg['base_dn']}"
            conn = _verbindung(server, user_dn, password, transport)
            conn.unbind()
            return True, {'username': username, 'default_role': cfg['default_role']}

        else:
            return False, "LDAP-Konfiguration unvollständig (Base DN oder DN Template erforderlich)."

    except ldap3.core.exceptions.LDAPBindError as e:
        logger.warning(f"LDAP Bind fehlgeschlagen für '{username}': {e}")
        return False, "Ungültiges LDAP-Passwort oder Benutzer nicht gefunden."
    except Exception as e:
        logger.error(f"Fehler bei LDAP-Authentifizierung für '{username}': {e}")
        return False, f"LDAP-Verbindungsfehler: {str(e)}"


# Beim Import (Anwendungsstart) einmal pruefen: Eine Konfiguration ohne SSL
# und ohne StartTLS wird sichtbar gemeldet, auch wenn sich niemand anmeldet.
pruefe_transport_konfiguration()
