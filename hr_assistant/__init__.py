import chainlit as cl
import ollama
import chromadb
import os, uuid
from chromadb.utils import embedding_functions

## FASE 1 - Lettura Files e Chucking

documents_dir = "resumes"

documents = []
metadatas = []
ids = []

for filename in os.listdir(documents_dir):
    if filename.endswith(".txt"):
        with open(os.path.join(documents_dir, filename), "r") as file:
            chuncks = file.read().replace("\n", ".").split("### ")

            for chunk in chuncks:
                if not chunk.isspace() and not chunk == "":
                    documents.append(chunk)
                    metadatas.append({"source": filename})
                    # Genera un nuovo GUID per ogni chunk
                    guid = str(uuid.uuid4())
                    ids.append(guid)

print(documents, metadatas, ids)

## Fase 2 - Embeddings e inseriemento nel DB Vettoriale

ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="embeddinggemma-2:270m",
)

chroma_client = chromadb.Client()

collection = chroma_client.get_or_create_collection(
    name="CVs", embedding_function=ollama_ef
)

collection.add(documents=documents, metadatas=metadatas, ids=ids)

## FASE 3 - CHAT !!!!


# Funzione chiamata all'inizio della chat per inizializzare la sessione utente
@cl.on_chat_start
def on_chat_start():
    """
    Inizializza la sessione utente con un messaggio del sistema.
    Questo messaggio definisce il ruolo del chatbot.
    """
    cl.user_session.set(
        "messages",
        [
            {
                "role": "system",  # o developer
                "content": """
                      Sei un assistente specializzato nel mondo HR, rispondi in modo professionale, sintetico e pragmatico. Il tuo ruolo è individuare il candidato ideale rispetto alle richieste dell'utente.
                      """,
            }
        ],
    )


# Funzione per gestire i messaggi dell'utente e generare risposte
@cl.on_message
async def handle_message(message: cl.Message):
    """
    Gestisce i messaggi inviati dall'utente, li passa al modello e restituisce le risposte.

    Args:
        message (cl.Message): Messaggio ricevuto dall'utente.
    """

    user_question = message.content

    results = collection.query(query_texts=[user_question], n_results=1)

    ## Mi serve la prima pagina del CV, o meglio le prime 100 righe;
    ## perche' ho bisogno del nome cognome

    def leggi_prime_100_righe(file_path):
        with open(file_path, "r") as file:
            righe = []
            for i, riga in enumerate(file):
                if i < 100:
                    righe.append(riga.strip())
                else:
                    break
        return righe

    # prendo la prima parte del file per leggere il nome del candidato
    filename = results["metadatas"][0][0]["source"]
    context_nome_candidato = leggi_prime_100_righe(
        os.path.join(documents_dir, filename)
    )

    nome = ollama.chat(
        model="bonsai-2:9b",
        messages=[
            {
                "role": "user",
                "content": f"""
                      Dato il seguente contesto individua il nome e cognome del candidato e ritorna solo il nome e cognome del candidato. quello che sto per fornirti e' il curriculum vite del candidato: {context_nome_candidato}
                      """,
            }
        ],
    )

    nome = nome["message"]["content"]

    context = f"CONTESTO: nome file {results['metadatas'][0][0]['source']} ecco il paragrafo piu' significativo: {results['documents'][0][0]}"

    prompt = f"""
        Dato il seguente contesto: 
        [[[
        {context}
        ]]].
        Rispondi alla domanda dell'utente: [[[ {user_question}]]] .
        Spiega che nel file individuato c'e' il profilo piu' adatto. 
        Assicurati di nominare il Nome dei file.
        Assicurati di indicare il nome del candidato: [[[ {nome} ]]].
        Argometa la scelta utilizzando il contenuto del testo individuato nel contesto.
        Se non trovi corrispondenza in nessun cv non inventare."""

    print("/n/n/n")
    print("*" * 80)
    print(nome)
    print("*" * 80)
    print(context)
    print("*" * 80)
    print(prompt)
    print("*" * 80)

    # Recupera i messaggi salvati nella sessione utente
    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": prompt})

    # print(messages)

    # Inizializza un messaggio vuoto per mostrare lo streaming
    response_message = cl.Message(content="")
    await response_message.send()

    try:
        # Invio della richiesta al modello tramite Ollama
        stream = ollama.chat(model="bonsai-2:9b", messages=messages, stream=True)

        # Streaming della risposta del modello verso l'utente
        for chunk in stream:
            # print(chunk["message"]["content"])
            await response_message.stream_token(chunk["message"]["content"])

        # Salva la risposta del modello nella sessione
        messages.append({"role": "assistant", "content": response_message.content})
        await response_message.update()
    except Exception as e:
        # Gestione degli errori
        error_message = f"An error occurred: {str(e)}"
        await cl.Message(content=error_message).send()
        print(error_message)  # Log dell'errore per debugging

    # Aggiorna i messaggi nella sessione utente
    cl.user_session.set("messages", messages)


# Funzione per gestire la fine della chat
@cl.on_chat_end
def on_chat_end():
    """
    Pulizia e messaggio finale alla fine della chat.
    """
    cl.Message(
        content="""
               Grazie per aver utilizzato il nostro assistente. 
               Buona giornata!
               """
    ).send()
