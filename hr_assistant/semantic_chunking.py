# semantic_chunking.py - Algoritmo di chunking semantico basato sulla distanza tra embedding di frasi consecutive
import os
import re
import numpy as np
from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
from config import Config


class SemanticChunking:

    # Calcola la distanza del coseno tra ogni frase e la frase successiva
    @staticmethod
    def calculate_cosine_distances(sentences):
        distances = []
        for i in range(len(sentences) - 1):
            # Embedding della frase corrente e della frase successiva
            embedding_current = sentences[i]["combined_sentence_embedding"]
            embedding_next = sentences[i + 1]["combined_sentence_embedding"]

            # Calcolo della similarita del coseno (valore da 0 a 1)
            similarity = cosine_similarity([embedding_current], [embedding_next])[0][0]

            # Conversione in distanza del coseno: 1 - similarita (piu e alto, piu le frasi sono semanticamente diverse)
            distance = 1 - similarity

            # Aggiunge la distanza alla lista e al dizionario della frase
            distances.append(distance)
            sentences[i]["distance_to_next"] = distance

        return distances, sentences

    # Aggiunge un buffer di frasi precedenti e successive a ciascuna frase per mantenere il contesto semantico
    @staticmethod
    def combine_sentences(sentences, buffer_size=1):
        for i in range(len(sentences)):
            combined_sentence = ""

            # Concatena le frasi precedenti in base al buffer_size
            for j in range(i - buffer_size, i):
                if j >= 0:
                    combined_sentence += sentences[j]["sentence"] + " "

            # Aggiunge la frase corrente
            combined_sentence += sentences[i]["sentence"]

            # Concatena le frasi successive in base al buffer_size
            for j in range(i + 1, i + 1 + buffer_size):
                if j < len(sentences):
                    combined_sentence += " " + sentences[j]["sentence"]

            # Memorizza la frase combinata con contesto
            sentences[i]["combined_sentence"] = combined_sentence

        return sentences

    # Metodo principale: suddivide il testo in chunk basandosi sui punti di rottura semantica
    @staticmethod
    def chunk_it(txt):
        # Suddivide il testo in singole frasi riconoscendo i punti, punti interrogativi ed esclamativi
        single_sentences_list = re.split(r"(?<=[.?!])\s+", txt)
        # Rimuove eventuali frasi vuote o composte solo da spazi
        single_sentences_list = [s.strip() for s in single_sentences_list if s.strip()]

        if not single_sentences_list:
            return []
        if len(single_sentences_list) == 1:
            return single_sentences_list

        # Crea un dizionario per ciascuna frase con il rispettivo indice
        sentences = [
            {"sentence": x, "index": i} for i, x in enumerate(single_sentences_list)
        ]

        # Applica il buffer di contesto prima e dopo ogni frase
        sentences = SemanticChunking.combine_sentences(sentences)
        texts_to_embed = [x["combined_sentence"] for x in sentences]

        # Genera gli embedding per ogni frase combinata (supporta sia OpenAI che Ollama locale)
        if Config.PROVIDER == "openai" and getattr(Config, "OPENAI_KEY", ""):
            oaiembeds = OpenAIEmbeddings(
                openai_api_key=Config.OPENAI_KEY,
                model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            )
            embeddings = oaiembeds.embed_documents(texts_to_embed)
        else:
            # Default: embedding locale tramite Ollama (es. embeddinggemma-2:270m)
            import ollama
            res = ollama.embed(model=Config.MODEL_NAME, input=texts_to_embed)
            embeddings = res["embeddings"]

        # Assegna l'embedding generato a ciascuna frase
        for i, sentence in enumerate(sentences):
            sentence["combined_sentence_embedding"] = embeddings[i]

        # Calcola le distanze del coseno tra frasi adiacenti
        distances, sentences = SemanticChunking.calculate_cosine_distances(sentences)
        if not distances:
            return [txt]

        # Calcola la soglia di taglio al 95° percentile: le distanze sopra questo valore rappresentano un cambio di argomento
        breakpoint_percentile_threshold = 95
        breakpoint_distance_threshold = np.percentile(
            distances, breakpoint_percentile_threshold
        )

        # Trova gli indici dove la distanza supera la soglia (punti di taglio)
        indices_above_thresh = [
            i for i, x in enumerate(distances) if x > breakpoint_distance_threshold
        ]

        # Raggruppa le frasi originali nei chunk finali in base agli indici di rottura trovati
        start_index = 0
        chunks = []

        for index in indices_above_thresh:
            end_index = index
            # Estrae il blocco di frasi dal punto di inizio al punto di rottura
            group = sentences[start_index : end_index + 1]
            combined_text = " ".join([d["sentence"] for d in group])
            if combined_text.strip():
                chunks.append(combined_text.strip())
            start_index = index + 1

        # Aggiunge l'ultimo gruppo di frasi rimaste
        if start_index < len(sentences):
            combined_text = " ".join([d["sentence"] for d in sentences[start_index:]])
            if combined_text.strip():
                chunks.append(combined_text.strip())

        return chunks
