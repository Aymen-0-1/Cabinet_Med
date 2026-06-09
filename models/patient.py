from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps
from models.database import Medecin, db, Utilisateur, Patient, RendezVous, Consultation, Ordonnance, Facture, Examen, DossierMedical
from datetime import datetime, timedelta

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

def verifier_disponibilite(medecin_id, date_rendezvous, rdv_id=None):
    """Vérifie si un créneau est disponible pour un médecin"""
    
    # Vérifier que la date n'est pas dans le passé
    if date_rendezvous < datetime.now():
        return False, "Impossible de prendre un rendez-vous dans le passé"
    
    # Vérifier qu'il n'y a pas de chevauchement (dans les 30 minutes)
    debut = date_rendezvous - timedelta(minutes=30)
    fin = date_rendezvous + timedelta(minutes=30)
    
    query = RendezVous.query.filter(
        RendezVous.medecin_id == medecin_id,
        RendezVous.date_rendezvous.between(debut, fin),
        RendezVous.statut != 'annule'
    )
    
    # Si on modifie un RDV existant, l'exclure de la vérification
    if rdv_id:
        query = query.filter(RendezVous.id != rdv_id)
    
    existing = query.first()
    
    if existing:
        return False, f"Le médecin est déjà occupé à {existing.date_rendezvous.strftime('%H:%M')}"
    
    return True, "Créneau disponible"

def patient_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'patient':
            return render_template('error.html', message="Accès non autorisé"), 403
        return f(*args, **kwargs)
    return decorated_function

def get_current_patient():
    user = Utilisateur.query.get(session['user_id'])
    return Patient.query.filter_by(user_id=user.id).first() if user else None

# ========== PAGES PRINCIPALES ==========
@patient_bp.route('/dashboard')
@patient_required
def dashboard():
    patient = get_current_patient()
    if not patient:
        return render_template('error.html', message="Profil patient non trouvé")
    
    rendezvous = RendezVous.query.filter_by(patient_id=patient.id).order_by(RendezVous.date_rendezvous).limit(5).all()
    consultations = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.date.desc()).limit(5).all()
    ordonnances = Ordonnance.query.filter_by(patient_id=patient.id).order_by(Ordonnance.date.desc()).limit(5).all()
    factures = Facture.query.filter_by(patient_id=patient.id).order_by(Facture.date.desc()).limit(5).all()
    
    return render_template('patient/dashboard.html',
                         patient=patient,
                         rendezvous=rendezvous,
                         consultations=consultations,
                         ordonnances=ordonnances,
                         factures=factures)

@patient_bp.route('/dossier')
@patient_required
def dossier():
    patient = get_current_patient()
    if not patient:
        return render_template('error.html', message="Profil patient non trouvé")
    
    dossier = DossierMedical.query.filter_by(patient_id=patient.id).first()
    consultations = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.date.desc()).all()
    ordonnances = Ordonnance.query.filter_by(patient_id=patient.id).order_by(Ordonnance.date.desc()).all()
    examens = Examen.query.filter_by(patient_id=patient.id).order_by(Examen.date_examen.desc()).all()
    
    return render_template('patient/dossier_medical.html',
                         patient=patient,
                         dossier_medical=dossier,
                         consultations=consultations,
                         ordonnances=ordonnances,
                         examens=examens)

@patient_bp.route('/profil', methods=['GET', 'POST'])
@patient_required
def profil():
    patient = get_current_patient()
    if not patient:
        return render_template('error.html', message="Profil patient non trouvé")
    
    user = Utilisateur.query.get(session['user_id'])
    
    if request.method == 'POST':
        # Mettre à jour les informations
        patient.telephone = request.form.get('telephone', patient.telephone)
        patient.email = request.form.get('email', patient.email)
        patient.adresse = request.form.get('adresse', patient.adresse)
        patient.date_naissance = datetime.strptime(request.form.get('date_naissance'), '%Y-%m-%d').date() if request.form.get('date_naissance') else patient.date_naissance
        patient.num_assurance = request.form.get('num_assurance', patient.num_assurance)
        
        user.telephone = request.form.get('telephone', user.telephone)
        user.adresse = request.form.get('adresse', user.adresse)
        
        # Changer le mot de passe
        new_password = request.form.get('new_password')
        if new_password:
            from werkzeug.security import generate_password_hash
            current_password = request.form.get('current_password')
            from werkzeug.security import check_password_hash
            
            if check_password_hash(user.password, current_password):
                user.password = generate_password_hash(new_password)
            else:
                return render_template('patient/profil.html', patient=patient, error="Mot de passe actuel incorrect")
        
        db.session.commit()
        return render_template('patient/profil.html', patient=patient, success="Profil mis à jour avec succès")
    
    return render_template('patient/profil.html', patient=patient)

@patient_bp.route('/factures')
@patient_required
def factures():
    patient = get_current_patient()
    if not patient:
        return render_template('error.html', message="Profil patient non trouvé")
    
    factures = Facture.query.filter_by(patient_id=patient.id).order_by(Facture.date.desc()).all()
    
    total_factures = len(factures)
    total_paye = sum(f.montant_paye or 0 for f in factures)
    total_restant = sum(f.montant - (f.montant_paye or 0) for f in factures)
    
    return render_template('patient/factures.html',
                         factures=factures,
                         total_factures=total_factures,
                         total_paye=total_paye,
                         total_restant=total_restant)

@patient_bp.route('/rendezvous', methods=['GET', 'POST'])
@patient_required
def rendezvous_page():
    patient = get_current_patient()
    if not patient:
        return render_template('error.html', message="Profil patient non trouvé")
    
    from models.database import Medecin, RendezVous
    
    if request.method == 'POST':
        medecin_id = request.form.get('medecin_id')
        date_rdv = request.form.get('date')
        heure_rdv = request.form.get('heure')
        motif = request.form.get('motif')
        
        date_time = datetime.strptime(f"{date_rdv} {heure_rdv}", '%Y-%m-%d %H:%M')
        
        # ✅ Vérifier la disponibilité
        disponible, message = verifier_disponibilite(medecin_id, date_time)
        
        if not disponible:
            medecins = Medecin.query.all()
            return render_template('patient/rendezvous.html', 
                                 medecins=medecins, 
                                 error=message)
        
        rendezvous = RendezVous(
            patient_id=patient.id,
            medecin_id=medecin_id,
            date_rendezvous=date_time,
            motif=motif,
            statut='en_attente'
        )
        db.session.add(rendezvous)
        db.session.commit()
        
        return redirect(url_for('patient.dashboard'))
    
    medecins = Medecin.query.all()
    return render_template('patient/rendezvous.html', medecins=medecins)

# ========== CONSULTATIONS & ORDONNANCES ==========
@patient_bp.route('/consultations')
@patient_required
def consultations():
    patient = get_current_patient()
    consultations = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.date.desc()).all()
    return render_template('patient/consultations.html', consultations=consultations)

@patient_bp.route('/ordonnances')
@patient_required
def ordonnances():
    patient = get_current_patient()
    ordonnances = Ordonnance.query.filter_by(patient_id=patient.id).order_by(Ordonnance.date.desc()).all()
    return render_template('patient/ordonnances.html', ordonnances=ordonnances)

@patient_bp.route('/ordonnance/print/<int:id>')
@patient_required
def print_ordonnance(id):
    ordonnance = Ordonnance.query.get_or_404(id)
    patient_id = session.get('patient_id')
    
    # ✅ Vérification avec patient_id de la session
    if not patient_id:
        return "Patient non trouvé dans la session", 404
    
    if ordonnance.patient_id != patient_id:
        return "Accès non autorisé", 403
    
    # ✅ Récupérer le patient
    patient = Patient.query.get(patient_id)
    if not patient:
        return "Patient non trouvé", 404
    
    # ✅ جلب معلومات الطبيب
    from models.database import Medecin
    medecin = Medecin.query.get(ordonnance.medecin_id)
    
    if medecin:
        medecin_nom = medecin.nom
        medecin_specialite = medecin.specialite
    else:
        medecin_nom = "Médecin"
        medecin_specialite = "Généraliste"
    
    # ✅ بناء HTML مبسط للطباعة (بدون أخطاء)
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Ordonnance Médicale</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 40px; margin: 0; }}
            .ordonnance {{ max-width: 700px; margin: 0 auto; border: 1px solid #ccc; padding: 30px; border-radius: 10px; }}
            .header {{ text-align: center; border-bottom: 2px solid #27ae60; padding-bottom: 15px; margin-bottom: 20px; }}
            .medecin {{ margin-bottom: 20px; }}
            .patient {{ margin-bottom: 20px; }}
            .medicaments {{ margin: 20px 0; }}
            .signature {{ margin-top: 50px; text-align: right; }}
            @media print {{ .no-print {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div class="ordonnance">
            <div class="header">
                <h1>🏥 Clinique Les Jumeaux</h1>
                <p>Aïn Defla | Tel: 0697 21 32 42</p>
            </div>
            <div class="medecin">
                <strong>Dr. {medecin_nom}</strong><br>
                {medecin_specialite}
            </div>
            <div class="patient">
                <strong>Patient:</strong> {patient.nom} {patient.prenom}<br>
                <strong>Date:</strong> {ordonnance.date.strftime('%d/%m/%Y') if ordonnance.date else '-'}
            </div>
            <div class="medicaments">
                <h3>Prescription médicale</h3>
                <div style="white-space: pre-line;">{ordonnance.medicaments or ''}</div>
            </div>
            {f'<div><strong>Posologie:</strong><br>{ordonnance.posologie}</div>' if ordonnance.posologie else ''}
            {f'<div><strong>Durée du traitement:</strong> {ordonnance.duree_traitement}</div>' if ordonnance.duree_traitement else ''}
            <div class="signature">
                <p>Signature et cachet du médecin</p>
            </div>
            <div class="no-print" style="text-align:center; margin-top:20px;">
                <button onclick="window.print()">🖨️ Imprimer</button>
            </div>
        </div>
    </body>
    </html>
    """
    return html

# ========== EXAMENS & ANALYSES ==========
@patient_bp.route('/examens')
@patient_required
def examens():
    patient = get_current_patient()
    examens = Examen.query.filter_by(patient_id=patient.id).order_by(Examen.date_examen.desc()).all()
    return render_template('patient/examens.html', examens=examens)

@patient_bp.route('/analyses')
@patient_required
def analyses():
    patient = get_current_patient()
    examens = Examen.query.filter_by(patient_id=patient.id).order_by(Examen.date_examen.desc()).all()
    return render_template('patient/analyses.html', examens=examens)

# ========== FACTURES ==========
@patient_bp.route('/facture/print/<int:id>')
@patient_required
def print_facture(id):
    facture = Facture.query.get_or_404(id)
    patient = get_current_patient()
    
    if facture.patient_id != patient.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    reste = facture.montant - (facture.montant_paye or 0)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Facture N° {facture.numero}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 40px; }}
        .facture {{ max-width: 700px; margin: 0 auto; border: 1px solid #ccc; padding: 30px; border-radius: 10px; }}
        .header {{ text-align: center; border-bottom: 2px solid #27ae60; padding-bottom: 15px; margin-bottom: 20px; }}
        .info {{ margin-bottom: 20px; }}
        .montant {{ font-size: 24px; font-weight: bold; color: #27ae60; margin: 20px 0; }}
        @media print {{ .no-print {{ display: none; }} }}
    </style>
    </head>
    <body>
        <div class="facture">
            <div class="header"><h1>🏥 Clinique Les Jumeaux</h1><p>Aïn Defla | Tel: 0697 21 32 42</p></div>
            <h2 style="text-align:center;">FACTURE</h2>
            <div class="info"><strong>N° Facture:</strong> {facture.numero}<br>
            <strong>Date:</strong> {facture.date.strftime('%d/%m/%Y') if facture.date else '-'}<br>
            <strong>Patient:</strong> {patient.nom} {patient.prenom}</div>
            <div class="montant">Montant: {facture.montant} DA</div>
            {f'<div>Déjà payé: {facture.montant_paye} DA</div>' if facture.montant_paye else ''}
            {f'<div><strong>Reste à payer: {reste} DA</strong></div>' if reste > 0 else '<div>✓ Facture payée</div>'}
            {f'<div>Description: {facture.description}</div>' if facture.description else ''}
            <div class="no-print" style="text-align:center; margin-top:20px;"><button onclick="window.print()">Imprimer</button></div>
        </div>
    </body>
    </html>
    """
    return html

# ========== API ROUTES ==========
@patient_bp.route('/api/factures/<int:id>/payer', methods=['POST'])
@patient_required
def api_payer_facture(id):
    data = request.json
    facture = Facture.query.get_or_404(id)
    patient = get_current_patient()
    
    if facture.patient_id != patient.id:
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    montant = data.get('montant', 0)
    if montant <= 0:
        return jsonify({'success': False, 'message': 'Montant invalide'}), 400
    
    paye_actuel = facture.montant_paye or 0
    nouveau_paye = paye_actuel + montant
    
    if nouveau_paye > facture.montant:
        return jsonify({'success': False, 'message': 'Montant dépasse le reste à payer'}), 400
    
    facture.montant_paye = nouveau_paye
    facture.montant_restant = facture.montant - nouveau_paye
    facture.date_paiement = datetime.now()
    facture.dernier_paiement = datetime.now().date()
    
    if nouveau_paye >= facture.montant:
        facture.statut = 'paye'
    else:
        facture.statut = 'partiel'
    
    db.session.commit()
    
    message = "Facture entièrement payée" if facture.statut == 'paye' else f"Paiement enregistré. Reste: {facture.montant_restant} DA"
    return jsonify({'success': True, 'message': message})

@patient_bp.route('/api/profile')
@patient_required
def api_profile():
    patient = get_current_patient()
    if not patient:
        return jsonify({'error': 'Patient non trouvé'}), 404
    
    return jsonify({
        'id': patient.id,
        'nom': patient.nom,
        'prenom': patient.prenom,
        'email': patient.email,
        'telephone': patient.telephone,
        'adresse': patient.adresse
    })

@patient_bp.route('/api/stats')
@patient_required
def api_stats():
    patient = get_current_patient()
    if not patient:
        return jsonify({'error': 'Patient non trouvé'}), 404
    
    consultations = Consultation.query.filter_by(patient_id=patient.id).count()
    ordonnances = Ordonnance.query.filter_by(patient_id=patient.id).count()
    examens = Examen.query.filter_by(patient_id=patient.id).count()
    
    last_consult = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.date.desc()).first()
    
    return jsonify({
        'consultations': consultations,
        'ordonnances': ordonnances,
        'examens': examens,
        'last_report': f"Dernier diagnostic: {last_consult.diagnostic}" if last_consult else None
    })