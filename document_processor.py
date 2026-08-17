import os
import uuid
import re
import csv
from pypdf import PdfReader
import docx

from config import MAX_CHUNK_SIZE, CHUNK_OVERLAP

class DocumentProcessor:
    def __init__(self):
        self.chunk_size = MAX_CHUNK_SIZE
        self.chunk_overlap = CHUNK_OVERLAP

    # --- ROUTER ---
    def extract_text_from_file(self, filepath):
        """Routes the file to the correct extractor based on extension."""
        ext = filepath.split(".")[-1].lower()
        if ext == "pdf":
            return self.read_pdf(filepath)
        elif ext == "txt":
            return self.read_txt(filepath)
        elif ext == "docx":
            return self.read_docx(filepath)
        elif ext == "csv":
            return self.read_csv(filepath)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    # --- EXTRACTORS ---
    def read_pdf(self, pdf_path):
        reader = PdfReader(pdf_path)
        pages = []
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text:
                pages.append({"page": f"Page {i}", "text": self.clean_text(text)})
        return pages

    def read_txt(self, txt_path):
        with open(txt_path, "r", encoding="utf-8") as file:
            text = file.read()
        return [{"page": "Text Document", "text": self.clean_text(text)}]

    def read_docx(self, docx_path):
        doc = docx.Document(docx_path)
        text = " ".join([paragraph.text for paragraph in doc.paragraphs])
        return [{"page": "Word Document", "text": self.clean_text(text)}]

    def read_csv(self, csv_path):
        text = ""
        with open(csv_path, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                text += " | ".join(row) + "\n"
        return [{"page": "CSV Spreadsheet", "text": self.clean_text(text)}]

    # --- TEXT CLEANING & CHUNKING ---
    def clean_text(self, text):
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def chunk_text(self, text):
        words = text.split()
        chunks = []
        start = 0
        step = max(1, self.chunk_size - self.chunk_overlap)
        while start < len(words):
            end = start + self.chunk_size
            chunks.append(" ".join(words[start:end]))
            start += step
        return chunks

    # --- MAIN PROCESSOR ---
    def process_document(self, filepath):
        print(f" [Debug] Extracting text from {filepath}...")
        pages = self.extract_text_from_file(filepath)

        if not pages:
            raise ValueError("No readable text found in this document.")

        documents, metadatas, ids = [], [], []
        filename = os.path.basename(filepath)

        for page in pages:
            chunks = self.chunk_text(page["text"])
            for chunk in chunks:
                documents.append(chunk)
                metadatas.append({"page": page["page"], "document": filename})
                ids.append(f"{filename}_{uuid.uuid4()}")

        print(f" [Debug] Processed {filename} into {len(documents)} chunks.")
        return documents, metadatas, ids