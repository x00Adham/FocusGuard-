from flask_socketio import emit
from datetime import datetime, timedelta
from . import socketio, db
from .ai_engine.focus_detector import FocusDetector
from .models import FocusLog

detector = FocusDetector()

# Server-side memory trackers
absence_tracker = {}     
distraction_tracker = {} 
last_status = {}         
last_save_time = {}      

@socketio.on('connect')
def handle_connect():
    print("🟢 Browser connected to the WebSocket.")
    emit('server_message', {'message': 'Connected to Focus Guard AI'})

@socketio.on('video_frame')
def handle_video_frame(data):
    image_data = data.get('image')
    user_id_raw = data.get('user_id')
    yaw_offset = data.get('yaw_offset', 0) 
    
    # CRASH PROTECTION: Ignore empty data or expired sessions
    if not image_data or not user_id_raw or user_id_raw == 'None':
        return
        
    try:
        user_id = int(user_id_raw)
    except ValueError:
        return # Stop processing if user_id is corrupted

    result = detector.process_frame(image_data, user_id, yaw_offset)
    
    raw_score = result['score']
    raw_status = result['status']
    landmarks = result.get('landmarks', [])

    if raw_status == 'Error':
        return # Skip processing if the AI failed to read the frame

    now = datetime.utcnow()
    
    # ==========================================
    # 1. THE GRACE PERIOD TIMERS
    # ==========================================
    if raw_status == 'Absent':
        if user_id in distraction_tracker: del distraction_tracker[user_id] 
        
        if user_id not in absence_tracker:
            absence_tracker[user_id] = now
            
        absent_duration = (now - absence_tracker[user_id]).total_seconds()
        
        if absent_duration < 300: # 5 minutes grace
            status = "Away (Grace Period)"
            score = raw_score 
        else:
            status = "Absent"
            score = 0
            
    elif 'Distracted' in raw_status:
        if user_id in absence_tracker: del absence_tracker[user_id] 
        
        if user_id not in distraction_tracker:
            distraction_tracker[user_id] = now
            
        distracted_duration = (now - distraction_tracker[user_id]).total_seconds()
        
        # THE 3-SECOND RULE (Ignore quick glances away)
        if distracted_duration < 3: 
            status = "Focused" 
            score = 100        
        else:
            status = raw_status
            score = raw_score
    else:
        # PERFECTLY FOCUSED! Clear all timers.
        if user_id in absence_tracker: del absence_tracker[user_id]
        if user_id in distraction_tracker: del distraction_tracker[user_id]
        status = raw_status
        score = raw_score

    # ==========================================
    # 2. SMART DATABASE LOGGING
    # ==========================================
    prev_status = last_status.get(user_id)
    last_save = last_save_time.get(user_id)
    
    should_save = False
    
    if prev_status != status:
        should_save = True
    elif last_save is None or (now - last_save).total_seconds() >= 60:
        should_save = True

    if should_save:
        last_status[user_id] = status
        last_save_time[user_id] = now

        print(f"💾 EVENT LOG SAVED - User: {user_id} | Status: {status}")

        try:
            log_entry = FocusLog(
                user_id=user_id,
                focus_score=score,
                is_distracted=('Distracted' in status),
                is_absent=(status == 'Absent'),
                status_message=status
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            print(f"❌ Database save error: {e}")
            db.session.rollback()

    emit('focus_result', {
        'score': score,
        'status': status,
        'landmarks': landmarks
    })