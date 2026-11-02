## Installazione Poetry

- https://python-poetry.org/

## Nuovo progetto Poetry

```
$ poetry new HR_Assistant

$ cd HR_Assistant

$ poetry env activate

$ poetry add chromadb openai ollama chainlit

```

se c'e' un errore di versioni di librerie, fare questa modifica al file pyproject.toml e poi provare a rilanciare ```poetry add chromadb openai ollama chainlit```

```

requires-python = ">=3.13,<4.0.0"

```

per eseguire l'applicazione

```
$ poetry install
$ eval $(poetry env activate)

$ chainlit run hr_assistant/__init__.py -w
```


## Esecuzione modelli in locale

```

# modello nuovissimo molto potente, ma leggero
$ ollama run deepseek-r1:1.5b
# oppure 
$ ollama run deepseek-r1:7b
# ma c'e' anche 671b ! https://ollama.com/library/deepseek-r1

# modello leggero
$ ollama run llama3.2

```


# Strategia per Sync dei file

La soluzione si basa su tre concetti principali:

1. **Tracciamento dei file**
   - Per ogni file viene calcolato un hash MD5 del contenuto
   - Questo hash funziona come una "impronta digitale" del file
   - Vengono anche memorizzati il nome del file e la data di ultima modifica
   - Queste informazioni vengono salvate nel database insieme ai contenuti

2. **Processo di sincronizzazione**
   - All'avvio del sistema, viene fatto un confronto tra:
     - I file attualmente presenti nella cartella dei curriculum
     - I file tracciati nel database
   - Il sistema identifica automaticamente tre categorie:
     - File nuovi (presenti nella cartella ma non nel database)
     - File modificati (presenti in entrambi ma con hash diverso)
     - File eliminati (presenti nel database ma non più nella cartella)

3. **Gestione dei contenuti**
   - Per i file nuovi:
     - Vengono divisi in frammenti (chunks)
     - Ogni frammento viene aggiunto al database con i relativi metadati
   - Per i file modificati:
     - Prima vengono rimossi tutti i vecchi frammenti dal database
     - Poi vengono aggiunti i nuovi frammenti del file aggiornato
   - Per i file eliminati:
     - Vengono rimossi tutti i frammenti associati dal database

Il vantaggio principale di questa strategia è che:
- Evita duplicazioni nel database
- Minimizza le operazioni di scrittura necessarie
- Mantiene il database sempre sincronizzato con i file reali
- È efficiente perché processa solo ciò che è effettivamente cambiato
- La verifica tramite hash garantisce che vengano identificate anche piccole modifiche nei file

In pratica, quando il sistema parte:
1. Scansiona la cartella dei curriculum
2. Calcola gli hash di tutti i file presenti
3. Confronta questi hash con quelli memorizzati nel database
4. Esegue solo le operazioni necessarie per sincronizzare le differenze
5. Aggiorna i metadati nel database per riflettere lo stato attuale

Questo approccio è particolarmente efficiente per gestire grandi quantità di curriculum, poiché:
- Non ricarica inutilmente documenti già presenti
- Gestisce automaticamente l'aggiornamento dei documenti modificati
- Mantiene il database pulito rimuovendo i riferimenti a file non più esistenti
- Riduce il carico di lavoro complessivo del sistema

La soluzione è anche resiliente agli errori, perché:
- Il confronto degli hash garantisce l'integrità dei dati
- Le operazioni di aggiornamento sono atomiche
- In caso di interruzione, alla successiva esecuzione il sistema si risincronizza automaticamente
