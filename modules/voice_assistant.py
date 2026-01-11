# modules/voice_assistant.py

import threading
import time
import re

import speech_recognition as sr
from speech_recognition import WaitTimeoutError, UnknownValueError


class VoiceAssistantController:
    """
    Microphone-based voice controller for PDF navigation and zoom.

    Start: VoiceAssistantController(pdf_path, shared_state).start()
    Stop : .stop()

    Commands supported (examples):
      - "next", "next page", "forward"
      - "previous", "back", "back page"
      - "first page", "go to start"
      - "last page", "go to end"
      - "page 5", "go to page 10"
      - "jump forward 3 pages", "jump back 2 pages"
      - "middle", "center", "halfway"
      - "zoom in", "zoom out", "zoom 150%", "zoom 100%", "back to normal"
      - "status", "where am I"
      - "repeat" (repeat last successful nav command)
      - "help"
      - "quit", "stop", "exit"
    """

    def __init__(self, pdf_path, shared_state):
        self.pdf_path = pdf_path
        self.shared_state = shared_state

        self.is_running = False
        self.thread = None

        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 250
        self.recognizer.pause_threshold = 0.7
        self.recognizer.dynamic_energy_threshold = True

        self.last_command_text = None
        self.last_nav_target = None  # store (page_index) for "repeat"

        print("🎤 Enhanced Voice Assistant Controller initialized!")

    # -------------------------------------------------------
    # MAIN LOOP
    # -------------------------------------------------------
    def run(self):
        print("\n🚀 Voice Assistant started!")
        print("🎤 Say things like:")
        print("   • 'next page' / 'previous page'")
        print("   • 'page 5' or 'go to page 10'")
        print("   • 'first page', 'last page'")
        print("   • 'jump forward 3 pages'")
        print("   • 'middle' / 'center'")
        print("   • 'zoom in', 'zoom out', 'zoom 150%', 'back to normal'")
        print("   • 'status' / 'where am I'")
        print("   • 'quit' / 'stop'")
        print("💡 Tip: Pause briefly between commands.\n")

        while self.is_running:
            try:
                command = self.listen_for_command()
                if not self.is_running:
                    break

                if command:
                    print(f"🔊 Heard: {command}")
                    self.handle_command(command)
                else:
                    print("🕒 (silence / no command)")

            except KeyboardInterrupt:
                print("\n🛑 Voice Assistant interrupted by user")
                self.stop()
                break
            except Exception as e:
                print(f"❌ Voice loop error: {e}")
                time.sleep(1)

        print("🎤 Voice Assistant loop ended")

    # -------------------------------------------------------
    # LISTEN
    # -------------------------------------------------------
    def listen_for_command(self):
        """
        Listen from default microphone with error handling
        """
        try:
            with sr.Microphone() as source:
                print("🎧 Listening...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(
                    source, timeout=6, phrase_time_limit=4
                )

            try:
                text = self.recognizer.recognize_google(audio)
                return text.lower().strip()
            except UnknownValueError:
                print("🔇 Could not understand audio")
            except Exception as e:
                print(f"❌ Recognition error: {e}")
        except WaitTimeoutError:
            print("⏰ Listening timeout")
        except Exception as e:
            print(f"❌ Microphone error: {e}")

        return ""

    # -------------------------------------------------------
    # COMMAND HANDLING
    # -------------------------------------------------------
    def handle_command(self, text: str):
        self.last_command_text = text
        current_page = self.shared_state.get_page()
        total = self.shared_state.total_pages
        new_page = current_page

        # Normalize
        t = text.lower().strip()

        # --------- STOP / EXIT ----------
        if any(word in t for word in ["quit", "exit", "stop listening", "stop voice"]):
            print("🛑 Stop command received")
            self.stop()
            return

        # --------- HELP ----------
        if "help" in t:
            self.show_help()
            return

        # --------- STATUS ----------
        if "status" in t or "where am i" in t or "which page" in t:
            current_zoom = self.shared_state.get_zoom()
            print(
                f"📊 You are on page {current_page + 1} of {total}, Zoom: {current_zoom}%"
            )
            return

        # --------- ZOOM COMMANDS ----------
        if "zoom" in t:
            self._handle_zoom_commands(t)
            return

        # --------- REPEAT ----------
        if "repeat" in t and self.last_nav_target is not None:
            print(f"🔁 Repeating last target → page {self.last_nav_target + 1}")
            new_page = self.last_nav_target
            self._apply_page_change(current_page, new_page)
            return

        # --------- BASIC NAVIGATION ----------
        if any(word in t for word in ["next page", "next", "forward"]):
            new_page = min(total - 1, current_page + 1)
            print("➡️ Voice: Next page")

        elif any(word in t for word in ["previous page", "previous", "back", "back page"]):
            new_page = max(0, current_page - 1)
            print("⬅️ Voice: Previous page")

        elif any(word in t for word in ["first page", "go to start", "beginning", "home page"]):
            new_page = 0
            print("🏠 Voice: First page")

        elif any(word in t for word in ["last page", "go to end", "final page", "end page"]):
            new_page = total - 1
            print("🔚 Voice: Last page")

        # --------- MIDDLE ----------
        elif any(word in t for word in ["middle", "center", "halfway"]):
            new_page = max(0, total // 2)
            print(f"🎯 Voice: Middle page → {new_page + 1}")

        # --------- JUMP FORWARD/BACK ----------
        elif "jump" in t and "page" in t:
            # e.g. "jump forward 3 pages", "jump back 2 pages"
            m_forward = re.search(r"jump (forward|ahead) (\d+)", t)
            m_back = re.search(r"jump (back|backward) (\d+)", t)
            if m_forward:
                n = int(m_forward.group(2))
                new_page = min(total - 1, current_page + n)
                print(f"➡️ Voice: Jump forward {n} → page {new_page + 1}")
            elif m_back:
                n = int(m_back.group(2))
                new_page = max(0, current_page - n)
                print(f"⬅️ Voice: Jump back {n} → page {new_page + 1}")

        # --------- SPECIFIC PAGE NUMBER ----------
        elif "page" in t:
            # look for "page X"
            m = re.search(r"page\s+(\d+)", t)
            if m:
                p = int(m.group(1)) - 1
                if 0 <= p < total:
                    new_page = p
                    print(f"🎯 Voice: Go to page {p + 1}")
                else:
                    print("❌ Page number out of range")
                    return
            else:
                # "go to 5" etc.
                m2 = re.search(r"\b(\d+)\b", t)
                if m2:
                    p = int(m2.group(1)) - 1
                    if 0 <= p < total:
                        new_page = p
                        print(f"🎯 Voice: Go to page {p + 1}")
                    else:
                        print("❌ Page number out of range")
                        return
                else:
                    print("❌ Could not find page number in command")
                    return

        # --------- RAW NUMBER ONLY ----------
        elif t.isdigit():
            p = int(t) - 1
            if 0 <= p < total:
                new_page = p
                print(f"🎯 Voice: Go to page {p + 1}")
            else:
                print("❌ Page number out of range")
                return

        else:
            print("❓ Unknown command. Say 'help' for options.")
            return

        # Apply change
        self._apply_page_change(current_page, new_page)

    # -------------------------------------------------------
    def _handle_zoom_commands(self, text: str):
        """Handle zoom-related voice commands"""
        current_zoom = self.shared_state.get_zoom()
        
        if "zoom in" in text:
            new_zoom = min(500, current_zoom + 25)
            self.shared_state.update_zoom(new_zoom)
            print(f"🔍 Zoom IN → {new_zoom}%")
            
        elif "zoom out" in text:
            new_zoom = max(25, current_zoom - 25)
            self.shared_state.update_zoom(new_zoom)
            print(f"🔎 Zoom OUT → {new_zoom}%")
            
        elif "back to normal" in text or "normal zoom" in text or "reset zoom" in text:
            new_zoom = self.shared_state.reset_zoom()
            print(f"🔄 Zoom reset → {new_zoom}%")
            
        elif "zoom 100" in text or "hundred percent" in text:
            new_zoom = self.shared_state.reset_zoom()
            print(f"🔢 Zoom 100% → {new_zoom}%")
            
        else:
            # Try to extract percentage from command
            zoom_match = re.search(r'zoom\s+(\d+)%?', text)
            if zoom_match:
                zoom_value = int(zoom_match.group(1))
                if 25 <= zoom_value <= 500:
                    new_zoom = self.shared_state.update_zoom(zoom_value)
                    print(f"🎯 Zoom set → {new_zoom}%")
                else:
                    print("❌ Zoom must be between 25% and 500%")
            else:
                print("❓ Unknown zoom command. Try 'zoom in', 'zoom out', or 'zoom 150%'")

    # -------------------------------------------------------
    def _apply_page_change(self, current_page, new_page):
        if new_page == current_page:
            print(f"ℹ️ Already on page {current_page + 1}")
            return

        if self.shared_state.update_page(new_page):
            self.last_nav_target = new_page
            print(
                f"✅ Now on page {new_page + 1} of {self.shared_state.total_pages}"
            )
        else:
            print("❌ Failed to update page in shared state")

    # -------------------------------------------------------
    def show_help(self):
        print("\n================ VOICE COMMAND HELP ================")
        print("Navigation:")
        print("  • 'next page' / 'previous page'")
        print("  • 'first page', 'last page'")
        print("  • 'page 5', 'go to page 10'")
        print("  • 'jump forward 3 pages', 'jump back 2 pages'")
        print("  • 'middle', 'center', 'halfway'")
        print("")
        print("Zoom Controls:")
        print("  • 'zoom in', 'zoom out'")
        print("  • 'zoom 150%', 'zoom 200%'")
        print("  • 'back to normal', 'reset zoom', 'zoom 100%'")
        print("")
        print("Utility:")
        print("  • 'status' / 'where am I'")
        print("  • 'repeat' (repeat last navigation)")
        print("  • 'help'")
        print("  • 'quit' / 'stop' / 'exit'")
        print("===================================================\n")

    # -------------------------------------------------------
    # Public API
    # -------------------------------------------------------
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        print("🎤 Voice Assistant Controller running in background...")

    def stop(self):
        self.is_running = False
        print("🛑 Voice Assistant stopping...")
        # don't join here if we're in the same thread, but safe if called externally
        if self.thread and self.thread.is_alive() and threading.current_thread() != self.thread:
            self.thread.join()
        print("🛑 Voice Assistant stopped.")