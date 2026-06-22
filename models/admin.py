from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps
from models.database import db, Patient, Medecin, Utilisateur, RendezVous, Consultation, Facture
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func

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
    now = datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0)
    
    total_patients = Patient.query.count()
    total_medecins = Medecin.query.count()
    total_users = Utilisateur.query.count()
    
    total_secretaires = Utilisateur.query.filter_by(role='secretaire').count()
    
    try:
        medecins_actifs = Medecin.query.filter_by(statut='actif').count()
    except:
        medecins_actifs = total_medecins
    
    try:
        nouveaux_patients_mois = Patient.query.filter(
            Patient.date_creation >= start_of_month
        ).count()
    except:
        nouveaux_patients_mois = 0
    
    try:
        nouveaux_users_mois = Utilisateur.query.filter(
            Utilisateur.date_creation >= start_of_month
        ).count()
    except:
        nouveaux_users_mois = 0
    
    total_rendezvous = RendezVous.query.count()
    total_consultations = Consultation.query.count()
    total_factures = Facture.query.count()
    
    factures_payees = Facture.query.filter_by(statut='paye').all()
    chiffre_affaires = sum(f.montant for f in factures_payees)
    
    derniers_patients = Patient.query.order_by(Patient.id.desc()).limit(10).all()
    derniers_medecins = Medecin.query.order_by(Medecin.id.desc()).limit(10).all()
    
    activite_recente = []
    
    derniers_rdv = RendezVous.query.order_by(RendezVous.date_rendezvous.desc()).limit(5).all()
    for rdv in derniers_rdv:
        activite_recente.append({
            'type': 'rendezvous',
            'description': f"RDV {rdv.patient.nom if rdv.patient else 'Patient'} avec Dr. {rdv.medecin.nom if rdv.medecin else 'Médecin'}",
            'date': rdv.date_rendezvous,
            'statut': rdv.statut
        })
    
    for patient in derniers_patients[:3]:
        activite_recente.append({
            'type': 'patient',
            'description': f"Nouveau patient: {patient.nom} {patient.prenom}",
            'date': patient.date_creation if hasattr(patient, 'date_creation') else now,
            'statut': 'inscrit'
        })
    
    activite_recente.sort(key=lambda x: x['date'], reverse=True)
    
    derniere_connexion = "Aujourd'hui"  
    
    return render_template('admin/dashboard.html',
                         total_patients=total_patients,
                         total_medecins=total_medecins,
                         total_users=total_users,
                         
                         total_secretaires=total_secretaires,
                         medecins_actifs=medecins_actifs,
                         nouveaux_patients_mois=nouveaux_patients_mois,
                         nouveaux_users_mois=nouveaux_users_mois,
                         
                         total_rendezvous=total_rendezvous,
                         total_consultations=total_consultations,
                         total_factures=total_factures,
                         chiffre_affaires=chiffre_affaires,
                         
                         derniers_patients=derniers_patients,
                         derniers_medecins=derniers_medecins,
                         activite_recente=activite_recente[:10],
                         
                         derniere_connexion=derniere_connexion)

@admin_bp.route('/gestion/utilisateurs')
@admin_required
def gestion_utilisateurs():
    users = Utilisateur.query.all()
    medecins = Medecin.query.all()
    return render_template('admin/gestion_utilisateurs.html', 
                         utilisateurs=users, 
                         medecins=medecins)

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
        
        if data['role'] == 'medecin':
            medecin = Medecin(
                nom=data.get('nom', ''),
                prenom=data.get('prenom', ''),
                specialite=data.get('specialite', ''),
                email=data.get('email', ''),
                telephone=data.get('telephone', ''),
                adresse_cabinet=data.get('adresse', ''),
            )
            db.session.add(medecin)
            db.session.flush()
            user.medecin_id = medecin.id
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Utilisateur créé avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/api/utilisateurs/<int:user_id>', methods=['GET'])
@admin_required
def get_utilisateur(user_id):
    user = Utilisateur.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Utilisateur non trouvé'}), 404
    
    return jsonify({
        'id': user.id,
        'email': user.email,
        'nom': user.nom,
        'prenom': user.prenom,
        'telephone': user.telephone,
        'role': user.role,
        'specialite': user.specialite,
        'adresse': user.adresse
    })

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
        
        if user.role == 'medecin':
            medecin = Medecin.query.filter_by(email=user.email).first()
            if medecin:
                medecin.nom = user.nom
                medecin.prenom = user.prenom
                medecin.specialite = user.specialite
                medecin.telephone = user.telephone
                medecin.adresse_cabinet = user.adresse
            elif user.medecin_id:
                medecin = Medecin.query.get(user.medecin_id)
                if medecin:
                    medecin.nom = user.nom
                    medecin.prenom = user.prenom
                    medecin.specialite = user.specialite
                    medecin.telephone = user.telephone
                    medecin.adresse_cabinet = user.adresse
            else:
                medecin = Medecin(
                    nom=user.nom,
                    prenom=user.prenom,
                    specialite=user.specialite,
                    email=user.email,
                    telephone=user.telephone,
                    adresse_cabinet=user.adresse
                )
                db.session.add(medecin)
                db.session.flush()
                user.medecin_id = medecin.id
        
        db.session.commit()
        
        if session.get('user_id') == user_id:
            session['nom'] = user.nom
            session['prenom'] = user.prenom
            session['email'] = user.email
            session['telephone'] = user.telephone
            session['role'] = user.role
            if user.role == 'medecin':
                session['specialite'] = user.specialite
        
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
    
@admin_bp.route('/statistiques')
@admin_required
def statistiques():
    
    now = datetime.now()
    first_day_month = datetime(now.year, now.month, 1)
    
    # ========== 1. STATISTIQUES GÉNÉRALES ==========
    stats = {}
    
    stats['total_patients'] = Patient.query.count()
    stats['new_patients_month'] = Patient.query.filter(Patient.date_creation >= first_day_month).count()
    
    stats['total_medecins'] = Medecin.query.count()
    stats['specialites_count'] = db.session.query(Medecin.specialite).distinct().count()
    
    stats['total_consultations'] = Consultation.query.count()
    stats['consultations_month'] = Consultation.query.filter(Consultation.date >= first_day_month).count()
    
    factures_payees = Facture.query.filter(Facture.statut == 'paye').all()
    stats['total_revenu'] = sum(f.montant for f in factures_payees)
    stats['revenu_month'] = sum(f.montant for f in Facture.query.filter(Facture.statut == 'paye', Facture.date >= first_day_month).all())
    
    medecins = Medecin.query.all()
    medecins_stats = []
    
    for med in medecins:
        consultations_count = Consultation.query.filter_by(medecin_id=med.id).count()
        ordonnances_count = Ordonnance.query.filter_by(medecin_id=med.id).count()
        patients_count = db.session.query(Consultation.patient_id).filter_by(medecin_id=med.id).distinct().count()
        
        rdv_count = RendezVous.query.filter(
            RendezVous.medecin_id == med.id,
            RendezVous.date_rendezvous >= first_day_month,
            RendezVous.statut != 'annule'
        ).count()
        occupation = min(100, int(rdv_count * 100 / 20))  
        
        medecins_stats.append({
            'nom': med.nom,
            'specialite': med.specialite,
            'consultations': consultations_count,
            'ordonnances': ordonnances_count,
            'patients': patients_count,
            'occupation': occupation
        })
    
    medecins_stats.sort(key=lambda x: x['consultations'], reverse=True)
    stats['medecins_stats'] = medecins_stats[:10]  # Top 10
    
    # ========== 3. STATISTIQUES MENSUELLES POUR GRAPHIQUES ==========
    mois_labels = []
    consultations_data = []
    revenus_data = []
    
    for i in range(5, -1, -1):  
        mois_date = datetime(now.year, now.month, 1) - timedelta(days=30*i)
        mois_suivant = datetime(mois_date.year, mois_date.month + 1, 1) if mois_date.month < 12 else datetime(mois_date.year + 1, 1, 1)
        
        mois_labels.append(mois_date.strftime('%b %Y'))
        
        consultations = Consultation.query.filter(
            Consultation.date >= mois_date,
            Consultation.date < mois_suivant
        ).count()
        consultations_data.append(consultations)
        
        revenus = sum(f.montant for f in Facture.query.filter(
            Facture.statut == 'paye',
            Facture.date >= mois_date,
            Facture.date < mois_suivant
        ).all())
        revenus_data.append(revenus)
    
    stats['mois_labels'] = mois_labels
    stats['consultations_data'] = consultations_data
    stats['revenus_data'] = revenus_data
    
    # ========== 4. DERNIÈRES ACTIVITÉS ==========
    stats['last_rendezvous'] = RendezVous.query.order_by(RendezVous.date_rendezvous.desc()).limit(5).all()
    stats['last_factures'] = Facture.query.order_by(Facture.date.desc()).limit(5).all()
    
    return render_template('admin/statistiques.html', stats=stats)