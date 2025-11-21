import threading
import time
import sys
import os
from modules.shared_state import shared_state

class SimpleVoiceAssistant:
    """
    Ultra-simple voice assistant that uses keyboard input
    No external dependencies required
    """
    
    def __init__(self, pdf_path, shared_state):
        self.pdf_path = pdf_path
        self.shared_state = shared_state
        self.is_running = False
        self.thread = None
        
        print("🎤 Simple Voice Assistant initialized!")
        print("🔧 Using keyboard input (no microphone required)")

    def get_user_input(self):
        """Get input from user via keyboard"""
        try:
            print("\n⌨️  Enter voice command (or number for page): ", end="", flush=True)
            
            if os.name == 'nt':  # Windows
                import msvcrt
                input_line = ""
                while True:
                    if msvcrt.kbhit():
                        char = msvcrt.getch()
                        if char == b'\r':  # Enter pressed
                            print()
                            return input_line.strip()
                        elif char == b'\x08':  # Backspace
                            if input_line:
                                input_line = input_line[:-1]
                                sys.stdout.write('\b \b')
                        else:
                            try:
                                char_decoded = char.decode('utf-8')
                                input_line += char_decoded
                                sys.stdout.write(char_decoded)
                            except:
                                pass
                    time.sleep(0.01)
            else:  # Linux/Mac
                return input().strip()
                
        except Exception as e:
            print(f"\n❌ Input error: {e}")
            return ""

    def process_command(self, command):
        """Process the user command"""
        if not command:
            return

        command_lower = command.lower().strip()
        current_page = self.shared_state.get_page()
        new_page = current_page

        # Direct page numbers
        if command.isdigit():
            page_num = int(command) - 1
            if 0 <= page_num < self.shared_state.total_pages:
                new_page = page_num
                print(f"📖 Jumping to page {page_num + 1}")

        # Navigation commands
        elif command_lower in ['n', 'next']:
            new_page = min(self.shared_state.total_pages - 1, current_page + 1)
            print("➡️ Next page")

        elif command_lower in ['p', 'prev', 'previous', 'back']:
            new_page = max(0, current_page - 1)
            print("⬅️ Previous page")

        elif command_lower in ['f', 'first', 'home']:
            new_page = 0
            print("🏠 First page")

        elif command_lower in ['l', 'last', 'end']:
            new_page = self.shared_state.total_pages - 1
            print("🔚 Last page")

        # Voice-like commands
        elif any(word in command_lower for word in ['next page', 'next']):
            new_page = min(self.shared_state.total_pages - 1, current_page + 1)
            print("🎯 'Next page' → Next page")

        elif any(word in command_lower for word in ['previous page', 'prev page', 'back']):
            new_page = max(0, current_page - 1)
            print("🎯 'Previous page' → Previous page")

        elif any(word in command_lower for word in ['first page', 'start']):
            new_page = 0
            print("🎯 'First page' → First page")

        elif any(word in command_lower for word in ['last page', 'end']):
            new_page = self.shared_state.total_pages - 1
            print("🎯 'Last page' → Last page")

        elif 'page' in command_lower:
            try:
                words = command_lower.split()
                for i, word in enumerate(words):
                    if word == 'page' and i + 1 < len(words):
                        page_num = int(words[i + 1]) - 1
                        if 0 <= page_num < self.shared_state.total_pages:
                            new_page = page_num
                            print(f"🎯 'Page {page_num + 1}' → Page {page_num + 1}")
                            break
            except ValueError:
                print("❌ Could not understand page number")

        elif command_lower in ['q', 'quit', 'exit', 'stop']:
            print("🛑 Quitting...")
            self.stop()
            return

        elif command_lower in ['h', 'help']:
            self.show_help()
            return

        else:
            print("❌ Unknown command. Type 'help' for available commands.")
            return

        # Update page if changed
        if new_page != current_page:
            if self.shared_state.update_page(new_page):
                print(f"✅ Now on page {new_page + 1} of {self.shared_state.total_pages}")
            else:
                print("❌ Failed to change page")

    def show_help(self):
        """Show help information"""
        print("\n" + "="*60)
        print("🎤 SIMPLE VOICE ASSISTANT - COMMANDS")
        print("="*60)
        print("\n📖 QUICK NAVIGATION:")
        print("  [number]     - Jump to page (e.g., '5' for page 5)")
        print("  n, next      - Next page")
        print("  p, prev      - Previous page")
        print("  f, first     - First page")
        print("  l, last      - Last page")
        
        print("\n🎯 VOICE-LIKE COMMANDS:")
        print("  'next page'  - Next page")
        print("  'prev page'  - Previous page")
        print("  'first page' - First page")
        print("  'last page'  - Last page")
        print("  'page 3'     - Go to page 3")
        
        print("\n⚡ OTHER COMMANDS:")
        print("  h, help      - Show this help")
        print("  q, quit      - Quit voice assistant")
        print("="*60)

    def run(self):
        """Main execution loop"""
        print("\n🚀 Simple Voice Assistant Started!")
        print("💡 Type commands as if you're speaking to the assistant")
        self.show_help()
        
        while self.is_running:
            try:
                command = self.get_user_input()
                if command:
                    self.process_command(command)
            except KeyboardInterrupt:
                print("\n🛑 Interrupted by user")
                self.stop()
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                time.sleep(1)

    def start(self):
        """Start the assistant"""
        self.is_running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()
        print("🎤 Simple Voice Assistant running in background...")

    def stop(self):
        """Stop the assistant"""
        self.is_running = False
        print("🛑 Simple Voice Assistant stopped")