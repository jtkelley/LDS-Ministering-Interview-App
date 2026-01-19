"""
Shared resources for Flask app and blueprints.
This module contains global objects that need to be accessed across
the main app and blueprint files to avoid circular imports.
"""
from flask_mail import Mail
import threading

# Flask-Mail instance (initialized in app.py)
mail = Mail()

# Global thread-safe storage for progress data (scraper, import operations)
progress_store = {}
progress_lock = threading.Lock()
