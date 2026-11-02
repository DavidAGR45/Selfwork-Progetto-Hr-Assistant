# document_processor.py - Gestione, estrazione e sincronizzazione dei curriculum nel database
import os
import re
import uuid
import hashlib
from config import Config
from semantic_chunking import SemanticChunking


class DocumentProcessor:

    # Legge le prime n_lines righe da un file (utile per ispezionare l'intestazione del CV)
    @staticmethod
    def read_first_lines(file_path, n_lines=100):
        with open(file_path, "r", encoding="utf-8") as file:
            return [line.strip() for line, _ in zip(file, range(n_lines))]

    # Calcola l'hash MD5 del contenuto di un file per verificare se e' stato modificato
    @staticmethod
    def get_file_hash(file_path):
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    # Recupera i metadati di base del documento: hash del contenuto, data di ultima modifica e nome file
    @staticmethod
    def get_document_metadata(file_path):
        return {
            "hash": DocumentProcessor.get_file_hash(file_path),
            "last_modified": os.path.getmtime(file_path),
            "source": os.path.basename(file_path),
        }

    # Estrae con regex nome, email e numero di telefono direttamente dal testo del CV
    # Questa estrazione deterministica elimina la doppia chiamata al modello LLM a runtime
    @staticmethod
    def extract_candidate_info(content: str) -> dict:
        # Cerca il nome e cognome: prima prova con il pattern "Nome: ...", poi cerca nella prima intestazione ###
        name = "Candidato"
        name_match = re.search(r'(?i)^nome:\s*(.+)$', content, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip()
        else:
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("### "):
                    header = line.replace("### ", "").strip()
                    # Salta titoli generici di sezione per prendere solo il nome effettivo
                    if header.upper() not in [
                        "INFORMAZIONI PERSONALI",
                        "CURRICULUM VITAE",
                        "PROFILO PROFESSIONALE",
                    ]:
                        name = header
                        break

        candidate_name = name.title() if name.isupper() else name

        # Cerca l'indirizzo email tramite espressione regolare
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        email = email_match.group(0).strip() if email_match else "N/D"

        # Cerca il recapito telefonico tramite espressione regolare
        phone_match = re.search(r'(?i)(?:tel|telefono)[:\s]+([+\d\s]{8,25})', content)
        phone = phone_match.group(1).strip() if phone_match else "N/D"

        return {
            "candidate_name": candidate_name,
            "email": email,
            "phone": phone,
        }

    # Strategia 1: divide il testo in base alle sezioni Markdown (### e ##)
    # Conserva la struttura logica e inietta il nome del candidato in testa a ciascun frammento
    @staticmethod
    def chunk_semantic_sections(content: str, candidate_name: str = "") -> list[str]:
        lines = content.splitlines()
        chunks = []
        parent_section = ""
        current_section = ""
        current_body = []

        # Funzione interna per creare un frammento con intestazione, contesto e corpo del paragrafo
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

        # Scorre riga per riga per identificare titoli di sezione o testo semplice
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
            # Se aggiungendo il paragrafo si supera la dimensione massima, salva il blocco
            if current_len + para_len > chunk_size and current_chunk:
                full_text = "\n\n".join(current_chunk)
                if candidate_name:
                    full_text = f"[Candidato: {candidate_name}]\n{full_text}"
                chunks.append(full_text)

                # Mantiene l'ultimo paragrafo come sovrapposizione se rientra nell'overlap
                if chunk_overlap > 0 and len(current_chunk[-1]) <= chunk_overlap:
                    current_chunk = [current_chunk[-1]]
                    current_len = len(current_chunk[0])
                else:
                    current_chunk = []
                    current_len = 0

            current_chunk.append(para)
            current_len += para_len

        # Aggiunge l'ultimo chunk rimanente
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
            # Chunking semantico rifattorizzato a oggetti (Step 06)
            sc = SemanticChunking()
            return sc.chunk_text(content)
        elif strategy == "semantic_sections":
            # Chunking a sezioni Markdown con iniezione del contesto candidato (Step 02)
            return DocumentProcessor.chunk_semantic_sections(content, candidate_name)
        elif strategy == "sliding_window":
            # Chunking a finestra scorrevole con sovrapposizione tra paragrafi (Step 02)
            chunk_size = getattr(Config, "CHUNK_SIZE", 500)
            chunk_overlap = getattr(Config, "CHUNK_OVERLAP", 100)
            return DocumentProcessor.chunk_sliding_window(
                content, candidate_name, chunk_size, chunk_overlap
            )
        elif strategy == "legacy":
            # Approccio iniziale originario
            return DocumentProcessor.chunk_legacy(content)
        else:
            return SemanticChunking.chunk_it(content)

    # Elabora un singolo file: estrae contatti, frammenta il testo e crea i metadati per ChromaDB
    @staticmethod
    def process_single_document(file_path):
        documents = []
        metadatas = []
        ids = []

        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        file_metadata = DocumentProcessor.get_document_metadata(file_path)
        info = DocumentProcessor.extract_candidate_info(content)
        chunks = DocumentProcessor.get_chunks(content, info["candidate_name"])

        # Associa i metadati estratti ad ogni singolo frammento generato
        for chunk in chunks:
            documents.append(chunk)
            metadatas.append(
                {
                    **file_metadata,
                    "candidate_name": info["candidate_name"],
                    "email": info["email"],
                    "phone": info["phone"],
                    "strategy": getattr(Config, "CHUNK_STRATEGY", "semantic_chunking"),
                }
            )
            # GUID univoco per ogni chunk inserito nel database
            ids.append(str(uuid.uuid4()))

        return documents, metadatas, ids

    # Sincronizza i file della cartella resumes con il database vettoriale
    @staticmethod
    def process_documents(db):
        # Verifica se la strategia di chunking nel file .env e cambiata rispetto a quella gia memorizzata nel DB
        existing_count = db.collection.count()
        if existing_count > 0:
            sample = db.collection.get(limit=1, include=["metadatas"])
            if sample and sample["metadatas"] and sample["metadatas"][0]:
                saved_strategy = sample["metadatas"][0].get("strategy")
                if saved_strategy != Config.CHUNK_STRATEGY:
                    print(f"Cambio strategia o metadati non aggiornati ({saved_strategy} -> {Config.CHUNK_STRATEGY}). Resetting collection...")
                    db.reset_collection()

        # Mappa i file attualmente presenti nella cartella resumes
        current_files = {
            f: DocumentProcessor.get_document_metadata(
                os.path.join(Config.DOCUMENTS_DIR, f)
            )
            for f in os.listdir(Config.DOCUMENTS_DIR)
            if f.endswith(".txt")
        }
        print("Current files in directory:", list(current_files.keys()))

        # Mappa i file gia memorizzati nel database
        existing_files = db.get_tracked_files()
        print("Existing files in db:", list(existing_files.keys()))

        # Calcola le differenze: file da aggiungere, rimuovere o aggiornare (con hash diverso)
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

        # Elabora le aggiunte e gli aggiornamenti
        for action, files in [("add", files_to_add), ("update", files_to_update)]:
            for filename in files:
                file_path = os.path.join(Config.DOCUMENTS_DIR, filename)
                documents, metadatas, ids = DocumentProcessor.process_single_document(file_path)

                # Se si tratta di un aggiornamento, prima elimina i vecchi chunk associati a quel file
                if action == "update":
                    db.remove_document_by_source(filename)

                # Aggiunge i nuovi chunk al database
                if documents:
                    db.add_documents(documents, metadatas, ids)

        # Rimuove dal database i file che non esistono piu su disco
        for filename in files_to_remove:
            db.remove_document_by_source(filename)

        return len(files_to_add), len(files_to_update), len(files_to_remove)
