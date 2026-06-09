import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

class Config:
    # ========== SECURITE ==========
    SECRET_KEY = os.environ.get('SECRET_KEY', 'clinique_les_jumeaux_secret_key_2024_123456789')
    
    # ========== BASE DE DONNEES ==========
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'instance', 'clinic.db'))
    
    # ========== SESSION ==========
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # 7 jours au lieu de 8 heures
    SESSION_COOKIE_SECURE = False   # False pour développement (True pour HTTPS)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # ========== SQLAlchemy ==========
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ========== APPLICATION ==========
    DEBUG = True
    TESTING = False