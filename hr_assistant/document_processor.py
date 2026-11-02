# document_processor.py
import os
import re
import uuid
import hashlib
from config import Config


class DocumentProcessor:

    @staticmethod
    def read_first_lines(file_path, n_lines=100):
        with open(file_path, "r", encoding="utf-8") as file:
            return [line.strip() for line, _ in zip(file, range(n_lines))]

    @staticmethod
    def get_file_hash(file_path):
        """Calculate MD5 hash of file content"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    @staticmethod
    def get_document_metadata(file_path):
        """Get document metadata including hash and last modified time"""
        return {
            "hash": DocumentProcessor.get_file_hash(file_path),
            "last_modified": os.path.getmtime(file_path),
            "source": os.path.basename(file_path),
        }

    @staticmethod
    def extract_candidate_info(content: str) -> dict:
        """
        Estrae deterministamente nome e cognome, email e numero di telefono dal testo del CV.
        Risolve il Punto 02 eliminando la necessità di una chiamata LLM aggiuntiva.
        """
        # Nome e cognome
        name = "Candidato"
        name_match = re.search(r'(?i)^nome:\s*(.+)$', content, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip()
        else:
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("### "):
                    header = line.replace("### ", "").strip()
                    if header.upper() not in [
                        "INFORMAZIONI PERSONALI",
                        "CURRICULUM VITAE",
                        "PROFILO PROFESSIONALE",
                    ]:
                        name = header
                        break

        candidate_name = name.title() if name.isupper() else name

        # Email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        email = email_match.group(0).strip() if email_match else "N/D"

        # Telefono
        phone_match = re.search(r'(?i)(?:tel|telefono)[:\s]+([+\d\s]{8,25})', content)
        phone = phone_match.group(1).strip() if phone_match else "N/D"

        return {
            "candidate_name": candidate_name,
            "email": email,
            "phone": phone,
        }

    @staticmethod
    def chunk_semantic_sections(content: str, candidate_name: str = "") -> list[str]:
        """
        Tecnica 1: Semantic Section Chunking.
        Divide il testo in base alle sezioni (### / ##) preservando la formattazione markdown.
        Gestisce le intestazioni padre associandole alle rispettive sotto-sezioni
        e inietta l'identità del candidato in testa a ogni chunk.
        """
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

    @staticmethod
    def chunk_sliding_window(
        content: str,
        candidate_name: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[str]:
        """
        Tecnica 2: Sliding Window con Overlap.
        Crea chunk di dimensione definita con sovrapposizione tra paragrafi,
        iniettando il contesto del candidato.
        """
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

    @staticmethod
    def chunk_legacy(content: str) -> list[str]:
        """
        Tecnica 0 (Legacy): Metodo originale con replace di newline e split su '### '.
        """
        raw_chunks = content.replace("\n", ".").split("### ")
        return [c for c in raw_chunks if not c.isspace() and c != ""]

    @staticmethod
    def get_chunks(content: str, candidate_name: str = "") -> list[str]:
        strategy = getattr(Config, "CHUNK_STRATEGY", "semantic_sections")
        if strategy == "semantic_sections":
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
            return DocumentProcessor.chunk_semantic_sections(content, candidate_name)

    @staticmethod
    def process_single_document(file_path):
        """Process a single document into chunks with enriched metadata"""
        documents = []
        metadatas = []
        ids = []

        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        file_metadata = DocumentProcessor.get_document_metadata(file_path)
        info = DocumentProcessor.extract_candidate_info(content)
        chunks = DocumentProcessor.get_chunks(content, info["candidate_name"])

        for chunk in chunks:
            documents.append(chunk)
            metadatas.append(
                {
                    **file_metadata,
                    "candidate_name": info["candidate_name"],
                    "email": info["email"],
                    "phone": info["phone"],
                    "strategy": getattr(Config, "CHUNK_STRATEGY", "semantic_sections"),
                }
            )
            ids.append(str(uuid.uuid4()))

        return documents, metadatas, ids

    @staticmethod
    def process_documents(db):
        """Process documents and sync with database, handling strategy changes and incremental sync"""
        # Verifica se la strategia di chunking salvata nel database è cambiata
        existing_count = db.collection.count()
        if existing_count > 0:
            sample = db.collection.get(limit=1, include=["metadatas"])
            if sample and sample["metadatas"] and sample["metadatas"][0]:
                saved_strategy = sample["metadatas"][0].get("strategy")
                if saved_strategy != Config.CHUNK_STRATEGY:
                    print(f"Cambio strategia o metadati non aggiornati ({saved_strategy} -> {Config.CHUNK_STRATEGY}). Resetting collection...")
                    db.reset_collection()

        # Get current files in directory
        current_files = {
            f: DocumentProcessor.get_document_metadata(
                os.path.join(Config.DOCUMENTS_DIR, f)
            )
            for f in os.listdir(Config.DOCUMENTS_DIR) if f.endswith(".txt")
        }
        print("Current files in directory:", list(current_files.keys()))

        # Get existing files from database
        existing_files = db.get_tracked_files()
        print("Existing files in db:", list(existing_files.keys()))

        # Identify files to add, update, and remove
        files_to_add = set(current_files.keys()) - set(existing_files.keys())
        files_to_remove = set(existing_files.keys()) - set(current_files.keys())
        files_to_update = {
            f
            for f in set(current_files.keys()) & set(existing_files.keys())
            if current_files[f]["hash"] != existing_files[f]["hash"]
        }

        print("Files to add:", files_to_add)
        print("Files to remove:", files_to_remove)
        print("Files to update:", files_to_update)

        # Process updates and additions
        for action, files in [("add", files_to_add), ("update", files_to_update)]:
            for filename in files:
                file_path = os.path.join(Config.DOCUMENTS_DIR, filename)
                documents, metadatas, ids = DocumentProcessor.process_single_document(file_path)

                if action == "update":
                    # Remove old entries first
                    db.remove_document_by_source(filename)

                # Add new entries
                if documents:
                    db.add_documents(documents, metadatas, ids)

        # Remove deleted files from database
        for filename in files_to_remove:
            db.remove_document_by_source(filename)

        return len(files_to_add), len(files_to_update), len(files_to_remove)
