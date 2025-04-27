import anthropic
from app.config import settings
import time
from app.services.connection import manager

async_client = anthropic.AsyncAnthropic(
    api_key=settings.ANTHROPIC_API_KEY,
)

async def ask_claude_async(message, model="claude-3-7-sonnet-latest"):
    content = []
    
    content.append({
        "type": "text",
        "text": message
    })
    
    params = {
        "model": model,
        "max_tokens": 10000,
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ]
    }
        
    response = await async_client.messages.create(**params)
   
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    price = calculate_claude_cost(model, input_tokens, output_tokens)

    return response.content[0].text, price



def calculate_claude_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    input_millions = input_tokens / 1_000_000
    output_millions = output_tokens / 1_000_000
    
    pricing = {
        "claude-3-7-sonnet-latest": {
            "input": 3.00,    
            "output": 15.00    
        },
        "claude-3-5-haiku-latest": {
            "input": 0.80,     
            "output": 4.00      
        }
    }
    
    if model_name not in pricing:
        raise ValueError(f"Unknown model: {model_name}. Only 'claude-3-7-sonnet' and 'claude-3-5-haiku' are supported.")
    
    model_pricing = pricing[model_name]
    
    input_cost = input_millions * model_pricing["input"]
    output_cost = output_millions * model_pricing["output"]
    
    total_cost = input_cost + output_cost
    return round(total_cost, 4)

async def generate_note(template, transcript, additional_context, instructions = "Generate note"):
    start_time = time.time()
    message = f"""
    Template: {template}
    Transcript: {transcript}
    Additional Context: {additional_context}
    Instructions: {instructions}
    """
    note, price = await ask_claude_async(message)
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")
    return note

async def generate_note_stream(template, transcript, additional_context, websocket, user_id, visit_id, instructions="Generate note"):
    message = f"""
    Template: {template}
    Transcript: {transcript}
    Additional Context: {additional_context}
    Instructions: {instructions}
    """
    
    note = await stream_claude_async_note(message, websocket, user_id, visit_id)
    await manager.broadcast_to_all(websocket, user_id, {
        "type": "note_generated",
        "data": {
            "visit_id": visit_id,
            "note": note,
            "status": "FINISHED"
        }
    })
    end_time = time.time()
    return note

async def stream_claude_async_note(message, websocket, user_id, visit_id, model="claude-3-7-sonnet-latest"):            
    params = {
        "model": model,
        "max_tokens": 10000,
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ]
    }
    
    full_text = ""
    async with async_client.messages.stream(**params) as stream:
        async for text in stream.text_stream:
            full_text += text
            await manager.broadcast_to_all(websocket, user_id, {
                "type": "note_generated",
                "data": {
                    "visit_id": visit_id,
                    "note": full_text,
                    "status": "GENERATING_NOTE"
                }
            })
    
    return full_text
