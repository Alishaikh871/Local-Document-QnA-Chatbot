import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")

CHAT_HISTORY_PATH = os.path.join(BASE_DIR, "chat_history")

MODEL_NAME = "mistral"

OLLAMA_URL = "http://localhost:11434/api/generate"

SECRET_KEY = "local_document_ai_secret"

MAX_CHUNK_SIZE = 500

CHUNK_OVERLAP = 100

TOP_K_RESULTS = 5

SUPPORTED_EXTENSIONS = {"pdf", "txt", "docx", "csv"}