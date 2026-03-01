from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import pandas as pd
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = 'ein_sehr_geheimer_schluessel_fuer_die_entwicklung'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'gefahrstoffe.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

app.jinja_env.globals.update(getattr=getattr)

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Bitte logge dich ein, um diese Seite zu sehen."

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Bereich(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unterbereiche = db.relationship('Unterbereich', backref='bereich', lazy=True, cascade="all, delete-orphan")

class Unterbereich(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bereich_id = db.Column(db.Integer, db.ForeignKey('bereich.id'), nullable=False)
    gefahrstoffe = db.relationship('Gefahrstoff', backref='unterbereich', lazy=True)

class Gefahrstoff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cas_nummer = db.Column(db.String(20), nullable=True)
    eg_nummer = db.Column(db.String(20), nullable=True)
    signalwort = db.Column(db.String(10), nullable=True)
    piktogramme = db.Column(db.String(100), nullable=True)
    h_saetze = db.Column(db.String(200), nullable=True)
    p_saetze = db.Column(db.String(300), nullable=True)
    lagerort = db.Column(db.String(100), nullable=True)
    menge = db.Column(db.Float, nullable=True)
    mengeneinheit = db.Column(db.String(10), nullable=True)
    datum_erfassung = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sicherheitsdatenblatt = db.Column(db.String(200), nullable=True)
    betriebsanweisung = db.Column(db.String(200), nullable=True)
    unterbereich_id = db.Column(db.Integer, db.ForeignKey('unterbereich.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def __repr__(self):
        return f'<Gefahrstoff {self.name}>'

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Dieser Benutzername ist bereits vergeben.', 'error')
            return redirect(url_for('register'))
            
        is_first_user = User.query.count() == 0
        new_user = User(username=username, is_admin=is_first_user)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registrierung erfolgreich! Du kannst dich nun einloggen.', 'success')
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

@app.route('/locations', methods=['GET', 'POST'])
@login_required
def locations():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_bereich':
            name = request.form.get('bereich_name')
            if name:
                neuer_bereich = Bereich(name=name)
                db.session.add(neuer_bereich)
                db.session.commit()
                flash(f'Bereich "{name}" erfolgreich hinzugefügt.', 'success')
                
        elif action == 'add_unterbereich':
            name = request.form.get('unterbereich_name')
            bereich_id = request.form.get('bereich_id')
            if name and bereich_id:
                neuer_unterbereich = Unterbereich(name=name, bereich_id=bereich_id)
                db.session.add(neuer_unterbereich)
                db.session.commit()
                flash(f'Unterbereich "{name}" erfolgreich hinzugefügt.', 'success')
                
        return redirect(url_for('locations'))
        
    bereiche = Bereich.query.all()
    return render_template('locations.html', bereiche=bereiche)

@app.route('/location/delete_bereich/<int:id>', methods=['POST'])
@login_required
def delete_bereich(id):
    bereich = Bereich.query.get_or_404(id)
    try:
        db.session.delete(bereich)
        db.session.commit()
        flash(f'Bereich "{bereich.name}" gelöscht.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen des Bereichs: {str(e)}', 'error')
    return redirect(url_for('locations'))

@app.route('/location/delete_unterbereich/<int:id>', methods=['POST'])
@login_required
def delete_unterbereich(id):
    unterbereich = Unterbereich.query.get_or_404(id)
    try:
        # Gefahrstoffe, die diesem Unterbereich zugeordnet waren, werden auf null gesetzt oder können per db relationship behandelt werden
        # Wir setzen sie hier proaktiv auf None, um Orphan-Fehler zu vermeiden
        for stoff in unterbereich.gefahrstoffe:
            stoff.unterbereich_id = None
        db.session.delete(unterbereich)
        db.session.commit()
        flash(f'Unterbereich "{unterbereich.name}" gelöscht.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen des Unterbereichs: {str(e)}', 'error')
    return redirect(url_for('locations'))

@app.route('/')
@login_required
def index():
    bereich_id = request.args.get('bereich_id', type=int)
    
    query = Gefahrstoff.query
    if not getattr(current_user, 'is_admin', False):
        query = query.filter_by(user_id=current_user.id)
        
    if bereich_id:
        gefahrstoffe = query.join(Unterbereich).filter(Unterbereich.bereich_id == bereich_id).order_by(Gefahrstoff.name).all()
        aktiver_bereich = Bereich.query.get(bereich_id)
    else:
        gefahrstoffe = query.order_by(Gefahrstoff.name).all()
        aktiver_bereich = None
        
    bereiche = Bereich.query.order_by(Bereich.name).all()
    
    return render_template('index.html', 
                         gefahrstoffe=gefahrstoffe, 
                         bereiche=bereiche, 
                         aktiver_bereich=aktiver_bereich)

@app.route('/view/<int:id>')
@login_required
def view_stoff(id):
    stoff = Gefahrstoff.query.get_or_404(id)
    if not getattr(current_user, 'is_admin', False) and stoff.user_id != current_user.id:
        flash('Keine Berechtigung, diesen Gefahrstoff anzusehen.', 'error')
        return redirect(url_for('index'))
    return render_template('view.html', stoff=stoff)

@app.route('/export/excel')
@login_required
def export_excel():
    query = Gefahrstoff.query
    if not getattr(current_user, 'is_admin', False):
        query = query.filter_by(user_id=current_user.id)
    stoffe = query.order_by(Gefahrstoff.name).all()
    
    data = []
    for s in stoffe:
        standort = f"{s.unterbereich.bereich.name} > {s.unterbereich.name}" if s.unterbereich else (s.lagerort or "-")
        data.append({
            'Name': s.name,
            'CAS-Nummer': s.cas_nummer,
            'EG-Nummer': s.eg_nummer,
            'Standort/Lagerort': standort,
            'Signalwort': s.signalwort,
            'H-Sätze': s.h_saetze,
            'P-Sätze': s.p_saetze,
            'Menge': f"{s.menge} {s.mengeneinheit}" if s.menge else "-"
        })
        
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Gefahrstoffe')
    output.seek(0)
    
    return send_file(output, download_name='gefahrstoffe_export.xlsx', as_attachment=True)

@app.route('/export/pdf')
@login_required
def export_pdf():
    query = Gefahrstoff.query
    if not getattr(current_user, 'is_admin', False):
        query = query.filter_by(user_id=current_user.id)
    stoffe = query.order_by(Gefahrstoff.name).all()
    
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4))
    elements = []
    
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Gefahrstoff-Übersicht", styles['Title']))
    elements.append(Spacer(1, 20))
    
    data = [['Name', 'CAS-Nr.', 'Standort', 'Signalwort', 'Menge']]
    for s in stoffe:
        standort = f"{s.unterbereich.bereich.name} > {s.unterbereich.name}" if s.unterbereich else (s.lagerort or "-")
        data.append([
            s.name,
            s.cas_nummer or '-',
            standort,
            s.signalwort or '-',
            f"{s.menge} {s.mengeneinheit}" if s.menge else "-"
        ])
        
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    doc.build(elements)
    output.seek(0)
    
    return send_file(output, download_name='gefahrstoffe_export.pdf', as_attachment=True)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    bereiche = Bereich.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        cas_nummer = request.form.get('cas_nummer')
        eg_nummer = request.form.get('eg_nummer')
        signalwort = request.form.get('signalwort')
        unterbereich_id = request.form.get('unterbereich_id')
        
        piktogramme_list = request.form.getlist('piktogramme')
        piktogramme = ",".join(piktogramme_list) if piktogramme_list else None
        
        h_saetze = request.form.get('h_saetze')
        p_saetze = request.form.get('p_saetze')
        lagerort = request.form.get('lagerort')
        menge_str = request.form.get('menge')
        mengeneinheit = request.form.get('mengeneinheit')

        menge = None
        if menge_str:
            try:
                menge = float(menge_str.replace(',', '.'))
            except ValueError:
                flash('Ungültiges Zahlenformat bei der Menge eingegeben.', 'error')
                return redirect(url_for('add'))

        sdb_filename = None
        ba_filename = None
        
        if 'sicherheitsdatenblatt' in request.files:
            file = request.files['sicherheitsdatenblatt']
            if file.filename != '':
                sdb_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], sdb_filename))
                
        if 'betriebsanweisung' in request.files:
            file = request.files['betriebsanweisung']
            if file.filename != '':
                ba_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], ba_filename))

        neuer_stoff = Gefahrstoff(
            name=name,
            cas_nummer=cas_nummer,
            eg_nummer=eg_nummer,
            signalwort=signalwort if signalwort else None,
            piktogramme=piktogramme,
            h_saetze=h_saetze,
            p_saetze=p_saetze,
            lagerort=lagerort,
            menge=menge,
            mengeneinheit=mengeneinheit,
            sicherheitsdatenblatt=sdb_filename,
            betriebsanweisung=ba_filename,
            unterbereich_id=unterbereich_id if unterbereich_id else None,
            user_id=current_user.id
        )

        try:
            db.session.add(neuer_stoff)
            db.session.commit()
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
    if not getattr(current_user, 'is_admin', False) and stoff.user_id != current_user.id:
        flash('Keine Berechtigung, diesen Gefahrstoff zu bearbeiten.', 'error')
        return redirect(url_for('index'))
        
    bereiche = Bereich.query.all()
    
    if request.method == 'POST':
        stoff.name = request.form.get('name')
        stoff.cas_nummer = request.form.get('cas_nummer')
        stoff.eg_nummer = request.form.get('eg_nummer')
        signalwort = request.form.get('signalwort')
        stoff.signalwort = signalwort if signalwort else None
        
        unterbereich_id = request.form.get('unterbereich_id')
        stoff.unterbereich_id = unterbereich_id if unterbereich_id else None
        
        piktogramme_list = request.form.getlist('piktogramme')
        stoff.piktogramme = ",".join(piktogramme_list) if piktogramme_list else None
        
        stoff.h_saetze = request.form.get('h_saetze')
        stoff.p_saetze = request.form.get('p_saetze')
        stoff.lagerort = request.form.get('lagerort')
        stoff.mengeneinheit = request.form.get('mengeneinheit')
        
        menge_str = request.form.get('menge')
        if menge_str:
            try:
                stoff.menge = float(menge_str.replace(',', '.'))
            except ValueError:
                flash('Ungültiges Zahlenformat bei der Menge eingegeben.', 'error')
                return redirect(url_for('edit_stoff', id=id))
        else:
            stoff.menge = None
            
        if 'sicherheitsdatenblatt' in request.files:
            file = request.files['sicherheitsdatenblatt']
            if file.filename != '':
                sdb_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], sdb_filename))
                stoff.sicherheitsdatenblatt = sdb_filename
                
        if 'betriebsanweisung' in request.files:
            file = request.files['betriebsanweisung']
            if file.filename != '':
                ba_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], ba_filename))
                stoff.betriebsanweisung = ba_filename

        try:
            db.session.commit()
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
    if not getattr(current_user, 'is_admin', False) and stoff.user_id != current_user.id:
        flash('Keine Berechtigung, diesen Gefahrstoff zu löschen.', 'error')
        return redirect(url_for('index'))
        
    try:
        # Delete associated files if they exist
        if stoff.sicherheitsdatenblatt:
            sdb_path = os.path.join(app.config['UPLOAD_FOLDER'], stoff.sicherheitsdatenblatt)
            if os.path.exists(sdb_path):
                os.remove(sdb_path)
                
        if stoff.betriebsanweisung:
            ba_path = os.path.join(app.config['UPLOAD_FOLDER'], stoff.betriebsanweisung)
            if os.path.exists(ba_path):
                os.remove(ba_path)
                
        db.session.delete(stoff)
        db.session.commit()
        flash(f'Gefahrstoff "{stoff.name}" wurde erfolgreich gelöscht.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen: {str(e)}', 'error')
        
    return redirect(url_for('index'))

@app.route('/move/<int:id>', methods=['GET', 'POST'])
@login_required
def move_stoff(id):
    stoff = Gefahrstoff.query.get_or_404(id)
    if not getattr(current_user, 'is_admin', False) and stoff.user_id != current_user.id:
        flash('Keine Berechtigung, diesen Gefahrstoff zu verschieben.', 'error')
        return redirect(url_for('index'))
        
    bereiche = Bereich.query.all()
    
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
    if not getattr(current_user, 'is_admin', False) and stoff.user_id != current_user.id:
        flash('Keine Berechtigung, diesen Gefahrstoff zu kopieren.', 'error')
        return redirect(url_for('index'))
        
    bereiche = Bereich.query.all()
    
    if request.method == 'POST':
        unterbereich_id = request.form.get('unterbereich_id')
        
        neuer_stoff = Gefahrstoff(
            name=stoff.name,
            cas_nummer=stoff.cas_nummer,
            eg_nummer=stoff.eg_nummer,
            signalwort=stoff.signalwort,
            piktogramme=stoff.piktogramme,
            h_saetze=stoff.h_saetze,
            p_saetze=stoff.p_saetze,
            lagerort=stoff.lagerort,
            menge=stoff.menge,
            mengeneinheit=stoff.mengeneinheit,
            sicherheitsdatenblatt=stoff.sicherheitsdatenblatt,
            betriebsanweisung=stoff.betriebsanweisung,
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

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
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

    return render_template('profile.html')

@app.route('/users')
@login_required
def users():
    if not getattr(current_user, 'is_admin', False):
        flash('Keine Berechtigung. Dieser Bereich ist nur für Administratoren.', 'error')
        return redirect(url_for('index'))
        
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/users/make_admin/<int:id>', methods=['POST'])
@login_required
def make_admin(id):
    if not getattr(current_user, 'is_admin', False):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))
        
    user = User.query.get_or_404(id)
    if user.username == 'admin':
        flash('Der Haupt-Admin kann nicht geändert werden.', 'error')
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        if user.is_admin:
            flash(f'Benutzer {user.username} ist nun Admin.', 'success')
        else:
            flash(f'Admin-Rechte für {user.username} entfernt.', 'info')
            
    return redirect(url_for('users'))

@app.route('/users/delete/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if not getattr(current_user, 'is_admin', False):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('index'))
        
    user = User.query.get_or_404(id)
    if user.username == 'admin':
        flash('Der Haupt-Admin Account kann nicht gelöscht werden.', 'error')
    elif user.id == current_user.id:
        flash('Du kannst nicht deinen eigenen Account löschen.', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'Benutzer {user.username} wurde gelöscht.', 'info')
        
    return redirect(url_for('users'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)