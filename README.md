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

$ poetry run chainlit run hr_assistant/__init__.py -w
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