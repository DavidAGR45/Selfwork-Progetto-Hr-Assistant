# utils.py - Funzioni helper per la comunicazione con i modelli di linguaggio (LLM)
from config import Config
from openai import OpenAI, AsyncOpenAI

# Inizializza il client sincrono standard per lo streaming dei messaggi
client = OpenAI(base_url=Config.AI_API_URL, api_key=Config.AI_API_KEY)

# Inizializza il client asincrono per evitare che chiamate lunghe (es. statistiche) blocchino l'interfaccia Chainlit
async_client = AsyncOpenAI(base_url=Config.AI_API_URL, api_key=Config.AI_API_KEY)


class LLMHelper:

    # Invia la lista dei messaggi al modello in streaming asincrono (non blocca l'event loop di Chainlit)
    @staticmethod
    async def chat(messages):
        return await async_client.chat.completions.create(
            model=Config.LLM_MODEL, messages=messages, stream=True
        )

    # Metodo di riserva asincrono per identificare nome e cognome tramite LLM (usato prima dell'estrazione regex)
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
        return response.choices[0].message.content or ""

    # Classifica l'intento dell'utente in modo asincrono: "search_cv" (ricerca nuovo) o "info_cv" (approfondimento)
    @staticmethod
    async def classify_intent(user_question):
        intent_prompt = f"""
Sei un assistente AI che aiuta a gestire la selezione del personale e le domande sui CV.
Classifica la seguente richiesta dell'utente in una delle due categorie:
- "search_cv": Se l'utente sta cercando un nuovo candidato o profilo (es. "cerco uno sviluppatore", "chi sa usare Docker?").
- "info_cv": Se l'utente sta chiedendo informazioni o chiarimenti su un candidato già trovato in precedenza (es. "quali sono i suoi contatti?", "quanti anni di esperienza ha?", "parlami dei suoi hobby").

Domanda dell'utente: "{user_question}"

Rispondi unicamente con "search_cv" o "info_cv", senza aggiungere altro testo o punteggiatura.
"""
        response = await async_client.chat.completions.create(
            model=Config.LLM_MODEL_LOW,
            messages=[{"role": "user", "content": intent_prompt}],
        )
        content = (response.choices[0].message.content or "").strip().lower()
        if "info_cv" in content:
            return "info_cv"
        return "search_cv"

    # Chiede al modello di formattare le metriche del database a elenco puntato con spiegazione della percentuale
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

    # Costruisce il prompt dettagliato per l'assistente HR con contesto, domanda e recapiti del candidato
    @staticmethod
    def create_prompt(
        context, question, candidate_name="Candidato", email="N/D", phone="N/D"
    ):
        # Se il documento e un CV valido con dati di contatto, include la scheda candidato
        has_candidate = candidate_name not in ["Candidato", "N/D"] or email != "N/D" or phone != "N/D"

        if has_candidate:
            contacts_instruction = f"""
            Spiega che nel file individuato c'e' il profilo piu' adatto.
            Argomenta la scelta utilizzando il contenuto del testo individuato nel contesto.
            Alla fine crea una sezione per i contatti del candidato indicando con precisione:
            - Nome: [[[ {candidate_name} ]]]
            - Email: [[[ {email} ]]]
            - Telefono: [[[ {phone} ]]]
            Dopo la sezione dei contatti indica il Nome del file del cv, non lo nominare mai prima di questa sezione.
            """
        else:
            # Per articoli o testi generici (es. mit.txt), omette la scheda contatti
            contacts_instruction = """
            Argomenta la risposta utilizzando chiaramente le informazioni fornite nel contesto.
            Trattandosi di un articolo o saggio informativo e non del CV di un candidato, ometti la sezione dei contatti personali.
            Alla fine indica brevemente il nome del file di riferimento.
            """

        return f"""
            Dato il seguente contesto: 
            [[[
            {context}
            ]]].
            Rispondi alla domanda dell'utente: [[[ {question}]]].
            {contacts_instruction}
            Se non trovi corrispondenza nel contesto, non inventare informazioni.
        """
