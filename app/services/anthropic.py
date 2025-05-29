import anthropic
from app.config import settings

"""
Anthropic Service for the Halo Application.

This module provides a service for interacting with the Anthropic API.
It includes functionality for streaming and non-streaming responses from the API.
"""

MODEL = "claude-3-7-sonnet-latest"
MAX_TOKENS = 20000

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

async def ask_claude_stream(message, callback, model=MODEL, max_tokens=MAX_TOKENS):
    """
    Streams a response from the Anthropic API.

    Args:
        message (str): The message to send to the API.
        callback (function): A callback function to handle the response.
        model (str): The model to use for the API call.
        max_tokens (int): The maximum number of tokens to generate.
        
    Returns:
        str: The full response from the API.
    """
    full_text = ""
    async with anthropic_client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": message}]
    ) as stream:
        async for text in stream.text_stream:
            full_text += text
            await callback(full_text)
    return full_text

async def ask_claude(message):
    """
    Asks the Anthropic API for a response.

    Args:
        message (str): The message to send to the API.
        
    Returns:
        str: The response from the API.
    """
    response = await anthropic_client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": message}]
    )
    return response.content[0].text
