# utils.py
from config import Config
from openai import OpenAI, AsyncOpenAI

client = OpenAI(base_url=Config.AI_API_URL, api_key=Config.AI_API_KEY)
async_client = AsyncOpenAI(base_url=Config.AI_API_URL, api_key=Config.AI_API_KEY)


class LLMHelper:

    @staticmethod
    def chat(messages):
        return client.chat.completions.create(
            model=Config.LLM_MODEL, messages=messages, stream=True
        )

    @staticmethod
    async def get_candidate_name(context):
        response = await async_client.chat.completions.create(
            model=Config.LLM_MODEL_LOW,
            messages=[
                {
                    "role": "user",
                    "content": f"""
                      Dato il seguente contesto individua il nome e cognome del candidato e ritorna solo il nome e cognome del candidato. Quello che sto per fornirti e' il curriculum vite del candidato: {context}
                      """,
                }
            ],
        )
        return response.choices[0].message.content

    @staticmethod
    async def get_db_stats(context):
        prompt = f"""Dati del database:
{context}

Il tuo compito è descrivere in modo sintetico le statistiche sopra indicate.
Formatta la risposta esattamente con questa struttura e spaziatura con punti elenco (non scrivere tutto attaccato in un unico paragrafo):

Ecco una sintesi delle statistiche contenute nel database dei frammenti indicizzati:

Collezione "[Nome Collezione]"

• Numero Totale Frazioni: [Numero totale Frammenti]
• Numero di Dati Correttamente Elaborati: [Numero Files Elaborati]

[Paragrafo con il calcolo della percentuale ed una breve spiegazione finale]."""

        response = await async_client.chat.completions.create(
            model=Config.LLM_MODEL_LOW,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def create_prompt(context, question, candidate_name="Candidato", email="N/D", phone="N/D"):
        return f"""
            Dato il seguente contesto: 
            [[[
            {context}
            ]]].
            Rispondi alla domanda dell'utente: [[[ {question}]]].
            Spiega che nel file individuato c'e' il profilo piu' adatto. 
            Argomenta la scelta utilizzando il contenuto del testo individuato nel contesto.
            Alla fine crea una sezione per i contatti del candidato indicando con precisione:
            - Nome: [[[ {candidate_name} ]]]
            - Email: [[[ {email} ]]]
            - Telefono: [[[ {phone} ]]]
            Dopo la sezione dei contatti indica il Nome del file del cv, non lo nominare mai prima di questa sezione.
            Se non trovi corrispondenza in nessun cv non inventare.
        """
