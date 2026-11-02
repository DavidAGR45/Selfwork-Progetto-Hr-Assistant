# document_processor.py
import os
import re
import uuid
from config import Config


class DocumentProcessor:
    @staticmethod
    def extract_candidate_info(content: str) -> dict:
        """
        Estrae nome e cognome, email e numero di telefono dal testo del CV.
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
        Gestisce le intestazioni padre (es. '### ESPERIENZA PROFESSIONALE') associandole
        alle rispettive sotto-sezioni, e inietta l'identità del candidato per un recupero semantico mirato.
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
        evitando di spezzare concetti su blocchi distinti.
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
        Tecnica 0 (Legacy): Chunking iniziale naive.
        Sostituzione dei newline con punti e split su '### '.
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
    def process_documents():
        documents = []
        metadatas = []
        ids = []

        for filename in os.listdir(Config.DOCUMENTS_DIR):
            if filename.endswith(".txt"):
                file_path = os.path.join(Config.DOCUMENTS_DIR, filename)
                with open(file_path, "r", encoding="utf-8") as file:
                    raw_content = file.read()

                info = DocumentProcessor.extract_candidate_info(raw_content)
                chunks = DocumentProcessor.get_chunks(raw_content, info["candidate_name"])

                for chunk in chunks:
                    documents.append(chunk)
                    metadatas.append(
                        {
                            "source": filename,
                            "candidate_name": info["candidate_name"],
                            "email": info["email"],
                            "phone": info["phone"],
                            "strategy": getattr(Config, "CHUNK_STRATEGY", "semantic_sections"),
                        }
                    )
                    ids.append(str(uuid.uuid4()))

        return documents, metadatas, ids

    @staticmethod
    def read_first_lines(file_path, n_lines=100):
        with open(file_path, "r", encoding="utf-8") as file:
            return [line.strip() for line, _ in zip(file, range(n_lines))]
