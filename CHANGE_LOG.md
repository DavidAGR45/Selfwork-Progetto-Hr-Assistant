# Changelog del Progetto HR Assistant

Tutti i progressi e le evoluzioni architetturali del progetto, dal setup iniziale fino all'orchestrazione avanzata dei modelli.

---

## 00. Setup Iniziale e Chat Base (Chainlit)
* **Obiettivo**: Configurazione dell'ambiente di sviluppo moderno e creazione della prima interfaccia conversazionale interattiva.
* **Cosa consisteva l'esercizio**:
  - Inizializzazione del progetto con il gestore di pacchetti **Poetry** (`pyproject.toml`) e definizione dell'albero dei sorgenti.
  - Configurazione delle dipendenze core (`chainlit`, `chromadb`, `openai`).
  - Creazione del server Chainlit di base (`@cl.on_message`) con gestione dei messaggi in stile echo per verificare la comunicazione bidirezionale su WebSocket.
  - Setup dei template e della configurazione multilingua di Chainlit (`.chainlit/config.toml`).

---

## 01. Ingestion Documenti, Database Vettoriale e RAG Base
* **Obiettivo**: Creazione della prima pipeline RAG (Retrieval-Augmented Generation) per l'interrogazione dei curriculum.
* **Cosa consisteva l'esercizio**:
  - Ingestion automatica di file di testo (`.txt`) contenenti curriculum vitae dalla cartella `resumes/`.
  - Prima strategia di chunking rudimentale basata su separatori manuali in formato Markdown (`### `).
  - Generazione di identificativi univoci UUID per ciascun frammento e associazione dei metadati essenziali (`source`).
  - Inizializzazione di **ChromaDB** in memoria con funzione di embedding fornita da **Ollama locale** (`embeddinggemma-2:270m`).
  - Implementazione della chat RAG su Chainlit: recupero per similarità del frammento più pertinente alla domanda dell'utente e generazione della risposta tramite LLM con prompt specializzato per le risorse umane.

---

## 02. Architettura Modulare, Regex Contatti e Multi-Provider
* **Obiettivo**: Riorganizzazione dell'intero applicativo secondo i principi OOP e della separazione delle responsabilità (Separation of Concerns).
* **Cosa consisteva l'esercizio**:
  - Refactoring del codice monolitico in moduli specializzati:
    - `config.py`: gestione centralizzata delle variabili d'ambiente (`.env`), provider attivi (`ollama`, `groq`, `openai`) e parametri dei modelli.
    - `database.py`: incapsulamento del client ChromaDB con persistenza su disco locale (`data/chromadb`).
    - `document_processor.py`: classe dedicata alla lettura dei file e all'estrazione automatica dei dati di contatto (nome candidato, email e telefono) tramite espressioni regolari (regex) applicate ai testi dei CV.
    - `utils.py`: classe `LLMHelper` per l'interazione standardizzata con le API e per la formattazione dei prompt.
  - Introduzione del supporto per risposte in **streaming asincrono** (`stream_token`) su Chainlit, migliorando drasticamente la reattività della UI.

---

## 03. Sincronizzazione Incrementale dei File con MD5
* **Obiettivo**: Ottimizzazione del processo di ingestion per evitare reindicizzazioni integrali e prevenire frammenti duplicati o orfani.
* **Cosa consisteva l'esercizio**:
  - Implementazione del calcolo dell'hash crittografico **MD5** per ogni file nella cartella `resumes/`, memorizzato nei metadati dei frammenti indicizzati su ChromaDB.
  - Creazione di un algoritmo di sincronizzazione differenziale in fase di avvio:
    - **Nuovi file**: identificazione e indicizzazione mirata dei soli documenti appena aggiunti.
    - **File modificati**: rilevamento tramite discordanza dell'hash MD5, rimozione atomica dei vecchi chunk dal database e re-indicizzazione della versione aggiornata.
    - **File eliminati**: rilevamento dei file rimossi dal disco e cancellazione selettiva dei chunk corrispondenti dalla collezione vettoriale.
  - Riduzione sostanziale dell'impiego di CPU/disco e mantenimento dell'integrità assoluta del database.

---

## 04. Dashboard Statistiche e Azioni Interattive
* **Obiettivo**: Dotare l'interfaccia utente di pulsanti operativi per monitorare lo stato del database vettoriale e comandare le operazioni.
* **Cosa consisteva l'esercizio**:
  - Creazione di bottoni interattivi (`cl.Action`) mostrati all'avvio della sessione chat:
    - **Pulsante "Statistiche Database" (`db_stats`)**: interroga la collezione ChromaDB per conteggiare frammenti totali e file censiti, inoltrando le metriche a un prompt specializzato di `LLMHelper.get_db_stats` che formatta un riassunto con elenchi puntati e calcolo della percentuale di ripartizione.
    - **Pulsante "Reindex Database" (`db_reindex`)**: esegue on-demand la sincronizzazione della cartella curriculum informando l'operatore sul numero di file aggiunti, modificati o eliminati.

---

## 05. Algoritmo di Semantic Chunking su Testi Complessi
* **Obiettivo**: Superare i limiti del chunking statico a caratteri fissi implementando una suddivisione guidata dal significato semantico del testo.
* **Cosa consisteva l'esercizio**:
  - Introduzione di un saggio lungo e discorsivo (`mit.txt`, "How to Start a Startup" di Paul Graham) come banco di prova avanzato.
  - Segmentazione del testo in singole frasi arricchite con finestre di contesto adiacenti (`buffer_size=1`).
  - Misurazione della distanza semantica tra finestre di frasi consecutive tramite distanza del coseno (`1 - cosine_similarity`) sui rispettivi embedding vettoriali.
  - Identificazione dei confini naturali di cambio tema ("breakpoint") determinati statisticamente tramite soglia a percentile (95° percentile).
  - Raggruppamento delle frasi in chunk semanticamente coesi e indipendenti dalla lunghezza fissa dei caratteri.

---

## 06. Refactoring OOP del Semantic Chunking
* **Obiettivo**: Standardizzazione e ingegnerizzazione della pipeline di chunking semantico in una classe riutilizzabile.
* **Cosa consisteva l'esercizio**:
  - Creazione della classe `SemanticChunking` in `hr_assistant/semantic_chunking.py`.
  - Scorporo delle responsabilità in metodi modulari:
    - `_process_sentences`: segmentazione regex e concatenazione del buffer contestuale.
    - `_calculate_distances`: generazione degli embedding ed elaborazione delle distanze del coseno.
    - `_calculate_threshold`: estrazione della soglia limite dinamica tramite `np.percentile`.
    - `_create_chunks`: assemblaggio finale delle frasi nei rispettivi chunk semantici.
  - Integrazione nativa all'interno di `DocumentProcessor`, rendendolo la strategia di chunking di riferimento del sistema.

---

## 06.1. Custom Embedding e Supporto SentenceTransformer Locale
* **Obiettivo**: Unificazione del motore di embedding tra ChromaDB e Semantic Chunking con supporto multi-provider sia locale che cloud.
* **Cosa consisteva l'esercizio**:
  - Creazione della classe unificata `CustomEmbeddingFunction` (ereditata da `chromadb.api.types.EmbeddingFunction`) in `hr_assistant/custom_embedding.py`.
  - Supporto configurabile da ambiente (`EMBEDDING_PROVIDER`):
    - `ollama`: inferenza vettoriale locale con batching ad alte prestazioni (`ollama.embed`).
    - `local`: modelli Hugging Face caricati ed eseguiti direttamente tramite `SentenceTransformer` (PyTorch) con salvataggio e cache su disco (`modelli/mio_modello`).
    - `openai`: wrapper ufficiale `OpenAIEmbeddingFunction` per embedding cloud (`text-embedding-3-small`).
  - Garanzia di coerenza vettoriale: sia la matrice di distanza del Semantic Chunking sia l'indice della collezione di ChromaDB impiegano lo stesso identico modello, azzerando discrepanze di dimensionalità.

---

## 06.2. Riconoscimento dell'Intento Utente e Memoria di Sessione
* **Obiettivo**: Abilitare un dialogo naturale multi-turno permettendo al sistema di distinguere tra la ricerca di un nuovo profilo e richieste di approfondimento su profili già estratti.
* **Cosa consisteva l'esercizio**:
  - Implementazione della funzione asincrona `LLMHelper.classify_intent`:
    - `"search_cv"`: identifica l'intenzione di individuare una nuova candidatura o competenza tecnica. Esegue la ricerca vettoriale su ChromaDB e memorizza il candidato in sessione.
    - `"info_cv"`: riconosce domande di follow-up (es. "quali sono i suoi contatti?", "parlami delle sue esperienze lavorative") relative all'ultimo profilo mostrato.
  - Utilizzo di `cl.user_session` per salvare e mantenere in memoria il contesto dell'ultimo CV, il file sorgente e i recapiti del candidato.
  - Eliminazione di chiamate vettoriali ridondanti per i follow-up e gestione di messaggi di guida se l'utente pone domande specifiche prima di aver cercato un profilo.

---

## 07. Supporto Documenti Eterogenei (MarkItDown) e Suddivisione Frasi Avanzata
* **Obiettivo**: Estendere l'ingestion dell'assistente HR a documenti in formati eterogenei del mondo reale (PDF, DOCX, PPTX, XLSX, CSV, HTML, archivi ZIP), superando il vincolo dei soli file di testo semplice (`.txt`).
* **Cosa consisteva l'esercizio**:
  - Adozione della libreria Microsoft **`markitdown`** (`poetry add markitdown`) per la conversione universale ad alta fedeltà di documenti ricchi in testo Markdown strutturato.
  - Mappatura granulare delle estensioni supportate (`SUPPORTED_EXTENSIONS`) con classificazione per tipologia (`document`, `presentation`, `spreadsheet`, `data`, `web`, `archive`) e arricchimento dei metadati vettoriali (`file_type`, `mime_type`, `extension`).
  - Gestione trasparente degli archivi `.zip`: estrazione in cartella temporanea (`tempfile.TemporaryDirectory`) e scansione ricorsiva dei documenti interni supportati.
  - Introduzione del metodo `_split_into_sentences` in `SemanticChunking`: previene il rischio che documenti non convenzionali o privi di punteggiatura standard (es. slide PPTX, celle Excel, dump di PDF) vengano interpretati come un'unica frase gigante, applicando un fallback intelligente a più livelli (newline, punti e virgola, due punti e virgole).
  - Taratura ottimizzata della soglia di chunking semantico (`breakpoint_percentile=65`, `buffer_size=3`) per una maggiore granularità nella suddivisione dei temi.

---

## 08. Upload File da Interfaccia Chat e Gestione Ciclo di Vita del Database
* **Obiettivo**: Rendere l'assistente HR completamente interattivo nell'acquisizione dei curriculum, permettendo all'utente di caricare file (singoli o multipli) direttamente tramite l'interfaccia Chainlit con indicizzazione vettoriale immediata, e fornendo comandi completi per il controllo del ciclo di vita del database vettoriale.
* **Cosa consisteva l'esercizio**:
  - **Upload interattivo di documenti (`message.elements`)**:
    - Intercettazione degli allegati caricati dall'utente tramite drag-and-drop o pulsante di allegato nella chat.
    - Validazione del formato dei file tramite `DocumentProcessor.SUPPORTED_EXTENSIONS` per garantire che vengano processati solo tipi supportati.
    - Archiviazione sicura nella cartella di destinazione `resumes/` tramite `shutil.move`.
    - Pipeline di ingestion al volo (`_process_and_index_file`): conversione in Markdown, estrazione dei dati del candidato, chunking semantico e inserimento immediato dei nuovi embedding in ChromaDB con messaggi di conferma dettagliati in tempo reale.
    - Gestione elegante dei carichi di lavoro: supporto per l'invio di soli file (senza testo), file multipli in parallelo, oppure file accompagnati da query di ricerca.
  - **Azione di reset totale del database (`db_remove`)**:
    - Implementazione del metodo `db.delete_collection()` in `Database` per eliminare e ripristinare la collezione vettoriale senza necessità di riavviare l'applicazione.
    - Aggiunta del pulsante interattivo "Svuota completamente il Database" nella schermata iniziale, con notifica guidata per l'utente sulla necessità di eseguire la reindicizzazione (`db_reindex`).
    - Aggiunta dell'azione dinamica di ricalcolo statistiche per monitorare l'evoluzione dei frammenti e dei documenti dopo ogni upload o cancellazione.
  - **Starters di onboarding (`@cl.set_starters`)**:
    - Configurazione di schede di avvio rapido con prompt predefiniti (es. "Ricerca candidato con competenze di un saldatore") per testare all'istante le capacità dell'assistente.


