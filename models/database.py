from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# ========== إنشاء كائن SQLAlchemy ==========
db = SQLAlchemy()

# ========== 1. نموذج المستخدم ==========
class Utilisateur(UserMixin, db.Model):
    __tablename__ = 'utilisateurs'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='patient')
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    telephone = db.Column(db.String(20))
    medecin_id = db.Column(db.Integer, db.ForeignKey('medecins.id'))
    specialite = db.Column(db.String(100))
    adresse = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    medecin = db.relationship('Medecin', backref='utilisateur', foreign_keys=[medecin_id])
    
    def get_id(self):
        return str(self.id)

# ========== 2. نموذج الطبيب ==========
class Medecin(db.Model):
    __tablename__ = 'medecins'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    specialite = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    telephone = db.Column(db.String(20))
    adresse_cabinet = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ✅ تعديل: استخدم back_populates بدلاً من backref
    rendezvous = db.relationship('RendezVous', back_populates='medecin', lazy='dynamic')
    consultations = db.relationship('Consultation', back_populates='medecin', lazy='dynamic')
    ordonnances = db.relationship('Ordonnance', back_populates='medecin', lazy='dynamic')

# ========== 3. نموذج المريض ==========
class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    telephone = db.Column(db.String(20), nullable=False)
    date_naissance = db.Column(db.Date)
    adresse = db.Column(db.Text)
    num_assurance = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    # ✅ أضف هذه الحقول الجديدة
    allergies = db.Column(db.Text)           # الحساسية
    chronic_diseases = db.Column(db.Text)    # الأمراض المزمنة
    current_medications = db.Column(db.Text) # العلاجات الحالية

    user = db.relationship('Utilisateur', backref='patient', foreign_keys=[user_id])
    
    # ✅ تعديل: استخدم back_populates بدلاً من backref
    rendezvous = db.relationship('RendezVous', back_populates='patient', lazy='dynamic')
    consultations = db.relationship('Consultation', back_populates='patient', lazy='dynamic')
    ordonnances = db.relationship('Ordonnance', back_populates='patient', lazy='dynamic')
    factures = db.relationship('Facture', back_populates='patient', lazy='dynamic')

# ========== 4. نموذج الموعد ==========
class RendezVous(db.Model):
    __tablename__ = 'rendezvous'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('medecins.id'), nullable=False)
    date_rendezvous = db.Column(db.DateTime, nullable=False)
    duree = db.Column(db.Integer, default=30)
    motif = db.Column(db.Text)
    statut = db.Column(db.String(20), default='en_attente')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ✅ تعديل: استخدم back_populates بدلاً من backref
    patient = db.relationship('Patient', back_populates='rendezvous', foreign_keys=[patient_id])
    medecin = db.relationship('Medecin', back_populates='rendezvous', foreign_keys=[medecin_id])

# ========== 5. نموذج الاستشارة ==========
class Consultation(db.Model):
    __tablename__ = 'consultations'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('medecins.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    diagnostic = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ✅ أضف هذه العلاقات
    patient = db.relationship('Patient', back_populates='consultations', foreign_keys=[patient_id])
    medecin = db.relationship('Medecin', back_populates='consultations', foreign_keys=[medecin_id])

# ========== 6. نموذج الوصفة الطبية ==========
class Ordonnance(db.Model):
    __tablename__ = 'ordonnances'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('medecins.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    medicaments = db.Column(db.Text)
    posologie = db.Column(db.Text)
    duree_traitement = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ✅ أضف هذه العلاقات
    patient = db.relationship('Patient', back_populates='ordonnances', foreign_keys=[patient_id])
    medecin = db.relationship('Medecin', back_populates='ordonnances', foreign_keys=[medecin_id])

# ========== 7. نموذج الفاتورة ==========
class Facture(db.Model):
    __tablename__ = 'factures'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    montant = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    statut = db.Column(db.String(20), default='en_attente')
    date_paiement = db.Column(db.DateTime)
    montant_paye = db.Column(db.Float, default=0)
    montant_restant = db.Column(db.Float, default=0)
    dernier_paiement = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ✅ أضف هذه العلاقة
    patient = db.relationship('Patient', back_populates='factures', foreign_keys=[patient_id])
    
# ========== 8. نموذج الدواء ==========
class Medicament(db.Model):
    __tablename__ = 'medicaments'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50))
    forme = db.Column(db.String(50))
    categorie = db.Column(db.String(50))
    prix = db.Column(db.Float)
    stock = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

# ========== 9. نموذج الملف الطبي ==========
class DossierMedical(db.Model):
    __tablename__ = 'dossiers_medicaux'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    antecedents = db.Column(db.Text)
    allergies = db.Column(db.Text)
    traitements_en_cours = db.Column(db.Text)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

# ========== 10. نموذج الفحص ==========
class Examen(db.Model):
    __tablename__ = 'examens'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('medecins.id'), nullable=False)
    type = db.Column(db.String(100), nullable=False)
    date_examen = db.Column(db.Date, nullable=False)
    resultat = db.Column(db.Text)
    fichier_pdf = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ========== 11. نموذج الشهادة الطبية ==========
class Certificat(db.Model):
    __tablename__ = 'certificats'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('medecins.id'), nullable=False)
    date_emission = db.Column(db.Date, nullable=False)
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)
    motif = db.Column(db.Text)
    diagnostic = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ========== كائن قاعدة البيانات ==========
database = db

def init_data():
    """إدخال البيانات الأولية بعد إنشاء الجداول"""
    from werkzeug.security import generate_password_hash
    from datetime import timedelta
    
    # التحقق من وجود الجدول
    inspector = db.inspect(db.engine)
    if not inspector.has_table('utilisateurs'):
        print("⚠️ Les tables ne sont pas encore prêtes")
        return
    
    # ========== إنشاء حساب Admin ==========
    if Utilisateur.query.count() == 0:
        admin = Utilisateur(
            email='admin@cabinet.com',
            password=generate_password_hash('admin123'),
            role='admin',
            nom='Administrateur',
            prenom='Système',
            telephone='0555000000'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Compte admin créé: admin@cabinet.com / admin123")
    
    # ========== إضافة أطباء تجريبيين ==========
    if Medecin.query.count() == 0:
        medecins_data = [
            {'nom': 'Mohammed', 'prenom': 'Ahmed', 'specialite': 'Cardiologie', 'email': 'ahmed@cabinet.com', 'telephone': '0555123456'},
            {'nom': 'Abdallah', 'prenom': 'Sara', 'specialite': 'Dermatologie', 'email': 'sara@cabinet.com', 'telephone': '0555234567'},
        ]
        for m_data in medecins_data:
            medecin = Medecin(
                nom=f"{m_data['nom']}",
                prenom=f"{m_data['prenom']}",
                specialite=m_data['specialite'],
                email=m_data['email'],
                telephone=m_data['telephone']
            )
            db.session.add(medecin)
        db.session.commit()
        print("✅ Médecins ajoutés")
        
        # إضافة حسابات للأطباء
        for m_data in medecins_data:
            medecin = Medecin.query.filter_by(email=m_data['email']).first()
            if medecin and not Utilisateur.query.filter_by(email=m_data['email']).first():
                user = Utilisateur(
                    email=m_data['email'],
                    password=generate_password_hash('doctor123'),
                    role='medecin',
                    nom=m_data['nom'].split()[0],
                    prenom=m_data['nom'].split()[1] if len(m_data['nom'].split()) > 1 else '',
                    telephone=m_data['telephone'],
                    medecin_id=medecin.id
                )
                db.session.add(user)
        db.session.commit()
        print("✅ Comptes médecins créés")
    
    # ========== إضافة سكرتير ==========
    if not Utilisateur.query.filter_by(email='fatima@cabinet.com').first():
        secretaire = Utilisateur(
            email='fatima@cabinet.com',
            password=generate_password_hash('secret123'),
            role='secretaire',
            nom='Fatima',
            prenom='Zahra',
            telephone='0555000001'
        )
        db.session.add(secretaire)
        db.session.commit()
        print("✅ Compte secrétaire créé: fatima@cabinet.com / secret123")
    
    # ========== إضافة مريض تجريبي ==========
    if not Utilisateur.query.filter_by(email='ali@email.com').first():
        patient_user = Utilisateur(
            email='ali@email.com',
            password=generate_password_hash('patient123'),
            role='patient',
            nom='Ali',
            prenom='Mohammed',
            telephone='0612345678',
            adresse='Alger'
        )
        db.session.add(patient_user)
        db.session.commit()
        
        patient = Patient(
            nom='Ali',
            prenom='Mohammed',
            email='ali@email.com',
            telephone='0612345678',
            user_id=patient_user.id
        )
        db.session.add(patient)
        db.session.commit()
        print("✅ Compte patient créé: ali@email.com / patient123")
    
    # ========== ✅ إضافة مواعيد تجريبية (هنا داخل الدالة) ==========
    if RendezVous.query.count() == 0:
        patients = Patient.query.all()
        medecins = Medecin.query.all()
        
        if patients and medecins:
            now = datetime.now()
            
            # موعد 1: مع أول طبيب وأول مريض
            rdv1 = RendezVous(
                patient_id=patients[0].id,
                medecin_id=medecins[0].id,
                date_rendezvous=now + timedelta(days=1),
                motif="Consultation générale",
                statut="confirme"
            )
            db.session.add(rdv1)
            print(f"✅ RDV ajouté: {patients[0].nom} avec Dr. {medecins[0].nom}")
            
            # موعد 2: مع أول مريض وطبيب ثانٍ (إذا وجد)
            if len(medecins) > 1:
                rdv2 = RendezVous(
                    patient_id=patients[0].id,
                    medecin_id=medecins[1].id,
                    date_rendezvous=now + timedelta(days=3),
                    motif="Contrôle",
                    statut="en_attente"
                )
                db.session.add(rdv2)
                print(f"✅ RDV ajouté: {patients[0].nom} avec Dr. {medecins[1].nom}")
            
            # موعد 3: مع مريض ثانٍ (إذا وجد) وأول طبيب
            if len(patients) > 1:
                rdv3 = RendezVous(
                    patient_id=patients[1].id,
                    medecin_id=medecins[0].id,
                    date_rendezvous=now + timedelta(days=5),
                    motif="Consultation de suivi",
                    statut="en_attente"
                )
                db.session.add(rdv3)
                print(f"✅ RDV ajouté: {patients[1].nom} avec Dr. {medecins[0].nom}")
            
            db.session.commit()
            print("✅ Tous les rendez-vous de démonstration ont été ajoutés")
        else:
            print("⚠️ Impossible d'ajouter des RDV: pas de patients ou médecins")