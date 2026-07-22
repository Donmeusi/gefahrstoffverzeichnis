from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import text
import os
import json
import subprocess
import platform
import threading
import time
from datetime import datetime
from flask_wtf.csrf import CSRFProtect
import pandas as pd
from io import BytesIO
import pdfplumber
import re
import qrcode
import base64
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# Reverse Proxy Unterstützung (z.B. für Nginx/Apache Subdomains wie gefstoff.hs-anhalt.de)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# --- Security & Session Configuration ---
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Falls Sie HTTPS verwenden, setzen Sie SESSION_COOKIE_SECURE = True in der Produktion
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True

app_data_dir = os.environ.get('APP_DATA_DIR', os.path.join(basedir, 'data'))
os.makedirs(app_data_dir, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app_data_dir, 'gefahrstoffe.db')




UPLOAD_FOLDER = os.path.join(app_data_dir, 'uploads')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

csrf = CSRFProtect(app)

APP_VERSION = "2.0.1"

@app.context_processor
def inject_globals():
    return {
        'APP_VERSION': APP_VERSION,
        'CURRENT_YEAR': datetime.utcnow().year
    }

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file_with_stoff_name(file_obj, stoff_name, suffix=""):
    """
    Speichert eine Datei und benennt sie nach dem Stoffnamen um.
    Beispiel: stoff_name="Aceton", suffix="SDB" -> Aceton_SDB.pdf
    """
    import re
    ext = file_obj.filename.rsplit('.', 1)[1].lower() if '.' in file_obj.filename else 'pdf'
    
    # Bereinige den Stoffnamen für Dateinamen
    safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', stoff_name)
    if not safe_name.strip('_'):
        safe_name = "stoff"
        
    base_name = f"{safe_name}_{suffix}" if suffix else safe_name
    
    filename = secure_filename(f"{base_name}.{ext}")
    if not filename: 
        filename = f"dokument_{suffix}.{ext}" if suffix else f"dokument.{ext}"
        
    counter = 1
    original_filename = filename
    name_part, ext_part = os.path.splitext(original_filename)
    
    while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        filename = f"{name_part}_{counter}{ext_part}"
        counter += 1
        
    file_obj.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename

app.jinja_env.globals.update(getattr=getattr)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Bitte logge dich ein, um diese Seite zu sehen."

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─── Assoziationstabelle User <-> Bereich ────────────────────────────────────
user_bereiche = db.Table('user_bereiche',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('bereich_id', db.Integer, db.ForeignKey('bereich.id'), primary_key=True)
)

# ─── Modelle ─────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    _is_admin     = db.Column('is_admin', db.Boolean, default=False, nullable=False)
    # Rollen: 'admin' | 'moderator' | 'benutzer'
    role          = db.Column(db.String(20), default='benutzer', nullable=False)
    created_by    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Bereiche, die diesem Benutzer (als regulärer User) zugewiesen sind
    assigned_bereiche = db.relationship(
        'Bereich', secondary=user_bereiche,
        back_populates='assigned_users', lazy='dynamic'
    )

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_mod_or_admin(self):
        return self.role in ('admin', 'moderator')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(50))  # CREATE, UPDATE, DELETE
    entity_type = db.Column(db.String(50))  # Gefahrstoff, etc.
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    
    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))


class Bereich(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    # Wer hat diesen Bereich erstellt (Moderator oder Admin)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    unterbereiche = db.relationship(
        'Unterbereich', backref='bereich', lazy=True, cascade="all, delete-orphan"
    )
    assigned_users = db.relationship(
        'User', secondary=user_bereiche,
        back_populates='assigned_bereiche', lazy='dynamic'
    )


class Unterbereich(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    bereich_id = db.Column(db.Integer, db.ForeignKey('bereich.id'), nullable=False)
    parent_id  = db.Column(db.Integer, db.ForeignKey('unterbereich.id'), nullable=True)
    
    gefahrstoffe = db.relationship('Gefahrstoff', backref='unterbereich', lazy=True)
    children = db.relationship(
        'Unterbereich', 
        backref=db.backref('parent', remote_side=[id]), 
        lazy=True, 
        cascade="all, delete-orphan"
    )

    def get_full_path(self):
        parts = []
        current = self
        while current:
            parts.insert(0, current.name)
            current = current.parent
        return f"{self.bereich.name} &rsaquo; {' &rsaquo; '.join(parts)}"


class Gefahrstoff(db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(100), nullable=False)
    cas_nummer          = db.Column(db.String(20), nullable=True)
    eg_nummer           = db.Column(db.String(20), nullable=True)
    signalwort          = db.Column(db.String(10), nullable=True)
    piktogramme         = db.Column(db.String(100), nullable=True)
    gefahrenkategorien  = db.Column(db.String(500), nullable=True)
    h_saetze            = db.Column(db.String(200), nullable=True)
    p_saetze            = db.Column(db.String(300), nullable=True)
    lagerort            = db.Column(db.String(100), nullable=True)
    lagerklasse         = db.Column(db.String(10), nullable=True)
    menge               = db.Column(db.Float, nullable=True)
    mengeneinheit       = db.Column(db.String(10), nullable=True)
    datum_erfassung     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sdb_datum           = db.Column(db.Date, nullable=True)
    substitutionspruefung = db.Column(db.String(10), nullable=True)
    ersatzstoff         = db.Column(db.String(200), nullable=True)
    begruendung         = db.Column(db.String(500), nullable=True)
    sicherheitsdatenblatt = db.Column(db.String(200), nullable=True)
    betriebsanweisung   = db.Column(db.String(200), nullable=True)
    gefaehrdungsbeurteilung = db.Column(db.String(200), nullable=True)
    is_deleted          = db.Column(db.Boolean, default=False)
    is_approved         = db.Column(db.Boolean, default=True)
    deleted_at          = db.Column(db.DateTime, nullable=True)
    unterbereich_id     = db.Column(db.Integer, db.ForeignKey('unterbereich.id'), nullable=True)
    user_id             = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def __repr__(self):
        return f'<Gefahrstoff {self.name}>'

    @property
    def trgs_warnings(self):
        try:
            from trgs510 import check_zusammenlagerung
        except ImportError:
            return []
            
        warnings = []
        if not self.unterbereich_id or not self.lagerklasse:
            return warnings
            
        for other in self.unterbereich.gefahrstoffe:
            if other.id != self.id and other.lagerklasse and not getattr(other, 'is_deleted', False):
                allowed, msg = check_zusammenlagerung(self.lagerklasse, other.lagerklasse)
                if not allowed:
                    warnings.append(f"Konflikt mit {other.name} (LGK {other.lagerklasse}): {msg}")
        return warnings

# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def log_audit_event(action, entity_type, entity_id, details=""):
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details) if isinstance(details, dict) else details
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Failed to log audit event: {e}")

def get_accessible_bereiche():
    """Gibt die Bereiche zurück, auf die der aktuelle Benutzer Zugriff hat."""
    if current_user.is_admin:
        return Bereich.query.order_by(Bereich.name).all()
    elif current_user.role == 'moderator':
        owned = Bereich.query.filter_by(owner_id=current_user.id).all()
        assigned = current_user.assigned_bereiche.all()
        all_b = list({b.id: b for b in owned + assigned}.values())
        all_b.sort(key=lambda x: x.name)
        return all_b
    else:
        return current_user.assigned_bereiche.order_by(Bereich.name).all()


def is_cmr_stoff(h_saetze):
    if not h_saetze:
        return False
    cmr_codes = ['H350', 'H350i', 'H351', 'H340', 'H341', 'H360', 'H360F', 'H360D', 'H360FD', 'H360Fd', 'H360Df', 'H361', 'H361f', 'H361d', 'H361fd', 'H362']
    return any(code in h_saetze for code in cmr_codes)

def get_gefahrstoff_query():
    """Gibt eine gefilterte Query für Gefahrstoffe zurück."""
    base_query = Gefahrstoff.query.filter(Gefahrstoff.is_deleted == False, Gefahrstoff.is_approved == True)
    
    if current_user.is_admin:
        return base_query

    if current_user.role == 'moderator':
        owned_ids   = [b.id for b in Bereich.query.filter_by(owner_id=current_user.id).all()]
        assigned_ids = [b.id for b in current_user.assigned_bereiche.all()]
        all_ids     = list(set(owned_ids + assigned_ids))
        sub_ids     = [u.id for u in Unterbereich.query.filter(Unterbereich.bereich_id.in_(all_ids)).all()]
        return base_query.filter(
            db.or_(
                Gefahrstoff.unterbereich_id.in_(sub_ids),
                db.and_(Gefahrstoff.unterbereich_id.is_(None), Gefahrstoff.user_id == current_user.id)
            )
        )

    # Regulärer Benutzer
    assigned_ids = [b.id for b in current_user.assigned_bereiche.all()]
    sub_ids      = [u.id for u in Unterbereich.query.filter(Unterbereich.bereich_id.in_(assigned_ids)).all()]
    return base_query.filter(
        db.or_(
            Gefahrstoff.unterbereich_id.in_(sub_ids),
            Gefahrstoff.user_id == current_user.id
        )
    )


def can_edit_gefahrstoff(stoff):
    """Prüft, ob der aktuelle Benutzer den Gefahrstoff bearbeiten darf."""
    if current_user.is_admin:
        return True
        
    if stoff.unterbereich_id:
        if current_user.role == 'moderator' and stoff.unterbereich.bereich.owner_id == current_user.id:
            return True
        return stoff.unterbereich.bereich in current_user.assigned_bereiche.all()
        
    return stoff.user_id == current_user.id


def can_manage_bereich(bereich):
    """Prüft, ob der aktuelle Benutzer diesen Bereich verwalten darf."""
    if current_user.is_admin:
        return True
    if current_user.role == 'moderator':
        return bereich.owner_id == current_user.id or bereich in current_user.assigned_bereiche.all()
    return False

# ─── Auth ────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Erster Benutzer wird als Admin registriert, danach ist die Registrierung deaktiviert."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if User.query.count() > 0:
        flash('Die Registrierung ist deaktiviert. Bitte wende dich an den Administrator.', 'info')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Bitte Benutzername und Passwort eingeben.', 'error')
            return redirect(url_for('register'))
            
        user = User(username=username, role='admin')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        log_audit_event(user.id, "USER_CREATE", "Erster Admin-Benutzer bei Systemstart angelegt.")
        flash('Erster Admin-Benutzer erfolgreich erstellt! Bitte einloggen.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('Ungültiger Benutzername oder Passwort', 'error')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ─── Startseite ──────────────────────────────────────────────────────────────

def get_filtered_gefahrstoff_query_for_request():
    bereich_id = request.args.get('bereich_id', type=int)
    unterbereich_id = request.args.get('unterbereich_id', type=int)
    query = get_gefahrstoff_query()
    aktiver_bereich = None
    aktiver_unterbereich = None
    error_message = None

    if bereich_id:
        aktiver_bereich = Bereich.query.get(bereich_id)
        if aktiver_bereich and not can_manage_bereich(aktiver_bereich) \
                and aktiver_bereich not in current_user.assigned_bereiche.all() \
                and not current_user.is_admin:
            error_message = 'Kein Zugriff auf diesen Bereich.'
            return query.filter(False), None, None, error_message
        if aktiver_bereich:
            query = query.join(Unterbereich).filter(Unterbereich.bereich_id == bereich_id)

    elif unterbereich_id:
        aktiver_unterbereich = Unterbereich.query.get(unterbereich_id)
        if aktiver_unterbereich:
            aktiver_bereich = aktiver_unterbereich.bereich
            if not can_manage_bereich(aktiver_bereich) \
                    and aktiver_bereich not in current_user.assigned_bereiche.all() \
                    and not current_user.is_admin:
                error_message = 'Kein Zugriff auf diesen Standort.'
                return query.filter(False), None, None, error_message
            
            def get_all_child_ids(ub):
                ids = [ub.id]
                for child in ub.children:
                    ids.extend(get_all_child_ids(child))
                return ids
            
            child_ids = get_all_child_ids(aktiver_unterbereich)
            query = query.filter(Gefahrstoff.unterbereich_id.in_(child_ids))

    return query, aktiver_bereich, aktiver_unterbereich, error_message


@app.route('/')
@login_required
def index():
    query, aktiver_bereich, aktiver_unterbereich, error_message = get_filtered_gefahrstoff_query_for_request()
    
    if error_message:
        flash(error_message, 'error')
        if request.args.get('bereich_id') or request.args.get('unterbereich_id'):
            return redirect(url_for('index'))
            
    bereiche = get_accessible_bereiche()
    gefahrstoffe = query.order_by(Gefahrstoff.name).all()
    
    # KPIs berechnen
    stats_total = len(gefahrstoffe)
    
    # Abgelaufene SDBs (älter als 3 Jahre)
    today = datetime.utcnow().date()
    stats_expired_sdb = 0
    for stoff in gefahrstoffe:
        if stoff.sicherheitsdatenblatt and stoff.sdb_datum:
            diff_years = (today - stoff.sdb_datum).days / 365
            if diff_years >= 3:
                stats_expired_sdb += 1
                
    # Anzahl der Standorte (distinct unterbereich_id)
    stats_locations = len(set(stoff.unterbereich_id for stoff in gefahrstoffe if stoff.unterbereich_id))

    return render_template('index.html', 
                           gefahrstoffe=gefahrstoffe,
                           bereiche=bereiche, 
                           aktiver_bereich=aktiver_bereich,
                           aktiver_unterbereich=aktiver_unterbereich,
                           today=today,
                           stats_total=stats_total,
                           stats_expired_sdb=stats_expired_sdb,
                           stats_locations=stats_locations)

@app.route('/betriebsanweisungen')
@login_required
def betriebsanweisungen_list():
    query = get_gefahrstoff_query()
    # Nur Stoffe mit Betriebsanweisung, alphabetisch sortiert
    stoffe = query.filter(Gefahrstoff.betriebsanweisung.isnot(None)).order_by(Gefahrstoff.name).all()
    return render_template('betriebsanweisungen.html', gefahrstoffe=stoffe)

@app.route('/sicherheitsdatenblaetter')
@login_required
def sicherheitsdatenblaetter_list():
    query = get_gefahrstoff_query()
    # Nur Stoffe mit Sicherheitsdatenblatt, alphabetisch sortiert
    stoffe = query.filter(Gefahrstoff.sicherheitsdatenblatt.isnot(None)).order_by(Gefahrstoff.name).all()
    return render_template('sicherheitsdatenblaetter.html', gefahrstoffe=stoffe, today=datetime.utcnow().date())

# ─── Standorte ───────────────────────────────────────────────────────────────

@app.route('/locations', methods=['GET', 'POST'])
@login_required
def locations():
    if current_user.role == 'benutzer':
        flash('Keine Berechtigung für die Standortverwaltung.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_bereich':
            name = request.form.get('bereich_name')
            if name:
                neuer_bereich = Bereich(name=name, owner_id=current_user.id)
                db.session.add(neuer_bereich)
                db.session.commit()
                flash(f'Bereich "{name}" erfolgreich hinzugefügt.', 'success')

        elif action == 'add_unterbereich':
            name       = request.form.get('unterbereich_name')
            parent_sel = request.form.get('parent_selection')
            
            if name and parent_sel:
                if parent_sel.startswith('B_'):
                    bereich_id = int(parent_sel[2:])
                    parent_id = None
                elif parent_sel.startswith('U_'):
                    parent_id = int(parent_sel[2:])
                    parent_ub = Unterbereich.query.get(parent_id)
                    bereich_id = parent_ub.bereich_id if parent_ub else None
                else:
                    bereich_id = None
                    
                if bereich_id:
                    bereich = Bereich.query.get(bereich_id)
                    if bereich and can_manage_bereich(bereich):
                        neuer = Unterbereich(name=name, bereich_id=bereich_id, parent_id=parent_id)
                        db.session.add(neuer)
                        db.session.commit()
                        flash(f'Unterbereich "{name}" erfolgreich hinzugefügt.', 'success')
                    else:
                        flash('Keine Berechtigung für diesen Bereich.', 'error')
                else:
                    flash('Keine Berechtigung für diesen Bereich.', 'error')

        return redirect(url_for('locations'))

    bereiche = get_accessible_bereiche()
    return render_template('locations.html', bereiche=bereiche)

@app.route('/location/<int:id>/qr')
@login_required
def location_qr(id):
    unterbereich = Unterbereich.query.get_or_404(id)
    
    # Check permissions
    if not can_manage_bereich(unterbereich.bereich) \
            and unterbereich.bereich not in current_user.assigned_bereiche.all() \
            and not current_user.is_admin:
        flash('Kein Zugriff auf diesen Standort.', 'error')
        return redirect(url_for('locations'))

    # Generate URL filtering by this unterbereich
    url = url_for('index', unterbereich_id=unterbereich.id, _external=True)
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # Create image in memory
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return render_template('print_qr.html', unterbereich=unterbereich, qr_code_b64=img_b64)


@app.route('/location/delete_bereich/<int:id>', methods=['POST'])
@login_required
def delete_bereich(id):
    bereich = Bereich.query.get_or_404(id)
    if not can_manage_bereich(bereich):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('locations'))
    try:
        db.session.delete(bereich)
        db.session.commit()
        flash(f'Bereich "{bereich.name}" gelöscht.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen: {str(e)}', 'error')
    return redirect(url_for('locations'))


@app.route('/location/delete_unterbereich/<int:id>', methods=['POST'])
@login_required
def delete_unterbereich(id):
    unterbereich = Unterbereich.query.get_or_404(id)
    if not can_manage_bereich(unterbereich.bereich):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('locations'))
    try:
        for stoff in unterbereich.gefahrstoffe:
            stoff.unterbereich_id = None
        db.session.delete(unterbereich)
        db.session.commit()
        flash(f'Unterbereich "{unterbereich.name}" gelöscht.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen: {str(e)}', 'error')
    return redirect(url_for('locations'))

# ─── Gefahrstoffe ────────────────────────────────────────────────────────────

@app.route('/view/<int:id>')
@login_required
def view_stoff(id):
    stoff = Gefahrstoff.query.get_or_404(id)
    accessible = get_gefahrstoff_query().filter(Gefahrstoff.id == id).first()
    if not accessible:
        flash('Keine Berechtigung, diesen Gefahrstoff anzusehen.', 'error')
        return redirect(url_for('index'))
    return render_template('view.html', stoff=stoff, today=datetime.utcnow().date())


@app.route('/gefahrstoff/<int:id>/betriebsanweisung')
@login_required
def betriebsanweisung_print(id):
    stoff = Gefahrstoff.query.get_or_404(id)
    accessible = get_gefahrstoff_query().filter(Gefahrstoff.id == id).first()
    if not accessible:
        flash('Keine Berechtigung, diesen Gefahrstoff anzusehen.', 'error')
        return redirect(url_for('index'))
    
    # Arbeitsbereich formatieren
    arbeitsbereich = "Unbekannter Bereich"
    if stoff.unterbereich:
        arbeitsbereich = f"{stoff.unterbereich.bereich.name} / {stoff.unterbereich.name}"
    elif stoff.lagerort:
        arbeitsbereich = stoff.lagerort

    # Sätze in Listen aufteilen inkl. Text aus JSON
    import json
    import os
    try:
        json_path = os.path.join(app.root_path, 'static', 'hp_data.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            hp_data = json.load(f)
        h_dict = {item['code']: item['text'] for item in hp_data.get('h_saetze', [])}
        p_dict = {item['code']: item['text'] for item in hp_data.get('p_saetze', [])}
    except Exception:
        h_dict = {}
        p_dict = {}

    h_saetze_list = []
    for h in (stoff.h_saetze or "").split(","):
        h_code = h.strip()
        if h_code:
            text = h_dict.get(h_code, "")
            h_saetze_list.append(f"{h_code}: {text}" if text else h_code)
            
    p_saetze_list = []
    for p in (stoff.p_saetze or "").split(","):
        p_code = p.strip()
        if p_code:
            text = p_dict.get(p_code, "")
            p_saetze_list.append(f"{p_code}: {text}" if text else p_code)

    return render_template('ba_print.html', 
                           stoff=stoff, 
                           arbeitsbereich=arbeitsbereich,
                           h_saetze_list=h_saetze_list,
                           p_saetze_list=p_saetze_list,
                           today=datetime.utcnow().date())


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    bereiche = get_accessible_bereiche()

    if request.method == 'POST':
        name         = request.form.get('name')
        cas_nummer   = request.form.get('cas_nummer')
        eg_nummer    = request.form.get('eg_nummer')
        signalwort   = request.form.get('signalwort')
        unterbereich_id = request.form.get('unterbereich_id')

        # Sicherheitscheck: Unterbereich muss zum zugänglichen Bereich gehören
        if unterbereich_id:
            unter = Unterbereich.query.get(unterbereich_id)
            if unter and unter.bereich.id not in [b.id for b in bereiche]:
                flash('Kein Zugriff auf diesen Standort.', 'error')
                return redirect(url_for('add'))

        piktogramme_list = request.form.getlist('piktogramme')
        piktogramme = ",".join(piktogramme_list) if piktogramme_list else None
        gefahrenkategorien = request.form.get('gefahrenkategorien')
        h_saetze    = request.form.get('h_saetze')
        p_saetze    = request.form.get('p_saetze')
        lagerort    = request.form.get('lagerort')
        lagerklasse = request.form.get('lagerklasse')
        menge_str   = request.form.get('menge')
        mengeneinheit = request.form.get('mengeneinheit')
        
        # Neue Felder Section 5
        sdb_datum_str = request.form.get('sdb_datum')
        sdb_datum = None
        if sdb_datum_str:
            try:
                sdb_datum = datetime.strptime(sdb_datum_str, '%Y-%m-%d').date()
            except ValueError:
                pass
                
        substitutionspruefung = request.form.get('substitutionspruefung')
        ersatzstoff = request.form.get('ersatzstoff') if substitutionspruefung == 'ja' else None
        begruendung = request.form.get('begruendung') if substitutionspruefung == 'nein' else None

        menge = None
        if menge_str:
            try:
                menge = float(menge_str.replace(',', '.'))
            except ValueError:
                flash('Ungültiges Zahlenformat bei der Menge.', 'error')
                return redirect(url_for('add'))

        sdb_filename = ba_filename = gb_filename = None
        if 'sicherheitsdatenblatt' in request.files:
            file = request.files['sicherheitsdatenblatt']
            if file and file.filename != '' and allowed_file(file.filename):
                sdb_filename = save_file_with_stoff_name(file, name, "SDB")
            elif file and file.filename != '':
                flash('Ungültiger Dateityp für das Sicherheitsdatenblatt.', 'error')
                return redirect(url_for('add'))

        if 'betriebsanweisung' in request.files:
            file = request.files['betriebsanweisung']
            if file and file.filename != '' and allowed_file(file.filename):
                ba_filename = save_file_with_stoff_name(file, name, "BA")
            elif file and file.filename != '':
                flash('Ungültiger Dateityp für die Betriebsanweisung.', 'error')
                return redirect(url_for('add'))

        if 'gefaehrdungsbeurteilung' in request.files:
            file = request.files['gefaehrdungsbeurteilung']
            if file and file.filename != '' and allowed_file(file.filename):
                gb_filename = save_file_with_stoff_name(file, name, "GB")
            elif file and file.filename != '':
                flash('Ungültiger Dateityp für die Gefährdungsbeurteilung.', 'error')
                return redirect(url_for('add'))

        neuer_stoff = Gefahrstoff(
            name=name, cas_nummer=cas_nummer, eg_nummer=eg_nummer,
            signalwort=signalwort if signalwort else None,
            piktogramme=piktogramme, gefahrenkategorien=gefahrenkategorien, h_saetze=h_saetze, p_saetze=p_saetze,
            lagerort=lagerort, lagerklasse=lagerklasse, menge=menge, mengeneinheit=mengeneinheit,
            sdb_datum=sdb_datum,
            substitutionspruefung=substitutionspruefung,
            ersatzstoff=ersatzstoff,
            begruendung=begruendung,
            sicherheitsdatenblatt=sdb_filename, betriebsanweisung=ba_filename,
            gefaehrdungsbeurteilung=gb_filename,
            unterbereich_id=unterbereich_id if unterbereich_id else None,
            user_id=current_user.id,
            is_approved=not is_cmr_stoff(h_saetze)
        )
        try:
            db.session.add(neuer_stoff)
            db.session.commit()
            
            log_audit_event('CREATE', 'Gefahrstoff', neuer_stoff.id, {'name': neuer_stoff.name})
            
            if not neuer_stoff.is_approved:
                flash(f'Gefahrstoff "{name}" erfolgreich hinzugefügt! Hinweis: Da es sich um einen CMR-Stoff handelt, muss er vor der Sichtbarkeit von einem Moderator/Admin freigegeben werden.', 'warning')
            else:
                flash(f'Gefahrstoff "{name}" erfolgreich hinzugefügt!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Speichern: {str(e)}', 'error')

    return render_template('add.html', bereiche=bereiche)


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_stoff(id):
    stoff = Gefahrstoff.query.get_or_404(id)
    if not can_edit_gefahrstoff(stoff):
        flash('Keine Berechtigung, diesen Gefahrstoff zu bearbeiten.', 'error')
        return redirect(url_for('index'))

    bereiche = get_accessible_bereiche()

    if request.method == 'POST':
        stoff.name       = request.form.get('name')
        stoff.cas_nummer = request.form.get('cas_nummer')
        stoff.eg_nummer  = request.form.get('eg_nummer')
        signalwort       = request.form.get('signalwort')
        stoff.signalwort = signalwort if signalwort else None

        unterbereich_id = request.form.get('unterbereich_id')
        if unterbereich_id:
            unter = Unterbereich.query.get(unterbereich_id)
            if unter and unter.bereich.id not in [b.id for b in bereiche]:
                flash('Kein Zugriff auf diesen Standort.', 'error')
                return redirect(url_for('edit_stoff', id=id))
        stoff.unterbereich_id = unterbereich_id if unterbereich_id else None

        piktogramme_list = request.form.getlist('piktogramme')
        stoff.piktogramme = ",".join(piktogramme_list) if piktogramme_list else None
        stoff.gefahrenkategorien = request.form.get('gefahrenkategorien')
        stoff.h_saetze    = request.form.get('h_saetze')
        stoff.p_saetze    = request.form.get('p_saetze')
        stoff.lagerort    = request.form.get('lagerort')
        stoff.lagerklasse = request.form.get('lagerklasse')
        stoff.mengeneinheit = request.form.get('mengeneinheit')
        
        # Neue Felder Section 5
        sdb_datum_str = request.form.get('sdb_datum')
        if sdb_datum_str:
            try:
                stoff.sdb_datum = datetime.strptime(sdb_datum_str, '%Y-%m-%d').date()
            except ValueError:
                stoff.sdb_datum = None
        else:
            stoff.sdb_datum = None
            
        stoff.substitutionspruefung = request.form.get('substitutionspruefung')
        stoff.ersatzstoff = request.form.get('ersatzstoff') if stoff.substitutionspruefung == 'ja' else None
        stoff.begruendung = request.form.get('begruendung') if stoff.substitutionspruefung == 'nein' else None

        menge_str = request.form.get('menge')
        if menge_str:
            try:
                stoff.menge = float(menge_str.replace(',', '.'))
            except ValueError:
                flash('Ungültiges Zahlenformat bei der Menge.', 'error')
                return redirect(url_for('edit_stoff', id=id))
        else:
            stoff.menge = None

        # Dokumente löschen
        if request.form.get('delete_sdb') == '1' and stoff.sicherheitsdatenblatt:
            try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], stoff.sicherheitsdatenblatt))
            except: pass
            stoff.sicherheitsdatenblatt = None

        if request.form.get('delete_ba') == '1' and stoff.betriebsanweisung:
            try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], stoff.betriebsanweisung))
            except: pass
            stoff.betriebsanweisung = None

        if request.form.get('delete_gb') == '1' and stoff.gefaehrdungsbeurteilung:
            try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], stoff.gefaehrdungsbeurteilung))
            except: pass
            stoff.gefaehrdungsbeurteilung = None

        # Neue Dokumente hochladen
        if 'sicherheitsdatenblatt' in request.files:
            file = request.files['sicherheitsdatenblatt']
            if file and file.filename != '' and allowed_file(file.filename):
                sdb_filename = save_file_with_stoff_name(file, stoff.name, "SDB")
                stoff.sicherheitsdatenblatt = sdb_filename
            elif file and file.filename != '':
                flash('Ungültiger Dateityp.', 'error')
                return redirect(url_for('edit_stoff', id=id))

        if 'betriebsanweisung' in request.files:
            file = request.files['betriebsanweisung']
            if file and file.filename != '' and allowed_file(file.filename):
                ba_filename = save_file_with_stoff_name(file, stoff.name, "BA")
                stoff.betriebsanweisung = ba_filename
            elif file and file.filename != '':
                flash('Ungültiger Dateityp.', 'error')
                return redirect(url_for('edit_stoff', id=id))
                
        if 'gefaehrdungsbeurteilung' in request.files:
            file = request.files['gefaehrdungsbeurteilung']
            if file and file.filename != '' and allowed_file(file.filename):
                gb_filename = save_file_with_stoff_name(file, stoff.name, "GB")
                stoff.gefaehrdungsbeurteilung = gb_filename
            elif file and file.filename != '':
                flash('Ungültiger Dateityp.', 'error')
                return redirect(url_for('edit_stoff', id=id))

        if is_cmr_stoff(stoff.h_saetze):
            stoff.is_approved = False
        else:
            stoff.is_approved = True

        try:
            db.session.commit()
            log_audit_event('UPDATE', 'Gefahrstoff', stoff.id, {'name': stoff.name})
            
            if not stoff.is_approved:
                flash(f'Gefahrstoff "{stoff.name}" erfolgreich aktualisiert! Hinweis: Er muss nun als CMR-Stoff neu freigegeben werden.', 'warning')
            else:
                flash(f'Gefahrstoff "{stoff.name}" erfolgreich aktualisiert!', 'success')
            return redirect(url_for('view_stoff', id=stoff.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Speichern: {str(e)}', 'error')

    return render_template('edit.html', stoff=stoff, bereiche=bereiche)


@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_stoff(id):
    stoff = Gefahrstoff.query.get_or_404(id)
    if not can_edit_gefahrstoff(stoff):
        flash('Keine Berechtigung, diesen Gefahrstoff zu löschen.', 'error')
        return redirect(url_for('index'))
    try:
        # Soft delete
        stoff.is_deleted = True
        stoff.deleted_at = datetime.utcnow()
        db.session.commit()
        
        log_audit_event('DELETE', 'Gefahrstoff', stoff.id, {'name': stoff.name})
        
        flash(f'Gefahrstoff "{stoff.name}" wurde erfolgreich gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen: {str(e)}', 'error')
    return redirect(url_for('index'))


@app.route('/move/<int:id>', methods=['GET', 'POST'])
@login_required
def move_stoff(id):
    stoff = Gefahrstoff.query.get_or_404(id)
    if not can_edit_gefahrstoff(stoff):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))
    bereiche = get_accessible_bereiche()
    if request.method == 'POST':
        unterbereich_id = request.form.get('unterbereich_id')
        stoff.unterbereich_id = unterbereich_id if unterbereich_id else None
        try:
            db.session.commit()
            flash(f'Gefahrstoff "{stoff.name}" erfolgreich verschoben!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Verschieben: {str(e)}', 'error')
    return render_template('move_copy.html', stoff=stoff, bereiche=bereiche, action='Verschieben')


@app.route('/copy/<int:id>', methods=['GET', 'POST'])
@login_required
def copy_stoff(id):
    stoff = Gefahrstoff.query.get_or_404(id)
    if not can_edit_gefahrstoff(stoff):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))
    bereiche = get_accessible_bereiche()
    if request.method == 'POST':
        unterbereich_id = request.form.get('unterbereich_id')
        neuer_stoff = Gefahrstoff(
            name=stoff.name, cas_nummer=stoff.cas_nummer, eg_nummer=stoff.eg_nummer,
            signalwort=stoff.signalwort, piktogramme=stoff.piktogramme,
            h_saetze=stoff.h_saetze, p_saetze=stoff.p_saetze,
            lagerort=stoff.lagerort, menge=stoff.menge, mengeneinheit=stoff.mengeneinheit,
            sdb_datum=stoff.sdb_datum,
            substitutionspruefung=stoff.substitutionspruefung,
            ersatzstoff=stoff.ersatzstoff,
            begruendung=stoff.begruendung,
            sicherheitsdatenblatt=stoff.sicherheitsdatenblatt,
            betriebsanweisung=stoff.betriebsanweisung,
            gefaehrdungsbeurteilung=stoff.gefaehrdungsbeurteilung,
            unterbereich_id=unterbereich_id if unterbereich_id else None,
            user_id=current_user.id
        )
        try:
            db.session.add(neuer_stoff)
            db.session.commit()
            flash(f'Gefahrstoff "{stoff.name}" erfolgreich kopiert!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Kopieren: {str(e)}', 'error')
    return render_template('move_copy.html', stoff=stoff, bereiche=bereiche, action='Kopieren')

# ─── Export ──────────────────────────────────────────────────────────────────

@app.route('/export/excel')
@login_required
def export_excel():
    import json
    query, _, _, error_message = get_filtered_gefahrstoff_query_for_request()
    if error_message:
        flash(error_message, 'error')
        return redirect(url_for('index'))
    stoffe = query.order_by(Gefahrstoff.name).all()
    data = []
    for s in stoffe:
        standort = f"{s.unterbereich.bereich.name} > {s.unterbereich.name}" if s.unterbereich else (s.lagerort or "-")
        
        piktos_str = ""
        if s.piktogramme:
            try:
                piktos_str = ", ".join(json.loads(s.piktogramme))
            except:
                piktos_str = str(s.piktogramme)
                
        data.append({
            'Name': s.name, 
            'CAS-Nummer': s.cas_nummer, 
            'EG-Nummer': s.eg_nummer,
            'Einstufung & Gefahren': s.gefahrenkategorien,
            'Piktogramme': piktos_str,
            'Signalwort': s.signalwort,
            'H-Sätze': s.h_saetze, 
            'P-Sätze': s.p_saetze,
            'Menge': f"{s.menge} {s.mengeneinheit}" if s.menge else "-",
            'Lagerklasse': s.lagerklasse,
            'Arbeitsbereich': standort,
            'Datum SDB': s.sdb_datum.strftime('%d.%m.%Y') if s.sdb_datum else "-",
            'Substitutionsprüfung': s.substitutionspruefung,
            'Ersatzstoff': s.ersatzstoff,
            'Begründung': s.begruendung
        })
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Gefahrstoffe')
        
        # Styling anpassen
        worksheet = writer.sheets['Gefahrstoffe']
        from openpyxl.styles import Font
        
        # Überschriften fett
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            
        # Spaltenbreiten anpassen (mit Maximalbreite)
        for col in worksheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                if cell.value:
                    length = len(str(cell.value))
                    if length > max_length:
                        max_length = length
                        
            # Spaltenbreite berechnen (minimale Breite, maximale Breite = 45 Zeichen für lange H-Sätze)
            adjusted_width = min(max_length + 2, 45)
            # Mindestbreite für kurze Spalten
            worksheet.column_dimensions[column].width = max(adjusted_width, 10)
            
    output.seek(0)
    return send_file(output, download_name='gefahrstoffe_export.xlsx', as_attachment=True)


@app.route('/export/pdf')
@login_required
def export_pdf():
    from svglib.svglib import svg2rlg
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import json
    import os

    query, _, _, error_message = get_filtered_gefahrstoff_query_for_request()
    if error_message:
        flash(error_message, 'error')
        return redirect(url_for('index'))
    stoffe = query.order_by(Gefahrstoff.name).all()
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=1*cm, rightMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10)

    elements.append(Paragraph("Gefahrstoff-Übersicht", styles['Title']))
    elements.append(Spacer(1, 10))
    
    # 6 Columns: 1:Name&CAS, 2:Einstufung, 3:Menge&LGK, 4:Standort, 5:Datum SDB, 6:Substitution
    data = [[
        Paragraph('<b>Name & Identifikation</b>', styles['Normal']), 
        Paragraph('<b>Einstufung & Gefahren</b>', styles['Normal']), 
        Paragraph('<b>Menge & LGK</b>', styles['Normal']), 
        Paragraph('<b>Arbeitsbereich</b>', styles['Normal']), 
        Paragraph('<b>Datum SDB</b>', styles['Normal']), 
        Paragraph('<b>Substitutionsprüfung</b>', styles['Normal'])
    ]]
    
    for s in stoffe:
        # Col 1: Name & CAS
        name_cas = f"<b>{s.name}</b><br/>"
        if s.cas_nummer:
            name_cas += f"CAS: {s.cas_nummer}<br/>"
        if s.eg_nummer:
            name_cas += f"EG: {s.eg_nummer}"
        p_name_cas = Paragraph(name_cas, cell_style)
        
        # Col 2: Einstufung (Piktogramme & H-Sätze)
        einstufung_elements = []
        if s.piktogramme:
            try:
                piktos = json.loads(s.piktogramme)
                img_elements = []
                for p in piktos:
                    svg_path = os.path.join(app.static_folder, 'pictograms', f"{p}.svg")
                    if os.path.exists(svg_path):
                        drawing = svg2rlg(svg_path)
                        if drawing:
                            scaling_factor = 20.0 / max(drawing.width, drawing.height)
                            drawing.width = drawing.width * scaling_factor
                            drawing.height = drawing.height * scaling_factor
                            drawing.scale(scaling_factor, scaling_factor)
                            img_elements.append(drawing)
                if img_elements:
                    pikto_table = Table([img_elements], colWidths=[22]*len(img_elements))
                    pikto_table.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
                        ('LEFTPADDING', (0,0), (-1,-1), 0), 
                        ('RIGHTPADDING', (0,0), (-1,-1), 2),
                        ('TOPPADDING', (0,0), (-1,-1), 0),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 2)
                    ]))
                    einstufung_elements.append(pikto_table)
            except Exception as e:
                pass
        
        if s.gefahrenkategorien:
            einstufung_elements.append(Paragraph(s.gefahrenkategorien, cell_style))
        if s.signalwort:
            einstufung_elements.append(Paragraph(f"<i>{s.signalwort}</i>", cell_style))
        if s.h_saetze:
            einstufung_elements.append(Paragraph(s.h_saetze, cell_style))
            
        # Col 3: Menge & LGK
        menge_str = f"{s.menge} {s.mengeneinheit}" if s.menge else "-"
        if s.lagerklasse:
            menge_str += f"<br/>LGK: {s.lagerklasse}"
        p_menge = Paragraph(menge_str, cell_style)
        
        # Col 4: Arbeitsbereich
        standort = f"{s.unterbereich.bereich.name} > {s.unterbereich.name}" if s.unterbereich else (s.lagerort or "-")
        p_standort = Paragraph(standort, cell_style)
        
        # Col 5: Datum SDB
        sdb_datum = s.sdb_datum.strftime('%d.%m.%Y') if s.sdb_datum else "-"
        p_sdb = Paragraph(sdb_datum, cell_style)
        
        # Col 6: Substitution
        subst_str = f"<b>{s.substitutionspruefung or '-'}</b>"
        if s.ersatzstoff:
            subst_str += f"<br/>Ersatzstoff: {s.ersatzstoff}"
        if s.begruendung:
            subst_str += f"<br/>Begründung: {s.begruendung}"
        p_subst = Paragraph(subst_str, cell_style)
        
        data.append([p_name_cas, einstufung_elements, p_menge, p_standort, p_sdb, p_subst])
        
    table = Table(data, colWidths=[130, 200, 70, 150, 70, 165])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(table)
    doc.build(elements)
    output.seek(0)
    return send_file(output, download_name='gefahrstoffe_export.pdf', as_attachment=True)


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ─── Profil & Freigaben ────────────────────────────────────────────────────────

@app.context_processor
def inject_pending_approvals():
    if current_user.is_authenticated and current_user.role in ['admin', 'moderator']:
        if current_user.is_admin:
            count = Gefahrstoff.query.filter_by(is_approved=False, is_deleted=False).count()
        else:
            owned_ids   = [b.id for b in Bereich.query.filter_by(owner_id=current_user.id).all()]
            assigned_ids = [b.id for b in current_user.assigned_bereiche.all()]
            all_ids     = list(set(owned_ids + assigned_ids))
            sub_ids     = [u.id for u in Unterbereich.query.filter(Unterbereich.bereich_id.in_(all_ids)).all()]
            count = Gefahrstoff.query.filter(
                Gefahrstoff.is_approved == False,
                Gefahrstoff.is_deleted == False,
                Gefahrstoff.unterbereich_id.in_(sub_ids)
            ).count()
        return dict(pending_approvals_count=count)
    return dict(pending_approvals_count=0)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        old_password    = request.form.get('old_password')
        new_password    = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not current_user.check_password(old_password):
            flash('Altes Passwort ist nicht korrekt.', 'error')
        elif new_password != confirm_password:
            flash('Die neuen Passwörter stimmen nicht überein.', 'error')
        elif len(new_password) < 4:
            flash('Das neue Passwort muss mindestens 4 Zeichen lang sein.', 'error')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Dein Passwort wurde erfolgreich geändert.', 'success')
            return redirect(url_for('profile'))
            
    pending_gefahrstoffe = []
    if current_user.role in ['admin', 'moderator']:
        if current_user.is_admin:
            pending_gefahrstoffe = Gefahrstoff.query.filter_by(is_approved=False, is_deleted=False).all()
        else:
            owned_ids   = [b.id for b in Bereich.query.filter_by(owner_id=current_user.id).all()]
            assigned_ids = [b.id for b in current_user.assigned_bereiche.all()]
            all_ids     = list(set(owned_ids + assigned_ids))
            sub_ids     = [u.id for u in Unterbereich.query.filter(Unterbereich.bereich_id.in_(all_ids)).all()]
            pending_gefahrstoffe = Gefahrstoff.query.filter(
                Gefahrstoff.is_approved == False,
                Gefahrstoff.is_deleted == False,
                Gefahrstoff.unterbereich_id.in_(sub_ids)
            ).all()

    return render_template('profile.html', pending_gefahrstoffe=pending_gefahrstoffe)

@app.route('/approve/<int:id>', methods=['POST'])
@login_required
def approve_stoff(id):
    if current_user.role not in ['admin', 'moderator']:
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))
    
    stoff = Gefahrstoff.query.get_or_404(id)
    if current_user.role == 'moderator':
        if not stoff.unterbereich:
            flash('Keine Berechtigung für diesen Stoff.', 'error')
            return redirect(url_for('profile'))
        owned_ids   = [b.id for b in Bereich.query.filter_by(owner_id=current_user.id).all()]
        assigned_ids = [b.id for b in current_user.assigned_bereiche.all()]
        if stoff.unterbereich.bereich_id not in owned_ids + assigned_ids:
            flash('Keine Berechtigung für diesen Stoff.', 'error')
            return redirect(url_for('profile'))

    stoff.is_approved = True
    db.session.commit()
    log_audit_event('APPROVE', 'Gefahrstoff', stoff.id, {'name': stoff.name})
    flash(f'Gefahrstoff "{stoff.name}" wurde freigegeben.', 'success')
    return redirect(url_for('profile'))

@app.route('/reject/<int:id>', methods=['POST'])
@login_required
def reject_stoff(id):
    if current_user.role not in ['admin', 'moderator']:
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))
    
    stoff = Gefahrstoff.query.get_or_404(id)
    if current_user.role == 'moderator':
        if not stoff.unterbereich:
            flash('Keine Berechtigung für diesen Stoff.', 'error')
            return redirect(url_for('profile'))
        owned_ids   = [b.id for b in Bereich.query.filter_by(owner_id=current_user.id).all()]
        assigned_ids = [b.id for b in current_user.assigned_bereiche.all()]
        if stoff.unterbereich.bereich_id not in owned_ids + assigned_ids:
            flash('Keine Berechtigung für diesen Stoff.', 'error')
            return redirect(url_for('profile'))

    db.session.delete(stoff)
    db.session.commit()
    log_audit_event('REJECT', 'Gefahrstoff', id, {'name': stoff.name})
    flash(f'Gefahrstoff "{stoff.name}" wurde abgelehnt und entfernt.', 'success')
    return redirect(url_for('profile'))

# ─── Benutzerverwaltung ──────────────────────────────────────────────────────

@app.route('/users')
@login_required
def users():
    if current_user.role == 'benutzer':
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))

    if current_user.is_admin:
        all_users   = User.query.order_by(User.username).all()
        all_bereiche = Bereich.query.order_by(Bereich.name).all()
    else:
        # Moderator sieht nur seine angelegten Benutzer
        all_users   = User.query.filter_by(created_by=current_user.id).order_by(User.username).all()
        all_bereiche = Bereich.query.filter_by(owner_id=current_user.id).order_by(Bereich.name).all()

    return render_template('users.html', users=all_users, bereiche=all_bereiche)


@app.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role == 'benutzer':
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))

    allowed_roles   = ['admin', 'moderator', 'benutzer'] if current_user.is_admin else ['benutzer']
    accessible      = get_accessible_bereiche()

    if request.method == 'POST':
        username   = request.form.get('username', '').strip()
        password   = request.form.get('password', '')
        role       = request.form.get('role', 'benutzer')
        bereich_ids = request.form.getlist('bereich_ids')

        if not username or not password:
            flash('Benutzername und Passwort sind Pflichtfelder.', 'error')
            return redirect(url_for('create_user'))

        if role not in allowed_roles:
            flash('Ungültige Rolle.', 'error')
            return redirect(url_for('create_user'))

        if User.query.filter_by(username=username).first():
            flash('Dieser Benutzername ist bereits vergeben.', 'error')
            return redirect(url_for('create_user'))

        new_user = User(username=username, role=role, created_by=current_user.id)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()  # ID generieren

        # Bereiche zuweisen
        if role in ['benutzer', 'moderator']:
            if current_user.role == 'moderator' and role == 'benutzer':
                # Automatisch alle eigenen Bereiche zuweisen
                for b in accessible:
                    new_user.assigned_bereiche.append(b)
            elif current_user.is_admin:
                # Admin: manuelle Auswahl
                for bid in bereich_ids:
                    b = Bereich.query.get(int(bid))
                    if b:
                        new_user.assigned_bereiche.append(b)

        try:
            db.session.commit()
            flash(f'Benutzer "{username}" erfolgreich angelegt!', 'success')
            return redirect(url_for('users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler: {str(e)}', 'error')

    return render_template('create_user.html', allowed_roles=allowed_roles, bereiche=accessible)


@app.route('/users/set_role/<int:id>', methods=['POST'])
@login_required
def set_role(id):
    if current_user.role == 'benutzer':
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))

    user = User.query.get_or_404(id)
    if user.username == 'admin':
        flash('Der Haupt-Admin-Account kann nicht geändert werden.', 'error')
        return redirect(url_for('users'))

    if current_user.role == 'moderator' and user.created_by != current_user.id:
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('users'))

    allowed_roles = ['admin', 'moderator', 'benutzer'] if current_user.is_admin else ['benutzer']
    new_role = request.form.get('role')
    if new_role not in allowed_roles:
        flash('Ungültige Rolle.', 'error')
        return redirect(url_for('users'))

    user.role = new_role
    db.session.commit()
    flash(f'Rolle von "{user.username}" auf "{new_role}" gesetzt.', 'success')
    return redirect(url_for('users'))


@app.route('/users/assign_bereiche/<int:id>', methods=['POST'])
@login_required
def assign_bereiche(id):
    if current_user.role == 'benutzer':
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))

    user = User.query.get_or_404(id)
    if current_user.role == 'moderator' and user.created_by != current_user.id:
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('users'))

    bereich_ids  = [int(x) for x in request.form.getlist('bereich_ids')]
    accessible   = get_accessible_bereiche()
    accessible_ids = {b.id for b in accessible}

    # Bestehende Zuweisungen in zugänglichen Bereichen entfernen, dann neu setzen
    current_assignments = user.assigned_bereiche.all()
    for b in current_assignments:
        if b.id in accessible_ids:
            user.assigned_bereiche.remove(b)

    for bid in bereich_ids:
        if bid in accessible_ids:
            b = Bereich.query.get(bid)
            if b:
                user.assigned_bereiche.append(b)

    db.session.commit()
    flash(f'Bereichszuweisung für "{user.username}" aktualisiert.', 'success')
    return redirect(url_for('users'))


@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role == 'benutzer':
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))

    user = User.query.get_or_404(id)
    
    if user.username == 'admin' and current_user.username != 'admin':
        flash('Der Haupt-Admin kann nicht bearbeitet werden.', 'error')
        return redirect(url_for('users'))
        
    if current_user.role == 'moderator' and user.created_by != current_user.id:
        flash('Keine Berechtigung, diesen Benutzer zu bearbeiten.', 'error')
        return redirect(url_for('users'))

    allowed_roles = ['admin', 'moderator', 'benutzer'] if current_user.is_admin else ['benutzer']
    accessible = get_accessible_bereiche()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', user.role)
        bereich_ids = request.form.getlist('bereich_ids')

        if not username:
            flash('Benutzername ist ein Pflichtfeld.', 'error')
            return redirect(url_for('edit_user', id=id))
            
        if role not in allowed_roles:
            role = user.role
            
        # Check if username exists and is not the current user
        existing = User.query.filter_by(username=username).first()
        if existing and existing.id != user.id:
            flash('Dieser Benutzername ist bereits vergeben.', 'error')
            return redirect(url_for('edit_user', id=id))

        user.username = username
        if user.username != 'admin':
            user.role = role
            
        if password:
            user.set_password(password)

        if current_user.is_admin and role in ['benutzer', 'moderator']:
            accessible_ids = {b.id for b in accessible}
            current_assignments = user.assigned_bereiche.all()
            for b in current_assignments:
                if b.id in accessible_ids:
                    user.assigned_bereiche.remove(b)

            for bid in bereich_ids:
                if int(bid) in accessible_ids:
                    b = Bereich.query.get(int(bid))
                    if b:
                        user.assigned_bereiche.append(b)

        try:
            db.session.commit()
            flash(f'Benutzer "{username}" erfolgreich aktualisiert!', 'success')
            return redirect(url_for('users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler: {str(e)}', 'error')

    return render_template('edit_user.html', user=user, allowed_roles=allowed_roles, bereiche=accessible)

@app.route('/users/delete/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.role == 'benutzer':
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))

    user = User.query.get_or_404(id)
    if user.username == 'admin':
        flash('Der Haupt-Admin Account kann nicht gelöscht werden.', 'error')
        return redirect(url_for('users'))
    if user.id == current_user.id:
        flash('Du kannst nicht deinen eigenen Account löschen.', 'error')
        return redirect(url_for('users'))
    if user.role == 'moderator' and not current_user.is_admin:
        flash('Moderatoren können nur durch den Administrator gelöscht werden.', 'error')
        return redirect(url_for('users'))
    if current_user.role == 'moderator' and user.created_by != current_user.id:
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('users'))

    db.session.delete(user)
    db.session.commit()
    flash(f'Benutzer "{user.username}" wurde gelöscht.', 'info')
    return redirect(url_for('users'))

# ─── Datenbank-Init & Migration ──────────────────────────────────────────────

def migrate_database():
    """Fügt neue Spalten zu bestehenden Tabellen hinzu, ohne Daten zu verlieren."""
    with db.engine.connect() as conn:
        # User-Tabelle
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(user)"))]
        if 'role' not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'benutzer'"))
            conn.execute(text("UPDATE user SET role = 'admin' WHERE is_admin = 1"))
            conn.commit()
        if 'created_by' not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN created_by INTEGER REFERENCES user(id)"))
            conn.commit()

        # Bereich-Tabelle
        bereich_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(bereich)"))]
        if 'owner_id' not in bereich_cols:
            conn.execute(text("ALTER TABLE bereich ADD COLUMN owner_id INTEGER REFERENCES user(id)"))
            # Bestehende Bereiche dem Admin zuweisen
            conn.execute(text(
                "UPDATE bereich SET owner_id = (SELECT id FROM user WHERE role = 'admin' LIMIT 1)"
            ))
            conn.commit()
            
        # Gefahrstoff-Tabelle
        stoff_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(gefahrstoff)"))]
        if 'gefaehrdungsbeurteilung' not in stoff_cols:
            conn.execute(text("ALTER TABLE gefahrstoff ADD COLUMN gefaehrdungsbeurteilung VARCHAR(200)"))
            conn.commit()
        if 'sdb_datum' not in stoff_cols:
            conn.execute(text("ALTER TABLE gefahrstoff ADD COLUMN sdb_datum DATE"))
            conn.execute(text("ALTER TABLE gefahrstoff ADD COLUMN substitutionspruefung VARCHAR(10)"))
            conn.execute(text("ALTER TABLE gefahrstoff ADD COLUMN ersatzstoff VARCHAR(200)"))
            conn.execute(text("ALTER TABLE gefahrstoff ADD COLUMN begruendung VARCHAR(500)"))
            conn.commit()
            
        # Unterbereich-Tabelle
        ub_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(unterbereich)"))]
        if 'parent_id' not in ub_cols:
            conn.execute(text("ALTER TABLE unterbereich ADD COLUMN parent_id INTEGER REFERENCES unterbereich(id)"))
            conn.commit()


with app.app_context():
    db.create_all()
    migrate_database()

@app.route('/api/parse_sdb', methods=['POST'])
@login_required
def parse_sdb():
    if 'file' not in request.files:
        return {'error': 'Keine Datei hochgeladen'}, 400
        
    file = request.files['file']
    if file.filename == '':
        return {'error': 'Keine Datei ausgewählt'}, 400
        
    if not file.filename.lower().endswith('.pdf'):
        return {'error': 'Bitte eine PDF-Datei hochladen'}, 400

    text_content = ""
    first_page_text = ""
    try:
        with pdfplumber.open(file) as pdf:
            if len(pdf.pages) > 0:
                first_page_text = pdf.pages[0].extract_text() or ""
                
            for page in pdf.pages[:15]:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
                    
        # Extract CAS
        cas_match = re.search(r'\b(\d{2,7}-\d{2}-\d)\b', text_content)
        cas = cas_match.group(1) if cas_match else ""
        
        # Extract EG-Nummer
        eg_explicit = re.search(r'(?:EG-Nr\.|EG-Nummer|EG Nr\.|EC-No\.|EC No\.)[\s:]*(\d{3}-\d{3}-\d)', text_content, re.IGNORECASE)
        if not eg_explicit:
            eg_match = re.search(r'\b([2459]\d{2}-\d{3}-\d)\b', text_content)
            eg = eg_match.group(1) if eg_match else ""
        else:
            eg = eg_explicit.group(1)
            
        # Extract Signalwort
        signal_match = re.search(r'\b(Gefahr|Achtung)\b', text_content, re.IGNORECASE)
        signalwort = signal_match.group(1).capitalize() if signal_match else ""
        
        # Extract Gefahrenkategorien aus Abschnitt 2.1
        gefahrenkategorien = []
        sec21_match = re.search(r'2\.1\b.*?(?:Einstufung).*?(?=2\.2|Kennzeichnungselemente)', text_content, re.IGNORECASE | re.DOTALL)
        if sec21_match:
            sec21_text = sec21_match.group(0)
            raw_cats = re.findall(r'\b(?:Met|Skin|Eye|Acute|Flam|Ox|Aquatic|Asp|STOT|Muta|Carc|Repr|Resp)[\.\s]*(?:Corr|Dam|Irrit|Tox|Liq|Sol|Gas|Sens|SE|RE|Chronic|Acute)?[\.\s]*[1-4]?[A-C]?\b', sec21_text, re.IGNORECASE)
            seen = set()
            for c in raw_cats:
                c = re.sub(r'\s+', ' ', c).replace(' .', '.').replace('.', '. ').replace('  ', ' ').strip()
                words = []
                for w in c.split():
                    if w.upper() in ['1A', '1B', '1C', '2A', '2B', '3', '4', 'SE', 'RE', 'STOT']:
                        words.append(w.upper())
                    else:
                        words.append(w.capitalize())
                c = " ".join(words)
                if c and c.upper() not in [s.upper() for s in seen]:
                    seen.add(c)
                    gefahrenkategorien.append(c)

        # Abschnitt 2.2 isolieren für präzise H- und P-Sätze (verhindert Auslesen von H-Sätzen aus Abschnitt 2.1 Einstufungstabelle)
        sec22_match = re.search(r'(?:2\.2\s*)?Kennzeichnungselemente(.*?)(?:2\.3\s*Sonstige Gefahren|3\.\s*Zusammensetzung|ABSCHNITT\s*3)', text_content, re.IGNORECASE | re.DOTALL)
        if sec22_match:
            search_text = sec22_match.group(1)
        else:
            sec2_match = re.search(r'ABSCHNITT\s*2\b.*?(?:Mögliche\s*Gefahren)?(.*?)ABSCHNITT\s*3\b', text_content, re.IGNORECASE | re.DOTALL)
            search_text = sec2_match.group(1) if sec2_match else text_content
        
        # Extract H-Sätze (jetzt auch mit mehreren Buchstaben wie H360FD und optionalen Leerzeichen)
        h_saetze_raw = re.findall(r'\b(H\s?[234]\d{2}\s?[a-zA-Z]{0,3})\b', search_text, re.IGNORECASE)
        euh_saetze_raw = re.findall(r'\b(EUH\s?\d{3}\s?[a-zA-Z]{0,3})\b', search_text, re.IGNORECASE)
        h_saetze = sorted(list(set([re.sub(r'[\s\n]+', '', h).upper() for h in h_saetze_raw + euh_saetze_raw])))
        
        # Extract P-Sätze
        p_saetze_raw = re.findall(r'\b(P\s?\d{3}(?:\s?\+\s?P\s?\d{3})*)\b', search_text, re.IGNORECASE)
        p_saetze = sorted(list(set([re.sub(r'[\s\n]+', '', p).upper() for p in p_saetze_raw])))
        
        # Extract Datum (Priorität: "Überarbeitet am" auf der ersten Seite)
        date_str = ""
        date_match = re.search(r'(?:Überarbeitet am|Datum der Überarbeitung|Druckdatum)[\s:]*(\d{2}\.\d{2}\.\d{4})', first_page_text, re.IGNORECASE)
        if date_match:
            try:
                d, m, y = date_match.group(1).split('.')
                dt = datetime(int(y), int(m), int(d))
                date_str = dt.strftime('%Y-%m-%d')
            except Exception:
                pass
                
        # Fallback für Datum, falls "Überarbeitet am" nicht gefunden
        if not date_str:
            date_matches = re.findall(r'\b(\d{2})\.(\d{2})\.(\d{4})\b', first_page_text)
            if date_matches:
                valid_dates = []
                for d, m, y in date_matches:
                    try:
                        dt = datetime(int(y), int(m), int(d))
                        if dt <= datetime.now():
                            valid_dates.append(dt)
                    except ValueError:
                        pass
                if valid_dates:
                    date_str = max(valid_dates).strftime('%Y-%m-%d')
        
        # Extract Handelsname (stark verbessert)
        name = ""
        # 1. Versuche Abschnitt 1.1 "Produktidentifikator" zu isolieren
        section_1_match = re.search(r'1\.1[^\n]*Produktidentifikator(.*?)(?:1\.2|Relevante identifizierte)', first_page_text, re.IGNORECASE | re.DOTALL)
        if section_1_match:
            chunk = section_1_match.group(1).strip()
            lines = [l.strip() for l in chunk.split('\n') if l.strip()]
            for line in lines:
                lower_line = line.lower()
                
                # Exakte Label-Zeilen ignorieren (Name steht oft in der Zeile danach)
                if lower_line in ['bezeichnung des stoffs', 'bezeichnung des stoffes', 'handelsname', 'produktname', 'stoffname', 'bezeichnung des gemischs', 'produktidentifikator']:
                    continue
                    
                # Zeilen mit Doppelpunkt prüfen (z.B. "Handelsname: Aceton")
                if ':' in line:
                    key, val = line.split(':', 1)
                    if any(k in key.lower() for k in ['bezeichnung', 'handelsname', 'produkt', 'stoff', 'gemisch', 'identifikator']):
                        if val.strip():
                            name = val.strip()
                            break
                        else:
                            continue # Nach Doppelpunkt leer -> nächste Zeile nehmen
                            
                # Fallback: Präfixe ohne Doppelpunkt entfernen
                cleaned_name = re.sub(r'^(?:Bezeichnung des Stoff(?:e)?s|Bezeichnung des Gemischs|Handelsname|Produktname|Stoffname|Produktidentifikator)[\s:]*', '', line, flags=re.IGNORECASE).strip()
                if cleaned_name:
                    name = cleaned_name
                    break

        # 2. Fallback auf altes Regex, falls 1.1 nicht eindeutig gefunden wurde
        if not name:
            name_match = re.search(r'(?:Handelsname|Produktname|Bezeichnung des Stoff(?:e)?s|Bezeichnung des Gemischs|Stoffname)[\s:]*([^\n]+)', first_page_text, re.IGNORECASE)
            if name_match and len(name_match.group(1).strip()) > 2:
                name = name_match.group(1).strip()
                name = re.sub(r'^(?:Bezeichnung des Stoff(?:e)?s|Bezeichnung des Gemischs|Handelsname|Produktname|Stoffname)[\s:]*', '', name, flags=re.IGNORECASE).strip()

        # 3. Absoluter Fallback auf erste sinnvolle Zeile
        if not name:
            lines = [l.strip() for l in first_page_text.split('\n') if l.strip() and len(l.strip()) > 3]
            for line in lines:
                if any(x in line for x in ["Sicherheitsdatenblatt", "gemäß", "Verordnung", "Abschnitt", "Version", "Gefahr", "Achtung", "Überarbeitet", "Druckdatum", "Bezeichnung des Stoff"]):
                    continue
                name = line[:100]
                break

        if len(name) > 100: name = name[:100]
                
        # Piktogramme explizit suchen und aus H-Sätzen ableiten (nur in Abschnitt 2)
        piktogramme = set(re.findall(r'\b(GHS0[1-9])\b', search_text, re.IGNORECASE))
        piktogramme = {p.upper() for p in piktogramme}
        for h in h_saetze:
            if h in ['H200', 'H201', 'H202', 'H203', 'H204', 'H240', 'H241']: piktogramme.add('GHS01')
            elif h.startswith('H22') or h in ['H241', 'H242', 'H250', 'H251', 'H252', 'H260', 'H261']: piktogramme.add('GHS02')
            elif h in ['H270', 'H271', 'H272']: piktogramme.add('GHS03')
            elif h in ['H280', 'H281']: piktogramme.add('GHS04')
            elif h in ['H290', 'H314', 'H318']: piktogramme.add('GHS05')
            elif h in ['H300', 'H301', 'H310', 'H311', 'H330', 'H331']: piktogramme.add('GHS06')
            elif h in ['H302', 'H312', 'H332', 'H315', 'H317', 'H319', 'H335', 'H336']: piktogramme.add('GHS07')
            elif h in ['H304', 'H334', 'H340', 'H341', 'H350', 'H351', 'H360', 'H361', 'H362', 'H370', 'H371', 'H372', 'H373', 'H373**']: piktogramme.add('GHS08')
            elif h in ['H400', 'H410', 'H411']: piktogramme.add('GHS09')
            
        # Extract Lagerklasse (robuste Suche mit Validierung)
        valid_lgk = {'1', '2A', '2B', '3', '4.1A', '4.1B', '4.2', '4.3', '5.1A', '5.1B', '5.1C', '5.2', '6.1A', '6.1B', '6.1C', '6.1D', '6.2', '7', '8A', '8B', '10', '11', '12', '13'}
        lagerklasse = ""
        # Suche nach "Lagerklasse" oder "LGK", gefolgt von max 40 Zeichen (ohne Zeilenumbruch) und dann einer Nummer (mit optionalem Leerzeichen)
        lgk_matches = re.findall(r'(?:Lagerklasse|LGK)[^\n]{0,40}?\b(\d{1,2}(?:\.\d)?\s?[A-Za-z]?)\b', text_content, re.IGNORECASE)
        for match in lgk_matches:
            match_upper = match.replace(' ', '').upper()
            if match_upper in valid_lgk:
                lagerklasse = match_upper
                break
                
        return {
            'success': True,
            'name': name,
            'cas': cas,
            'eg': eg,
            'gefahrenkategorien': gefahrenkategorien,
            'signalwort': signalwort,
            'h_saetze': ", ".join(h_saetze),
            'p_saetze': ", ".join(p_saetze),
            'piktogramme': list(piktogramme),
            'sdb_datum': date_str,
            'lagerklasse': lagerklasse
        }
    except Exception as e:
        return {'error': str(e)}, 500
@app.route('/audit_logs')
@login_required
def audit_logs():
    if not current_user.is_admin:
        flash('Keine Berechtigung für diese Seite.', 'error')
        return redirect(url_for('index'))
    
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template('audit_logs.html', logs=logs)

@app.route('/admin/system')
@login_required
def admin_system():
    if not current_user.is_admin:
        flash('Keine Berechtigung für diese Seite.', 'error')
        return redirect(url_for('index'))
    
    try:
        remote_url = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], stderr=subprocess.STDOUT).decode('utf-8').strip()
    except Exception:
        remote_url = "https://github.com/Donmeusi/gefahrstoffverzeichnis"
        
    updates_available = False
    local_commit = "Unbekannt"
    remote_commit = "Unbekannt"
    try:
        subprocess.check_call(['git', 'fetch'], stderr=subprocess.STDOUT)
        local_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.STDOUT).decode('utf-8').strip()[:7]
        remote_commit = subprocess.check_output(['git', 'rev-parse', 'origin/main'], stderr=subprocess.STDOUT).decode('utf-8').strip()[:7]
        if local_commit != remote_commit:
            updates_available = True
    except Exception as e:
        pass

    return render_template('admin_system.html', remote_url=remote_url, local_commit=local_commit, remote_commit=remote_commit, updates_available=updates_available)

@app.route('/admin/system/update_repo', methods=['POST'])
@login_required
def update_repo():
    if not current_user.is_admin:
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))
    new_url = request.form.get('repo_url', '').strip()
    if not new_url:
        new_url = "https://github.com/Donmeusi/gefahrstoffverzeichnis"
    try:
        subprocess.check_call(['git', 'remote', 'set-url', 'origin', new_url], stderr=subprocess.STDOUT)
        flash('Repository-URL erfolgreich aktualisiert.', 'success')
    except subprocess.CalledProcessError:
        try:
            subprocess.check_call(['git', 'remote', 'add', 'origin', new_url], stderr=subprocess.STDOUT)
            flash('Repository-URL erfolgreich hinzugefügt.', 'success')
        except Exception as e:
            flash(f'Fehler beim Setzen der URL: {e}', 'error')
    except Exception as e:
        flash(f'Ein unerwarteter Fehler ist aufgetreten: {e}', 'error')
    
    return redirect(url_for('admin_system'))

@app.route('/admin/system/do_update', methods=['POST'])
@login_required
def do_update():
    if not current_user.is_admin:
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))
        
    def trigger_update_script():
        import time, os, subprocess
        time.sleep(2)
        
        if os.environ.get('RUNNING_IN_DOCKER') == 'true':
            # In Docker: Backup DB, git pull, then exit. 
            # Docker (restart: always) and entrypoint will handle pip and migrate.
            db_path = os.path.join(app_data_dir, "gefahrstoffe.db")
            if os.path.exists(db_path):
                backup_dir = os.path.join(app_data_dir, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                import shutil
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy(db_path, os.path.join(backup_dir, f"gefahrstoffe_{timestamp}.db"))
            
            subprocess.run(["git", "pull"])
        else:
            import platform
            if platform.system() == "Windows":
                subprocess.Popen(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "update.ps1"])
            else:
                subprocess.Popen(["bash", "update.sh"])
        
        os._exit(0)
        
    import threading
    threading.Thread(target=trigger_update_script).start()
    
    flash('Update wird im Hintergrund ausgeführt. Der Server startet in wenigen Sekunden neu.', 'success')
    return redirect(url_for('index'))

@app.route('/api/autofill/<cas_nummer>')
@login_required
def api_autofill(cas_nummer):
    import urllib.request
    import urllib.parse
    import json
    import re
    
    cas = cas_nummer.strip()
    if not cas:
        return jsonify({'error': 'Keine CAS-Nummer angegeben'}), 400
        
    try:
        url1 = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(cas)}/cids/JSON'
        try:
            req1 = urllib.request.urlopen(url1, timeout=5)
            res1 = json.loads(req1.read())
            cid = res1['IdentifierList']['CID'][0]
        except Exception:
            return jsonify({'error': 'CAS-Nummer in PubChem nicht gefunden.'}), 404
            
        name_url = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/Title/JSON'
        try:
            name_req = urllib.request.urlopen(name_url, timeout=5)
            name_res = json.loads(name_req.read())
            name = name_res['PropertyTable']['Properties'][0]['Title']
        except Exception:
            name = ""
            
        url2 = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON/?heading=Safety+and+Hazards'
        try:
            req2 = urllib.request.urlopen(url2, timeout=5)
            res2 = json.loads(req2.read())
        except Exception:
            return jsonify({'error': 'Keine GHS-Gefahrstoffdaten bei PubChem hinterlegt.'}), 404
            
        ghs_data = {
            'name': name,
            'signalwort': '',
            'h_saetze': [],
            'p_saetze': [],
            'piktogramme': []
        }
        
        references = {ref.get('ReferenceNumber'): ref.get('SourceName', '') for ref in res2.get('Record', {}).get('Reference', [])}
        
        def get_best_reference(info_list):
            eu_refs = []
            all_refs = []
            for info in info_list:
                ref_num = info.get('ReferenceNumber')
                if not ref_num: continue
                source_name = references.get(ref_num, "")
                if ref_num not in all_refs:
                    all_refs.append(ref_num)
                if "EU" in source_name or "European" in source_name or "ECHA" in source_name or "1272/2008" in source_name:
                    if ref_num not in eu_refs:
                        eu_refs.append(ref_num)
            if eu_refs:
                return eu_refs[0]
            if all_refs:
                return all_refs[0]
            return None

        sections = res2.get('Record', {}).get('Section', [])
        for sec in sections:
            if sec.get('TOCHeading') == 'Safety and Hazards':
                for subsec in sec.get('Section', []):
                    if subsec.get('TOCHeading') == 'Hazards Identification':
                        for subsubsec in subsec.get('Section', []):
                            if subsubsec.get('TOCHeading') == 'GHS Classification':
                                info_list = subsubsec.get('Information', [])
                                best_ref = get_best_reference(info_list)
                                
                                for info in info_list:
                                    if best_ref and info.get('ReferenceNumber') != best_ref:
                                        continue
                                        
                                    name_val = info.get('Name')
                                    markup = info.get('Value', {}).get('StringWithMarkup', [])
                                    
                                    if name_val == 'Pictogram(s)':
                                        for m in markup:
                                            for mk in m.get('Markup', []):
                                                url = mk.get('URL', '')
                                                match = re.search(r'(GHS0\d)', url, re.IGNORECASE)
                                                if match:
                                                    ghs_data['piktogramme'].append(match.group(1).upper())
                                    
                                    elif name_val == 'Signal':
                                        if markup:
                                            signal_en = markup[0].get('String', '').lower()
                                            if 'danger' in signal_en:
                                                ghs_data['signalwort'] = 'Gefahr'
                                            elif 'warning' in signal_en:
                                                ghs_data['signalwort'] = 'Achtung'
                                                
                                    elif name_val == 'GHS Hazard Statements':
                                        for m in markup:
                                            s = m.get('String', '')
                                            match = re.search(r'(H\d{3}[a-zA-Z]*)', s)
                                            if match:
                                                ghs_data['h_saetze'].append(match.group(1))
                                                
                                    elif name_val == 'Precautionary Statement Codes':
                                        for m in markup:
                                            s = m.get('String', '')
                                            matches = re.findall(r'(P\d{3}[a-zA-Z]*)', s)
                                            ghs_data['p_saetze'].extend(matches)
                                            
        ghs_data['piktogramme'] = list(set(ghs_data['piktogramme']))
        ghs_data['h_saetze'] = ", ".join(sorted(list(set(ghs_data['h_saetze']))))
        ghs_data['p_saetze'] = ", ".join(sorted(list(set(ghs_data['p_saetze']))))
        
        return jsonify(ghs_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── Security Headers & Error Handlers ─────────────────────────────────────────

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ─── Application Start ───────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        # Falls DB nicht existiert, erstellen
        if not os.path.exists(os.path.join(app_data_dir, 'gefahrstoffe.db')):
            db.create_all()
            print("Datenbank gefahrstoffe.db erstellt.")
    
    # Im Entwicklungsmodus laufen lassen
    # Für Produktion nutzen Sie stattdessen run_prod.py
    app.run(debug=True)