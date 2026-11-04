# database.py - Gestione del database vettoriale persistente ChromaDB
import os
import chromadb
from config import Config
from custom_embedding import CustomEmbeddingFunction


class Database:

    # Inizializza il client persistente ChromaDB e la funzione di embedding unificata
    def __init__(self):
        # Inizializza la funzione di embedding personalizzata (supporta openai, local con SentenceTransformer, ollama)
        self.local_ef = CustomEmbeddingFunction()

        # Inizializza il client persistente su cartella locale (data/chromadb)
        self.client = chromadb.PersistentClient(path=Config.PERSISTENT_DIR)

        # Crea o recupera la collezione dei CV; gestisce l'eccezione se le dimensioni dell'embedding non coincidono
        try:
            self.collection = self.client.get_or_create_collection(
                name=Config.COLLECTION_NAME, embedding_function=self.local_ef
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                self.reset_collection()
            else:
                raise e

    # Reimposta la collezione cancellandola e ricreandola (utile in caso di cambio modello o strategia)
    def reset_collection(self):
        try:
            self.client.delete_collection(name=Config.COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME, embedding_function=self.local_ef
        )

    # Elimina e ripristina la collezione svuotando completamente il database (Step 08)
    def delete_collection(self):
        self.reset_collection()

    # Aggiunge frammenti di testo, metadati associati e identificativi univoci alla collezione
    def add_documents(self, documents, metadatas, ids):
        try:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        except Exception as e:
            # Se la dimensione dei vettori non coincide (es. cambio da Ollama a OpenAI o viceversa), resetta e reinserisce
            if "dimension" in str(e).lower():
                print("Rilevato mismatch dimensioni embedding in add_documents. Resetting collection...")
                self.reset_collection()
                self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            else:
                raise e

    # Esegue la ricerca per similarita vettoriale (cosine similarity) rispetto alla domanda dell'utente
    def query(self, query_text, n_results=1):
        try:
            return self.collection.query(query_texts=[query_text], n_results=n_results)
        except Exception as e:
            # Se rileva un cambio di dimensione vettoriale al volo, resetta la collezione
            if "dimension" in str(e).lower():
                print("Rilevato mismatch dimensioni embedding. Resetting collection...")
                self.reset_collection()
                return {"documents": [[]], "metadatas": [[]], "ids": [[]]}
            raise e

    # Restituisce un dizionario con i file tracciati nel DB e i rispettivi hash per il controllo incrementale
    def get_tracked_files(self):
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

    # Rimuove tutti i frammenti associati a un file specifico (utilizzato prima di un aggiornamento o dopo l'eliminazione)
    def remove_document_by_source(self, source):
        result = self.collection.get(where={"source": source})
        if result and result["ids"]:
            self.collection.delete(ids=result["ids"])

    # Calcola e restituisce le metriche correnti del database per il pulsante delle statistiche
    def get_stats(self):
        result = self.collection.get()
        # Calcola quanti file sorgente distinti sono presenti tra i metadati dei frammenti
        valori_distinti = (
            set(d["source"] for d in result["metadatas"])
            if result and result.get("metadatas")
            else set()
        )
        numero_files = len(valori_distinti)

        return f"""
            Nome Collezione: {self.collection.name}
            Numero totale Frammenti: {self.collection.count()}
            Numero Files Elaborati: {numero_files}
        """
