import os

# Gets the absolute path of the directory this file is in
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Security key for session management and form validation
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-graduation-key'
    
    # SQLite Database Configuration
    # This creates a file named 'focusguard.db' directly in your project root
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'focusguard.db')
    
    # Disables a feature that consumes extra memory
    SQLALCHEMY_TRACK_MODIFICATIONS = False