from pydantic import BaseModel
from typing import Literal
class SignInRequest(BaseModel):
    email: str
    password: str

class SignUpRequest(BaseModel):
    name: str
    email: str
    password: str

class GetUserRequest(BaseModel):
    session_id: str

class GetTemplatesRequest(BaseModel):
    session_id: str

class GetVisitsRequest(BaseModel):
    session_id: str

class WebSocketMessage(BaseModel):
    type: Literal["create_template", "update_template", "delete_template", 
                 "create_visit", "update_visit", "delete_visit", "update_user", "start_recording", "pause_recording", "resume_recording", "finish_recording", "audio_chunk", "transcribe_audio"]
    session_id: str
    data: dict

class WebSocketResponse(BaseModel):
    type: Literal["create_template", "update_template", "delete_template", 
                 "create_visit", "update_visit", "delete_visit", "update_user", "start_recording", "pause_recording", "resume_recording", "finish_recording", "audio_chunk", "transcribe_audio"]
    data: dict 
    was_requested: bool