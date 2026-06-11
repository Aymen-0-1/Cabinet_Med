from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps
from models.database import db, Utilisateur, Patient, Medecin, RendezVous, Facture
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash

secretaire_bp = Blueprint('secretaire', __name__, url_prefix='/secretaire')

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

def secretaire_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'secretaire':
            return render_template('error.html', message="Accès non autorisé"), 403
        return f(*args, **kwargs)
    return decorated_function

# ========== PAGES PRINCIPALES ==========
from datetime import datetime
import pytz  # إذا كنت تستخدم timezone

@secretaire_bp.route('/dashboard')
@secretaire_required
def dashboard():
    total_patients = Patient.query.count()
    
    # ✅ استخدم نفس تنسيق التاريخ المخزن في قاعدة البيانات
    now = datetime.now()
    
    # ✅ للتصحيح: طبع التاريخ الحالي
    print(f"📅 Date actuelle (backend): {now}")
    
    total_rendezvous = RendezVous.query.filter(
        RendezVous.date_rendezvous >= now
    ).count()
    
    factures_attente = Facture.query.filter(Facture.statut != 'paye').count()
    
    # ✅ جلب المواعيد القادمة
    rendezvous = RendezVous.query.filter(
        RendezVous.date_rendezvous >= now
    ).order_by(
        RendezVous.date_rendezvous
    ).all()  # ✅ جلب الكل للتصحيح، ثم نحدد 10 فقط في Template
    
    # ✅ للتصحيح: طبع عدد المواعيد القادمة
    print(f"📅 Nombre de RDV futurs: {len(rendezvous)}")
    for rdv in rendezvous:
        print(f"   - RDV {rdv.id}: {rdv.date_rendezvous} (patient: {rdv.patient.nom if rdv.patient else '?'})")
    
    return render_template('secretaire/dashboard.html',
                         total_patients=total_patients,
                         total_rendezvous=total_rendezvous,
                         factures_attente=factures_attente,
                         rendezvous=rendezvous[:10])  # ✅ 10 فقط في Template

@secretaire_bp.route('/patients')
@secretaire_required
def patients():
    patients = Patient.query.order_by(Patient.date_creation.desc()).all()
    medecins = Medecin.query.all()
    return render_template('secretaire/patients.html', patients=patients, medecins=medecins)

@secretaire_bp.route('/rendezvous')
@secretaire_required
def rendezvous():
    rendezvous = RendezVous.query.order_by(RendezVous.date_rendezvous).all()
    medecins = Medecin.query.all()
    patients = Patient.query.all()
    
    total = len(rendezvous)
    en_attente = len([r for r in rendezvous if r.statut == 'en_attente'])
    confirme = len([r for r in rendezvous if r.statut == 'confirme'])
    annule = len([r for r in rendezvous if r.statut == 'annule'])
    
    return render_template('secretaire/rendezvous.html',
                         rendezvous=rendezvous,
                         medecins=medecins,
                         all_patients=patients,
                         total=total,
                         en_attente=en_attente,
                         confirme=confirme,
                         annule=annule)

@secretaire_bp.route('/factures')
@secretaire_required
def factures():
    factures = Facture.query.order_by(Facture.date.desc()).all()
    patients = Patient.query.all()
    
    total_factures = len(factures)
    total_montant = sum(f.montant for f in factures)
    total_impayee = sum(f.montant - (f.montant_paye or 0) for f in factures if f.statut != 'paye')
    total_payee = sum(f.montant_paye or 0 for f in factures)
    
    return render_template('secretaire/factures.html',
                         factures=factures,
                         all_patients=patients,
                         total_factures=total_factures,
                         total_montant=total_montant,
                         total_impayee=total_impayee,
                         total_payee=total_payee)

# ========== GESTION PATIENTS ==========
@secretaire_bp.route('/patient/<int:id>/dossier')
@secretaire_required
def patient_dossier(id):
    patient = Patient.query.get_or_404(id)
    return render_template('secretaire/patient_dossier.html', patient=patient)

@secretaire_bp.route('/patient/<int:id>/edit', methods=['GET', 'POST'])
@secretaire_required
def edit_patient(id):
    patient = Patient.query.get_or_404(id)
    
    if request.method == 'POST':
        patient.nom = request.form.get('nom', patient.nom)
        patient.prenom = request.form.get('prenom', patient.prenom)
        patient.telephone = request.form.get('telephone', patient.telephone)
        patient.email = request.form.get('email', patient.email)
        patient.adresse = request.form.get('adresse', patient.adresse)
        patient.num_assurance = request.form.get('num_assurance', patient.num_assurance)
        
        if request.form.get('date_naissance'):
            patient.date_naissance = datetime.strptime(request.form.get('date_naissance'), '%Y-%m-%d').date()
        
        db.session.commit()
        return redirect(url_for('secretaire.patient_dossier', id=id))
    
    return render_template('secretaire/patient_edit.html', patient=patient)

# ========== API ROUTES ==========
@secretaire_bp.route('/api/patient/create-account', methods=['POST'])
@secretaire_required
def api_create_patient_account():
    data = request.json
    patient_id = data.get('patient_id')
    email = data.get('email')
    password = data.get('password')
    
    patient = Patient.query.get_or_404(patient_id)
    
    existing = Utilisateur.query.filter_by(email=email).first()
    if existing:
        return jsonify({'success': False, 'message': 'Email déjà utilisé'}), 400
    
    hashed = generate_password_hash(password)
    
    user = Utilisateur(
        email=email,
        password=hashed,
        role='patient',
        nom=patient.nom,
        prenom=patient.prenom,
        telephone=patient.telephone,
        adresse=patient.adresse
    )
    db.session.add(user)
    db.session.flush()
    
    patient.user_id = user.id
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Compte patient créé avec succès'})

@secretaire_bp.route('/api/patients/<int:id>', methods=['DELETE'])
@secretaire_required
def api_delete_patient(id):
    patient = Patient.query.get_or_404(id)
    
    if patient.user_id:
        user = Utilisateur.query.get(patient.user_id)
        if user:
            db.session.delete(user)
    
    db.session.delete(patient)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Patient supprimé avec succès'})

# ========== API RENDEZ-VOUS ==========
@secretaire_bp.route('/api/rendezvous', methods=['POST'])
@secretaire_required
def api_create_rendezvous():
    data = request.json
    
    try:
        date_rdv = datetime.strptime(data['date_rendezvous'], '%Y-%m-%dT%H:%M')
        
        # ✅ التحقق من التاريخ في الماضي
        if date_rdv < datetime.now():
            return jsonify({'success': False, 'message': 'Impossible de prendre un rendez-vous dans le passé'}), 400
        
        # ✅ التحقق فقط من توفر نفس الطبيب في نفس الوقت (وليس كل الأطباء)
        existing = RendezVous.query.filter_by(
            medecin_id=data['medecin_id'],
            date_rendezvous=date_rdv,
            statut='confirme'
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Ce médecin est déjà occupé à cet horaire'}), 400
        
        # ✅ التحقق من عدم وجود موعد معلق لنفس الطبيب في نفس الوقت
        pending = RendezVous.query.filter_by(
            medecin_id=data['medecin_id'],
            date_rendezvous=date_rdv,
            statut='en_attente'
        ).first()
        
        if pending:
            return jsonify({'success': False, 'message': 'Un rendez-vous en attente existe déjà pour ce médecin à cet horaire'}), 400
        
        # إنشاء الموعد
        rdv = RendezVous(
            patient_id=data['patient_id'],
            medecin_id=data['medecin_id'],
            date_rendezvous=date_rdv,
            motif=data.get('motif', ''),
            statut='en_attente'
        )
        db.session.add(rdv)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Rendez-vous créé avec succès'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@secretaire_bp.route('/api/rendezvous/booked', methods=['GET'])
@secretaire_required
def get_booked_slots():
    medecin_id = request.args.get('medecin_id')
    date = request.args.get('date')
    
    if not medecin_id or not date:
        return jsonify({'booked_slots': []})
    
    # جلب جميع المواعيد المؤكدة والمعلقة لهذا الطبيب في هذا التاريخ
    rendezvous = RendezVous.query.filter(
        RendezVous.medecin_id == medecin_id,
        RendezVous.date_rendezvous.between(f"{date} 00:00:00", f"{date} 23:59:59"),
        RendezVous.statut.in_(['confirme', 'en_attente'])
    ).all()
    
    booked_slots = [rdv.date_rendezvous.strftime('%H:%M') for rdv in rendezvous]
    
    return jsonify({'booked_slots': booked_slots})
    
@secretaire_bp.route('/api/rendezvous/<int:id>', methods=['PUT'])
@secretaire_required
def api_update_rendezvous(id):
    data = request.json
    rdv = RendezVous.query.get_or_404(id)
    
    if 'date_rendezvous' in data:
        new_date = datetime.strptime(data['date_rendezvous'], '%Y-%m-%dT%H:%M')
        new_medecin_id = data.get('medecin_id', rdv.medecin_id)
        
        # ✅ التحقق من عدم وجود تعارض (مع استثناء الموعد الحالي)
        existing = RendezVous.query.filter(
            RendezVous.medecin_id == new_medecin_id,
            RendezVous.date_rendezvous == new_date,
            RendezVous.id != id
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Ce créneau est déjà pris'}), 400
        
        rdv.date_rendezvous = new_date
        rdv.medecin_id = new_medecin_id
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Rendez-vous modifié avec succès'})

@secretaire_bp.route('/api/rendezvous/<int:id>/status', methods=['PUT'])
@secretaire_required
def api_update_rendezvous_status(id):
    data = request.json
    rdv = RendezVous.query.get_or_404(id)
    rdv.statut = data.get('statut', rdv.statut)
    db.session.commit()
    return jsonify({'success': True})

@secretaire_bp.route('/api/rendezvous/<int:id>', methods=['DELETE'])
@secretaire_required
def api_delete_rendezvous(id):
    rdv = RendezVous.query.get_or_404(id)
    db.session.delete(rdv)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Rendez-vous supprimé avec succès'})

# ========== API FACTURES ==========
@secretaire_bp.route('/api/factures', methods=['POST'])
@secretaire_required
def api_create_facture():
    data = request.json
    
    facture = Facture(
        patient_id=data['patient_id'],
        numero=data['numero'],
        date=datetime.strptime(data['date'], '%Y-%m-%d'),
        montant=data['montant'],
        description=data.get('description', ''),
        statut='en_attente',
        montant_paye=0,
        montant_restant=data['montant']
    )
    db.session.add(facture)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Facture créée avec succès'})

@secretaire_bp.route('/api/factures/<int:id>/paiement', methods=['POST'])
@secretaire_required
def api_enregistrer_paiement(id):
    data = request.json
    facture = Facture.query.get_or_404(id)
    montant = data.get('montant', 0)
    
    if montant <= 0:
        return jsonify({'success': False, 'message': 'Montant invalide'}), 400
    
    nouveau_paye = (facture.montant_paye or 0) + montant
    
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

@secretaire_bp.route('/api/factures/<int:id>', methods=['DELETE'])
@secretaire_required
def api_delete_facture(id):
    facture = Facture.query.get_or_404(id)
    db.session.delete(facture)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Facture supprimée avec succès'})

@secretaire_bp.route('/facture/print/<int:id>')
@secretaire_required
def print_facture(id):
    facture = Facture.query.get_or_404(id)
    patient = Patient.query.get(facture.patient_id)
    
    reste = facture.montant - (facture.montant_paye or 0)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Facture N° {facture.numero}</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #e8ecef;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                padding: 20px;
            }}
            .facture {{
                width: 600px;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #0D9488 0%, #0F766E 100%);
                color: white;
                text-align: center;
                padding: 20px 16px;
            }}
            .header h1 {{ font-size: 18px; font-weight: bold; margin-bottom: 4px; }}
            .header p {{ font-size: 11px; opacity: 0.85; margin: 2px 0; }}
            .header .subtitle {{
                margin-top: 10px;
                padding-top: 8px;
                border-top: 1px solid rgba(255,255,255,0.2);
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 2px;
            }}
            .info-section {{ padding: 16px 16px 8px 16px; }}
            .info-row {{
                display: flex;
                align-items: flex-start;
                gap: 12px;
                margin-bottom: 14px;
            }}
            .info-icon {{
                width: 28px;
                height: 28px;
                background: #E6FFFA;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .info-icon i {{ font-size: 12px; color: #0D9488; }}
            .info-label {{ font-size: 9px; color: #94A3B8; text-transform: uppercase; margin-bottom: 2px; }}
            .info-value {{ font-size: 13px; font-weight: 600; color: #1E293B; }}
            .montant-section {{ padding: 16px; background: #F0FDF9; margin: 8px 16px; border-radius: 8px; text-align: center; }}
            .montant {{ font-size: 24px; font-weight: bold; color: #0D9488; }}
            .description {{ padding: 8px 16px; font-size: 11px; color: #64748B; text-align: center; }}
            .footer {{ background: #F8FAFC; padding: 14px 16px; border-top: 1px solid #E2E8F0; text-align: center; }}
            .footer p {{ font-size: 9px; color: #64748B; }}
            .btn-print {{ text-align: center; margin-top: 15px; }}
            .btn-print button {{ background: #0D9488; color: white; border: none; padding: 8px 24px; border-radius: 6px; font-size: 12px; cursor: pointer; }}
            @media print {{
                body {{ background: white; padding: 0; }}
                .facture {{ box-shadow: none; width: 100%; }}
                .btn-print {{ display: none; }}
                .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            }}
        </style>
    </head>
    <body>
        <div class="facture">
            <div class="header">
                <h1>CLINIQUE LES JUMEAUX</h1>
                <p>Aïn Defla, Algérie</p>
                <p>Tel: 0697 21 32 42</p>
                <div class="subtitle">FACTURE</div>
            </div>
            
            <div class="info-section">
                <div class="info-row">
                    <div class="info-icon"><i class="fas fa-receipt"></i></div>
                    <div class="info-content">
                        <div class="info-label">N° Facture</div>
                        <div class="info-value">{facture.numero}</div>
                    </div>
                </div>
                <div class="info-row">
                    <div class="info-icon"><i class="fas fa-calendar-alt"></i></div>
                    <div class="info-content">
                        <div class="info-label">Date</div>
                        <div class="info-value">{facture.date.strftime('%d/%m/%Y') if facture.date else '-'}</div>
                    </div>
                </div>
                <div class="info-row">
                    <div class="info-icon"><i class="fas fa-user"></i></div>
                    <div class="info-content">
                        <div class="info-label">Patient</div>
                        <div class="info-value">{patient.nom} {patient.prenom}</div>
                    </div>
                </div>
            </div>
            
            <div class="montant-section">
                <div class="montant">{facture.montant} DA</div>
                {f'<div style="font-size: 11px; margin-top: 5px;">Déjà payé: {facture.montant_paye} DA</div>' if facture.montant_paye else ''}
                {f'<div style="font-size: 11px; color: #DC2626;">Reste: {reste} DA</div>' if reste > 0 else '<div style="font-size: 11px; color: #0D9488;">✓ Payée</div>'}
            </div>
            
            {f'<div class="description">{facture.description}</div>' if facture.description else ''}
            
            <div class="footer">
                <p>Merci de votre confiance</p>
                <p>Clinique Les Jumeaux - Votre santé, notre priorité</p>
            </div>
        </div>
        
        <div class="btn-print">
            <button onclick="window.print()"><i class="fas fa-print mr-1"></i> Imprimer la facture</button>
        </div>
    </body>
    </html>
    """
    return html

# ========== API LISTS ==========
@secretaire_bp.route('/api/patients/list')
@secretaire_required
def api_patients_list():
    patients = Patient.query.all()
    return jsonify([{'id': p.id, 'nom': p.nom, 'prenom': p.prenom, 'telephone': p.telephone} for p in patients])

@secretaire_bp.route('/api/medecins/list')
@secretaire_required
def api_medecins_list():
    medecins = Medecin.query.all()
    return jsonify([{'id': m.id, 'nom': m.nom, 'specialite': m.specialite} for m in medecins])

@secretaire_bp.route('/debug/check')
def debug_check():
    from datetime import datetime
    rendezvous = RendezVous.query.filter(RendezVous.date_rendezvous >= datetime.now()).all()
    
    result = {
        'count': len(rendezvous),
        'rendezvous': []
    }
    
    for rdv in rendezvous:
        result['rendezvous'].append({
            'id': rdv.id,
            'date': str(rdv.date_rendezvous),
            'statut': rdv.statut,
            'has_patient': rdv.patient is not None,
            'patient_name': f"{rdv.patient.nom} {rdv.patient.prenom}" if rdv.patient else None,
            'has_medecin': rdv.medecin is not None,
            'medecin_name': rdv.medecin.nom if rdv.medecin else None
        })
    
    return jsonify(result)