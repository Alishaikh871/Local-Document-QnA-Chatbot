import os
import json
import uuid
from datetime import datetime

from config import CHAT_HISTORY_PATH

class ChatManager:
    def __init__(self):
        os.makedirs(CHAT_HISTORY_PATH, exist_ok=True)

    # ---------------------------------------
    # Create New Chat
    # ---------------------------------------
    def create_chat(self, user_id, title="New Chat"):
        chat_id = str(uuid.uuid4())
        data = {
            "id": chat_id,
            "user_id": user_id,  # Secures the chat to the specific user
            "title": title,
            "created": datetime.now().isoformat(),
            "messages": []
        }
        self.save_chat(chat_id, data)
        return chat_id

    # ---------------------------------------
    # Save Chat
    # ---------------------------------------
    def save_chat(self, chat_id, data):
        path = os.path.join(CHAT_HISTORY_PATH, f"{chat_id}.json")
        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )

    # ---------------------------------------
    # Load Chat
    # ---------------------------------------
    def load_chat(self, chat_id):
        path = os.path.join(CHAT_HISTORY_PATH, f"{chat_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    # ---------------------------------------
    # Add Message
    # ---------------------------------------
    def add_message(self, chat_id, role, content, source=None):
        chat = self.load_chat(chat_id)
        if chat is None:
            return
        
        chat["messages"].append({
            "role": role,
            "content": content,
            "source": source,
            "time": datetime.now().strftime("%H:%M")
        })
        self.save_chat(chat_id, chat)

    # ---------------------------------------
    # Rename Chat
    # ---------------------------------------
    def rename_chat(self, chat_id, new_title):
        chat = self.load_chat(chat_id)
        if chat is None:
            return
        
        chat["title"] = new_title
        self.save_chat(chat_id, chat)

    # ---------------------------------------
    # Delete Chat
    # ---------------------------------------
    def delete_chat(self, chat_id):
        path = os.path.join(CHAT_HISTORY_PATH, f"{chat_id}.json")
        if os.path.exists(path):
            os.remove(path)

    # ---------------------------------------
    # List Chats (Filtered by User)
    # ---------------------------------------
    def get_all_chats(self, user_id):
        chats = []
        for file in os.listdir(CHAT_HISTORY_PATH):
            if file.endswith(".json"):
                path = os.path.join(CHAT_HISTORY_PATH, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        chat_data = json.load(f)
                        # Ensure only the logged-in user's chats are returned
                        if chat_data.get("user_id") == user_id:
                            chats.append(chat_data)
                except (json.JSONDecodeError, KeyError):
                    # Ignore invalid or corrupted JSON files
                    continue

        chats.sort(key=lambda x: x["created"], reverse=True)
        return chats

    # ---------------------------------------
    # Delete Everything (Filtered by User)
    # ---------------------------------------
    def clear_all_chats(self, user_id):
        for file in os.listdir(CHAT_HISTORY_PATH):
            if file.endswith(".json"):
                filepath = os.path.join(CHAT_HISTORY_PATH, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        chat_data = json.load(f)
                    
                    # Ensure a user can only delete their own files
                    if chat_data.get("user_id") == user_id:
                        os.remove(filepath)
                except (json.JSONDecodeError, KeyError):
                    continue