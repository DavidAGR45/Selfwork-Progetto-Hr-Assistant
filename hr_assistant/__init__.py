import chainlit as cl

@cl.on_message
async def handle_message(message: cl.Message):
    response = f"Ciao, mi hai scritto: {message.content}!"
    await cl.Message(response).send()