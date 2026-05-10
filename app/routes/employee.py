from flask import Blueprint, render_template, session, redirect, url_for
from datetime import datetime
from ..models import User, Attendance, FocusLog, Department, db

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

@employee_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'employee':
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # 1. Fetch the User to get their specific break allowance
    user = User.query.get(user_id)
    
    attendance = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.id.desc()).first()
    
    clocked_in = False
    clock_in_time = None
    session_avg_focus = 0 
    
    on_break = False
    
    # 2. Multiply their custom minutes by 60 to get seconds
    total_break_allowed = user.allowed_break_minutes * 60 
    
    remaining_break_seconds = total_break_allowed
    
    if attendance and attendance.check_in and not attendance.check_out:
        clocked_in = True
        clock_in_time = attendance.check_in.strftime("%I:%M %p")
        
        # Calculate Break Data
        on_break = attendance.is_on_break
        used_seconds = attendance.used_break_seconds
        
        # If currently on a break, calculate the time ticking away right now
        if on_break and attendance.break_start_time:
            current_break_duration = (datetime.utcnow() - attendance.break_start_time).total_seconds()
            used_seconds += current_break_duration
            
        remaining_break_seconds = max(0, total_break_allowed - used_seconds)
        
        # Calculate Focus
        shift_logs = FocusLog.query.filter(
            FocusLog.user_id == user_id,
            FocusLog.timestamp >= attendance.check_in
        ).all()
        if shift_logs:
            total_score = sum(log.focus_score for log in shift_logs)
            session_avg_focus = round(total_score / len(shift_logs), 1)

    # Convert seconds to a readable string (e.g., "45m 30s")
    rem_mins = int(remaining_break_seconds // 60)
    rem_secs = int(remaining_break_seconds % 60)
    break_text = f"{rem_mins}m {rem_secs}s"

    return render_template('employee/dashboard.html', 
                           clocked_in=clocked_in, 
                           clock_in_time=clock_in_time,
                           session_avg_focus=session_avg_focus,
                           on_break=on_break,
                           break_text=break_text,
                           remaining_seconds=remaining_break_seconds)

# ... (Keep your dashboard function exactly the same) ...

@employee_bp.route('/clock-in', methods=['POST'])
def clock_in():
    user_id = session.get('user_id')
    current_shift = Attendance.query.filter_by(user_id=user_id, check_out=None).first()
    
    if not current_shift:
        new_attendance = Attendance(
            user_id=user_id,
            date=datetime.utcnow().date(),
            check_in=datetime.utcnow()
        )
        db.session.add(new_attendance)
        
        # NEW: Log Event
        db.session.add(FocusLog(user_id=user_id, focus_score=100, status_message="Shift Started"))
        db.session.commit()
    return redirect(url_for('employee.dashboard'))

@employee_bp.route('/clock-out', methods=['POST'])
def clock_out():
    user_id = session.get('user_id')
    current_shift = Attendance.query.filter_by(user_id=user_id, check_out=None).first()
    
    if current_shift:
        if current_shift.is_on_break:
            time_diff = datetime.utcnow() - current_shift.break_start_time
            current_shift.used_break_seconds += int(time_diff.total_seconds())
            current_shift.is_on_break = False
            
        current_shift.check_out = datetime.utcnow()
        time_diff = current_shift.check_out - current_shift.check_in
        current_shift.total_hours = round(time_diff.total_seconds() / 3600, 2)
        
        # NEW: Log Event
        db.session.add(FocusLog(user_id=user_id, focus_score=0, status_message="Shift Ended"))
        db.session.commit()
    return redirect(url_for('employee.dashboard'))

@employee_bp.route('/start-break', methods=['POST'])
def start_break():
    user_id = session.get('user_id')
    current_shift = Attendance.query.filter_by(user_id=user_id, check_out=None).first()
    
    if current_shift and not current_shift.is_on_break:
        current_shift.is_on_break = True
        current_shift.break_start_time = datetime.utcnow()
        
        # NEW: Log Event
        db.session.add(FocusLog(user_id=user_id, focus_score=100, status_message="Break Started"))
        db.session.commit()
        
    return redirect(url_for('employee.dashboard'))

@employee_bp.route('/end-break', methods=['POST'])
def end_break():
    user_id = session.get('user_id')
    current_shift = Attendance.query.filter_by(user_id=user_id, check_out=None).first()
    
    if current_shift and current_shift.is_on_break:
        time_diff = datetime.utcnow() - current_shift.break_start_time
        current_shift.used_break_seconds += int(time_diff.total_seconds())
        current_shift.is_on_break = False
        current_shift.break_start_time = None
        
        # NEW: Log Event
        db.session.add(FocusLog(user_id=user_id, focus_score=100, status_message="Break Ended"))
        db.session.commit()
        
    return redirect(url_for('employee.dashboard'))