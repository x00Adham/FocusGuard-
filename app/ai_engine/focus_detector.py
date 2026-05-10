import cv2
import mediapipe as mp
import numpy as np
import base64
import math

class FocusDetector:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        # refine_landmarks=True is the secret to getting Iris tracking (Points 468-477)
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True, 
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # Facial Landmark Indices
        self.LEFT_EYE = [33, 160, 158, 133, 153, 144]
        self.RIGHT_EYE = [362, 385, 387, 263, 373, 380]
        self.MOUTH = [78, 81, 13, 311, 308, 402, 14, 178] 
        
        # --- NEW: IRIS TRACKING INDICES ---
        self.LEFT_IRIS_CENTER = 473
        self.RIGHT_IRIS_CENTER = 468
        self.LEFT_EYE_CORNERS = [33, 133]  # Outer, Inner
        self.RIGHT_EYE_CORNERS = [362, 263] # Inner, Outer
        
        # 3D generic face model points for PnP calculation
        self.model_points = np.array([
            (0.0, 0.0, 0.0),             
            (0.0, -330.0, -65.0),        
            (-225.0, 170.0, -135.0),     
            (225.0, 170.0, -135.0),      
            (-150.0, -150.0, -125.0),    
            (150.0, -150.0, -125.0)      
        ], dtype=np.float64)

        self.user_states = {}

    def _dist(self, a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def calculate_ear(self, landmarks, indices, img_w, img_h):
        pts = [(int(landmarks[i].x * img_w), int(landmarks[i].y * img_h)) for i in indices]
        v1 = self._dist(pts[1], pts[5])
        v2 = self._dist(pts[2], pts[4])
        h = self._dist(pts[0], pts[3])
        return (v1 + v2) / (2.0 * h + 1e-6)

    def calculate_mar(self, landmarks, img_w, img_h):
        top = (int(landmarks[13].x * img_w), int(landmarks[13].y * img_h))
        bottom = (int(landmarks[14].x * img_w), int(landmarks[14].y * img_h))
        left = (int(landmarks[78].x * img_w), int(landmarks[78].y * img_h))
        right = (int(landmarks[308].x * img_w), int(landmarks[308].y * img_h))
        
        v = self._dist(top, bottom)
        h = self._dist(left, right)
        return v / (h + 1e-6)

    def calculate_gaze_ratio(self, landmarks, iris_idx, corners, img_w, img_h):
        """Calculates where the iris is looking relative to the eye corners"""
        iris = (int(landmarks[iris_idx].x * img_w), int(landmarks[iris_idx].y * img_h))
        corner1 = (int(landmarks[corners[0]].x * img_w), int(landmarks[corners[0]].y * img_h))
        corner2 = (int(landmarks[corners[1]].x * img_w), int(landmarks[corners[1]].y * img_h))
        
        # Distance from iris to the first corner
        dist_iris_c1 = self._dist(iris, corner1)
        # Total eye width
        eye_width = self._dist(corner1, corner2)
        
        # A ratio around 0.5 means looking straight. < 0.4 or > 0.6 means looking away.
        return dist_iris_c1 / (eye_width + 1e-6)

    def calculate_head_pose_3d(self, landmarks, img_w, img_h):
        image_points = np.array([
            (landmarks[1].x * img_w, landmarks[1].y * img_h),       
            (landmarks[152].x * img_w, landmarks[152].y * img_h),   
            (landmarks[33].x * img_w, landmarks[33].y * img_h),     
            (landmarks[263].x * img_w, landmarks[263].y * img_h),   
            (landmarks[61].x * img_w, landmarks[61].y * img_h),     
            (landmarks[291].x * img_w, landmarks[291].y * img_h)    
        ], dtype=np.float64)

        focal_length = img_w
        center = (img_w / 2, img_h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)

        success, rotation_vector, translation_vector = cv2.solvePnP(
            self.model_points, image_points, camera_matrix, np.zeros((4, 1)), flags=cv2.SOLVEPNP_ITERATIVE
        )

        rmat, _ = cv2.Rodrigues(rotation_vector)
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
        
        return angles[0], angles[1], angles[2]

    def process_frame(self, base64_string, user_id, yaw_offset=0.0):
        try:
            header, encoded = base64_string.split(",", 1)
            nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            img_h, img_w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)

            prev_score = self.user_states.get(user_id, 100)

            if not results.multi_face_landmarks:
                new_score = max(0, prev_score - 15)
                self.user_states[user_id] = new_score
                return {"status": "Absent", "score": int(new_score), "landmarks": []}

            landmarks = results.multi_face_landmarks[0].landmark

            # 1. Base Drowsiness & Fatigue (EAR & MAR)
            ear_left = self.calculate_ear(landmarks, self.LEFT_EYE, img_w, img_h)
            ear_right = self.calculate_ear(landmarks, self.RIGHT_EYE, img_w, img_h)
            avg_ear = (ear_left + ear_right) / 2.0
            mar = self.calculate_mar(landmarks, img_w, img_h)

            # 2. Head Pose (Pitch, Yaw)
            pitch, raw_yaw, roll = self.calculate_head_pose_3d(landmarks, img_w, img_h)
            adjusted_yaw = raw_yaw - float(yaw_offset)

            # 3. GAZE ESTIMATION (The Gold Standard)
            gaze_left = self.calculate_gaze_ratio(landmarks, self.LEFT_IRIS_CENTER, self.LEFT_EYE_CORNERS, img_w, img_h)
            gaze_right = self.calculate_gaze_ratio(landmarks, self.RIGHT_IRIS_CENTER, self.RIGHT_EYE_CORNERS, img_w, img_h)
            avg_gaze = (gaze_left + gaze_right) / 2.0

            target_score = 100
            status = "Focused"

            # --- THE NEW SCORING LOGIC ---
            # We care less about head pose now, and MUCH more about the Eyes.

            # Gaze Check: ~0.5 is straight ahead. If it drops below 0.35 or above 0.65, they are looking hard left/right.
            if avg_gaze < 0.35 or avg_gaze > 0.65:
                target_score -= 40
                status = "Distracted (Eyes Off Screen)"
            
            # Head Pose: We allow MASSIVE head movement (35 degrees!) as long as the eyes are looking at the screen.
            elif abs(adjusted_yaw) > 35:
                target_score -= 30 
                status = "Distracted (Looking Away)"

            # Looking Down: Often implies looking at a phone, but we check if eyes are closed first
            if pitch < -25:
                target_score -= 30
                if status == "Focused": status = "Distracted (Looking Down)"

            # Drowsiness Check
            if avg_ear < 0.18: 
                target_score -= 60
                status = "Distracted (Eyes Closed)"

            if mar > 0.6: 
                target_score -= 20
                if status == "Focused": status = "Fatigued (Yawning)"

            target_score = max(0, min(100, target_score))
            
            # Smoothing Math
            if target_score == 100 and prev_score < 100:
                smoothed_score = (prev_score * 0.5) + (target_score * 0.5)
            else:
                smoothed_score = (prev_score * 0.7) + (target_score * 0.3)
                
            final_score = math.ceil(smoothed_score)
            if final_score > 98: final_score = 100
            
            self.user_states[user_id] = final_score
            
            if final_score < 50 and status == "Focused":
                status = "Distracted"

            # Return the Iris centers so the employee can see their pupils being tracked!
            tracked_points = [
                {'x': landmarks[self.LEFT_IRIS_CENTER].x, 'y': landmarks[self.LEFT_IRIS_CENTER].y},   
                {'x': landmarks[self.RIGHT_IRIS_CENTER].x, 'y': landmarks[self.RIGHT_IRIS_CENTER].y}, 
                {'x': landmarks[1].x, 'y': landmarks[1].y}       
            ]

            return {
                "status": status, 
                "score": final_score, 
                "landmarks": tracked_points
            }

        except Exception as e:
            print(f"AI Processing Error: {e}")
            return {"status": "Error", "score": 0, "landmarks": []}