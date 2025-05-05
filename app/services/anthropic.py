import anthropic
from app.config import settings
from app.services.connection import manager
from datetime import datetime

async_client = anthropic.AsyncAnthropic(
    api_key=settings.ANTHROPIC_API_KEY,
)

async def generate_note_stream(template, transcript, additional_context, websocket, user_id, visit_id, instructions="Generate note"):
    message = f"""
    Template: {template}
    Transcript: {transcript}
    Additional Context: {additional_context}
    Instructions: {instructions}
    """
    await manager.broadcast_to_all(websocket, user_id, {
        "type": "note_generating",
        "data": {
            "visit_id": visit_id,
            "status": "GENERATING_NOTE",
            "note": "asldkfkalsd",
        }
    })
    note = await stream_claude_async_note(message, websocket, user_id, visit_id)
    note_generated_at = str(datetime.utcnow())
    await manager.broadcast_to_all(websocket, user_id, {
        "type": "note_generated",
        "data": {
            "visit_id": visit_id,
            "note": note,
            "status": "FINISHED",
            "template_modified_at": note_generated_at
        }
    })
    return note, note_generated_at


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