# ==========================================
# IMPORTS
# ==========================================
import os

# --- PREVENTS GPU CRASH (Forces CPU processing for heavy models) ---
#os.environ["OLLAMA_NUM_GPU"] = "0" 
# ------------------------------------------------------------------

import shutil
import traceback
import sqlite3
import json
import threading
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for, session, flash, Response, stream_with_context
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Custom Modules (Ensure these exist in your project)
from config import (
    SECRET_KEY,
    UPLOAD_FOLDER,
    SUPPORTED_EXTENSIONS,
    TOP_K_RESULTS
)
from document_processor import DocumentProcessor
from embedding_engine import EmbeddingEngine
from vector_store import VectorStore
from ollama_engine import OllamaEngine

# ==========================================
# FLASK APP & DATABASE SETUP
# ==========================================
app = Flask(__name__)
app.secret_key = SECRET_KEY 
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # 1. Users Table 
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, 
                  username TEXT UNIQUE, 
                  password TEXT, 
                  security_q TEXT, 
                  security_a TEXT)''')
                  
    # 2. Advanced Features Tables (For Chat History & Async Uploads)
    c.execute('''CREATE TABLE IF NOT EXISTS chats
                 (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY, chat_id INTEGER, role TEXT, content TEXT, source TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS uploads
                 (id INTEGER PRIMARY KEY, user_id INTEGER, filename TEXT, status TEXT, chat_id INTEGER)''')
                 
    conn.commit()
    conn.close()

init_db()

# ==========================================
# CREATE FOLDERS
# ==========================================
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==========================================
# INITIALIZE ENGINES
# ==========================================
print("Loading Local Document AI...")

document_processor = DocumentProcessor()
embedding_engine = EmbeddingEngine()
vector_store = VectorStore()
ollama_engine = OllamaEngine()

print("Application Ready.")

# ==========================================
# HELPER FUNCTIONS & DECORATORS
# ==========================================
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in SUPPORTED_EXTENSIONS
    )

def save_uploaded_file(file):
    filename = secure_filename(file.filename)
    # Privacy Fix: Prepend user_id to the filename on disk to avoid conflicts
    user_filename = f"user_{session.get('user_id')}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], user_filename)
    file.save(filepath)
    return filepath, filename

def login_required(f):
    """Protects routes from unauthorized access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# PAGE ROUTES & AUTHENTICATION
# ==========================================
@app.route("/")
def root():
    if "user_id" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid Username or Password.")

    return render_template("login.html")

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('new_username').strip()
    password = request.form.get('new_password')
    security_q = request.form.get('security_q').strip()
    security_a = request.form.get('security_a').strip()
    
    hashed_password = generate_password_hash(password)
    hashed_answer = generate_password_hash(security_a.lower()) 
    
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, security_q, security_a) VALUES (?, ?, ?, ?)",
                  (username, hashed_password, security_q, hashed_answer))
        conn.commit()
        conn.close()
        return render_template('login.html', error="Account created successfully! Please log in.")
    except sqlite3.IntegrityError:
        return render_template('login.html', error="Username already exists.")

@app.route('/reset_password', methods=['POST'])
def reset_password():
    username = request.form.get('reset_username').strip()
    security_a = request.form.get('reset_answer').lower().strip()
    new_password = request.form.get('reset_password')
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    
    if user and check_password_hash(user[4], security_a):
        new_hashed_password = generate_password_hash(new_password)
        c.execute("UPDATE users SET password=? WHERE username=?", (new_hashed_password, username))
        conn.commit()
        conn.close()
        return render_template('login.html', error="Password reset successful! Please log in.")
    else:
        conn.close()
        return render_template('login.html', error="Invalid username or security answer.")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==========================================
# PROTECTED DASHBOARD PAGES
# ==========================================
@app.route("/home")
@login_required
def home():
    user = session.get('username')
    user_id = session.get('user_id')
    
    # Fetch chats directly from SQLite for this specific user
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, title FROM chats WHERE user_id = ? ORDER BY id DESC", (user_id,))
    chats = [{"id": row[0], "title": row[1]} for row in c.fetchall()]
    conn.close()
    
    return render_template("home.html", user=user, chats=chats)

@app.route("/chatbot")
@login_required
def chatbot():
    return render_template(
        "index.html",
        user=session.get('username'),
        current_document=session.get('current_document')
    )

@app.route("/contact")
@login_required
def contact():
    return render_template("contact.html", user=session.get('username'))

@app.route("/about")
@login_required
def about():
    return render_template("about.html", user=session.get('username'))

# ==========================================
# MULTI-FILE UPLOAD API (ASYNC & PRIVACY FIXED)
# ==========================================
def background_processor(user_id, chat_id, upload_id, filepaths):
    """Runs in a separate thread to prevent freezing the Flask server."""
    try:
        for filepath in filepaths:
            documents, metadatas, ids = document_processor.process_document(filepath)
            
            # Privacy Fix: Tag all metadata chunks with the user's ID
            for meta in metadatas:
                meta["user_id"] = user_id
                
            embeddings = embedding_engine.embed_documents(documents)
            vector_store.add_document(ids, documents, embeddings, metadatas)
        
        # Mark as completed
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE uploads SET status='completed' WHERE id=?", (upload_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        traceback.print_exc()
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE uploads SET status='error' WHERE id=?", (upload_id,))
        conn.commit()
        conn.close()

@app.route("/upload", methods=["POST"])
@login_required
def upload_document():
    uploaded_files = request.files.getlist("file")

    if not uploaded_files or uploaded_files[0].filename == "":
        return jsonify({"success": False, "message": "No files selected."}), 400

    filepaths, processed_filenames = [], []
    user_id = session.get("user_id")

    for uploaded_file in uploaded_files:
        if not allowed_file(uploaded_file.filename): continue
        filepath, display_filename = save_uploaded_file(uploaded_file)
        filepaths.append(filepath)
        processed_filenames.append(display_filename)

    if not processed_filenames:
        return jsonify({"success": False, "message": "No supported files were uploaded."}), 400

    chat_title = f"{len(processed_filenames)} Documents Uploaded" if len(processed_filenames) > 1 else processed_filenames[0]
    display_names = ", ".join(processed_filenames)
    session["current_document"] = display_names
    
    # Initialize DB tracking for the new chat and background processing
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT INTO chats (user_id, title) VALUES (?, ?)", (user_id, chat_title))
    chat_id = c.lastrowid
    session["current_chat"] = chat_id
    
    c.execute("INSERT INTO uploads (user_id, filename, status, chat_id) VALUES (?, ?, ?, ?)", (user_id, display_names, "processing", chat_id))
    upload_id = c.lastrowid
    conn.commit()
    conn.close()

    # Start the background thread
    thread = threading.Thread(target=background_processor, args=(user_id, chat_id, upload_id, filepaths))
    thread.start()

    return jsonify({"success": True, "upload_id": upload_id, "message": "Processing started in background."})

@app.route("/upload_status/<int:upload_id>", methods=["GET"])
@login_required
def upload_status(upload_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT status, filename, chat_id FROM uploads WHERE id = ? AND user_id = ?", (upload_id, session['user_id']))
    row = c.fetchone()
    conn.close()
    
    if not row: return jsonify({"success": False, "message": "Upload not found."}), 404
    return jsonify({"success": True, "status": row[0], "filename": row[1], "chat_id": row[2]})

# ==========================================
# CHAT API (STREAMING & PRIVACY FIXED)
# ==========================================
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    try:
        data = request.get_json()
        if not data: return jsonify({"success": False, "message": "No request data received."}), 400
        
        question = data.get("query", "").strip()
        if question == "": return jsonify({"success": False, "message": "Please enter a question."}), 400

        user_id = session.get("user_id")
        current_chat = session.get("current_chat")
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        if current_chat is None:
            c.execute("INSERT INTO chats (user_id, title) VALUES (?, ?)", (user_id, "New Chat"))
            current_chat = c.lastrowid
            session["current_chat"] = current_chat

        # Auto Rename New Chat
        c.execute("SELECT title FROM chats WHERE id = ?", (current_chat,))
        row = c.fetchone()
        if row and row[0] == "New Chat":
            new_title = question[:30].strip() + "..." if len(question) > 30 else question
            c.execute("UPDATE chats SET title = ? WHERE id = ?", (new_title, current_chat))

        c.execute("INSERT INTO messages (chat_id, role, content, source) VALUES (?, ?, ?, ?)", (current_chat, "user", question, ""))
        conn.commit()
        conn.close()

        query_embedding = embedding_engine.embed_query(question)
        
        # Privacy Fix: Filter DB search by the specific user_id
        results = vector_store.search(
            query_embedding, 
            TOP_K_RESULTS, 
            where_filter={"user_id": user_id}
        )

        if not results["documents"] or len(results["documents"][0]) == 0:
            return jsonify({"success": False, "message": "Please upload a document to begin querying."})

        documents, metadatas = results["documents"][0], results["metadatas"][0]
        context = "\n\n".join(documents)
        pages = sorted(list(set([f"{meta['document']} (Page: {meta.get('page', 'N/A')})" for meta in metadatas])))
        sources = ", ".join(pages)

        # Real-time SSE Generator
        def generate():
            yield f"data: {json.dumps({'type': 'start', 'source': sources})}\n\n"
            full_answer = ""
            for chunk in ollama_engine.stream_answer(context, question):
                full_answer += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO messages (chat_id, role, content, source) VALUES (?, ?, ?, ?)", (current_chat, "assistant", full_answer, sources))
            conn.commit()
            conn.close()

            yield f"data: {json.dumps({'type': 'end'})}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "An error occurred during retrieval."}), 500

# ==========================================
# CHAT MANAGEMENT APIs (SQLITE UPGRADED)
# ==========================================
@app.route("/history", methods=["GET"])
@login_required
def history():
    user_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, title FROM chats WHERE user_id = ? ORDER BY id DESC", (user_id,))
    chats = [{"id": row[0], "title": row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify({"success": True, "chats": chats})

@app.route("/new_chat", methods=["POST"])
@login_required
def new_chat():
    user_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT INTO chats (user_id, title) VALUES (?, ?)", (user_id, "New Chat"))
    chat_id = c.lastrowid
    conn.commit()
    conn.close()
    session["current_chat"] = chat_id
    return jsonify({"success": True, "chat_id": chat_id})

@app.route("/load_chat/<int:chat_id>", methods=["GET"])
@login_required
def load_chat(chat_id):
    user_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
    if not c.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Unauthorized"}), 403
        
    c.execute("SELECT role, content, source FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    messages = [{"role": row[0], "content": row[1], "source": row[2]} for row in c.fetchall()]
    conn.close()
    
    session["current_chat"] = chat_id
    return jsonify({"success": True, "messages": messages})

@app.route("/delete_chat/<int:chat_id>", methods=["DELETE"])
@login_required
def delete_chat(chat_id):
    user_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()
    if session.get("current_chat") == chat_id: session.pop("current_chat", None)
    return jsonify({"success": True, "message": "Chat deleted."})

@app.route("/rename_chat", methods=["POST"])
@login_required
def rename_chat():
    user_id = session.get('user_id')
    data = request.get_json()
    chat_id = data.get("chat_id")
    new_title = data.get("title", "").strip()
    if new_title == "": return jsonify({"success": False, "message": "Title cannot be empty."})
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE chats SET title = ? WHERE id = ? AND user_id = ?", (new_title, chat_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Chat renamed."})

@app.route("/clear_history", methods=["DELETE"])
@login_required
def clear_history():
    user_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM chats WHERE user_id = ?", (user_id,))
    chat_ids = [row[0] for row in c.fetchall()]
    for cid in chat_ids:
        c.execute("DELETE FROM messages WHERE chat_id = ?", (cid,))
    c.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    session.pop("current_chat", None)
    return jsonify({"success": True, "message": "All chats deleted."})

# ==========================================
# DOCUMENT MANAGEMENT APIs (PRESERVED & PRIVACY-UPDATED)
# ==========================================
@app.route("/current_document", methods=["GET"])
@login_required
def get_current_document():
    return jsonify({"success": True, "document": session.get('current_document')})

@app.route("/documents", methods=["GET"])
@login_required
def get_documents():
    documents = []
    user_prefix = f"user_{session.get('user_id')}_"
    if os.path.exists(app.config["UPLOAD_FOLDER"]):
        for file in os.listdir(app.config["UPLOAD_FOLDER"]):
            # Only return files that belong to the logged-in user
            if file.startswith(user_prefix):
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], file)
                if os.path.isfile(filepath):
                    documents.append({
                        # Strip the prefix so the UI looks clean
                        "name": file.replace(user_prefix, "", 1), 
                        "size": round(os.path.getsize(filepath) / 1024, 2),
                        "modified": os.path.getmtime(filepath)
                    })
    return jsonify({"success": True, "documents": documents})

@app.route("/delete_document/<filename>", methods=["DELETE"])
@login_required
def delete_document(filename):
    user_filename = f"user_{session.get('user_id')}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], user_filename)
    if not os.path.exists(filepath):
        return jsonify({"success": False, "message": "Document not found."}), 404

    os.remove(filepath)
    return jsonify({"success": True, "message": "Document deleted successfully."})

@app.route("/check_document/<filename>", methods=["GET"])
@login_required
def check_document(filename):
    user_filename = f"user_{session.get('user_id')}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], user_filename)
    return jsonify({"exists": os.path.exists(filepath)})

@app.route("/document_stats", methods=["GET"])
@login_required
def document_stats():
    user_prefix = f"user_{session.get('user_id')}_"
    files = [
        file for file in os.listdir(app.config["UPLOAD_FOLDER"])
        if file.split(".")[-1].lower() in SUPPORTED_EXTENSIONS and file.startswith(user_prefix)
    ]
    
    total_size = sum(
        os.path.getsize(os.path.join(app.config["UPLOAD_FOLDER"], file)) 
        for file in files
    )
        
    return jsonify({
        "success": True,
        "total_documents": len(files),
        "database_chunks": "Active", # Global chunks vs isolated chunks is complex, marked active.
        "storage_mb": round(total_size / (1024 * 1024), 2)
    })

@app.route("/reset_database", methods=["DELETE"])
@login_required
def reset_database():
    # Note: Clearing ChromaDB entirely affects all users.
    try:
        vector_store.clear()
        return jsonify({"success": True, "message": "Vector database cleared."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/delete_all_documents", methods=["DELETE"])
@login_required
def delete_all_documents():
    try:
        user_prefix = f"user_{session.get('user_id')}_"
        folder = app.config["UPLOAD_FOLDER"]
        for file in os.listdir(folder):
            # Only delete their own files
            if file.startswith(user_prefix):
                path = os.path.join(folder, file)
                if os.path.isfile(path):
                    os.remove(path)
        return jsonify({"success": True, "message": "Your documents have been deleted."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ==========================================
# SYSTEM API & ERROR HANDLERS
# ==========================================
@app.route("/health", methods=["GET"])
def health():
    try:
        ollama_status = ollama_engine.is_running()
    except Exception:
        ollama_status = False

    return jsonify({
        "success": True,
        "application": "Local Document AI",
        "ollama_running": ollama_status,
        "documents_indexed": vector_store.count(),
        "current_document": session.get('current_document', 'Not Logged In'),
        "current_chat": session.get('current_chat', 'Not Logged In')
    })

@app.errorhandler(404)
def page_not_found(error):
    return jsonify({"success": False, "message": "404 - Resource not found."}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "message": "500 - Internal Server Error."}), 500

@app.errorhandler(Exception)
def handle_exception(error):
    return jsonify({"success": False, "message": str(error)}), 500

# ==========================================
# APPLICATION START
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("        LOCAL DOCUMENT AI CHATBOT")
    print("=" * 60)
    print("Flask Server : http://127.0.0.1:5000")
    print("Login Page   : http://127.0.0.1:5000/login")
    print("Home Page    : http://127.0.0.1:5000/home")
    print("Chatbot      : http://127.0.0.1:5000/chatbot")
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True
    )