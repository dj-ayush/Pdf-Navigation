import threading

class SharedState:
    def __init__(self):
        self.current_page = 0
        self.total_pages = 0
        self.pdf_path = None
        self.control_active = False
        self.current_control_type = None
        self.zoom_level = 100  # Default zoom level in percentage
        self.lock = threading.Lock()
    
    def set_pdf_info(self, pdf_path, total_pages):
        with self.lock:
            self.pdf_path = pdf_path
            self.total_pages = total_pages
            self.current_page = 0
    
    def update_page(self, new_page):
        with self.lock:
            if 0 <= new_page < self.total_pages:
                self.current_page = new_page
                return True
        return False
    
    def get_page(self):
        with self.lock:
            return self.current_page
    
    def update_zoom(self, zoom_level):
        with self.lock:
            # Limit zoom between 25% and 500%
            self.zoom_level = max(25, min(500, zoom_level))
            return self.zoom_level
    
    def get_zoom(self):
        with self.lock:
            return self.zoom_level
    
    def reset_zoom(self):
        with self.lock:
            self.zoom_level = 100
            return self.zoom_level

# Global shared state instance
shared_state = SharedState()