"""
Application configuration.
"""
import os
from datetime import timedelta


class Config:
    """Base configuration class"""

    # SECRET_KEY is used for:
    # 1. Flask session security (signing cookies)
    # 2. CSRF protection
    # 3. Database encryption key derivation (via SHA-256 hash)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production-1234567890abcdef')

    # Database configuration
    @staticmethod
    def get_database_uri():
        """Get database URI based on environment"""
        database_url = os.environ.get('DATABASE_URL', '')

        # Use DATABASE_URL if it's for production (Render/Heroku/DigitalOcean)
        if database_url and any(domain in database_url for domain in
            ['render.com', 'herokuapp.com', 'digitalocean.com', 'ondigitalocean.app']):
            return database_url

        # Check if running in DO App Platform with persistent disk
        if os.path.exists('/data'):
            # Use persistent disk for SQLite on DigitalOcean
            db_path = '/data/interviews.db'
            return f'sqlite:///{db_path}'

        # Local development: use SQLite with absolute path
        # Go up one level from core/ to project root
        basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        db_path = os.path.join(basedir, 'instance', 'interviews.db')
        return f'sqlite:///{db_path}'

    SQLALCHEMY_DATABASE_URI = get_database_uri.__func__()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-User configuration
    USER_APP_NAME = 'Ministering Interview App'
    USER_EMAIL_SENDER_EMAIL = os.environ.get('MAIL_USERNAME', 'noreply@example.com')
    USER_EMAIL_SENDER_NAME = 'Ministering Interview App'
    USER_ENABLE_EMAIL = True
    USER_ENABLE_USERNAME = False  # Use email as login identifier
    USER_ENABLE_REGISTER = False  # Disable registration - only via invite or admin
    USER_REQUIRE_RETYPE_PASSWORD = False
    USER_PASSWORD_MIN_LENGTH = 6
    USER_PASSLIB_CRYPTCONTEXT_SCHEMES = ['pbkdf2_sha256', 'bcrypt', 'argon2']
    USER_ENABLE_FORGOT_PASSWORD = True
    USER_ENABLE_CHANGE_PASSWORD = True
    USER_ENABLE_CHANGE_EMAIL = False
    USER_ENABLE_RETYPE_EMAIL = False
    REMEMBER_COOKIE_DURATION = timedelta(days=7)


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
