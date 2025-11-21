import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename

from modules.shared_state import shared_state
from modules.eye_gaze import EyeGazeController
from modules.hand_gesture import HandGestureController
from modules.simple_voice_assistant import SimpleVoiceAssistant
from modules.voice_assistant import VoiceAssistantController

import fitz  # PyMuPDF

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

current_controller = None


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secret"
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

    socketio = SocketIO(app, cors_allowed_origins="*")

    # ==========================================================
    # HOME
    # ==========================================================
    @app.route("/")
    def index():
        return render_template("index.html")

    # ==========================================================
    # UPLOAD PDF (PyMuPDF)
    # ==========================================================
    @app.route("/upload", methods=["POST"])
    def upload():
        try:
            file = request.files.get("pdf_file")
            if not file:
                return jsonify({"success": False, "error": "No PDF file received"})

            filename = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            file.save(file_path)

            doc = fitz.open(file_path)
            total_pages = len(doc)
            doc.close()

            shared_state.set_pdf_info(file_path, total_pages)

            return jsonify({"success": True, "total_pages": total_pages})

        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    # ==========================================================
    # GET PAGE COUNT
    # ==========================================================
    @app.route("/get_page_count")
    def get_page_count():
        return jsonify({"page_count": shared_state.total_pages})

    # ==========================================================
    # NEW — GET CURRENT PAGE FOR POLLING
    # ==========================================================
    @app.route("/get_current_page")
    def get_current_page():
        return jsonify({
            "current_page": shared_state.get_page(),
            "total_pages": shared_state.total_pages
        })

    # ==========================================================
    # RENDER A PDF PAGE AS IMAGE
    # ==========================================================
    @app.route("/get_page_image/<int:page>")
    def get_page_image(page):
        if not shared_state.pdf_path:
            return "PDF not loaded", 400

        try:
            zoom = float(request.args.get("zoom", "1"))
            doc = fitz.open(shared_state.pdf_path)

            if page < 0 or page >= len(doc):
                doc.close()
                return "Invalid page number", 400

            pdf_page = doc.load_page(page)
            zoom_matrix = fitz.Matrix(zoom, zoom)
            pix = pdf_page.get_pixmap(matrix=zoom_matrix)

            temp_file = f"temp_{uuid.uuid4()}.jpg"
            pix.save(temp_file)
            doc.close()

            return send_file(temp_file, mimetype="image/jpeg")

        except Exception as e:
            return f"Error: {e}", 500

    # ==========================================================
    # START CONTROL (EYE, HAND, VOICE)
    # ==========================================================
    @app.route("/start_control", methods=["POST"])
    def start_control():
        global current_controller

        try:
            data = request.get_json()
            ctype = data.get("control_type")

            if not shared_state.pdf_path:
                return jsonify({"success": False, "error": "Upload PDF first"})

            if current_controller:
                current_controller.stop()

            if ctype == "eye_gaze":
                current_controller = EyeGazeController(shared_state.pdf_path, shared_state)

            elif ctype == "hand_gesture":
                current_controller = HandGestureController(shared_state.pdf_path, shared_state)

            elif ctype == "voice":
                current_controller = SimpleVoiceAssistant(shared_state.pdf_path, shared_state)

            else:
                return jsonify({"success": False, "error": "Invalid control type"})

            # Start controller thread
            current_controller.start()

            return jsonify({"success": True, "message": f"{ctype} started"})

        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    # ==========================================================
    # STOP CONTROL
    # ==========================================================
    @app.route("/stop_control", methods=["POST"])
    def stop_control():
        global current_controller

        if current_controller:
            current_controller.stop()
            current_controller = None

        return jsonify({"success": True, "message": "Control stopped"})

    # ==========================================================
    # GOTO PAGE
    # ==========================================================
    @app.route("/goto_page", methods=["POST"])
    def goto_page():
        data = request.get_json()
        page_num = data.get("page_num")

        if shared_state.update_page(page_num):
            # NEW: notify frontend instantly
            socketio.emit("page_update", {
                "page_number": page_num + 1,
                "total_pages": shared_state.total_pages
            })

            return jsonify({"success": True})

        return jsonify({"success": False})

    return app


# ONLY RUN IF DIRECTLY EXECUTED (not via gunicorn)
if __name__ == "__main__":
    app = create_app()
    socketio = SocketIO(app, cors_allowed_origins="*")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
