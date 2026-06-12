from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps
from models.database import Medecin, db, Utilisateur, Patient, RendezVous, Consultation, Ordonnance, Facture, Examen, DossierMedical
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
    
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
     # ✅ تأكد من أن session متزامنة مع قاعدة البيانات
    user = Utilisateur.query.get(session['user_id'])
    if user:
        session['nom'] = user.nom
        session['prenom'] = user.prenom

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
        # Récupérer les nouvelles valeurs
        nouveau_nom = request.form.get('nom')
        nouveau_prenom = request.form.get('prenom')
        nouveau_telephone = request.form.get('telephone')
        nouvel_email = request.form.get('email')
        nouvelle_adresse = request.form.get('adresse')
        patient.allergies = request.form.get('allergies', '')
        patient.chronic_diseases = request.form.get('chronic_diseases', '')
        patient.current_medications = request.form.get('current_medications', '')
        
        # ✅ Mettre à jour patient ET user
        if nouveau_nom:
            patient.nom = nouveau_nom
            user.nom = nouveau_nom
        
        if nouveau_prenom:
            patient.prenom = nouveau_prenom
            user.prenom = nouveau_prenom
        
        if nouveau_telephone:
            patient.telephone = nouveau_telephone
            user.telephone = nouveau_telephone
        
        # ✅ ✅ ✅ TRÈS IMPORTANT: Mettre à jour l'email dans les deux tables
        if nouvel_email:
            patient.email = nouvel_email
            user.email = nouvel_email   # ← C'est ce qui manquait!
            print(f"✅ Email mis à jour: {user.email}")
        
        if nouvelle_adresse:
            patient.adresse = nouvelle_adresse
            user.adresse = nouvelle_adresse
        
        # Date de naissance
        if request.form.get('date_naissance'):
            patient.date_naissance = datetime.strptime(request.form.get('date_naissance'), '%Y-%m-%d').date()
        
        patient.num_assurance = request.form.get('num_assurance', patient.num_assurance)
        
        # Mettre à jour la session
        session['nom'] = user.nom
        session['prenom'] = user.prenom
        session['telephone'] = user.telephone
        session['email'] = user.email  # ← Mettre à jour l'email dans la session
        session['adresse'] = user.adresse
        
        # Changer le mot de passe
        new_password = request.form.get('new_password')
        if new_password:
            current_password = request.form.get('current_password')
            from werkzeug.security import check_password_hash, generate_password_hash
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

@patient_bp.route('/api/booked-slots', methods=['GET'])
@patient_required
def get_booked_slots():
    """Récupère les créneaux déjà réservés pour un médecin et une date donnés"""
    medecin_id = request.args.get('medecin_id')
    date = request.args.get('date')
    
    if not medecin_id or not date:
        return jsonify({'booked_slots': []})
    
    from models.database import RendezVous
    
    # جلب جميع المواعيد المؤكدة والمعلقة لهذا الطبيب في هذا التاريخ
    rendezvous = RendezVous.query.filter(
        RendezVous.medecin_id == medecin_id,
        RendezVous.date_rendezvous.between(f"{date} 00:00:00", f"{date} 23:59:59"),
        RendezVous.statut.in_(['confirme', 'en_attente'])
    ).all()
    
    booked_slots = [rdv.date_rendezvous.strftime('%H:%M') for rdv in rendezvous]
    
    return jsonify({'booked_slots': booked_slots})

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

def _generate_medicaments_table(medicaments, posologie, duree):
    """Génère le HTML du tableau des médicaments"""
    if not medicaments:
        return '<tr><td colspan="4" style="text-align:center; padding:20px; color:#94A3B8;">Aucun médicament prescrit</td></tr>'
    
    lignes = medicaments.split('\n')
    posologie_lignes = posologie.split('\n') if posologie else []
    html_rows = ""
    
    for idx, ligne in enumerate(lignes):
        if not ligne.strip():
            continue
        
        # Extraction du nom et dosage
        parts = ligne.split(',')
        nom = parts[0].strip() if parts else ligne
        dosage = parts[1].strip() if len(parts) > 1 else "---"
        
        # Posologie correspondante
        poso = posologie_lignes[idx] if idx < len(posologie_lignes) else (posologie[:40] if posologie else "---")
        
        html_rows += f"""
        <tr>
            <td>{nom}</td>
            <td>{dosage}</td>
            <td>{poso}</td>
            <td>{duree or '---'}</td>
        </tr>
        """
    
    return html_rows

def _generate_posologie_box(posologie):
    """Génère le HTML de la posologie détaillée"""
    if not posologie or len(posologie) <= 30:
        return ""
    
    return f"""
    <div class="posologie-box">
        <p><i class="fas fa-info-circle"></i> Posologie et instructions</p>
        <div>{posologie}</div>
    </div>
    """

@patient_bp.route('/ordonnance/print/<int:id>')
@patient_required
def print_ordonnance(id):
    ordonnance = Ordonnance.query.get_or_404(id)
    
    # ✅ استخدم get_current_patient() بدلاً من session
    patient = get_current_patient()
    
    # ✅ Vérification
    if not patient:
        return "Patient non trouvé", 404
    
    if ordonnance.patient_id != patient.id:
        return "Accès non autorisé", 403
    
    # ✅ جلب معلومات الطبيب
    from models.database import Medecin
    medecin = Medecin.query.get(ordonnance.medecin_id)
    
    if medecin:
        medecin_nom = medecin.nom
        medecin_specialite = medecin.specialite
    else:
        medecin_nom = "Médecin"
        medecin_specialite = "Généraliste"
    
    # ✅ بناء HTML للطباعة
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Ordonnance Médicale</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #e8ecef;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }}
            
            .ordonnance {{
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
            
            .header h1 {{
                font-size: 18px;
                font-weight: bold;
                letter-spacing: 1px;
                margin-bottom: 4px;
            }}
            
            .header p {{
                font-size: 11px;
                opacity: 0.85;
                margin: 2px 0;
            }}
            
            .header .subtitle {{
                margin-top: 10px;
                padding-top: 8px;
                border-top: 1px solid rgba(255,255,255,0.2);
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 2px;
            }}
            
            .info-section {{
                padding: 16px 16px 8px 16px;
            }}
            
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
                flex-shrink: 0;
            }}
            
            .info-icon i {{
                font-size: 12px;
                color: #0D9488;
            }}
            
            .info-content {{
                flex: 1;
            }}
            
            .info-label {{
                font-size: 9px;
                color: #94A3B8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 2px;
            }}
            
            .info-value {{
                font-size: 13px;
                font-weight: 600;
                color: #1E293B;
            }}
            
            .info-sub {{
                font-size: 11px;
                color: #0D9488;
                margin-top: 2px;
            }}
            
            .info-meta {{
                display: flex;
                gap: 12px;
                margin-top: 4px;
                font-size: 10px;
                color: #64748B;
            }}
            
            .medicaments-section {{
                padding: 8px 16px 16px 16px;
            }}
            
            .section-title {{
                font-size: 12px;
                font-weight: 600;
                color: #0F766E;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            
            .section-title i {{
                font-size: 12px;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 11px;
            }}
            
            th {{
                background: #F0FDF9;
                padding: 8px 6px;
                text-align: left;
                font-weight: 600;
                color: #0F766E;
                border-bottom: 1px solid #CCFBF1;
            }}
            
            td {{
                padding: 6px;
                border-bottom: 1px solid #F1F5F9;
                color: #334155;
            }}
            
            .posologie-box {{
                margin: 8px 16px 16px 16px;
                padding: 10px 12px;
                background: #FFFBEB;
                border-left: 3px solid #F59E0B;
                border-radius: 4px;
            }}
            
            .posologie-box p {{
                font-size: 11px;
                color: #78350F;
                margin-bottom: 2px;
                font-weight: 600;
            }}
            
            .posologie-box div {{
                font-size: 11px;
                color: #451A03;
            }}
            
            .footer {{
                background: #F8FAFC;
                padding: 14px 16px;
                border-top: 1px solid #E2E8F0;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 10px;
            }}
            
            .signature {{
                text-align: center;
            }}
            
            .signature-line {{
                width: 130px;
                border-top: 1px dashed #94A3B8;
                margin-bottom: 4px;
            }}
            
            .signature-text {{
                font-size: 9px;
                color: #64748B;
            }}
            
            .mention {{
                text-align: center;
                font-size: 8px;
                color: #94A3B8;
                padding: 8px 16px;
                border-top: 1px solid #E2E8F0;
                background: white;
            }}
            
            .btn-print {{
                text-align: center;
                padding: 12px;
                background: #F8FAFC;
            }}
            
            .btn-print button {{
                background: #0D9488;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 6px;
                font-size: 12px;
                cursor: pointer;
            }}
            
            @media print {{
                body {{
                    background: white;
                    padding: 0;
                    margin: 0;
                }}
                .ordonnance {{
                    box-shadow: none;
                    width: 100%;
                }}
                .btn-print {{
                    text-align: center;
                    margin-top: 15px;
                    clear: both;  /* منع الالتصاق */
                }}
                .header {{
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
                th {{
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="ordonnance">
            <div class="header">
                <h1>CLINIQUE LES JUMEAUX</h1>
                <p>Aïn Defla, Algérie</p>
                <p>Tel: 0697 21 32 42</p>
                <div class="subtitle">ORDONNANCE MEDICALE</div>
            </div>
            
            <div class="info-section">
                <div class="info-row">
                    <div class="info-icon">
                        <i class="fas fa-user-md"></i>
                    </div>
                    <div class="info-content">
                        <div class="info-label">Médecin prescripteur</div>
                        <div class="info-value">Dr. {medecin.nom}</div>
                        <div class="info-sub">{medecin.specialite}</div>
                    </div>
                </div>
                
                <div class="info-row">
                    <div class="info-icon">
                        <i class="fas fa-user"></i>
                    </div>
                    <div class="info-content">
                        <div class="info-label">Patient</div>
                        <div class="info-value">{ordonnance.patient.nom} {ordonnance.patient.prenom}</div>
                        <div class="info-meta">
                            <span><i class="fas fa-calendar-alt"></i> {ordonnance.date.strftime('%d/%m/%Y') if ordonnance.date else '-'}</span>
                            <span><i class="fas fa-id-card"></i> N° {ordonnance.patient.id}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="medicaments-section">
                <div class="section-title">
                    <i class="fas fa-pills"></i> Prescription médicale
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Médicament</th>
                            <th>Dosage</th>
                            <th>Posologie</th>
                            <th>Durée</th>
                        </tr>
                    </thead>
                    <tbody>
                        {_generate_medicaments_table(ordonnance.medicaments, ordonnance.posologie, ordonnance.duree_traitement)}
                    </tbody>
                </table>
            </div>
            
            {_generate_posologie_box(ordonnance.posologie) if ordonnance.posologie and len(ordonnance.posologie) > 30 else ''}
            
            <div class="footer">
                <div class="signature">
                    <div class="signature-line"></div>
                    <div class="signature-text">Signature du médecin</div>
                </div>
                <div class="signature">
                    <div class="signature-line"></div>
                    <div class="signature-text">Cachet de la clinique</div>
                </div>
            </div>
            
            <div class="mention">
                Valable 3 mois - Clinique Les Jumeaux - Votre santé, notre priorité
            </div>
        </div>
        <div class="btn-print" style="text-align: center; margin-top: 15px;">
            <button onclick="window.print()" style="background: #0D9488; color: white; border: none; padding: 8px 24px; border-radius: 6px; font-size: 12px; cursor: pointer;">
                <i class="fas fa-print mr-1"></i> Imprimer l'ordonnance
            </button>
        </div>
    </body>
    </html>
    """
    return html

@patient_bp.route('/consultation/print/<int:id>')
@patient_required
def print_consultation(id):
    consultation = Consultation.query.get_or_404(id)
    patient = get_current_patient()
    
    if not patient:
        return "Patient non trouvé", 404
    
    if consultation.patient_id != patient.id:
        return "Accès non autorisé", 403
    
    medecin = Medecin.query.get(consultation.medecin_id)
    medecin_nom = medecin.nom if medecin else "Médecin"
    medecin_specialite = medecin.specialite if medecin else "Généraliste"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Consultation Médicale</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
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
            
            .consultation {{
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
            
            .header h1 {{
                font-size: 18px;
                font-weight: bold;
                letter-spacing: 1px;
                margin-bottom: 4px;
            }}
            
            .header p {{
                font-size: 11px;
                opacity: 0.85;
                margin: 2px 0;
            }}
            
            .header .subtitle {{
                margin-top: 10px;
                padding-top: 8px;
                border-top: 1px solid rgba(255,255,255,0.2);
                font-size: 11px;
                font-weight: 500;
                letter-spacing: 2px;
            }}
            
            .info-section {{
                padding: 16px 16px 8px 16px;
            }}
            
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
                flex-shrink: 0;
            }}
            
            .info-icon i {{
                font-size: 12px;
                color: #0D9488;
            }}
            
            .info-content {{
                flex: 1;
            }}
            
            .info-label {{
                font-size: 9px;
                color: #94A3B8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 2px;
            }}
            
            .info-value {{
                font-size: 13px;
                font-weight: 600;
                color: #1E293B;
            }}
            
            .info-sub {{
                font-size: 11px;
                color: #0D9488;
                margin-top: 2px;
            }}
            
            .info-meta {{
                display: flex;
                gap: 12px;
                margin-top: 4px;
                font-size: 10px;
                color: #64748B;
            }}
            
            .content-section {{
                padding: 8px 16px 16px 16px;
            }}
            
            .section-title {{
                font-size: 12px;
                font-weight: 600;
                color: #0F766E;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            
            .section-title i {{
                font-size: 12px;
            }}
            
            .diagnostic-box {{
                background: #F0F9FF;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 16px;
                border-left: 3px solid #3B82F6;
            }}
            
            .diagnostic-box p {{
                font-size: 11px;
                color: #1E3A5F;
                margin-bottom: 6px;
                font-weight: 600;
            }}
            
            .diagnostic-box div {{
                font-size: 11px;
                color: #1E293B;
            }}
            
            .prescription-box {{
                background: #F0FDF4;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 16px;
                border-left: 3px solid #22C55E;
            }}
            
            .prescription-box p {{
                font-size: 11px;
                color: #14532D;
                margin-bottom: 6px;
                font-weight: 600;
            }}
            
            .prescription-box div {{
                font-size: 11px;
                color: #1E293B;
                white-space: pre-line;
            }}
            
            .notes-box {{
                background: #FEF3C7;
                padding: 12px;
                border-radius: 8px;
                margin-top: 8px;
                border-left: 3px solid #F59E0B;
            }}
            
            .notes-box p {{
                font-size: 11px;
                color: #78350F;
                margin-bottom: 6px;
                font-weight: 600;
            }}
            
            .notes-box div {{
                font-size: 11px;
                color: #451A03;
            }}
            
            .footer {{
                background: #F8FAFC;
                padding: 14px 16px;
                border-top: 1px solid #E2E8F0;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 10px;
            }}
            
            .signature {{
                text-align: center;
            }}
            
            .signature-line {{
                width: 130px;
                border-top: 1px dashed #94A3B8;
                margin-bottom: 4px;
            }}
            
            .signature-text {{
                font-size: 9px;
                color: #64748B;
            }}
            
            .mention {{
                text-align: center;
                font-size: 8px;
                color: #94A3B8;
                padding: 8px 16px;
                border-top: 1px solid #E2E8F0;
                background: white;
            }}
            
            .btn-print {{
                text-align: center;
                margin-top: 15px;
            }}
            
            .btn-print button {{
                background: #0D9488;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 6px;
                font-size: 12px;
                cursor: pointer;
            }}
            
            @media print {{
                body {{
                    background: white;
                    padding: 0;
                    margin: 0;
                }}
                .consultation {{
                    box-shadow: none;
                    width: 100%;
                }}
                .btn-print {{
                    display: none;
                }}
                .header {{
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
                .diagnostic-box {{
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
                .prescription-box {{
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="consultation">
            <div class="header">
                <h1>CLINIQUE LES JUMEAUX</h1>
                <p>Aïn Defla, Algérie</p>
                <p>Tel: 0697 21 32 42</p>
                <div class="subtitle">COMPTE RENDU DE CONSULTATION</div>
            </div>
            
            <div class="info-section">
                <div class="info-row">
                    <div class="info-icon">
                        <i class="fas fa-user-md"></i>
                    </div>
                    <div class="info-content">
                        <div class="info-label">Médecin traitant</div>
                        <div class="info-value">Dr. {medecin.nom}</div>
                        <div class="info-sub">{medecin.specialite}</div>
                    </div>
                </div>
                
                <div class="info-row">
                    <div class="info-icon">
                        <i class="fas fa-user"></i>
                    </div>
                    <div class="info-content">
                        <div class="info-label">Patient</div>
                        <div class="info-value">{consultation.patient.nom} {consultation.patient.prenom}</div>
                        <div class="info-meta">
                            <span><i class="fas fa-calendar-alt"></i> {consultation.date.strftime('%d/%m/%Y à %H:%M') if consultation.date else '-'}</span>
                            <span><i class="fas fa-id-card"></i> N° {consultation.patient.id}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="content-section">
                <div class="section-title">
                    <i class="fas fa-stethoscope"></i> Examen clinique
                </div>
                
                <div class="diagnostic-box">
                    <p><i class="fas fa-diagnoses"></i> Diagnostic</p>
                    <div>{consultation.diagnostic or 'Non spécifié'}</div>
                </div>
                
                <div class="prescription-box">
                    <p><i class="fas fa-prescription-bottle"></i> Prescription</p>
                    <div>{consultation.prescription or 'Non spécifiée'}</div>
                </div>
                
                {f'''
                <div class="notes-box">
                    <p><i class="fas fa-pencil-alt"></i> Notes complémentaires</p>
                    <div>{consultation.notes}</div>
                </div>
                ''' if consultation.notes else ''}
            </div>
            
            <div class="footer">
                <div class="signature">
                    <div class="signature-line"></div>
                    <div class="signature-text">Signature du médecin</div>
                </div>
                <div class="signature">
                    <div class="signature-line"></div>
                    <div class="signature-text">Cachet de la clinique</div>
                </div>
            </div>
            
            <div class="mention">
                Document médical confidentiel - Clinique Les Jumeaux
            </div>
        </div>
        
        <div class="btn-print">
            <button onclick="window.print()">Imprimer le compte rendu</button>
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