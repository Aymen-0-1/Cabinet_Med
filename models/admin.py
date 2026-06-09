from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps
from models.database import db, Utilisateur, Patient, Medecin
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            return render_template('error.html', message="Accès non autorisé"), 403
        return f(*args, **kwargs)
    return decorated_function

# ========== PAGES ==========
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    total_patients = Patient.query.count()
    total_medecins = Medecin.query.count()
    total_users = Utilisateur.query.count()
    
    return render_template('admin/dashboard.html',
                         total_patients=total_patients,
                         total_medecins=total_medecins,
                         total_users=total_users)

@admin_bp.route('/gestion/utilisateurs')
@admin_required
def gestion_utilisateurs():
    users = Utilisateur.query.all()
    medecins = Medecin.query.all()
    return render_template('admin/gestion_utilisateurs.html', 
                         utilisateurs=users, 
                         medecins=medecins)

# ========== API - GESTION UTILISATEURS ==========
@admin_bp.route('/api/utilisateurs', methods=['GET'])
@admin_required
def get_utilisateurs():
    users = Utilisateur.query.all()
    return jsonify([u.to_dict() for u in users])

@admin_bp.route('/api/utilisateurs', methods=['POST'])
@admin_required
def create_utilisateur():
    data = request.json
    try:
        existing = Utilisateur.query.filter_by(email=data['email']).first()
        if existing:
            return jsonify({'success': False, 'message': 'Email déjà utilisé'}), 400
        
        hashed = generate_password_hash(data['password'])
        
        user = Utilisateur(
            email=data['email'],
            password=hashed,
            role=data['role'],
            nom=data.get('nom', ''),
            prenom=data.get('prenom', ''),
            telephone=data.get('telephone', ''),
            specialite=data.get('specialite', ''),
            adresse=data.get('adresse', '')
        )
        db.session.add(user)
        
        # Si c'est un médecin, créer aussi dans la table medecins
        if data['role'] == 'medecin':
            medecin = Medecin(
                nom=data.get('nom', ''),
                specialite=data.get('specialite', ''),
                email=data.get('email', ''),
                telephone=data.get('telephone', ''),
                adresse_cabinet=data.get('adresse', ''),
                numero_ordre=data.get('numero_ordre', '')
            )
            db.session.add(medecin)
            db.session.flush()
            user.medecin_id = medecin.id
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Utilisateur créé avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/api/utilisateurs/<int:user_id>', methods=['PUT'])
@admin_required
def update_utilisateur(user_id):
    data = request.json
    try:
        user = Utilisateur.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Utilisateur non trouvé'}), 404
        
        user.nom = data.get('nom', user.nom)
        user.prenom = data.get('prenom', user.prenom)
        user.email = data.get('email', user.email)
        user.telephone = data.get('telephone', user.telephone)
        user.role = data.get('role', user.role)
        user.specialite = data.get('specialite', user.specialite)
        user.adresse = data.get('adresse', user.adresse)
        
        if data.get('password'):
            user.password = generate_password_hash(data['password'])
        
        # Si changement de rôle vers médecin
        if data['role'] == 'medecin' and not user.medecin_id:
            medecin = Medecin(
                nom=user.nom,
                specialite=user.specialite,
                email=user.email,
                telephone=user.telephone,
                adresse_cabinet=user.adresse
            )
            db.session.add(medecin)
            db.session.flush()
            user.medecin_id = medecin.id
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Utilisateur modifié avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/api/utilisateurs/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_utilisateur(user_id):
    try:
        user = Utilisateur.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Utilisateur non trouvé'}), 404
        
        if user.role == 'admin':
            return jsonify({'success': False, 'message': 'Impossible de supprimer un admin'}), 400
        
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Utilisateur supprimé avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400