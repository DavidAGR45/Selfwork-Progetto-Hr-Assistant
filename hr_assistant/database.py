# database.py
import httpx
import chromadb
from chromadb.utils import embedding_functions
from config import Config


class Database:
    def __init__(self):
        self.ollama_ef = embedding_functions.OllamaEmbeddingFunction(
            url=Config.OLLAMA_URL, model_name=Config.MODEL_NAME
        )
        self.ollama_ef._session.timeout = httpx.Timeout(120.0)

        # Initialize persistent client
        self.client = chromadb.PersistentClient(path=Config.PERSISTENT_DIR)
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME, embedding_function=self.ollama_ef
        )

    def add_documents(self, documents, metadatas, ids):
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def reset_collection(self):
        try:
            self.client.delete_collection(Config.COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME, embedding_function=self.ollama_ef
        )

    def query(self, query_text, n_results=1):
        return self.collection.query(query_texts=[query_text], n_results=n_results)
