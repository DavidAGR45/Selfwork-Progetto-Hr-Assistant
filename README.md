## Installazione Poetry

- https://python-poetry.org/

## Nuovo progetto Poetry

```
$ poetry new HR_Assistant

$ cd HR_Assistant

$ eval $(poetry env activate)

$ poetry add chromadb openai chainlit

```

se c'e' un errore di versioni di librerie, fare questa modifica al file pyproject.toml 

```

requires-python = ">=3.13,<4.0.0"

```

e poi provare a rilanciare ```poetry add chromadb ollama openai chainlit```

## per eseguire l'applicazione

```
$ poetry install
$ eval $(poetry env activate)

$ poetry run chainlit run hr_assistant/__init__.py -w
```