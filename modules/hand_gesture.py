import cv2
import numpy as np
import mediapipe as mp
from collections import deque
import threading
import time


class HandGestureController:
    """
    Enhanced hand-gesture controller for page navigation and zoom.

    Modes:
      - "none"  : no specific gesture detected
      - "zoom"  : thumb + index pinch → zoom in/out
      - "turn"  : index + middle pinch → swipe left/right to change pages
    """

    def __init__(self, pdf_path, shared_state):
        self.pdf_path = pdf_path
        self.shared_state = shared_state

        # Mediapipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )

        # Mode tracking
        self.current_mode = "none"

        # TURN (page change) state
        self.turn_start = None          # (x, y) when turn mode begins
        self.last_action_time = 0
        self.ACTION_COOLDOWN = 0.7      # seconds between page changes
        self.TURN_THRESHOLD = 70        # pixels of horizontal movement required
        self.MAX_VERTICAL_DRIFT = 60    # ignore swipes with too much vertical drift

        # ZOOM state
        self.zoom_baseline_dist = None
        self.ZOOM_SENSITIVITY = 0.18    # how much change before we call it zoom in/out
        self.last_zoom_direction = None
        self.last_zoom_time = 0
        self.ZOOM_COOLDOWN = 0.35       # seconds between zoom actions
        self.zoom_gesture_start_time = None
        self.zoom_gesture_cooldown = 0.5  # relax time between zoom gestures

        self.is_running = False
        self.thread = None

        print("👋 Enhanced Hand Gesture Controller initialized!")

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
    def _distance(self, p1, p2):
        return np.hypot(p1[0] - p2[0], p1[1] - p2[1])

    # ------------------------------------------------------------------
    # Main gesture processing
    # ------------------------------------------------------------------
    def process_gestures(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        h, w = frame.shape[:2]

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            landmarks = hand_landmarks.landmark

            # Key points
            thumb_tip = (int(landmarks[4].x * w), int(landmarks[4].y * h))
            index_tip = (int(landmarks[8].x * w), int(landmarks[8].y * h))
            middle_tip = (int(landmarks[12].x * w), int(landmarks[12].y * h))
            wrist = (int(landmarks[0].x * w), int(landmarks[0].y * h))

            thumb_index_dist = self._distance(thumb_tip, index_tip)
            index_middle_dist = self._distance(index_tip, middle_tip)

            # -----------------------------
            # Mode detection
            # -----------------------------
            # Zoom mode: thumb & index close, index & middle apart
            if thumb_index_dist < 40 and index_middle_dist > 55:
                if self.current_mode != "zoom":
                    self.current_mode = "zoom"
                    self.zoom_baseline_dist = thumb_index_dist
                    self.last_zoom_direction = None
                    self.zoom_gesture_start_time = time.time()
                    print("🔍 Zoom mode activated")

            # Turn mode: index & middle close, thumb away
            elif index_middle_dist < 35 and thumb_index_dist > 50:
                if self.current_mode != "turn":
                    self.current_mode = "turn"
                    self.turn_start = (
                        (index_tip[0] + middle_tip[0]) // 2,
                        (index_tip[1] + middle_tip[1]) // 2,
                    )
                    print("📖 Turn mode activated")

            # Open hand: reset
            elif thumb_index_dist > 60 and index_middle_dist > 60:
                if self.current_mode != "none":
                    print("🤚 Back to neutral mode")
                self.current_mode = "none"
                self.turn_start = None
                self.zoom_baseline_dist = None
                self.last_zoom_direction = None
                self.zoom_gesture_start_time = None

            # -----------------------------
            # Handle modes
            # -----------------------------
            if self.current_mode == "turn" and self.turn_start is not None:
                self._handle_turn_mode(index_tip, middle_tip)

            elif self.current_mode == "zoom" and self.zoom_baseline_dist is not None:
                self._handle_zoom_mode(thumb_tip, index_tip)

            # -----------------------------
            # Visual feedback
            # -----------------------------
            mode_colors = {
                "none": (255, 255, 255),
                "zoom": (0, 255, 255),
                "turn": (255, 0, 255),
            }
            color = mode_colors.get(self.current_mode, (255, 255, 255))

            cv2.putText(
                frame,
                f"Mode: {self.current_mode.upper()}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2,
            )
            cv2.putText(
                frame,
                f"Page: {self.shared_state.get_page() + 1}/{self.shared_state.total_pages}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                frame,
                f"Zoom: {self.shared_state.get_zoom()}%",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            mp.solutions.drawing_utils.draw_landmarks(
                frame,
                hand_landmarks,
                self.mp_hands.HAND_CONNECTIONS,
                mp.solutions.drawing_utils.DrawingSpec(
                    color=(121, 22, 76), thickness=2, circle_radius=3
                ),
                mp.solutions.drawing_utils.DrawingSpec(
                    color=(250, 44, 250), thickness=2, circle_radius=2
                ),
            )

        else:
            cv2.putText(
                frame,
                "Show hand to camera",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )

        return frame

    # ------------------------------------------------------------------
    # Turn pages (swipe)
    # ------------------------------------------------------------------
    def _handle_turn_mode(self, index_tip, middle_tip):
        # current averaged point
        current_point = (
            (index_tip[0] + middle_tip[0]) // 2,
            (index_tip[1] + middle_tip[1]) // 2,
        )
        dx = current_point[0] - self.turn_start[0]
        dy = current_point[1] - self.turn_start[1]

        # require mostly horizontal movement
        if abs(dy) > self.MAX_VERTICAL_DRIFT:
            return

        current_time = time.time()
        if current_time - self.last_action_time < self.ACTION_COOLDOWN:
            return

        # Swipe left = NEXT page, Swipe right = PREVIOUS page
        if dx <= -self.TURN_THRESHOLD:
            current_page = self.shared_state.get_page()
            new_page = min(self.shared_state.total_pages - 1, current_page + 1)
            if new_page != current_page:
                self.shared_state.update_page(new_page)
                print(f"👋 Swipe LEFT → Next Page: {new_page + 1}")
                self.last_action_time = current_time
                # reset start so we don't chain-trigger without a new gesture
                self.turn_start = current_point

        elif dx >= self.TURN_THRESHOLD:
            current_page = self.shared_state.get_page()
            new_page = max(0, current_page - 1)
            if new_page != current_page:
                self.shared_state.update_page(new_page)
                print(f"👋 Swipe RIGHT → Previous Page: {new_page + 1}")
                self.last_action_time = current_time
                self.turn_start = current_point

    # ------------------------------------------------------------------
    # Zoom mode (pinch)
    # ------------------------------------------------------------------
    def _handle_zoom_mode(self, thumb_tip, index_tip):
        current_dist = self._distance(thumb_tip, index_tip)
        if self.zoom_baseline_dist is None:
            self.zoom_baseline_dist = current_dist
            return

        current_time = time.time()
        
        # Check relax time between zoom gestures
        if (self.zoom_gesture_start_time and 
            current_time - self.zoom_gesture_start_time < self.zoom_gesture_cooldown):
            return
            
        if current_time - self.last_zoom_time < self.ZOOM_COOLDOWN:
            return

        # Compare current pinch distance to baseline
        ratio = (current_dist - self.zoom_baseline_dist) / max(
            self.zoom_baseline_dist, 1
        )

        if ratio > self.ZOOM_SENSITIVITY:
            # fingers moved AWAY → Zoom OUT
            if self.last_zoom_direction != "out":
                current_zoom = self.shared_state.get_zoom()
                new_zoom = min(500, current_zoom + 25)  # Increase by 25%
                self.shared_state.update_zoom(new_zoom)
                print(f"🔎 Zoom OUT → {new_zoom}%")
                self.last_zoom_direction = "out"
                self.last_zoom_time = current_time
                self.zoom_gesture_start_time = current_time

        elif ratio < -self.ZOOM_SENSITIVITY:
            # fingers moved CLOSER → Zoom IN
            if self.last_zoom_direction != "in":
                current_zoom = self.shared_state.get_zoom()
                new_zoom = max(25, current_zoom - 25)  # Decrease by 25%
                self.shared_state.update_zoom(new_zoom)
                print(f"🔍 Zoom IN → {new_zoom}%")
                self.last_zoom_direction = "in"
                self.last_zoom_time = current_time
                self.zoom_gesture_start_time = current_time

        # small adjustments → ignore (avoid flicker)

    # ------------------------------------------------------------------
    # Thread loop
    # ------------------------------------------------------------------
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
        print("🤏 Thumb+Index Pinch  → Zoom mode (in/out)")
        print("✌️ Index+Middle Pinch → Turn mode (swipe to change page)")
        print("✋ Open Hand          → Neutral/reset")
        print("➡️ Swipe RIGHT  (in turn mode) → Previous Page")
        print("⬅️ Swipe LEFT   (in turn mode) → Next Page")
        print("➕ Pinch OUT (fingers apart)   → Zoom Out")
        print("➖ Pinch IN  (fingers closer)  → Zoom In")
        print("⏹️ Press 'Q' to quit window\n")

        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            frame = self.process_gestures(frame)

            cv2.imshow("Hand Gesture Control - Press Q to quit", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        print("🚀 Hand Gesture Controller started!")

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
        cv2.destroyAllWindows()
        print("🛑 Hand Gesture Controller stopped!")