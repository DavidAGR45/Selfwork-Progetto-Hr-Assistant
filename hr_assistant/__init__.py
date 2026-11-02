import os
import chainlit as cl
from document_processor import DocumentProcessor
from database import Database
from config import Config
from utils import LLMHelper


# Process documents
documents, metadatas, ids = DocumentProcessor.process_documents()

# print("*" * 80)
# print("Chucks, metadata e ids")
# print("*" * 80)
# print(documents, metadatas, ids)

# Initialize database and add documents
db = Database()
existing_count = db.collection.count()
strategy_changed = False
if existing_count > 0:
    res = db.collection.get(limit=1, include=["metadatas"])
    if res["metadatas"] and res["metadatas"][0].get("strategy") != Config.CHUNK_STRATEGY:
        strategy_changed = True

if existing_count == 0 or strategy_changed:
    db.reset_collection()
    db.add_documents(documents, metadatas, ids) 


@cl.on_chat_start
def start():
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


@cl.on_message
async def handle_message(message: cl.Message):
    user_question = message.content
    results = db.query(user_question)

    metadata = results["metadatas"][0][0]
    filename = metadata.get("source", "N/D")
    candidate_name = metadata.get("candidate_name", "Candidato")
    candidate_email = metadata.get("email", "N/D")
    candidate_phone = metadata.get("phone", "N/D")

    context = f"CONTESTO: nome file {filename} ecco il paragrafo piu' significativo: {results['documents'][0][0]}"

    prompt = LLMHelper.create_prompt(
        context, user_question, candidate_name, candidate_email, candidate_phone
    )

    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": prompt})

    # print("*" * 80)
    # print("*" * 80)
    # print("prompt", prompt)
    # print("*" * 80)
    # print("*" * 80)

    response_message = cl.Message(content="")
    await response_message.send()

    try:
        stream = LLMHelper.chat(messages)

        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                await response_message.stream_token(token)

        messages.append({"role": "assistant", "content": response_message.content})
        await response_message.update()

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await cl.Message(content=error_message).send()
        print(error_message)

    cl.user_session.set("messages", messages)


# @cl.on_chat_end
# def end():
#     cl.Message(content="Grazie per aver utilizzato il nostro assistente. Buona giornata!").send()
