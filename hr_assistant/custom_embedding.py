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
        # Recupera la chiave API specifica per OpenAI
        api_key = (
            getattr(Config, "OPENAI_EMBEDDINGS_KEY", None)
            or getattr(Config, "OPENAI_KEY", None)
            or (getattr(Config, "AI_API_KEY", None) if getattr(Config, "PROVIDER", "") == "openai" else None)
            or os.getenv("OPENAI_API_KEY", "")
        )
        api_base = getattr(Config, "OPENAI_BASE_URL", "https://api.openai.com/v1")

        # Verifica preliminare per guidare l'utente nel file .env
        if not api_key or api_key.strip() in ("", "ollama", "your_openai_api_key_here"):
            raise ValueError(
                "Configurazione OpenAI Embedding incompleta: 'OPENAI_API_KEY' non è impostata "
                "o contiene un valore non valido/segnaposto nel file .env.\n"
                "Inserisci una chiave valida (es. OPENAI_API_KEY=sk-...) oppure mantieni EMBEDDING_PROVIDER=ollama."
            )

        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key.strip(),
            model_name=self.model_name,
            api_base=api_base,
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

        # 1. Chiamata a OpenAI con gestione robusta degli errori (quota, autenticazione, rate limit)
        if self.provider == "openai":
            try:
                return self.embedding_function(texts)
            except Exception as e:
                err_str = str(e)
                if "insufficient_quota" in err_str or "quota" in err_str.lower():
                    raise RuntimeError(
                        f"Errore OpenAI Embeddings [Quota Esaurita]: Il credito OpenAI associato alla chiave è esaurito.\n"
                        f"Dettagli: {err_str}\n"
                        f"Soluzione: Ricarica il credito sul portale OpenAI o imposta EMBEDDING_PROVIDER=ollama nel file .env."
                    ) from e
                elif "401" in err_str or "invalid_api_key" in err_str or "incorrect api key" in err_str.lower():
                    raise RuntimeError(
                        f"Errore OpenAI Embeddings [Chiave non valida]: La chiave OPENAI_API_KEY fornita non è valida (401).\n"
                        f"Dettagli: {err_str}\n"
                        f"Soluzione: Verifica la chiave generata su platform.openai.com e aggiorna il file .env."
                    ) from e
                elif "429" in err_str or "rate_limit" in err_str.lower():
                    raise RuntimeError(
                        f"Errore OpenAI Embeddings [Rate Limit]: Limite di frequenza o concurrency raggiunto per OpenAI.\n"
                        f"Dettagli: {err_str}"
                    ) from e
                raise RuntimeError(
                    f"Errore durante la generazione degli embedding OpenAI ({self.model_name}): {err_str}"
                ) from e

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

    # Metodo statico di diagnostica per testare immediatamente se l'embedding funziona
    @classmethod
    def test_connection(cls):
        """Esegue un test rapido per verificare il corretto funzionamento dell'embedding attivo."""
        try:
            ef = cls()
            vec = ef(["Test diagnostico connessione embedding"])
            dims = len(vec[0]) if vec and len(vec) > 0 else 0
            return {
                "success": True,
                "provider": ef.provider,
                "model": ef.model_name,
                "dimensions": dims,
                "message": f"Embedding generato con successo! Provider: '{ef.provider}', Modello: '{ef.model_name}', Dimensioni: {dims}",
            }
        except Exception as e:
            return {
                "success": False,
                "provider": getattr(Config, "EMBEDDING_PROVIDER", "unknown"),
                "model": getattr(Config, "MODEL_NAME", "unknown"),
                "dimensions": 0,
                "message": str(e),
            }

