from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps
from models.database import db, Utilisateur, Medecin, Patient, RendezVous, Consultation, Ordonnance
from datetime import datetime

medecin_bp = Blueprint('medecin', __name__, url_prefix='/medecin')

def medecin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'medecin':
            return render_template('error.html', message="Accès non autorisé"), 403
        return f(*args, **kwargs)
    return decorated_function

def get_current_medecin():
    user = Utilisateur.query.get(session['user_id'])
    if user and user.medecin_id:
        return Medecin.query.get(user.medecin_id)
    return None

# ========== PAGES PRINCIPALES ==========
@medecin_bp.route('/dashboard')
@medecin_required
def dashboard():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    total_consultations = Consultation.query.filter_by(medecin_id=medecin.id).count()
    total_ordonnances = Ordonnance.query.filter_by(medecin_id=medecin.id).count()
    rendezvous = RendezVous.query.filter(
        RendezVous.medecin_id == medecin.id,
        RendezVous.date_rendezvous >= datetime.now()
    ).order_by(RendezVous.date_rendezvous).limit(10).all()
    
    return render_template('medecin/dashboard.html',
                         medecin=medecin,
                         total_consultations=total_consultations,
                         total_ordonnances=total_ordonnances,
                         rendezvous=rendezvous)

@medecin_bp.route('/patients')
@medecin_required
def patients():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    consultations = Consultation.query.filter_by(medecin_id=medecin.id).all()
    patient_ids = list(set([c.patient_id for c in consultations]))
    patients = Patient.query.filter(Patient.id.in_(patient_ids)).all() if patient_ids else []
    
    return render_template('medecin/patients.html', patients=patients)

# ========== GESTION CONSULTATIONS (قالب واحد) ==========
@medecin_bp.route('/consultation/new', methods=['GET', 'POST'])
@medecin_required
def new_consultation():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    if request.method == 'POST':
        consultation = Consultation(
            patient_id=request.form.get('patient_id'),
            medecin_id=medecin.id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%dT%H:%M'),
            diagnostic=request.form.get('diagnostic'),
            prescription=request.form.get('prescription'),
            notes=request.form.get('notes')
        )
        db.session.add(consultation)
        db.session.commit()
        return redirect(url_for('medecin.view_consultation', id=consultation.id))
    
    patients = Patient.query.all()
    return render_template('medecin/new_consultation.html', 
                         patients=patients, 
                         now=datetime.now().strftime('%Y-%m-%dT%H:%M'))

@medecin_bp.route('/consultation/<int:id>', methods=['GET', 'POST'])
@medecin_required
def view_consultation(id):
    consultation = Consultation.query.get_or_404(id)
    medecin = get_current_medecin()
    
    if consultation.medecin_id != medecin.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    if request.method == 'POST':
        consultation.diagnostic = request.form.get('diagnostic')
        consultation.prescription = request.form.get('prescription')
        consultation.notes = request.form.get('notes')
        db.session.commit()
        return redirect(url_for('medecin.view_consultation', id=id))
    
    show_edit = request.args.get('edit', False)
    return render_template('medecin/new_consultation.html', 
                         consultation=consultation, 
                         show_edit=show_edit)

# ========== GESTION ORDONNANCES (قالب واحد) ==========
@medecin_bp.route('/ordonnance/new', methods=['GET', 'POST'])
@medecin_required
def new_ordonnance():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    if request.method == 'POST':
        ordonnance = Ordonnance(
            patient_id=request.form.get('patient_id'),
            medecin_id=medecin.id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%dT%H:%M'),
            medicaments=request.form.get('medicaments'),
            posologie=request.form.get('posologie'),
            duree_traitement=request.form.get('duree_traitement')
        )
        db.session.add(ordonnance)
        db.session.commit()
        return redirect(url_for('medecin.view_ordonnance', id=ordonnance.id))
    
    patients = Patient.query.all()
    return render_template('medecin/new_ordonnance.html', 
                         patients=patients, 
                         now=datetime.now().strftime('%Y-%m-%dT%H:%M'))

@medecin_bp.route('/ordonnance/<int:id>', methods=['GET', 'POST'])
@medecin_required
def view_ordonnance(id):
    ordonnance = Ordonnance.query.get_or_404(id)
    medecin = get_current_medecin()
    
    if ordonnance.medecin_id != medecin.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    if request.method == 'POST':
        ordonnance.medicaments = request.form.get('medicaments')
        ordonnance.posologie = request.form.get('posologie')
        ordonnance.duree_traitement = request.form.get('duree_traitement')
        db.session.commit()
        return redirect(url_for('medecin.view_ordonnance', id=id))
    
    show_form = request.args.get('edit', False)
    return render_template('medecin/new_ordonnance.html', 
                         ordonnance=ordonnance, 
                         show_form=show_form)

@medecin_bp.route('/ordonnance/print/<int:id>')
def print_ordonnance(id):
    ordonnance = Ordonnance.query.get_or_404(id)
    medecin = get_current_medecin()
    
    if ordonnance.medecin_id != medecin.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    # قالب طباعة مستقل بدون أزرار
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Ordonnance Médicale</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body {{ font-family: Arial, sans-serif; padding: 40px; margin: 0; }}
            .ordonnance {{ max-width: 700px; margin: 0 auto; border: 1px solid #ccc; padding: 30px; border-radius: 10px; }}
            .header {{ text-align: center; border-bottom: 2px solid #27ae60; padding-bottom: 15px; margin-bottom: 20px; }}
            .medecin {{ margin-bottom: 20px; }}
            .patient {{ margin-bottom: 20px; }}
            .medicaments {{ margin: 20px 0; }}
            .signature {{ margin-top: 50px; text-align: right; }}
            @media print {{
                body {{ padding: 0; }}
                .no-print {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="ordonnance">
            <div class="header">
                <h1><i class="fas fa-heartbeat text-primary mr-2"></i>Clinique Les Jumeaux</h1>
                <p>Aïn Defla | Tel: 0697 21 32 42</p>
            </div>
            <div class="medecin">
                <strong>Dr. {medecin.nom}</strong><br>
                {medecin.specialite}
            </div>
            <div class="patient">
                <strong>Patient:</strong> {ordonnance.patient.nom} {ordonnance.patient.prenom}<br>
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
        </div>
        <div class="no-print" style="text-align:center; margin-top:20px;">
            <button onclick="window.print()"><i class="fas fa-print mr-1"></i> Imprimer</button>
        </div>
    </body>
    </html>
    """
    return html

@medecin_bp.route('/consultation/print/<int:id>')
def print_consultation(id):
    consultation = Consultation.query.get_or_404(id)
    medecin = get_current_medecin()
    
    if consultation.medecin_id != medecin.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Consultation Médicale</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body {{ font-family: Arial, sans-serif; padding: 40px; margin: 0; }}
            .consultation {{ max-width: 700px; margin: 0 auto; border: 1px solid #ccc; padding: 30px; border-radius: 10px; }}
            .header {{ text-align: center; border-bottom: 2px solid #27ae60; padding-bottom: 15px; margin-bottom: 20px; }}
            .info {{ margin-bottom: 20px; }}
            .diagnostic {{ background: #f0f7ff; padding: 15px; margin: 15px 0; border-radius: 8px; }}
            .prescription {{ background: #f0fff0; padding: 15px; margin: 15px 0; border-radius: 8px; }}
            @media print {{ body {{ padding: 0; }} }}
        </style>
    </head>
    <body>
        <div class="consultation">
            <div class="header">
                <h1><i class="fas fa-heartbeat text-primary mr-2"></i>Clinique Les Jumeaux</h1>
                <p>Aïn Defla | Tel: 0697 21 32 42</p>
            </div>
            <div class="info">
                <p><strong>Patient:</strong> {consultation.patient.nom} {consultation.patient.prenom}</p>
                <p><strong>Médecin:</strong> Dr. {medecin.nom} - {medecin.specialite}</p>
                <p><strong>Date:</strong> {consultation.date.strftime('%d/%m/%Y à %H:%M') if consultation.date else '-'}</p>
            </div>
            <div class="diagnostic">
                <h3><i class="fas fa-stethoscope mr-1"></i> Diagnostic</h3>
                <p>{consultation.diagnostic or 'Non spécifié'}</p>
            </div>
            <div class="prescription">
                <h3><i class="fas fa-pills mr-1"></i> Prescription</h3>
                <div style="white-space: pre-line;">{consultation.prescription or 'Non spécifiée'}</div>
            </div>
            {f'<div class="notes"><strong>Notes:</strong><br>{consultation.notes}</div>' if consultation.notes else ''}
        </div>
        <div class="no-print" style="text-align:center; margin-top:20px;">
            <button onclick="window.print()"><i class="fas fa-print mr-1"></i> Imprimer</button>
        </div>
    </body>
    </html>
    """
    return html

# ========== LISTES ==========
@medecin_bp.route('/consultations')
@medecin_required
def consultations():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    consultations = Consultation.query.filter_by(medecin_id=medecin.id).order_by(Consultation.date.desc()).all()
    return render_template('medecin/consultations.html', consultations=consultations)

@medecin_bp.route('/ordonnances')
@medecin_required
def ordonnances():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    ordonnances = Ordonnance.query.filter_by(medecin_id=medecin.id).order_by(Ordonnance.date.desc()).all()
    return render_template('medecin/ordonnances.html', ordonnances=ordonnances)

@medecin_bp.route('/rendezvous')
@medecin_required
def rendezvous():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    rendezvous = RendezVous.query.filter_by(medecin_id=medecin.id).order_by(RendezVous.date_rendezvous).all()
    
    total = len(rendezvous)
    en_attente = len([r for r in rendezvous if r.statut == 'en_attente'])
    confirme = len([r for r in rendezvous if r.statut == 'confirme'])
    annule = len([r for r in rendezvous if r.statut == 'annule'])
    
    return render_template('medecin/rendezvous.html',
                         rendezvous=rendezvous,
                         total=total,
                         en_attente=en_attente,
                         confirme=confirme,
                         annule=annule)

# ========== DOSSIER PATIENT ==========
@medecin_bp.route('/patient/<int:id>/dossier')
@medecin_required
def patient_dossier(id):
    medecin = get_current_medecin()
    patient = Patient.query.get_or_404(id)
    
    consultations = Consultation.query.filter_by(patient_id=id, medecin_id=medecin.id).all()
    if not consultations:
        return render_template('error.html', message="Ce patient n'est pas votre patient"), 403
    
    return render_template('medecin/patient_dossier.html', patient=patient)

# ========== API ROUTES ==========
@medecin_bp.route('/api/consultations', methods=['POST'])
@medecin_required
def api_create_consultation():
    data = request.json
    medecin = get_current_medecin()
    
    try:
        consultation = Consultation(
            patient_id=data['patient_id'],
            medecin_id=medecin.id,
            date=datetime.strptime(data['date'], '%Y-%m-%dT%H:%M'),
            diagnostic=data.get('diagnostic', ''),
            prescription=data.get('prescription', ''),
            notes=data.get('notes', '')
        )
        db.session.add(consultation)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Consultation créée avec succès'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@medecin_bp.route('/api/ordonnances', methods=['POST'])
@medecin_required
def api_create_ordonnance():
    data = request.json
    medecin = get_current_medecin()
    
    try:
        ordonnance = Ordonnance(
            patient_id=data['patient_id'],
            medecin_id=medecin.id,
            date=datetime.strptime(data['date'], '%Y-%m-%dT%H:%M'),
            medicaments=data.get('medicaments', ''),
            posologie=data.get('posologie', ''),
            duree_traitement=data.get('duree_traitement', '')
        )
        db.session.add(ordonnance)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Ordonnance créée avec succès'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@medecin_bp.route('/api/rendezvous/<int:id>', methods=['PUT'])
@medecin_required
def api_update_rendezvous(id):
    data = request.json
    medecin = get_current_medecin()
    
    rdv = RendezVous.query.get_or_404(id)
    if rdv.medecin_id != medecin.id:
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    if 'statut' in data:
        rdv.statut = data['statut']
    if 'date_rendezvous' in data:
        rdv.date_rendezvous = datetime.strptime(data['date_rendezvous'], '%Y-%m-%dT%H:%M')
    
    db.session.commit()
    return jsonify({'success': True})