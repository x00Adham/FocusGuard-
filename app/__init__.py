from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from config import Config

# Initialize extensions globally but without attaching them to the app yet
db = SQLAlchemy()
socketio = SocketIO()

def create_app():
    """
    Constructs the core application.
    This pattern is the industry standard for scalable Flask applications.
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions with the application instance
    db.init_app(app)
    
    # cors_allowed_origins="*" allows the frontend to communicate with the WebSocket server
    socketio.init_app(app, cors_allowed_origins="*")

    # The app context ensures that the database tables are created 
    # before the first request if they don't already exist.
    with app.app_context():
        from . import models 
        db.create_all()

        from .routes.auth import auth_bp
        from .routes.admin import admin_bp
        from .routes.employee import employee_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(employee_bp)
        
    # --- NEW: Import socket events so they register ---
    from . import events 

    return app