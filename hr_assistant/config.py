# config.py
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Cerca il file .env partendo dalla cartella corrente verso l'alto (fino alla radice del repo)
_env_path = find_dotenv(usecwd=True)
if not _env_path:
    _repo_root = Path(__file__).resolve().parents[2]
    _env_path = _repo_root / ".env"
load_dotenv(_env_path)


class Config:
    DOCUMENTS_DIR = "resumes"
    COLLECTION_NAME = "CVs"
    PERSISTENT_DIR = "data/chromadb"

    # Provider selezionato: "ollama", "groq", oppure "openai"
    PROVIDER = os.getenv("ACTIVE_PROVIDER", "ollama").lower()

    # Embedding (ChromaDB / Ollama)
    MODEL_NAME = os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma-2:270m")
    OLLAMA_URL = os.getenv("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embeddings")

    # LLM / Chat Completion
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
    else:  # default: ollama locale
        LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "bonsai-2:9b")
        LLM_MODEL_LOW = os.getenv("OLLAMA_LLM_MODEL", "bonsai-2:9b")
        AI_API_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        AI_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")

    # Strategie di Chunking: "semantic_sections" (consigliata), "sliding_window", "legacy"
    CHUNK_STRATEGY = os.getenv("CHUNK_STRATEGY", "semantic_sections")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
