import threading

class SharedState:
    def __init__(self):
        self.current_page = 0
        self.total_pages = 0
        self.pdf_path = None
        self.control_active = False
        self.current_control_type = None
        self.lock = threading.Lock()
    
    def update_page(self, new_page):
        with self.lock:
            if 0 <= new_page < self.total_pages:
                self.current_page = new_page
                return True
        return False
    
    def get_page(self):
        with self.lock:
            return self.current_page
    
    def set_pdf_info(self, pdf_path, total_pages):
        with self.lock:
            self.pdf_path = pdf_path
            self.total_pages = total_pages
            self.current_page = 0

shared_state = SharedState()
