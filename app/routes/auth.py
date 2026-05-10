from flask import Blueprint, request, session, redirect, url_for, render_template
from werkzeug.security import check_password_hash
from ..models import User # Import our database model

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 1. Query the database for a user with this email
        user = User.query.filter_by(email=email).first()
        
        # 2. Check if user exists AND the password hash matches
        if user and check_password_hash(user.password_hash, password):
            
            # 3. Create a secure session dictionary
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            
            # 4. Role-Based Routing!
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'employee':
                return redirect(url_for('employee.dashboard'))
        else:
            error_message = "Invalid email or password. Please try again."
            
    # Render the login page, passing any error messages
    return render_template('auth/login.html', error=error_message)

@auth_bp.route('/logout')
def logout():
    # Clear the entire session dictionary securely
    session.clear()
    return redirect(url_for('auth.login'))