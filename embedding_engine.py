from sentence_transformers import SentenceTransformer


class EmbeddingEngine:

    def __init__(self):

        print("Loading embedding model...")

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        print("Embedding model loaded successfully.")

    # ----------------------------------------
    # Create embedding for one text
    # ----------------------------------------

    def embed_text(self, text):

        embedding = self.model.encode(text)

        return embedding.tolist()

    # ----------------------------------------
    # Create embeddings for multiple texts
    # ----------------------------------------

    def embed_documents(self, documents):

        embeddings = self.model.encode(documents)

        return embeddings.tolist()

    # ----------------------------------------
    # Query embedding
    # ----------------------------------------

    def embed_query(self, query):

        embedding = self.model.encode(query)

        return embedding.tolist()