# semantic_chunking.py - Algoritmo di chunking semantico rifattorizzato a oggetti (Step 07)
import os
import re
import numpy as np
from custom_embedding import CustomEmbeddingFunction
from sklearn.metrics.pairwise import cosine_similarity
from config import Config

# Spiegazione Generale della Logica:
# Questo codice implementa un sistema di "semantic chunking", ovvero un modo intelligente di dividere un testo lungo in parti più piccole (chunk) che hanno senso semantico.
# Invece di dividere il testo in modo meccanico (per esempio ogni 500 caratteri), questo sistema usa l'intelligenza artificiale per capire dove il significato del testo cambia significativamente.
# Lo fa analizzando ogni frase nel suo contesto e utilizzando gli embedding per misurare quanto due frasi consecutive sono semanticamente diverse.
# Quando trova un punto dove la differenza semantica è particolarmente alta (sopra una certa soglia percentile), usa quel punto come confine per creare un nuovo chunk.


class SemanticChunking:

    # Inizializza i parametri di soglia percentile e buffer di contesto
    def __init__(self, breakpoint_percentile=65, buffer_size=3):
        self.breakpoint_percentile = breakpoint_percentile
        self.buffer_size = buffer_size

        # Riutilizza la funzione di embedding unificata (supporta openai, local con SentenceTransformer, ollama)
        self.embedding_function = CustomEmbeddingFunction()

    # Suddivide il testo in frasi con fallback su altri delimitatori per evitare che documenti privi di punteggiatura standard diventino una frase unica (Step 07)
    def _split_into_sentences(self, text):
        # 1. Prova prima a dividere usando la punteggiatura standard di chiusura frase (.!?)
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())

        # Se ottiene una sola frase ma il testo supera i 100 caratteri, usa delimitatori alternativi (linee, punti e virgola, due punti)
        if len(sentences) == 1 and len(text) > 100:
            delimiters = r"([.!?\n;:])"
            parts = re.split(delimiters, text.strip())

            # Ricompone le parti preservando i rispettivi delimitatori
            sentences = []
            for i in range(0, len(parts) - 1, 2):
                if parts[i].strip():
                    sentences.append(parts[i].strip() + parts[i + 1])

            # Come ultima risorsa, se e' rimasta una sola frase, divide per virgola
            if len(sentences) == 1:
                sentences = [s.strip() + "," for s in text.split(",") if s.strip()]
                if sentences:
                    sentences[-1] = sentences[-1][:-1] + "."

        # Assicura che ci sia almeno una frase non vuota
        sentences = [s for s in sentences if s.strip()]
        if not sentences:
            sentences = [text + "."]

        return sentences

    # Divide il testo in frasi e arricchisce ogni frase con il contesto delle frasi adiacenti (buffer)
    def _process_sentences(self, text):
        # Utilizza la suddivisione avanzata delle frasi per gestire formati eterogenei (PDF, PPTX, XLSX)
        raw_sentences = self._split_into_sentences(text)
        sentences = [
            {"sentence": s.strip(), "index": i}
            for i, s in enumerate(raw_sentences)
            if s.strip()
        ]

        # Combina ogni frase con il suo contesto precedente e successivo in base al buffer_size
        for i, current in enumerate(sentences):
            context_range = range(
                max(0, i - self.buffer_size),
                min(len(sentences), i + self.buffer_size + 1),
            )
            current["combined_sentence"] = " ".join(
                sentences[j]["sentence"] for j in context_range
            )

        return sentences

    # Calcola la distanza del coseno tra i vettori di embedding di frasi consecutive
    def _calculate_distances(self, sentences):
        # Calcola gli embedding per tutte le frasi combinate usando la funzione personalizzata unificata
        embeddings = self.embedding_function([s["combined_sentence"] for s in sentences])

        # Calcola la distanza del coseno: 1 - similarita (valori piu alti indicano un distacco semantico)
        distances = []
        for i in range(len(sentences) - 1):
            distance = 1 - cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
            distances.append(distance)

        return distances

    # Metodo principale: suddivide il testo calcolando i punti di taglio sul percentile
    def chunk_text(self, text):
        # Se il testo e vuoto, restituisce lista vuota
        if not text or not text.strip():
            return []

        # Elabora le frasi e i relativi buffer
        sentences = self._process_sentences(text)
        if not sentences:
            return []
        if len(sentences) == 1:
            return [sentences[0]["sentence"]]

        # Calcola le distanze semantiche tra frasi consecutive
        distances = self._calculate_distances(sentences)
        if not distances:
            return [text.strip()]

        # Determina la soglia di taglio basata sul percentile (es. 65 o 95)
        threshold = np.percentile(distances, self.breakpoint_percentile)
        split_points = [i for i, d in enumerate(distances) if d > threshold]

        # Crea i chunk finali unendo le frasi comprese tra i punti di rottura
        chunks = []
        start = 0
        for point in split_points + [len(sentences) - 1]:
            chunk = " ".join(s["sentence"] for s in sentences[start : point + 1]).strip()
            if chunk:
                chunks.append(chunk)
            start = point + 1

        return chunks

    # Metodo statico di compatibilita rapida
    @staticmethod
    def chunk_it(text):
        sc = SemanticChunking()
        return sc.chunk_text(text)
