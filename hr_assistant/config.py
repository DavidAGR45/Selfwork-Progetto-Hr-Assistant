# config.py - Configurazione centralizzata del sistema con caricamento da file .env
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Cerca il file .env partendo dalla cartella corrente verso l'alto (fino alla radice del repo)
_env_path = find_dotenv(usecwd=True)
if not _env_path:
    _repo_root = Path(__file__).resolve().parents[1]
    _env_path = _repo_root / ".env"
load_dotenv(_env_path)


class Config:
    # Cartelle di lavoro e nome collezione vettoriale
    DOCUMENTS_DIR = "resumes"
    COLLECTION_NAME = "CVs"
    PERSISTENT_DIR = "data/chromadb"

    # Selezione del provider attivo: "ollama" (locale), "groq" o "openai"
    PROVIDER = os.getenv("ACTIVE_PROVIDER", "ollama").lower()

    # Configurazione del modello di Embedding (ChromaDB / Ollama / OpenAI / SentenceTransformer)
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", PROVIDER).lower()
    MODEL_NAME = os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma-2:270m")
    MODEL_PATH = os.getenv("MODEL_PATH", "modelli/mio_modello")
    OLLAMA_URL = os.getenv("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embeddings")
    OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDINGS_KEY = os.getenv("OPENAI_API_KEY", "")

    # Configurazione dei modelli di Chat e completamento in base al provider scelto
    if PROVIDER == "groq":
        LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
        LLM_MODEL_LOW = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
        AI_API_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        AI_API_KEY = os.getenv("GROQ_API_KEY", "")
    elif PROVIDER == "openai":
        LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        LLM_MODEL_LOW = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        AI_API_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        AI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    else:
        # Default: Ollama locale
        LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "bonsai-2:9b")
        LLM_MODEL_LOW = os.getenv("OLLAMA_LLM_MODEL", "bonsai-2:9b")
        AI_API_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        AI_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")

    # Strategia di chunking attiva: "semantic_chunking", "semantic_sections", "sliding_window", "legacy"
    CHUNK_STRATEGY = os.getenv("CHUNK_STRATEGY", "semantic_chunking")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
