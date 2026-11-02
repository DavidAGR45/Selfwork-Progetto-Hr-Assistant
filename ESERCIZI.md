## 01. Sperimentate con diverse tecniche di Chunking

### Analisi dei problemi dell'approccio iniziale (Legacy):
Nel codice originario il chunking veniva effettuato in modo ingenuo:
```python
chunks = file.read().replace('\n', '.').split('### ')
```
Questo causava tre problemi principali:
1. **Distruzione della struttura del testo**: la sostituzione cieca di `\n` con `.` rovinava gli elenchi puntati e la coerenza sintattica delle frasi, peggiorando la qualità dei vettori di embedding.
2. **Chunk vuoti o privi di valore**: intestazioni di categoria come `### ESPERIENZA PROFESSIONALE` o `### COMPETENZE TECNICHE` generavano chunk costituiti dal solo titolo, privi di dettagli o descrizioni lavorative.
3. **Mancanza di contesto nei chunk intermedi**: un frammento di testo a metà del CV (es. `- Python, Docker, Kubernetes`) non conteneva informazioni sull'identità o sul ruolo del candidato, rendendo difficile per la ricerca semantica associare correttamente le competenze alla persona.

### Tecniche implementate in `document_processor.py`:

1. **Semantic Section Chunking con Context Injection (`chunk_semantic_sections` - Default consigliata)**:
   - Suddivide i documenti riconoscendo la struttura gerarchica delle intestazioni Markdown (`###` e `##`).
   - Associa le intestazioni padre senza corpo immediato (es. `### ESPERIENZA PROFESSIONALE`) alle rispettive sotto-sezioni (es. `Sezione: ESPERIENZA PROFESSIONALE > Lead Software Architect | TechScale`).
   - **Context Injection**: antepone ad ogni chunk il prefisso `[Candidato: <Nome>]`, garantendo che ogni vettore conservi l'informazione di chi possiede quelle competenze/esperienze.
   - Preserva intatta la formattazione con ritorni a capo ed elenchi puntati.

2. **Sliding Window con Overlap (`chunk_sliding_window`)**:
   - Raggruppa paragrafi fino al raggiungimento di una dimensione definita (`CHUNK_SIZE`, es. 500 caratteri).
   - Mantiene una sovrapposizione (`CHUNK_OVERLAP`, es. 100 caratteri) tra blocchi contigui, evitando la perdita di contesto a cavallo dei confini dei chunk.
   - Anch'essa integra il contesto del candidato in testa a ciascun frammento.

3. **Approccio Legacy (`chunk_legacy`)**:
   - Mantenuto come riferimento storico per eseguire test e comparazioni dirette di accuratezza rispetto ai nuovi metodi.

### Configurazione delle strategie (`config.py`):
In [`config.py`](hr_assistant/config.py) è ora possibile selezionare facilmente la strategia desiderata:
```python
# Opzioni disponibili: "semantic_sections", "sliding_window", "legacy"
CHUNK_STRATEGY = os.getenv("CHUNK_STRATEGY", "semantic_sections")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
```
All'avvio dell'applicazione (`DocumentProcessor.process_documents(db)`), il sistema verifica automaticamente se la strategia configurata coincide con quella memorizzata nei metadati del database; in caso di cambio strategia, la collezione viene rigenerata al volo in automatico.

---

## 02. Provate ad eliminare la doppia chiamata al modello di linguaggio, quella necessaria a tirare fuori il nome e cognome del candidato. Meglio ancora, provate a tirar fuori anche il numero di telefono ed e-mail

### Passaggi effettuati per risolvere il Punto 02:

1. **Estrazione deterministica dei dati in fase di Ingestion (`document_processor.py`)**:
   - Creato il metodo `DocumentProcessor.extract_candidate_info(content)` che analizza il testo grezzo del CV tramite espressioni regolari (regex).
   - Estrae istantaneamente:
     - **Nome e Cognome**: rilevato dall'intestazione iniziale o dalla riga `Nome:` e normalizzato in formato Title Case.
     - **Email**: individuata tramite pattern per indirizzi email (`[\w\.-]+@[\w\.-]+\.\w+`).
     - **Numero di Telefono**: individuato tramite pattern per prefissi e numerazioni telefoniche (`tel`/`telefono`).
   - In `process_single_document()`, questi dati vengono integrati nei metadati del chunk insieme a `hash`, `last_modified` e `source`, garantendo piena sinergia con il sistema di sincronizzazione incrementale.

2. **Eliminazione della prima chiamata all'LLM a runtime (`__init__.py`)**:
   - Nella funzione `handle_message`, è stata rimossa la lettura del file dal disco (`DocumentProcessor.read_first_lines`) e la chiamata asincrona `LLMHelper.get_candidate_name(...)`.
   - Nome, email e telefono vengono ora recuperati istantaneamente dai metadati del chunk restituito dalla query vettoriale di ChromaDB (`results["metadatas"][0][0]`).
   - Il flusso di chat esegue ora **una sola chiamata al modello di linguaggio** (la generazione della risposta in streaming), dimezzando la latenza complessiva.

3. **Aggiornamento del Prompt con i Contatti (`utils.py`)**:
   - Modificato `LLMHelper.create_prompt` per accogliere ed esporre esplicitamente nel prompt per il modello il nome, l'email e il telefono del candidato selezionato.
   - Rispetta le specifiche del template di step 04, richiedendo la sezione contatti prima dell'indicazione del nome file.

4. **Integrazione con le Action di Chainlit (`__init__.py` & `database.py`)**:
   - Mantenuta la piena compatibilità con i bottoni interattivi di Chainlit (`Statistiche Database` e `Reindex Database`).
   - L'azione `db_reindex` esegue in tempo reale `DocumentProcessor.process_documents(db)` riapplicando le strategie di chunking e l'estrazione contatti.
