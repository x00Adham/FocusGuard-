from . import db
from datetime import datetime

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Relationship to link users to this department
    users = db.relationship('User', backref='department', lazy=True)

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='employee') 
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- NEW: Custom Break Allowance ---
    allowed_break_minutes = db.Column(db.Integer, default=60) 
    
    attendance_records = db.relationship('Attendance', backref='employee', lazy=True)
    focus_logs = db.relationship('FocusLog', backref='employee', lazy=True)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)
    total_hours = db.Column(db.Float, nullable=True)
    
    is_on_break = db.Column(db.Boolean, default=False)
    break_start_time = db.Column(db.DateTime, nullable=True)
    used_break_seconds = db.Column(db.Integer, default=0)

class FocusLog(db.Model):
    __tablename__ = 'focus_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Focus metrics from the AI engine
    focus_score = db.Column(db.Float, nullable=False) # 0.0 to 1.0 (or 0 to 100)
    is_distracted = db.Column(db.Boolean, default=False)
    is_absent = db.Column(db.Boolean, default=False)
    status_message = db.Column(db.String(255), nullable=True)