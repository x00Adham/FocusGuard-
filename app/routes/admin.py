from flask import Blueprint, render_template, session, redirect, url_for, request
from datetime import datetime
from ..models import User, Attendance, FocusLog, Department, db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
def dashboard():
    # Security check
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    # 1. Get Total Employees (excluding admins)
    total_employees = User.query.filter_by(role='employee').count()

    # 2. Get Currently Active Employees (Anyone without a check_out time)
    active_attendance = Attendance.query.filter_by(check_out=None).all()
    active_user_ids = [record.user_id for record in active_attendance]
    active_count = len(active_user_ids)

    # 3. Calculate Company Average Focus for Today (Safe SQLite Query)
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    
    # Get all logs from midnight today onwards
    logs_today = FocusLog.query.filter(FocusLog.timestamp >= start_of_day).all()
    
    if logs_today:
        avg_focus = sum(log.focus_score for log in logs_today) / len(logs_today)
        avg_focus = round(avg_focus, 1)
    else:
        avg_focus = 0.0

    # 4. Build data for the Live Employee Table
    employee_data = []
    employees = User.query.filter_by(role='employee').all()
    
    for emp in employees:
        dept_name = emp.department.name if emp.department else "Unassigned"
        
        # Get latest log (order by ID descending is safer and faster in SQLite)
        latest_log = FocusLog.query.filter_by(user_id=emp.id).order_by(FocusLog.id.desc()).first()
        
        if latest_log:
            current_status = latest_log.status_message
            current_score = latest_log.focus_score
        else:
            current_status = "Offline"
            current_score = 0

        employee_data.append({
            'id': emp.id,
            'name': emp.username.replace('_', ' ').title(),
            'department': dept_name,
            'status': current_status,
            'score': current_score,
            'is_active': emp.id in active_user_ids
        })

    return render_template('admin/dashboard.html', 
                           total_employees=total_employees,
                           active_count=active_count,
                           avg_focus=avg_focus,
                           employee_data=employee_data)

@admin_bp.route('/employee/<int:emp_id>/log')
def employee_log(emp_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))
        
    employee = User.query.get_or_404(emp_id)
    
    # NEW: Fetch Attendance Sessions instead of raw Focus Logs
    sessions = Attendance.query.filter_by(user_id=emp_id).order_by(Attendance.id.desc()).all()
    
    return render_template('admin/employee_log.html', employee=employee, sessions=sessions)

@admin_bp.route('/employee/<int:emp_id>/session/<int:session_id>')
def session_details(emp_id, session_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))
        
    employee = User.query.get_or_404(emp_id)
    shift = Attendance.query.get_or_404(session_id)
    
    # Fetch all FocusLogs that happened during this specific shift
    query = FocusLog.query.filter(
        FocusLog.user_id == emp_id,
        FocusLog.timestamp >= shift.check_in
    )
    
    # If the shift has ended, stop fetching logs after the check_out time
    if shift.check_out:
        query = query.filter(FocusLog.timestamp <= shift.check_out)
        
    # Order chronologically for a proper timeline
    logs = query.order_by(FocusLog.timestamp.asc()).all()
    
    return render_template('admin/session_details.html', employee=employee, shift=shift, logs=logs)

@admin_bp.route('/employee/<int:emp_id>/update-break', methods=['POST'])
def update_break(emp_id):
    # (Keep your existing update_break function exactly as it is here...)
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))
    
    employee = User.query.get_or_404(emp_id)
    new_break_time = request.form.get('break_minutes')
    
    if new_break_time and new_break_time.isdigit():
        employee.allowed_break_minutes = int(new_break_time)
        db.session.commit()
        
    return redirect(url_for('admin.employee_log', emp_id=emp_id))