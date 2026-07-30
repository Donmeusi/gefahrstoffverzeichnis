import os
import ssl
import logging

try:
    import ldap3
    from ldap3 import Server, Connection, ALL, Tls
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
    base_dn = os.environ.get('LDAP_BASE_DN', '').strip()
    bind_dn = os.environ.get('LDAP_BIND_DN', '').strip()
    bind_password = os.environ.get('LDAP_BIND_PASSWORD', '')
    user_search_filter = os.environ.get('LDAP_USER_SEARCH_FILTER', '(sAMAccountName={username})')
    user_dn_template = os.environ.get('LDAP_USER_DN_TEMPLATE', '').strip()
    default_role = os.environ.get('LDAP_DEFAULT_ROLE', 'lesen').strip().lower()
    require_cert = os.environ.get('LDAP_REQUIRE_CERT', 'false').lower() in ('true', '1', 'yes')

    if default_role not in ('admin', 'moderator', 'benutzer', 'lesen'):
        default_role = 'lesen'

    return {
        'host': host,
        'port': port,
        'use_ssl': use_ssl,
        'base_dn': base_dn,
        'bind_dn': bind_dn,
        'bind_password': bind_password,
        'user_search_filter': user_search_filter,
        'user_dn_template': user_dn_template,
        'default_role': default_role,
        'require_cert': require_cert
    }

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
    
    try:
        # TLS / SSL Zertifikatskonfiguration
        tls_ctx = None
        if cfg['use_ssl'] or cfg['port'] == 636:
            validate = ssl.CERT_REQUIRED if cfg['require_cert'] else ssl.CERT_NONE
            tls_ctx = Tls(validate=validate)

        # Server-Objekt erstellen
        host_str = cfg['host']
        if not (host_str.startswith('ldap://') or host_str.startswith('ldaps://')):
            prefix = 'ldaps://' if (cfg['use_ssl'] or cfg['port'] == 636) else 'ldap://'
            host_str = f"{prefix}{host_str}"

        server = Server(
            host_str,
            port=cfg['port'],
            use_ssl=cfg['use_ssl'] or cfg['port'] == 636,
            tls=tls_ctx,
            get_info=ALL,
            connect_timeout=5
        )

        user_dn = None

        # Methode A: Direct DN Template (z.B. uid={username},ou=users,dc=example,dc=com)
        if cfg['user_dn_template']:
            user_dn = cfg['user_dn_template'].format(username=username)
            conn = Connection(server, user=user_dn, password=password, auto_bind=True)
            conn.unbind()
            return True, {'username': username, 'default_role': cfg['default_role']}

        # Methode B: Service Account Search Bind -> User Direct Bind
        elif cfg['bind_dn'] and cfg['base_dn']:
            # 1. Mit Service Account binden
            admin_conn = Connection(server, user=cfg['bind_dn'], password=cfg['bind_password'], auto_bind=True)
            
            # 2. Nach dem User DN suchen
            search_filter = cfg['user_search_filter'].format(username=username)
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
            user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
            user_conn.unbind()
            return True, {'username': username, 'default_role': cfg['default_role']}

        # Methode C: Direkte Authentifizierung mit Base DN
        elif cfg['base_dn']:
            user_dn = f"cn={username},{cfg['base_dn']}"
            conn = Connection(server, user=user_dn, password=password, auto_bind=True)
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
