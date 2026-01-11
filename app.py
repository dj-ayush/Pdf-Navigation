import os
import uuid
import fitz  # PyMuPDF
import threading
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# Import shared state first
from modules.shared_state import shared_state

# Initialize Flask app first
app = Flask(__name__)
app.config["SECRET_KEY"] = "secret"
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize SocketIO AFTER app
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global controller variable - initialized as None
current_controller = None
controller_lock = threading.Lock()

# Import controllers after socketio initialization
try:
    from modules.eye_gaze import EyeGazeController
    from modules.hand_gesture import HandGestureController
    from modules.voice_assistant import VoiceAssistantController
except ImportError as e:
    print(f"Warning: Could not import all modules: {e}")
    # Create dummy classes for missing modules
    class DummyController:
        def __init__(self, *args, **kwargs):
            pass
        def start(self):
            print("Dummy controller started")
        def stop(self):
            print("Dummy controller stopped")
    
    EyeGazeController = DummyController
    HandGestureController = DummyController
    VoiceAssistantController = DummyController

# ==========================================================
# ROUTES
# ==========================================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    try:
        if 'pdf_file' not in request.files:
            return jsonify({"success": False, "error": "No PDF file received"})
        
        file = request.files['pdf_file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No selected file"})

        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(file_path)

        doc = fitz.open(file_path)
        total_pages = len(doc)
        doc.close()

        shared_state.set_pdf_info(file_path, total_pages)

        return jsonify({
            "success": True, 
            "total_pages": total_pages,
            "filename": filename
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_page_count")
def get_page_count():
    return jsonify({"page_count": shared_state.total_pages})

@app.route("/get_current_page")
def get_current_page():
    return jsonify({
        "current_page": shared_state.get_page(),
        "total_pages": shared_state.total_pages
    })

@app.route("/get_page_image/<int:page>")
def get_page_image(page):
    if not shared_state.pdf_path:
        return "PDF not loaded", 400

    try:
        zoom_param = request.args.get("zoom", "1.0")
        zoom = float(zoom_param)
        
        doc = fitz.open(shared_state.pdf_path)
        
        # Ensure page is within bounds (0-based)
        if page < 0 or page >= len(doc):
            doc.close()
            return "Invalid page number", 400

        pdf_page = doc.load_page(page)
        pix = pdf_page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))

        # Save to temporary file in uploads folder
        temp_file = f"temp_{uuid.uuid4()}.jpg"
        temp_path = os.path.join(app.config["UPLOAD_FOLDER"], temp_file)
        pix.save(temp_path)
        doc.close()

        # Send file and schedule cleanup
        response = send_file(temp_path, mimetype="image/jpeg")
        
        # Cleanup after sending
        def cleanup_temp_file():
            try:
                os.remove(temp_path)
            except:
                pass
        
        # Schedule cleanup
        import atexit
        atexit.register(cleanup_temp_file)
        
        return response

    except Exception as e:
        return f"Error: {e}", 500

@app.route("/start_control", methods=["POST"])
def start_control():
    global current_controller
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})
        
        ctype = data.get("control_type")
        
        if not shared_state.pdf_path:
            return jsonify({"success": False, "error": "Upload PDF first"})

        with controller_lock:
            if current_controller:
                current_controller.stop()
                current_controller = None

            if ctype == "eye_gaze":
                current_controller = EyeGazeController(shared_state.pdf_path, shared_state)
            elif ctype == "hand_gesture":
                current_controller = HandGestureController(shared_state.pdf_path, shared_state)
            elif ctype == "voice":
                current_controller = VoiceAssistantController(shared_state.pdf_path, shared_state)
            else:
                return jsonify({"success": False, "error": "Invalid control type"})

            current_controller.start()
            return jsonify({"success": True, "message": f"{ctype} started"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/stop_control", methods=["POST"])
def stop_control():
    global current_controller
    
    with controller_lock:
        if current_controller:
            current_controller.stop()
            current_controller = None
    
    return jsonify({"success": True})

@app.route("/goto_page", methods=["POST"])
def goto_page():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"})
    
    page_num = data.get("page_num")
    if page_num is None:
        return jsonify({"success": False, "error": "No page number provided"})
    
    # Convert to int and ensure it's 0-based
    try:
        page_num = int(page_num)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid page number"})

    if shared_state.update_page(page_num):
        socketio.emit("page_update", {
            "page_number": page_num + 1,
            "total_pages": shared_state.total_pages
        })
        return jsonify({"success": True})
    
    return jsonify({"success": False, "error": "Invalid page number"})

@app.route("/update_zoom", methods=["POST"])
def update_zoom():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"})
    
    zoom_level = data.get("zoom_level")
    if zoom_level is None:
        return jsonify({"success": False, "error": "No zoom level provided"})
    
    try:
        zoom_level = float(zoom_level)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid zoom level"})

    new_zoom = shared_state.update_zoom(zoom_level)
    return jsonify({"success": True, "zoom_level": new_zoom})

@app.route("/get_zoom_level")
def get_zoom_level():
    return jsonify({"zoom_level": shared_state.get_zoom()})

@app.route("/reset_zoom", methods=["POST"])
def reset_zoom():
    new_zoom = shared_state.reset_zoom()
    return jsonify({"success": True, "zoom_level": new_zoom})

# ==========================================================
# SOCKET.IO EVENTS
# ==========================================================
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connection_status', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# ==========================================================
# ENTRY POINT
# ==========================================================
if __name__ == "__main__":
    print("=" * 60)
    print("NeuroRead Pro - Advanced PDF Navigation System")
    print("=" * 60)
    print(f"Server starting on http://localhost:5000")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print("=" * 60)
    
    socketio.run(app, 
                 host="0.0.0.0", 
                 port=5000, 
                 debug=True, 
                 allow_unsafe_werkzeug=True)