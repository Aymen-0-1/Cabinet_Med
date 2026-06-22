from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from functools import wraps
from models.database import Certificat, db, Utilisateur, Medecin, Patient, RendezVous, Consultation, Ordonnance
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
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    user = Utilisateur.query.get(user_id)
    if not user or user.role != 'medecin':
        return None
    
    if user.medecin_id:
        return Medecin.query.get(user.medecin_id)
    
    return Medecin.query.filter_by(email=user.email).first()

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
    certificats = Certificat.query.filter_by(
        medecin_id=medecin.id
    ).order_by(Certificat.date_emission.desc()).limit(5).all()
    try:
        ordonnances_recentes = Ordonnance.query.filter_by(
            medecin_id=medecin.id
        ).order_by(Ordonnance.created_at.desc()).limit(5).all()
    except AttributeError:
        try:
            ordonnances_recentes = Ordonnance.query.filter_by(
                medecin_id=medecin.id
            ).order_by(Ordonnance.date.desc()).limit(5).all()
        except AttributeError:
            try:
                ordonnances_recentes = Ordonnance.query.filter_by(
                    medecin_id=medecin.id
                ).order_by(Ordonnance.created_date.desc()).limit(5).all()
            except AttributeError:
                ordonnances_recentes = Ordonnance.query.filter_by(
                    medecin_id=medecin.id
                ).order_by(Ordonnance.id.desc()).limit(5).all()
    
    return render_template('medecin/dashboard.html',
                         medecin=medecin,
                         ordonnances_recentes=ordonnances_recentes,
                         total_consultations=total_consultations,
                         total_ordonnances=total_ordonnances,
                         rendezvous=rendezvous,
                         certificats=certificats)

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

# ========== GESTION CONSULTATIONS  ==========
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
    
    patient_id = request.args.get('patient_id', type=int)
    patients = Patient.query.all()
    preselected_patient = None
    if patient_id:
        preselected_patient = Patient.query.get(patient_id)
    
    return render_template('medecin/new_consultation.html', 
                         patients=patients,
                         preselected_patient=preselected_patient,
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

# ========== GESTION ORDONNANCES ==========
@medecin_bp.route('/ordonnance/new', methods=['GET', 'POST'])
@medecin_required
def new_ordonnance():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    from models.medicament_data import MEDICAMENTS_DATA, PRISE_MEDICAMENT
    import json
    
    if request.method == 'POST':
        # Récupérer les médicaments combinés
        medicaments_combined = request.form.get('medicaments_combined', '')
        
        ordonnance = Ordonnance(
            patient_id=request.form.get('patient_id'),
            medecin_id=medecin.id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%dT%H:%M'),
            medicaments=medicaments_combined,
            posologie=request.form.get('posologie', ''),
            duree_traitement=''
        )
        db.session.add(ordonnance)
        db.session.commit()
        return redirect(url_for('medecin.view_ordonnance', id=ordonnance.id))
    
    patients = Patient.query.all()
    medicaments_json = json.dumps({m['nom']: {'dosages': m['dosages']} for m in MEDICAMENTS_DATA})
    
    return render_template('medecin/new_ordonnance.html', 
                         patients=patients, 
                         now=datetime.now().strftime('%Y-%m-%dT%H:%M'),
                         medicaments=MEDICAMENTS_DATA,
                         prises=PRISE_MEDICAMENT,
                         medicaments_json=medicaments_json)

@medecin_bp.route('/ordonnance/<int:id>', methods=['GET', 'POST'])
@medecin_required
def view_ordonnance(id):
    ordonnance = Ordonnance.query.get_or_404(id)
    medecin = get_current_medecin()
    
    if ordonnance.medecin_id != medecin.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    if request.method == 'POST':
        ordonnance.medicaments = request.form.get('medicaments_combined', '')
        ordonnance.posologie = request.form.get('posologie', '')
        ordonnance.duree_traitement = ''
        db.session.commit()
        return redirect(url_for('medecin.view_ordonnance', id=id))
    
    show_form = request.args.get('edit', False)
    
    return render_template('medecin/new_ordonnance.html', 
                         ordonnance=ordonnance,
                         patients=[], 
                         medicaments=[], 
                         medicaments_json={}, 
                         prises=[],   
                         now=ordonnance.date.strftime('%d/%m/%Y') if ordonnance.date else '',
                         show_form=show_form)


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
        
        parts = ligne.split(',')
        nom = parts[0].strip() if parts else ligne
        dosage = parts[1].strip() if len(parts) > 1 else "---"
        
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

def generate_medicaments_table_new(medicaments):
    """Génère le HTML du tableau des médicaments (nouveau format avec |)"""
    if not medicaments:
        return '<tr><td colspan="4" style="text-align:center; padding:20px; color:#94A3B8;">Aucun médicament prescrit</td></tr>'
    
    lignes = medicaments.split('\n')
    html_rows = ""
    
    for ligne in lignes:
        if not ligne.strip():
            continue
        
        parts = ligne.split('|')
        nom = parts[0].strip() if len(parts) > 0 else '-'
        dosage = parts[1].strip() if len(parts) > 1 else '-'
        prise = parts[2].strip() if len(parts) > 2 else '-'
        duree = parts[3].strip() if len(parts) > 3 else '-'
        
        html_rows += f"""
        <tr>
            <td>{nom}</td>
            <td>{dosage}</td>
            <td>{prise}</td>
            <td>{duree}</td>
        </tr>
        """
    
    return html_rows

def generate_posologie_box_new(posologie):
    """Génère le HTML de la posologie détaillée"""
    if not posologie:
        return ""
    
    return f"""
    <div class="posologie-box">
        <p><i class="fas fa-info-circle"></i> Posologie et instructions</p>
        <div>{posologie}</div>
    </div>
    """

@medecin_bp.route('/ordonnance/print/<int:id>')
@medecin_required
def print_ordonnance(id):
    ordonnance = Ordonnance.query.get_or_404(id)
    medecin = get_current_medecin()
    
    if ordonnance.medecin_id != medecin.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    table_html = generate_medicaments_table_new(ordonnance.medicaments)
    posologie_html = generate_posologie_box_new(ordonnance.posologie) if ordonnance.posologie else  ''
    
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
                .ordonnance {{
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
                            <th>Prise</th>
                            <th>Durée</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_html}
                    </tbody>
                </table>
            </div>
            
            {posologie_html}
            
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
        <div class="btn-print">
            <button onclick="window.print()">Imprimer l'ordonnance</button>
        </div>
    </body>
    </html>
    """
    return html

@medecin_bp.route('/consultation/print/<int:id>')
@medecin_required
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

# ========== CERTIFICATS MEDICAUX ==========

@medecin_bp.route('/certificat/new', methods=['GET', 'POST'])
@medecin_required
def new_certificat():
    medecin = get_current_medecin()
    if not medecin:
        return render_template('error.html', message="Profil médecin non trouvé")
    
    patients = Patient.query.order_by(Patient.nom).all()
    
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        date_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%d').date()
        date_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%d').date()
        motif = request.form.get('motif', '')
        diagnostic = request.form.get('diagnostic', '')
        
        if not patient_id:
            flash('Veuillez sélectionner un patient', 'error')
            return redirect(url_for('medecin.new_certificat'))
        
        if date_fin < date_debut:
            flash('La date de fin doit être postérieure à la date de début', 'error')
            return redirect(url_for('medecin.new_certificat'))
        
        certificat = Certificat(
            patient_id=int(patient_id),
            medecin_id=medecin.id,
            date_emission=datetime.now().date(),
            date_debut=date_debut,
            date_fin=date_fin,
            motif=motif,
            diagnostic=diagnostic
        )
        
        db.session.add(certificat)
        db.session.commit()
        
        flash('Certificat médical créé avec succès', 'success')
        return redirect(url_for('medecin.view_certificat', id=certificat.id))
    
    return render_template('medecin/new_certificat.html',
                         patients=patients,
                         medecin=medecin,
                         now=datetime.now().date())


@medecin_bp.route('/certificat/<int:id>')
@medecin_required
def view_certificat(id):
    certificat = Certificat.query.get_or_404(id)
    medecin = get_current_medecin()
    
    if certificat.medecin_id != medecin.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    medecin_data = Medecin.query.get(certificat.medecin_id)
    patient_data = Patient.query.get(certificat.patient_id)

    return render_template('medecin/view_certificat.html', 
                         certificat=certificat,
                         medecin=medecin_data,
                         patient=patient_data)


@medecin_bp.route('/certificat/print/<int:id>')
@medecin_required
def print_certificat(id):
    certificat = Certificat.query.get_or_404(id)
    medecin = get_current_medecin()
    
    if certificat.medecin_id != medecin.id:
        return render_template('error.html', message="Accès non autorisé"), 403
    
    medecin_data = Medecin.query.get(certificat.medecin_id)
    patient_data = Patient.query.get(certificat.patient_id)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Certificat Médical</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #f0f2f5;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                padding: 20px;
            }}
            .certificat {{
                width: 700px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #0D9488 0%, #0F766E 100%);
                color: white;
                text-align: center;
                padding: 25px 20px;
            }}
            .header h1 {{ font-size: 22px; font-weight: bold; }}
            .header p {{ font-size: 13px; opacity: 0.85; margin: 4px 0; }}
            .header .subtitle {{
                margin-top: 12px;
                padding-top: 10px;
                border-top: 1px solid rgba(255,255,255,0.2);
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 3px;
            }}
            .content {{ padding: 30px; }}
            .info-row {{
                display: flex;
                margin-bottom: 15px;
                border-bottom: 1px solid #f0f0f0;
                padding-bottom: 12px;
            }}
            .info-label {{
                width: 130px;
                font-size: 13px;
                color: #64748B;
                font-weight: 500;
            }}
            .info-value {{
                font-size: 14px;
                color: #1E293B;
                font-weight: 500;
            }}
            .certificat-text {{
                margin-top: 20px;
                padding: 20px;
                background: #F8FAFC;
                border-radius: 8px;
                border-left: 4px solid #0D9488;
                font-size: 14px;
                line-height: 1.8;
                color: #334155;
            }}
            .certificat-text strong {{ color: #0D9488; }}
            .footer {{
                padding: 20px 30px;
                border-top: 1px solid #E2E8F0;
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: #F8FAFC;
            }}
            .signature {{
                text-align: center;
            }}
            .signature .line {{
                width: 150px;
                border-top: 1px dashed #94A3B8;
                margin: 8px auto 4px;
            }}
            .signature p {{ font-size: 12px; color: #64748B; }}
            .btn-print {{ text-align: center; margin-top: 15px; }}
            .btn-print button {{
                background: #0D9488;
                color: white;
                border: none;
                padding: 10px 30px;
                border-radius: 8px;
                font-size: 14px;
                cursor: pointer;
            }}
            .badge {{
                display: inline-block;
                background: #E6FFFA;
                color: #0D9488;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
            }}
            @media print {{
                body {{ background: white; padding: 0; }}
                .certificat {{ box-shadow: none; width: 100%; border-radius: 0; }}
                .btn-print {{ display: none; }}
                .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                .badge {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            }}
        </style>
    </head>
    <body>
        <div class="certificat">
            <div class="header">
                <h1>CLINIQUE LES JUMEAUX</h1>
                <p>Aïn Defla, Algérie</p>
                <p>Tel: 0697 21 32 42</p>
                <div class="subtitle">CERTIFICAT MÉDICAL</div>
            </div>
            
            <div class="content">
                <div class="info-row">
                    <div class="info-label">N° Certificat</div>
                    <div class="info-value">#00{certificat.id}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Date d'émission</div>
                    <div class="info-value">{certificat.date_emission.strftime('%d/%m/%Y')}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Patient</div>
                    <div class="info-value">{patient_data.nom} {patient_data.prenom}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Date de naissance</div>
                    <div class="info-value">{patient_data.date_naissance.strftime('%d/%m/%Y') if patient_data.date_naissance else '-'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Médecin</div>
                    <div class="info-value">Dr. {medecin_data.nom}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Période</div>
                    <div class="info-value">Du {certificat.date_debut.strftime('%d/%m/%Y')} au {certificat.date_fin.strftime('%d/%m/%Y')}</div>
                </div>
                
                <div class="certificat-text">
                    <p><strong>Je soussigné, Dr. {medecin_data.nom}</strong>, certifie que l'état de santé de <strong>{patient_data.nom} {patient_data.prenom}</strong> nécessite un repos médical.</p>
                    <br>
                    <p><strong>Motif:</strong> {certificat.motif or 'Non spécifié'}</p>
                    <br>
                    <p><strong>Diagnostic:</strong> {certificat.diagnostic or 'Non spécifié'}</p>
                    <br>
                    <p><span class="badge">Durée: {(certificat.date_fin - certificat.date_debut).days + 1} jour(s)</span></p>
                </div>
            </div>
            
            <div class="footer">
                <div>
                    <p style="font-size: 12px; color: #94A3B8;">Fait à Aïn Defla, le {certificat.date_emission.strftime('%d/%m/%Y')}</p>
                </div>
                <div class="signature">
                    <div class="line"></div>
                    <p>Dr. {medecin_data.nom}</p>
                </div>
            </div>
        </div>
        
        <div class="btn-print">
            <button onclick="window.print()"><i class="fas fa-print mr-2"></i> Imprimer le certificat</button>
        </div>
    </body>
    </html>
    """
    return html

@medecin_bp.route('/certificat/patient/<int:patient_id>')
@medecin_required
def patient_certificats(patient_id):
    """Voir tous les certificats d'un patient"""
    patient = Patient.query.get_or_404(patient_id)
    certificats = Certificat.query.filter_by(patient_id=patient_id).order_by(Certificat.date_emission.desc()).all()
    
    return render_template('medecin/patient_certificats.html',
                         patient=patient,
                         certificats=certificats)