import cv2
import numpy as np
import mediapipe as mp
from collections import deque
import threading
import time

class HandGestureController:
    def __init__(self, pdf_path, shared_state):
        self.pdf_path = pdf_path
        self.shared_state = shared_state
        
        # Gesture Recognition
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )
        
        # Mode tracking
        self.current_mode = "none"
        self.zoom_history = deque(maxlen=5)
        self.turn_start = None
        self.last_zoom_percentage = 50
        self.last_action_time = 0
        
        # Constants
        self.TURN_THRESHOLD = 50
        self.ACTION_COOLDOWN = 0.8
        
        self.is_running = False
        self.thread = None
        
        print("👋 Enhanced Hand Gesture Controller initialized!")

    def process_gestures(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        h, w = frame.shape[:2]
        
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            landmarks = hand_landmarks.landmark
            
            # Get key points
            thumb_tip = (int(landmarks[4].x * w), int(landmarks[4].y * h))
            index_tip = (int(landmarks[8].x * w), int(landmarks[8].y * h))
            middle_tip = (int(landmarks[12].x * w), int(landmarks[12].y * h))
            wrist = (int(landmarks[0].x * w), int(landmarks[0].y * h))
            
            # Calculate distances
            thumb_index_dist = np.hypot(thumb_tip[0]-index_tip[0], thumb_tip[1]-index_tip[1])
            index_middle_dist = np.hypot(index_tip[0]-middle_tip[0], index_tip[1]-middle_tip[1])
            
            # Gesture recognition with better thresholds
            if thumb_index_dist < 30 and index_middle_dist > 40:
                if self.current_mode != "zoom":
                    self.current_mode = "zoom"
                    print("🔍 Zoom mode activated")
                    
            elif index_middle_dist < 30 and thumb_index_dist > 40:
                if self.current_mode != "turn":
                    self.current_mode = "turn"
                    self.turn_start = ((index_tip[0] + middle_tip[0]) // 2, 
                                     (index_tip[1] + middle_tip[1]) // 2)
                    print("📖 Turn mode activated")
                    
            elif thumb_index_dist > 40 and index_middle_dist > 40:
                if self.current_mode != "none":
                    self.current_mode = "none"
                    self.turn_start = None
            
            # Handle turn page gesture
            if self.current_mode == "turn" and self.turn_start:
                current_point = ((index_tip[0] + middle_tip[0]) // 2, 
                               (index_tip[1] + middle_tip[1]) // 2)
                dx = current_point[0] - self.turn_start[0]
                
                current_time = time.time()
                if abs(dx) > self.TURN_THRESHOLD and current_time - self.last_action_time > self.ACTION_COOLDOWN:
                    current_page = self.shared_state.get_page()
                    
                    if dx > 0:  # Swipe right - previous page
                        new_page = max(0, current_page - 1)
                        if new_page != current_page:
                            self.shared_state.update_page(new_page)
                            print(f"👋 Swipe Right → Previous Page: {new_page + 1}")
                    else:  # Swipe left - next page
                        new_page = min(self.shared_state.total_pages - 1, current_page + 1)
                        if new_page != current_page:
                            self.shared_state.update_page(new_page)
                            print(f"👋 Swipe Left → Next Page: {new_page + 1}")
                    
                    self.last_action_time = current_time
                    self.turn_start = None  # Reset after action
            
            # Visual feedback
            mode_colors = {
                "none": (255, 255, 255),
                "zoom": (0, 255, 255),
                "turn": (255, 0, 255)
            }
            
            color = mode_colors.get(self.current_mode, (255, 255, 255))
            cv2.putText(frame, f"Mode: {self.current_mode.upper()}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, f"Page: {self.shared_state.get_page() + 1}/{self.shared_state.total_pages}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Draw hand landmarks
            mp.solutions.drawing_utils.draw_landmarks(
                frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                mp.solutions.drawing_utils.DrawingSpec(color=(121, 22, 76), thickness=2, circle_radius=3),
                mp.solutions.drawing_utils.DrawingSpec(color=(250, 44, 250), thickness=2, circle_radius=2)
            )
        
        else:
            cv2.putText(frame, "Show hand to camera", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return frame

    def run(self):
        print("🚀 Starting Enhanced Hand Gesture Control...")
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("❌ Error: No camera found!")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("\n👋 GESTURE CONTROLS:")
        print("🤏 Thumb+Index Pinch → Zoom Mode")
        print("✌️ Index+Middle Pinch → Turn Pages")
        print("👋 Open Hand → Ready Mode")
        print("➡️ Swipe Right → Previous Page") 
        print("⬅️ Swipe Left → Next Page")
        print("⏹️ Press 'Q' to quit\n")
        
        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame = cv2.flip(frame, 1)
            frame = self.process_gestures(frame)
            
            cv2.imshow("Hand Gesture Control - Press Q to quit", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        print("🚀 Hand Gesture Controller started!")

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
        cv2.destroyAllWindows()
        print("🛑 Hand Gesture Controller stopped!")