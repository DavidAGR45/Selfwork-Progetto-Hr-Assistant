# document_processor.py - Gestione, estrazione e sincronizzazione dei curriculum nel database (Step 07)
import os
import re
import uuid
import hashlib
import mimetypes
import tempfile
from zipfile import ZipFile
from typing import Tuple, List, Dict, Any
from markitdown import MarkItDown
from config import Config
from semantic_chunking import SemanticChunking


class DocumentProcessor:

    # Mappatura delle estensioni supportate e relativa tipologia di documento (Step 07)
    SUPPORTED_EXTENSIONS = {
        # Formati documento
        ".txt": "text",
        ".pdf": "document",
        ".doc": "document",
        ".docx": "document",
        ".ppt": "presentation",
        ".pptx": "presentation",
        ".xls": "spreadsheet",
        ".xlsx": "spreadsheet",
        # Formati web
        ".html": "web",
        ".htm": "web",
        # Formati dati
        ".csv": "data",
        ".json": "data",
        ".xml": "data",
        # Archivi compressi
        ".zip": "archive",
    }

    # Inizializza il convertitore MarkItDown per supportare file eterogenei (PDF, Office, tabelle, archivi)
    def __init__(self):
        self.md_converter = MarkItDown()

    # Legge le prime n_lines righe da un file di testo (gestisce l'eccezione se il file e' binario come PDF o DOCX)
    @staticmethod
    def read_first_lines(file_path: str, n_lines: int = 100) -> List[str]:
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return [line.strip() for line, _ in zip(file, range(n_lines))]
        except (UnicodeDecodeError, Exception):
            return []

    # Calcola l'hash MD5 del contenuto di un file per verificare se e' stato modificato
    @staticmethod
    def get_file_hash(file_path: str) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    # Recupera i metadati arricchiti del documento (tipo file, MIME type, estensione, hash, ultima modifica)
    @staticmethod
    def get_document_metadata(file_path: str) -> Dict[str, Any]:
        extension = os.path.splitext(file_path)[1].lower()
        file_type = DocumentProcessor.SUPPORTED_EXTENSIONS.get(extension, "unknown")
        mime_type, _ = mimetypes.guess_type(file_path)

        return {
            "hash": DocumentProcessor.get_file_hash(file_path),
            "last_modified": os.path.getmtime(file_path),
            "source": os.path.basename(file_path),
            "file_type": file_type,
            "mime_type": mime_type or "unknown",
            "extension": extension,
        }

    # Converte un file in formato Markdown leggibile tramite la libreria MarkItDown (Step 07)
    def _convert_to_markdown(self, file_path: str) -> str:
        try:
            result = self.md_converter.convert(file_path)
            return result.text_content or ""
        except Exception as e:
            print(f"Errore nella conversione Markdown di '{file_path}': {str(e)}")
            return ""

    # Elabora archivi ZIP estraendo i file supportati in una cartella temporanea (Step 07)
    def _process_zip_file(self, file_path: str) -> List[Tuple[str, str]]:
        results = []
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            inner_file_path = os.path.join(root, file)
                            ext = os.path.splitext(file)[1].lower()
                            if ext in self.SUPPORTED_EXTENSIONS and ext != ".zip":
                                content = self._convert_to_markdown(inner_file_path)
                                if content:
                                    results.append((file, content))
            except Exception as e:
                print(f"Errore nell'elaborazione dell'archivio zip '{file_path}': {str(e)}")
        return results

    # Estrae con regex nome, email e numero di telefono direttamente dal testo del CV
    @staticmethod
    def extract_candidate_info(content: str) -> dict:
        # Cerca il nome: prima con "Nome: ...", poi cerca nelle prime intestazioni
        name = "Candidato"
        name_match = re.search(r'(?i)^nome:\s*(.+)$', content, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip()
        else:
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("### ") or line.startswith("## ") or line.startswith("# "):
                    header = re.sub(r"^#+\s*", "", line).strip()
                    if header.upper() not in [
                        "INFORMAZIONI PERSONALI",
                        "CURRICULUM VITAE",
                        "PROFILO PROFESSIONALE",
                        "RESUME",
                    ]:
                        name = header
                        break

        candidate_name = name.title() if name.isupper() else name

        # Cerca l'indirizzo email tramite regex
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        email = email_match.group(0).strip() if email_match else "N/D"

        # Cerca il recapito telefonico tramite regex
        phone_match = re.search(r'(?i)(?:tel|telefono|cellulare|mobile)[:\s]+([+\d\s]{8,25})', content)
        phone = phone_match.group(1).strip() if phone_match else "N/D"

        return {
            "candidate_name": candidate_name,
            "email": email,
            "phone": phone,
        }

    # Strategia 1: divide il testo in base alle sezioni Markdown (### e ##)
    @staticmethod
    def chunk_semantic_sections(content: str, candidate_name: str = "") -> list[str]:
        lines = content.splitlines()
        chunks = []
        parent_section = ""
        current_section = ""
        current_body = []

        def flush():
            nonlocal current_section, current_body, parent_section
            body = "\n".join(current_body).strip()
            if current_section or body:
                header = current_section
                if parent_section and parent_section != current_section:
                    header = f"{parent_section} > {current_section}" if current_section else parent_section

                parts = []
                if candidate_name:
                    parts.append(f"[Candidato: {candidate_name}]")
                if header:
                    parts.append(f"Sezione: {header}")
                if body:
                    parts.append(body)

                result = "\n".join(parts).strip()
                if result:
                    chunks.append(result)
            current_body = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("### ") or stripped.startswith("## "):
                header_text = re.sub(r"^#{2,3}\s+", "", stripped)
                if not current_body and current_section:
                    parent_section = current_section
                    current_section = header_text
                else:
                    flush()
                    current_section = header_text
            else:
                if stripped:
                    current_body.append(stripped)

        flush()
        return chunks

    # Strategia 2: sliding window con overlap tra paragrafi consecutivi
    @staticmethod
    def chunk_sliding_window(
        content: str,
        candidate_name: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[str]:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > chunk_size and current_chunk:
                full_text = "\n\n".join(current_chunk)
                if candidate_name:
                    full_text = f"[Candidato: {candidate_name}]\n{full_text}"
                chunks.append(full_text)

                if chunk_overlap > 0 and len(current_chunk[-1]) <= chunk_overlap:
                    current_chunk = [current_chunk[-1]]
                    current_len = len(current_chunk[0])
                else:
                    current_chunk = []
                    current_len = 0

            current_chunk.append(para)
            current_len += para_len

        if current_chunk:
            full_text = "\n\n".join(current_chunk)
            if candidate_name:
                full_text = f"[Candidato: {candidate_name}]\n{full_text}"
            chunks.append(full_text)

        return chunks

    # Strategia 0 (Legacy): metodo originario con replace dei newline con punto e split su '### '
    @staticmethod
    def chunk_legacy(content: str) -> list[str]:
        raw_chunks = content.replace("\n", ".").split("### ")
        return [c for c in raw_chunks if not c.isspace() and c != ""]

    # Seleziona dinamicamente la tecnica di chunking in base a quanto configurato nel file .env
    @staticmethod
    def get_chunks(content: str, candidate_name: str = "") -> list[str]:
        strategy = getattr(Config, "CHUNK_STRATEGY", "semantic_chunking")
        if strategy == "semantic_chunking":
            sc = SemanticChunking(breakpoint_percentile=65, buffer_size=3)
            return sc.chunk_text(content)
        elif strategy == "semantic_sections":
            return DocumentProcessor.chunk_semantic_sections(content, candidate_name)
        elif strategy == "sliding_window":
            chunk_size = getattr(Config, "CHUNK_SIZE", 500)
            chunk_overlap = getattr(Config, "CHUNK_OVERLAP", 100)
            return DocumentProcessor.chunk_sliding_window(
                content, candidate_name, chunk_size, chunk_overlap
            )
        elif strategy == "legacy":
            return DocumentProcessor.chunk_legacy(content)
        else:
            sc = SemanticChunking(breakpoint_percentile=65, buffer_size=3)
            return sc.chunk_text(content)

    # Elabora un singolo documento (PDF, DOCX, XLSX, TXT, ZIP) convertendolo in Markdown e frammentandolo
    def process_single_document(
        self, file_path: str
    ) -> Tuple[List[str], List[Dict], List[str]]:
        extension = os.path.splitext(file_path)[1].lower()
        file_type = self.SUPPORTED_EXTENSIONS.get(extension)

        if not file_type:
            return [], [], []

        # 1. Converte il contenuto in testo Markdown
        content = ""
        if file_type == "archive":
            zip_contents = self._process_zip_file(file_path)
            for inner_filename, zip_content in zip_contents:
                if zip_content:
                    content += f"\n\nFile: {inner_filename}\n{zip_content}"
        else:
            content = self._convert_to_markdown(file_path)

        if not content or not content.strip():
            return [], [], []

        # 2. Estrae recapiti ed estremi del candidato dal testo Markdown
        candidate_info = self.extract_candidate_info(content)

        # 3. Frammenta il testo con il chunking semantico avanzato
        chunks = self.get_chunks(content, candidate_info["candidate_name"])

        # 4. Genera i metadati completi del documento
        file_metadata = self.get_document_metadata(file_path)
        file_metadata.update(candidate_info)
        file_metadata["strategy"] = getattr(Config, "CHUNK_STRATEGY", "semantic_chunking")

        documents = []
        metadatas = []
        ids = []

        for chunk in chunks:
            if chunk and not chunk.isspace():
                documents.append(chunk)
                metadatas.append(dict(file_metadata))
                ids.append(str(uuid.uuid4()))

        return documents, metadatas, ids

    # Sincronizza i file della cartella resumes con il database vettoriale
    def process_documents(self, db) -> Tuple[int, int, int]:
        # Verifica se la strategia di chunking nel file .env e cambiata rispetto a quella gia memorizzata nel DB
        existing_count = db.collection.count()
        if existing_count > 0:
            sample = db.collection.get(limit=1, include=["metadatas"])
            if sample and sample.get("metadatas") and sample["metadatas"][0]:
                saved_strategy = sample["metadatas"][0].get("strategy")
                if saved_strategy and saved_strategy != Config.CHUNK_STRATEGY:
                    print(f"Cambio strategia ({saved_strategy} -> {Config.CHUNK_STRATEGY}). Resetting collection...")
                    db.reset_collection()

        # Mappa tutti i file con estensione supportata presenti nella cartella resumes
        current_files = {
            f: self.get_document_metadata(os.path.join(Config.DOCUMENTS_DIR, f))
            for f in os.listdir(Config.DOCUMENTS_DIR)
            if os.path.splitext(f)[1].lower() in self.SUPPORTED_EXTENSIONS
        }
        print("File supportati rilevati nella cartella:", list(current_files.keys()))

        # Mappa i file gia memorizzati nel database
        existing_files = db.get_tracked_files()
        print("File gia censiti nel database:", list(existing_files.keys()))

        # Calcola le differenze: file da aggiungere, rimuovere o aggiornare
        files_to_add = set(current_files.keys()) - set(existing_files.keys())
        files_to_remove = set(existing_files.keys()) - set(current_files.keys())
        files_to_update = {
            f
            for f in set(current_files.keys()) & set(existing_files.keys())
            if current_files[f]["hash"] != existing_files[f]["hash"]
        }

        print("File da aggiungere:", files_to_add)
        print("File da aggiornare:", files_to_update)
        print("File da rimuovere:", files_to_remove)

        # Elabora le aggiunte e gli aggiornamenti
        for action, files in [("add", files_to_add), ("update", files_to_update)]:
            for filename in files:
                file_path = os.path.join(Config.DOCUMENTS_DIR, filename)
                documents, metadatas, ids = self.process_single_document(file_path)

                if action == "update":
                    db.remove_document_by_source(filename)

                if documents:
                    db.add_documents(documents, metadatas, ids)

        # Rimuove dal database i file che non esistono piu su disco
        for filename in files_to_remove:
            db.remove_document_by_source(filename)

        return len(files_to_add), len(files_to_update), len(files_to_remove)
