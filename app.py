# app.py - ZİMMET SİSTEMİ - RAILWAY UYUMLU SON HAL (19.11.2025)
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import datetime
import os   # <--- RAILWAY İÇİN ZORUNLU

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guvenli_sifre_2025_degistir_bunu'

# RAILWAY POSTGRESQL UYUMLU VERİTABANI BAĞLANTISI
# Railway DATABASE_URL verir → postgres:// ile başlar
# SQLAlchemy postgresql:// ister → replace ile düzeltiyoruz
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1) or 'sqlite:///zimmet.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Yönetici şifresi: 27080606
ADMIN_HASH = generate_password_hash('27080606')

# ==================== MODELLER ====================
class Personnel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    duty = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    description = db.Column(db.Text)

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    serial = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey('personnel.id'))
    in_depot = db.Column(db.Boolean, default=True)

# ==================== YARDIMCI DEKORATÖR ====================
def login_required_manager(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_manager'):
            flash('Bu işlem için yönetici girişi gereklidir.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ==================== ROUTES ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manager', methods=['GET', 'POST'])
def manager_login():
    if request.method == 'POST':
        if check_password_hash(ADMIN_HASH, request.form['password']):
            session['is_manager'] = True
            flash('Yönetici girişi başarılı!', 'success')
        else:
            flash('Yanlış şifre!', 'danger')
        return redirect(url_for('index'))
    return redirect(url_for('index'))

@app.route('/guest_login', methods=['POST'])
def guest_login():
    session['is_guest'] = True
    flash('Misafir olarak giriş yaptınız (sadece görüntüleme).', 'info')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('index'))

# —— MİSAFİR + YÖNETİCİ GÖREBİLİR ——
@app.route('/personnel')
def personnel_list():
    if not (session.get('is_manager') or session.get('is_guest')):
        return redirect(url_for('index'))
    return render_template('personnel_list.html',
                         personnels=Personnel.query.all(),
                         is_manager=session.get('is_manager', False),
                         is_guest=session.get('is_guest', False))

@app.route('/personnel_detail/<int:id>')
def personnel_detail(id):
    if not (session.get('is_manager') or session.get('is_guest')):
        return redirect(url_for('index'))
    person = Personnel.query.get_or_404(id)
    equipments = Equipment.query.filter_by(assigned_to=id).all()
    return render_template('personnel_detail.html',
                         person=person,
                         equipments=equipments,
                         personnels=Personnel.query.all(),
                         is_manager=session.get('is_manager', False),
                         is_guest=session.get('is_guest', False))

@app.route('/print_card/<int:person_id>')
def print_card(person_id):
    if not (session.get('is_manager') or session.get('is_guest')):
        return redirect(url_for('index'))
    person = Personnel.query.get_or_404(person_id)
    equipments = Equipment.query.filter_by(assigned_to=person_id).all()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
        c.setFont('DejaVuSans', 12)
    except:
        c.setFont('Helvetica', 12)
    c.setFillColorRGB(0, 0.3, 0.6); c.rect(0, height-100, width, 100, fill=1)
    c.setFillColorRGB(1,1,1); c.drawCentredString(width/2, height-70, "ZİMMET FORMU")
    c.setFillColorRGB(0,0,0)
    y = height - 140
    c.drawString(60, y, f"Personel: {person.name} {person.surname}"); y -= 30
    c.drawString(60, y, f"Görev: {person.duty or '-'}"); y -= 30
    c.drawString(60, y, f"Telefon: {person.phone or '-'}"); y -= 50
    for i, eq in enumerate(equipments, 1):
        c.drawString(60, y, f"{i}. {eq.name} - {eq.serial}"); y -= 25
    c.drawString(60, y-40, f"Tarih: {datetime.datetime.now().strftime('%d.%m.%Y')}")
    c.save(); buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=zimmet_{person.name}_{person.surname}.pdf'
    return response

# —— SADECE YÖNETİCİ ——
@app.route('/equipment')
@login_required_manager
def equipment_list():
    return render_template('equipment_list.html',
                         equipments=Equipment.query.all(),
                         personnels=Personnel.query.all())

@app.route('/equipment_detail/<int:eq_id>')
@login_required_manager
def equipment_detail(eq_id):
    eq = Equipment.query.get_or_404(eq_id)
    owner = Personnel.query.get(eq.assigned_to) if eq.assigned_to else None
    return render_template('equipment_detail.html',
                         eq=eq,
                         owner=owner,
                         personnels=Personnel.query.all(),
                         is_manager=True)

@app.route('/search', methods=['GET', 'POST'])
@login_required_manager
def search():
    persons = []
    eqs = []
    query = None
    if request.method == 'POST':
        query = request.form['query'].strip()
        if query:
            pattern = f"%{query}%"
            persons = Personnel.query.filter(
                Personnel.name.ilike(pattern) |
                Personnel.surname.ilike(pattern) |
                Personnel.duty.ilike(pattern) |
                Personnel.phone.ilike(pattern)
            ).all()
            eqs = Equipment.query.filter(
                Equipment.name.ilike(pattern) |
                Equipment.serial.ilike(pattern)
            ).all()
    return render_template('search.html',
                         persons=persons,
                         eqs=eqs,
                         personnels=Personnel.query.all(),
                         query=query)

# PERSONEL İŞLEMLERİ
@app.route('/add_personnel', methods=['GET', 'POST'])
@login_required_manager
def add_personnel():
    if request.method == 'POST':
        p = Personnel(name=request.form['name'],
                      surname=request.form['surname'],
                      duty=request.form['duty'],
                      phone=request.form['phone'],
                      description=request.form['description'])
        db.session.add(p); db.session.commit()
        flash('Personel eklendi.', 'success')
        return redirect(url_for('personnel_list'))
    return render_template('add_personnel.html')

@app.route('/edit_personnel/<int:id>', methods=['GET', 'POST'])
@login_required_manager
def edit_personnel(id):
    p = Personnel.query.get_or_404(id)
    if request.method == 'POST':
        p.name = request.form['name']
        p.surname = request.form['surname']
        p.duty = request.form['duty']
        p.phone = request.form['phone']
        p.description = request.form['description']
        db.session.commit()
        flash('Personel güncellendi.', 'success')
        return redirect(url_for('personnel_list'))
    return render_template('edit_personnel.html', person=p)

@app.route('/delete_personnel/<int:id>')
@login_required_manager
def delete_personnel(id):
    p = Personnel.query.get_or_404(id)
    Equipment.query.filter_by(assigned_to=id).update({'assigned_to': None, 'in_depot': True})
    db.session.delete(p); db.session.commit()
    flash('Personel silindi.', 'success')
    return redirect(url_for('personnel_list'))

# EKİPMAN İŞLEMLERİ
@app.route('/add_equipment', methods=['GET', 'POST'])
@login_required_manager
def add_equipment():
    if request.method == 'POST':
        eq = Equipment(name=request.form['name'],
                       serial=request.form['serial'],
                       description=request.form['description'])
        db.session.add(eq); db.session.commit()
        flash('Ekipman eklendi.', 'success')
        return redirect(url_for('equipment_list'))
    return render_template('add_equipment.html')

@app.route('/edit_equipment/<int:id>', methods=['GET', 'POST'])
@login_required_manager
def edit_equipment(id):
    eq = Equipment.query.get_or_404(id)
    if request.method == 'POST':
        eq.name = request.form['name']
        eq.serial = request.form['serial']
        eq.description = request.form['description']
        db.session.commit()
        flash('Ekipman güncellendi.', 'success')
        return redirect(url_for('equipment_list'))
    return render_template('edit_equipment.html', eq=eq)

@app.route('/delete_equipment/<int:id>')
@login_required_manager
def delete_equipment(id):
    eq = Equipment.query.get_or_404(id)
    db.session.delete(eq); db.session.commit()
    flash('Ekipman silindi.', 'success')
    return redirect(url_for('equipment_list'))

@app.route('/assign_equipment/<int:eq_id>', methods=['POST'])
@login_required_manager
def assign_equipment(eq_id):
    eq = Equipment.query.get_or_404(eq_id)
    target = request.form['assign_to']
    if target == 'depot':
        eq.assigned_to = None
        eq.in_depot = True
    else:
        eq.assigned_to = int(target)
        eq.in_depot = False
    db.session.commit()
    flash('Zimmet aktarıldı.', 'success')
    return redirect(request.referrer or url_for('personnel_list'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)
