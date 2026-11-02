# database.py
import os
import httpx
import chromadb
from chromadb.utils import embedding_functions
from config import Config


class Database:
    def __init__(self):
        if Config.PROVIDER == "openai":
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=Config.AI_API_KEY,
                model_name=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            )
        else:
            self.embedding_fn = embedding_functions.OllamaEmbeddingFunction(
                url=Config.OLLAMA_URL,
                model_name=Config.MODEL_NAME,
            )
            # Timeout esteso a 120s per evitare errori con Ollama durante il caricamento del modello
            self.embedding_fn._session.timeout = httpx.Timeout(120.0)

        # Initialize persistent client
        self.client = chromadb.PersistentClient(path=Config.PERSISTENT_DIR)

        try:
            self.collection = self.client.get_or_create_collection(
                name=Config.COLLECTION_NAME, embedding_function=self.embedding_fn
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                self.reset_collection()
            else:
                raise e

    def reset_collection(self):
        """Reimposta la collezione in caso di cambio modello o mismatch di dimensioni"""
        try:
            self.client.delete_collection(name=Config.COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME, embedding_function=self.embedding_fn
        )

    def add_documents(self, documents, metadatas, ids):
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def query(self, query_text, n_results=1):
        try:
            return self.collection.query(query_texts=[query_text], n_results=n_results)
        except Exception as e:
            if "dimension" in str(e).lower():
                print("Rilevato mismatch dimensioni embedding. Resetting collection...")
                self.reset_collection()
                return {"documents": [[]], "metadatas": [[]], "ids": [[]]}
            raise e

    def get_tracked_files(self):
        """Get all unique files and their metadata from the database"""
        result = self.collection.get()
        tracked_files = {}

        if result and result["metadatas"]:
            for metadata in result["metadatas"]:
                if metadata["source"] not in tracked_files:
                    tracked_files[metadata["source"]] = {
                        "hash": metadata["hash"],
                        "last_modified": metadata["last_modified"],
                        "source": metadata["source"],
                    }

        return tracked_files

    def remove_document_by_source(self, source):
        """Remove all entries for a specific source file"""
        result = self.collection.get(where={"source": source})
        if result and result["ids"]:
            self.collection.delete(ids=result["ids"])
