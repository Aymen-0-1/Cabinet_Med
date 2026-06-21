from flask import Flask, render_template
from config import Config
from models.database import db, database, init_data, Utilisateur, Medecin
from datetime import timedelta

def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    
    app.config.from_object(Config)
    
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['SESSION_PERMANENT'] = Config.SESSION_PERMANENT
    app.config['PERMANENT_SESSION_LIFETIME'] = Config.PERMANENT_SESSION_LIFETIME
    app.config['SESSION_COOKIE_SECURE'] = Config.SESSION_COOKIE_SECURE
    app.config['SESSION_COOKIE_HTTPONLY'] = Config.SESSION_COOKIE_HTTPONLY
    app.config['SESSION_COOKIE_SAMESITE'] = Config.SESSION_COOKIE_SAMESITE
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        init_data()
        
        medecins = Medecin.query.all()
        
        for med in medecins:
            user = Utilisateur.query.filter_by(email=med.email).first()
            if user and user.role == 'medecin':
                user.medecin_id = med.id
        
        db.session.commit()
    
    from models.auth import auth_bp
    from models.admin import admin_bp
    from models.medecin import medecin_bp
    from models.patient import patient_bp
    from models.secretaire import secretaire_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(medecin_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(secretaire_bp)
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)