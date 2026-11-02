# custom_embedding.py - Gestore centralizzato per la generazione di embedding (Step 06.1)
import os
import chromadb
from chromadb.api.types import EmbeddingFunction
from chromadb.utils import embedding_functions
import ollama
from config import Config


class CustomEmbeddingFunction(EmbeddingFunction):
    """
    Classe per generare embedding compatibili con ChromaDB e Semantic Chunking.
    Supporta in modo intercambiabile:
    - OpenAI (API cloud)
    - Modelli locali con HuggingFace SentenceTransformer (PyTorch)
    - Modelli locali eseguiti tramite Ollama
    """

    def __init__(self):
        # Recupera il provider configurato in Config (openai, local, ollama)
        self.provider = getattr(Config, "EMBEDDING_PROVIDER", Config.PROVIDER).lower()
        self.model_name = Config.MODEL_NAME
        self.model_path = getattr(Config, "MODEL_PATH", "modelli/mio_modello")

        # Inizializza il provider scelto
        if self.provider == "openai":
            self._setup_openai()
        elif self.provider == "local":
            self._setup_local_model()
        elif self.provider == "ollama":
            self._setup_ollama()
        else:
            raise ValueError(f"Provider embedding non supportato: '{self.provider}'")

    # Configura l'integrazione con OpenAI Embeddings
    def _setup_openai(self):
        api_key = getattr(Config, "OPENAI_EMBEDDINGS_KEY", Config.AI_API_KEY)
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=self.model_name,
        )

    # Configura o scarica il modello locale tramite SentenceTransformer
    def _setup_local_model(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "Per usare EMBEDDING_PROVIDER='local' occorre installare sentence-transformers e torch."
            )

        # Se il modello e gia stato scaricato nella cartella locale, lo carica da disco
        if os.path.exists(self.model_path):
            self.embedding_function = SentenceTransformer(self.model_path)
        else:
            # Altrimenti lo scarica da Hugging Face e lo salva per i riavvii successivi
            self.embedding_function = SentenceTransformer(self.model_name)
            self.embedding_function.save_pretrained(self.model_path)

    # Configura l'uso di Ollama locale per gli embedding
    def _setup_ollama(self):
        # Con Ollama l'endpoint viene chiamato direttamente tramite la libreria ollama
        pass

    # Metodo richiesto da ChromaDB e Semantic Chunking per trasformare una lista di testi in vettori
    def __call__(self, texts):
        if not texts:
            return []

        # 1. Chiamata a OpenAI
        if self.provider == "openai":
            return self.embedding_function(texts)

        # 2. Inferenza locale tramite SentenceTransformer
        if self.provider == "local":
            return self.embedding_function.encode(texts).tolist()

        # 3. Chiamata locale a Ollama (utilizza l'API batch embed se disponibile)
        if self.provider == "ollama":
            try:
                res = ollama.embed(model=self.model_name, input=texts)
                return res["embeddings"]
            except Exception:
                # Fallback su endpoint singolo in caso di versioni precedenti di Ollama
                return [
                    ollama.embeddings(model=self.model_name, prompt=t)["embedding"]
                    for t in texts
                ]

