import cv2
import mediapipe as mp
import numpy as np
import time
import threading
from collections import deque

class EyeGazeController:
    def __init__(self, pdf_path, shared_state):
        self.pdf_path = pdf_path
        self.shared_state = shared_state
        self.is_running = False
        self.thread = None
        
        # Mediapipe Setup
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            refine_landmarks=True, 
            max_num_faces=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Landmarks
        self.LEFT_IRIS = [474, 475, 476, 477]
        self.RIGHT_IRIS = [469, 470, 471, 472]
        self.LEFT_EYE = [33, 133]
        self.RIGHT_EYE = [362, 263]
        
        # Smoothing and timing
        self.recent_gazes = deque(maxlen=10)
        self.stable_gaze = "Center"
        self.gaze_start_time = None
        self.last_action_time = 0
        self.action_cooldown = 1.5  # seconds between actions
        
        print("🎯 Eye Gaze Controller Enhanced!")

    def iris_center(self, landmarks, eye_indices, w, h):
        try:
            pts = np.array([[landmarks[i].x * w, landmarks[i].y * h] for i in eye_indices], dtype=np.float32)
            if len(pts) < 3:
                return None
            (cx, cy), _ = cv2.minEnclosingCircle(pts)
            return int(cx), int(cy)
        except:
            return None

    def detect_gaze(self, landmarks, w, h):
        left_center = self.iris_center(landmarks, self.LEFT_IRIS, w, h)
        right_center = self.iris_center(landmarks, self.RIGHT_IRIS, w, h)

        if left_center is None or right_center is None:
            return "Center"

        # Average iris position
        avg_x = (left_center[0] + right_center[0]) / 2
        avg_y = (left_center[1] + right_center[1]) / 2

        # Reference: eye corners
        left_eye = np.mean([[landmarks[i].x * w, landmarks[i].y * h] for i in self.LEFT_EYE], axis=0)
        right_eye = np.mean([[landmarks[i].x * w, landmarks[i].y * h] for i in self.RIGHT_EYE], axis=0)
        mid_x = (left_eye[0] + right_eye[0]) / 2
        mid_y = (left_eye[1] + right_eye[1]) / 2

        dx = avg_x - mid_x
        dy = avg_y - mid_y

        # Adjusted thresholds for better sensitivity
        if dx < -10:   return "Left"
        elif dx > 10:  return "Right"
        elif dy < -5:  return "Up"
        elif dy > 1:   return "Down"
        else:          return "Center"

    def handle_gaze_action(self, gaze_direction):
        current_time = time.time()
        if current_time - self.last_action_time < self.action_cooldown:
            return
        
        current_page = self.shared_state.get_page()
        new_page = current_page
        
        if gaze_direction == "Right":
            if current_page < self.shared_state.total_pages - 1:
                new_page = current_page + 1
                print(f"👁️ Gaze Right → Next Page: {new_page + 1}")
                
        elif gaze_direction == "Left":
            if current_page > 0:
                new_page = current_page - 1
                print(f"👁️ Gaze Left → Previous Page: {new_page + 1}")
                
        elif gaze_direction == "Up":
            new_page = 0
            print(f"👁️ Gaze Up → First Page")
            
        elif gaze_direction == "Down":
            new_page = self.shared_state.total_pages - 1
            print(f"👁️ Gaze Down → Last Page")
        
        if new_page != current_page:
            if self.shared_state.update_page(new_page):
                self.last_action_time = current_time

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Error: Could not open camera")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("\n🎯 Enhanced Eye Gaze Control Active!")
        print("⬆️ Look Up → First Page")
        print("⬇️ Look Down → Last Page") 
        print("⬅️ Look Left → Previous Page")
        print("➡️ Look Right → Next Page")
        print("⏸️ Look Center → No Action\n")

        while self.is_running:
            success, frame = cap.read()
            if not success:
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb)

            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark
                direction = self.detect_gaze(landmarks, w, h)

                # Smooth gaze detection
                self.recent_gazes.append(direction)
                if len(self.recent_gazes) >= 5:
                    most_common = max(set(self.recent_gazes), key=self.recent_gazes.count)
                    
                    if most_common != self.stable_gaze:
                        self.gaze_start_time = time.time()
                        self.stable_gaze = most_common
                    else:
                        # Trigger action after 1.5 seconds of stable gaze
                        if (self.gaze_start_time and 
                            (time.time() - self.gaze_start_time > 1.5) and 
                            most_common != "Center"):
                            
                            self.handle_gaze_action(most_common)
                            self.gaze_start_time = None  # Reset after action

                # Visual feedback
                color = (0, 255, 0) if self.stable_gaze != "Center" else (255, 255, 255)
                cv2.putText(frame, f"Gaze: {self.stable_gaze}", (30, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(frame, f"Page: {self.shared_state.get_page() + 1}/{self.shared_state.total_pages}", 
                           (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Draw iris points
                for i in self.LEFT_IRIS + self.RIGHT_IRIS:
                    try:
                        x, y = int(landmarks[i].x * w), int(landmarks[i].y * h)
                        cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
                    except:
                        pass
            else:
                cv2.putText(frame, "No face detected", (30, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            cv2.imshow("Eye Gaze Tracking - Press Q to quit", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        print("🚀 Eye Gaze Controller started!")

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
        cv2.destroyAllWindows()
        print("🛑 Eye Gaze Controller stopped!")