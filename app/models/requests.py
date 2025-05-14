from pydantic import BaseModel
from typing import Literal
from fastapi import File

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

class DeleteAllVisitsForUserRequest(BaseModel):
    user_id: str

class GetUserStatsRequest(BaseModel):
    user_emails: list[str] = None
    start_date: str = None
    end_date: str = None

class TranscribeAudioRequest(BaseModel):
    session_id: str
    visit_id: str
    audio_buffer: bytes = File(...)

class CreateDefaultTemplateRequest(BaseModel):
    name: str
    instructions: str

class GetDefaultTemplateRequest(BaseModel):
    template_id: str

class DeleteDefaultTemplateRequest(BaseModel):
    template_id: str



class WebSocketMessage(BaseModel):
    type: Literal["create_template", "update_template", "delete_template", "duplicate_template", "polish_template",
                 "create_visit", "update_visit", "delete_visit", "note_generated", "regenerate_note",
                 "update_user", 
                 "start_recording", "pause_recording", "resume_recording", "finish_recording", 
                 "audio_chunk", "transcribe_audio", 
                 "error"]
    session_id: str
    data: dict

class WebSocketResponse(BaseModel):
    type: Literal["create_template", "update_template", "delete_template", "duplicate_template", "polish_template",
                 "create_visit", "update_visit", "delete_visit", "note_generated", "regenerate_note",
                 "update_user", 
                 "start_recording", "pause_recording", "resume_recording", "finish_recording", 
                 "audio_chunk", "transcribe_audio", 
                 "error"]
    data: dict 
    was_requested: bool