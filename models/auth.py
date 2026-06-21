from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models.database import db, Utilisateur, Patient
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def login_user(email, password):
    user = Utilisateur.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        return user
    return None

def register_patient(data):    
    existing = Utilisateur.query.filter_by(email=data['email']).first()
    if existing:
        return False, "Email déjà utilisé"
    
    hashed = generate_password_hash(data['password'])
    
    user = Utilisateur(
        email=data['email'],
        password=hashed,
        role='patient',
        nom=data['nom'],
        prenom=data['prenom'],
        telephone=data['telephone'],
        adresse=data.get('adresse', '')
    )
    db.session.add(user)
    db.session.flush()
    
    date_naissance = None
    if data.get('date_naissance'):
        date_naissance = datetime.strptime(data['date_naissance'], '%Y-%m-%d').date()
    
    patient = Patient(
        nom=data['nom'],
        prenom=data['prenom'],
        email=data['email'],
        telephone=data['telephone'],
        user_id=user.id,
        num_assurance=data.get('num_assurance', ''),
        date_naissance=date_naissance,
        adresse=data.get('adresse', '')
    )
    db.session.add(patient)
    db.session.commit()
    
    return True, "Compte patient créé avec succès"

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = login_user(email, password)
        
        if user:
            session.permanent = True

            session['user_id'] = user.id
            session['email'] = user.email
            session['role'] = user.role
            session['nom'] = user.nom
            session['prenom'] = user.prenom
            session['telephone'] = user.telephone or ''
            
            print(f"=== LOGIN: rôle={user.role}, user_id={user.id} ===")
            
            if user.role == 'patient':
                patient = Patient.query.filter_by(user_id=user.id).first()
                if patient:
                    session['patient_id'] = patient.id
                    print(f"✅ Patient ID ajouté à la session via user_id: {patient.id}")
                else:
                    patient = Patient.query.filter_by(email=user.email).first()
                    if patient:
                        session['patient_id'] = patient.id
                        patient.user_id = user.id
                        db.session.commit()
                        print(f"✅ Patient ID ajouté à la session via email: {patient.id}")
                    else:
                        print(f"⚠️ Aucun patient trouvé pour user_id={user.id} ou email={user.email}")
            
            if user.role == 'medecin' and user.medecin_id:
                session['medecin_id'] = user.medecin_id
                print(f"✅ Médecin ID ajouté à la session: {user.medecin_id}")
            
            # Redirection selon le rôle
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'medecin':
                return redirect(url_for('medecin.dashboard'))
            elif user.role == 'secretaire':
                return redirect(url_for('secretaire.dashboard'))
            else:
                return redirect(url_for('patient.dashboard'))
        else:
            return render_template('auth/login.html', error="Email ou mot de passe incorrect")
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        data = {
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'nom': request.form.get('nom'),
            'prenom': request.form.get('prenom'),
            'telephone': request.form.get('telephone'),
            'num_assurance': request.form.get('num_assurance', ''),
            'date_naissance': request.form.get('date_naissance'),
            'adresse': request.form.get('adresse', '')
        }
        
        if data['password'] != request.form.get('confirm_password'):
            return render_template('auth/register.html', error="Les mots de passe ne correspondent pas")
        
        if len(data['password']) < 4:
            return render_template('auth/register.html', error="Le mot de passe doit contenir au moins 4 caractères")
        
        success, message = register_patient(data)
        
        if success:
            return render_template('auth/register.html', success=message)
        else:
            return render_template('auth/register.html', error=message)
    
    return render_template('auth/register.html')