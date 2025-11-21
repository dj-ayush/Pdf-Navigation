import threading
import time
import speech_recognition as sr
from speech_recognition import WaitTimeoutError, UnknownValueError

class VoiceAssistantController:
    def __init__(self, pdf_path, shared_state):
        self.pdf_path = pdf_path
        self.shared_state = shared_state
        self.is_running = False
        self.thread = None
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.8
        self.recognizer.dynamic_energy_threshold = False
        
        print("🎤 Enhanced Voice Assistant Controller initialized!")

    def listen_for_command(self):
        """Listen for voice command with better error handling"""
        try:
            # Try different microphone sources
            for microphone_index in [None, 0, 1]:
                try:
                    with sr.Microphone(device_index=microphone_index) as source:
                        print("🎤 Listening... Speak now!")
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=4)
                        command = self.recognizer.recognize_google(audio).lower()
                        print(f"🎯 Heard: {command}")
                        return command
                except WaitTimeoutError:
                    continue
                except Exception as e:
                    if microphone_index == 1:  # Last attempt
                        raise e
                    continue
                    
        except WaitTimeoutError:
            print("⏰ Listening timeout")
        except UnknownValueError:
            print("🔇 Could not understand audio")
        except Exception as e:
            print(f"❌ Microphone error: {e}")
            print("💡 Using keyboard fallback...")
            return self.keyboard_fallback()
        
        return ""

    def keyboard_fallback(self):
        """Fallback to keyboard input if microphone fails"""
        print("\n⌨️ Keyboard Fallback Activated!")
        print("Press: N(ext), P(revious), F(irst), L(ast), 1-9 (Page number), Q(uit)")
        
        try:
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').upper()
                key_commands = {
                    'N': 'next page',
                    'P': 'previous page', 
                    'F': 'first page',
                    'L': 'last page',
                    '1': 'page 1', '2': 'page 2', '3': 'page 3',
                    '4': 'page 4', '5': 'page 5', '6': 'page 6',
                    '7': 'page 7', '8': 'page 8', '9': 'page 9'
                }
                return key_commands.get(key, '')
        except:
            pass
        
        return ""

    def process_command(self, command):
        """Process voice command and update page"""
        if not command:
            return

        current_page = self.shared_state.get_page()
        new_page = current_page
        
        # Next page commands
        if any(word in command for word in ["next", "forward", "right", "next page"]):
            new_page = min(self.shared_state.total_pages - 1, current_page + 1)
            print(f"🎯 'Next' → Page {new_page + 1}")
            
        # Previous page commands  
        elif any(word in command for word in ["previous", "back", "left", "go back", "previous page"]):
            new_page = max(0, current_page - 1)
            print(f"🎯 'Previous' → Page {new_page + 1}")
            
        # First page commands
        elif any(word in command for word in ["first", "start", "beginning", "first page"]):
            new_page = 0
            print("🎯 'First' → Page 1")
            
        # Last page commands
        elif any(word in command for word in ["last", "end", "last page"]):
            new_page = self.shared_state.total_pages - 1
            print(f"🎯 'Last' → Page {new_page + 1}")
            
        # Specific page commands
        elif "page" in command:
            try:
                words = command.split()
                for i, word in enumerate(words):
                    if word == "page" and i + 1 < len(words):
                        page_num = int(words[i + 1]) - 1
                        if 0 <= page_num < self.shared_state.total_pages:
                            new_page = page_num
                            print(f"🎯 'Page {page_num + 1}' → Page {page_num + 1}")
                            break
            except ValueError:
                print("❌ Could not understand page number")
        
        # Number commands (page 1, page 2, etc.)
        elif any(str(i) in command.split() for i in range(1, 10)):
            for i in range(1, 10):
                if str(i) in command.split():
                    page_num = i - 1
                    if page_num < self.shared_state.total_pages:
                        new_page = page_num
                        print(f"🎯 'Page {i}' → Page {i}")
                        break
        
        # Update page if changed
        if new_page != current_page:
            self.shared_state.update_page(new_page)

    def run(self):
        print("🚀 Enhanced Voice Assistant started!")
        print("🎤 Say commands like: 'next page', 'previous page', 'page 5', 'first page', 'last page'")
        print("💡 Make sure your microphone is connected and allowed in browser permissions")
        
        while self.is_running:
            command = self.listen_for_command()
            if command:
                if "quit" in command or "exit" in command or "stop" in command:
                    print("🛑 Quit command received")
                    self.stop()
                    break
                self.process_command(command)
            
            time.sleep(0.5)  # Small delay between listening attempts

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        print("🚀 Voice Assistant Controller started!")

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
        print("🛑 Voice Assistant Controller stopped!")