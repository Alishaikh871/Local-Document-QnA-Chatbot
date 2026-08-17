import chromadb
import os

class VectorStore:
    def __init__(self, persist_directory="./chroma_db"):
        # Initialize a persistent local ChromaDB instance
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name="document_chunks")

    def add_document(self, ids, documents, embeddings, metadatas):
        """Adds vectorized document chunks to the database."""
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def search(self, query_embedding, n_results, where_filter=None):
        """
        Searches the database for the most relevant chunks.
        The 'where_filter' ensures users only query their own documents!
        """
        if where_filter:
            return self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
            )
        else:
            return self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )

    def is_empty(self):
        """Checks if the database has any documents."""
        return self.collection.count() == 0

    def count(self):
        """Returns the total number of chunks in the database."""
        return self.collection.count()

    def clear(self):
        """Completely wipes the vector database."""
        self.client.delete_collection(name="document_chunks")
        self.collection = self.client.get_or_create_collection(name="document_chunks")