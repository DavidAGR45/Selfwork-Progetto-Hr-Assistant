# __init__.py - Entry point dell'assistente HR con Chainlit
import os
import chainlit as cl
from document_processor import DocumentProcessor
from database import Database
from config import Config
from utils import LLMHelper

# Inizializza il database vettoriale ChromaDB
db = Database()

# Sincronizza i file della cartella resumes con il database (aggiunge nuovi, aggiorna modificati, rimuove eliminati)
added, updated, removed = DocumentProcessor.process_documents(db)
print(f"Document sync complete: {added} added, {updated} updated, {removed} removed")


# Gestione del pulsante per mostrare le statistiche del database
@cl.action_callback("db_stats")
async def on_action(action: cl.Action):
    # Recupera le statistiche numeriche dalla collezione di ChromaDB
    db_info = db.get_stats()
    # Chiamata asincrona a LLM per generare una risposta formattata senza bloccare l'interfaccia
    response = await LLMHelper.get_db_stats(db_info)
    await cl.Message(response).send()


# Gestione del pulsante per forzare la reindicizzazione dei curriculum
@cl.action_callback("db_reindex")
async def on_action(action: cl.Action):
    # Rielabora i documenti e aggiorna i frammenti nel database
    added, updated, removed = DocumentProcessor.process_documents(db)
    message = f"DB reindicizzato con successo. Document sync complete: {added} added, {updated} updated, {removed} removed"
    await cl.Message(message).send()


# Pulsante di test / saluto
@cl.action_callback("say_hello")
async def on_action(action: cl.Action):
    action = action.payload["value"]
    await cl.Message(f"Hello {action}").send()


# Funzione chiamata all'avvio della chat per inizializzare l'interfaccia e la sessione
@cl.on_chat_start
async def start():
    # Pulsanti di azione interattivi mostrati all'avvio
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


# Funzione per gestire i messaggi inviati dall'utente
@cl.on_message
async def handle_message(message: cl.Message):
    user_question = message.content

    # Query di ricerca semantica nel database vettoriale (estrae i 3 frammenti piu pertinenti)
    results = db.query(user_question, 3)

    # Verifica di sicurezza per evitare errori se la collezione e vuota
    if not results or not results.get("documents") or not results["documents"][0]:
        await cl.Message(content="Nessun profilo o documento trovato nel database per questa richiesta.").send()
        return

    # Recupera i dati del candidato direttamente dai metadati del chunk (evita la doppia chiamata a LLM)
    metadata = results["metadatas"][0][0]
    filename = metadata.get("source", "N/D")
    candidate_name = metadata.get("candidate_name", "Candidato")
    candidate_email = metadata.get("email", "N/D")
    candidate_phone = metadata.get("phone", "N/D")

    # Contesto con nome file e testo del frammento piu significativo trovato
    context = f"CONTESTO: nome file {filename} ecco il paragrafo piu' significativo: {results['documents'][0][0]}"

    # Costruzione del prompt finale arricchito con domanda, contesto e recapiti del candidato
    prompt = LLMHelper.create_prompt(
        context, user_question, candidate_name, candidate_email, candidate_phone
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
