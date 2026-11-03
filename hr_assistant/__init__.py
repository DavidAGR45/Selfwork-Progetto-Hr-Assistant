# __init__.py - Entry point dell'assistente HR con Chainlit
import os
import shutil
import chainlit as cl
from document_processor import DocumentProcessor
from database import Database
from config import Config
from utils import LLMHelper

# Inizializza il database vettoriale ChromaDB
db = Database()

# Inizializza il processore documenti MarkItDown e sincronizza i file eterogenei con il database (Step 07)
dp = DocumentProcessor()
added, updated, removed = dp.process_documents(db)
print(f"Document sync complete: {added} added, {updated} updated, {removed} removed")


# Starter predefiniti per avviare rapidamente ricerche comuni nell'interfaccia Chainlit (Step 08)
@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Ricerca candidato",
            message="Cercami un candidato che abbia le competenze di un saldatore",
            icon="/public/idea.svg",
        ),
    ]


# Gestione del pulsante per mostrare le statistiche del database
@cl.action_callback("db_stats")
async def on_action(action: cl.Action):
    # Recupera le statistiche numeriche dalla collezione di ChromaDB
    db_info = db.get_stats()
    # Chiamata asincrona a LLM per generare una risposta formattata senza bloccare l'interfaccia
    response = await LLMHelper.get_db_stats(db_info)
    # Mostra il pulsante per permettere all'utente di ricalcolare le statistiche dopo nuove modifiche (Step 08)
    actions = [
        cl.Action(
            name="db_stats",
            icon="mouse-pointer-click",
            payload={"value": "db_stats"},
            label="Ricalcola Statistiche Database",
        ),
    ]
    await cl.Message(content=response, actions=actions).send()


# Gestione del pulsante per forzare la reindicizzazione dei curriculum
@cl.action_callback("db_reindex")
async def on_action(action: cl.Action):
    # Rielabora i documenti e aggiorna i frammenti nel database
    added, updated, removed = dp.process_documents(db)
    message = f"DB reindicizzato con successo. Document sync complete: {added} added, {updated} updated, {removed} removed"
    await cl.Message(message).send()


# Gestione del pulsante per azzerare completamente il database vettoriale (Step 08)
@cl.action_callback("db_remove")
async def on_action(action: cl.Action):
    db.delete_collection()
    message = "Il database e' stato completamente rimosso. E' necessario lanciare il reindex."
    await cl.Message(message).send()


# Pulsante di test / saluto
@cl.action_callback("say_hello")
async def on_action(action: cl.Action):
    action = action.payload["value"]
    await cl.Message(f"Hello {action}").send()


# Funzione chiamata all'avvio della chat per inizializzare l'interfaccia e la sessione
@cl.on_chat_start
async def start():
    # Pulsanti di azione interattivi mostrati all'avvio (incluso lo svuotamento DB)
    actions = [
        cl.Action(
            name="db_stats",
            icon="mouse-pointer-click",
            payload={"value": "db_stats"},
            label="Statistiche Database",
        ),
        cl.Action(
            name="db_reindex",
            icon="mouse-pointer-click",
            payload={"value": "db_reindex"},
            label="Reindex Database",
        ),
        cl.Action(
            name="db_remove",
            icon="mouse-pointer-click",
            payload={"value": "db_remove"},
            label="Svuota completamente il Database",
        ),
    ]

    await cl.Message(content="Informazioni del sistema:", actions=actions).send()

    # Messaggio di sistema per definire il ruolo dell'assistente HR
    cl.user_session.set(
        "messages",
        [
            {
                "role": "system",
                "content": """
                    Sei un assistente specializzato nel mondo HR, rispondi in modo professionale, sintetico e pragmatico.
                    Il tuo ruolo è individuare il candidato ideale rispetto alle richieste dell'utente.
                """,
            }
        ],
    )


# Elabora e indicizza un singolo documento caricato dall'utente (Step 08)
async def _process_and_index_file(file_path: str, file_name: str) -> str:
    documents, metadatas, ids = dp.process_single_document(file_path)
    if documents:
        db.add_documents(documents, metadatas, ids)
        return f"File '{file_name}' caricato e indicizzato con successo."
    return f"Errore nel processare il file '{file_name}'."


# Sposta il file caricato nella cartella resumes e ne avvia l'indicizzazione immediata (Step 08)
async def _file_upload(file) -> str:
    file_name = file.name
    src_file_path = file.path
    dst_file_path = os.path.join(Config.DOCUMENTS_DIR, file_name)
    os.makedirs(Config.DOCUMENTS_DIR, exist_ok=True)
    shutil.move(src_file_path, dst_file_path)
    return await _process_and_index_file(dst_file_path, file_name)


# Funzione per gestire i messaggi inviati dall'utente
@cl.on_message
async def handle_message(message: cl.Message):
    # 1. Gestione del caricamento di file dall'interfaccia chat (Step 08)
    if message.elements:
        await cl.Message(content="Caricamento e indicizzazione documenti in corso...").send()

        # Filtra solo i file che hanno un'estensione supportata
        files = [
            file
            for file in message.elements
            if os.path.splitext(file.name.lower())[1] in DocumentProcessor.SUPPORTED_EXTENSIONS
        ]

        if files:
            results = [await _file_upload(file) for file in files]
        else:
            results = ["Nessun file con formato supportato rilevato tra gli allegati."]

        result_message = "\n".join(results)
        await cl.Message(content=result_message).send()
        await cl.Message(content=f"Completato: {len(files)} file elaborati.").send()

    user_question = message.content

    # Se l'utente ha solamente caricato dei file senza inserire una domanda di testo, conclude qui
    if not user_question or not user_question.strip():
        return

    # 2. Determina l'intenzione dell'utente tramite LLM ("search_cv" oppure "info_cv")
    intent = await LLMHelper.classify_intent(user_question)

    # 2. Se l'intento e cercare un nuovo CV o profilo
    if intent == "search_cv":
        # Query di ricerca semantica nel database vettoriale (estrae i 3 frammenti piu pertinenti)
        results = db.query(user_question, 3)

        # Verifica di sicurezza per evitare errori se la collezione e vuota
        if not results or not results.get("documents") or not results["documents"][0]:
            await cl.Message(
                content="Nessun profilo o documento trovato nel database per questa richiesta.\n"
                "Prova con altre parole chiave o con una descrizione piu dettagliata."
            ).send()
            return

        # Recupera i dati del candidato direttamente dai metadati del chunk (evita la doppia chiamata a LLM)
        metadata = results["metadatas"][0][0]
        filename = metadata.get("source", "N/D")
        candidate_name = metadata.get("candidate_name", "Candidato")
        candidate_email = metadata.get("email", "N/D")
        candidate_phone = metadata.get("phone", "N/D")

        # Contesto con nome file e testo del frammento piu significativo trovato
        context = f"CONTESTO: nome file {filename} ecco il paragrafo piu' significativo: {results['documents'][0][0]}"

        # Salva il contesto e i dati del candidato nella sessione utente per gestire eventuali domande successive (follow-up)
        cl.user_session.set("last_cv_context", context)
        cl.user_session.set("last_cv_filename", filename)
        cl.user_session.set("last_candidate_name", candidate_name)
        cl.user_session.set("last_candidate_email", candidate_email)
        cl.user_session.set("last_candidate_phone", candidate_phone)

        # Costruzione del prompt finale arricchito con domanda, contesto e recapiti del candidato
        prompt = LLMHelper.create_prompt(
            context, user_question, candidate_name, candidate_email, candidate_phone
        )

    # 3. Se l'intento e chiedere informazioni aggiuntive su un CV gia individuato in precedenza
    else:
        last_context = cl.user_session.get("last_cv_context", "")

        # Se non c'e ancora un CV di riferimento nella sessione, guida l'utente a cercarne prima uno
        if not last_context:
            avviso = (
                "Non ci sono ancora profili a cui fare riferimento in questa conversazione.\n"
                "Prova prima a cercare un candidato, ad esempio:\n"
                "- 'Cerco uno sviluppatore Python senior'\n"
                "- 'Chi ha esperienza in controllo di gestione?'"
            )
            await cl.Message(content=avviso).send()
            return

        # Recupera i dati del candidato salvati nella sessione
        candidate_name = cl.user_session.get("last_candidate_name", "Candidato")
        candidate_email = cl.user_session.get("last_candidate_email", "N/D")
        candidate_phone = cl.user_session.get("last_candidate_phone", "N/D")

        # Costruisce il prompt per rispondere alla domanda di follow-up mantenendo il contesto del CV gia trovato
        prompt = LLMHelper.create_prompt(
            last_context, user_question, candidate_name, candidate_email, candidate_phone
        )

    # Recupera la cronologia dei messaggi della sessione corrente e appende il nuovo prompt
    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": prompt})

    # Inizializza un messaggio vuoto per inviare la risposta in streaming
    response_message = cl.Message(content="")
    await response_message.send()

    try:
        # Chiamata asincrona al modello per lo streaming continuo dei token (non congela il loop di eventi)
        stream = await LLMHelper.chat(messages)

        # Invia i token in modo asincrono verso l'interfaccia Chainlit
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                await response_message.stream_token(token)

        # Salva la risposta completata nella cronologia della sessione
        messages.append({"role": "assistant", "content": response_message.content})
        await response_message.update()

    except Exception as e:
        # Gestione errori in caso di problemi di comunicazione con il modello
        error_message = f"An error occurred: {str(e)}"
        await cl.Message(content=error_message).send()
        print(error_message)

    # Salva la cronologia aggiornata nella sessione utente
    cl.user_session.set("messages", messages)


# @cl.on_chat_end
# def end():
#     # Messaggio di saluto alla chiusura della sessione chat
#     cl.Message(content="Grazie per aver utilizzato il nostro assistente. Buona giornata!").send()
