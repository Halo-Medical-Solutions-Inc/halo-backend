from pydantic import BaseModel
from app.models.models import UpdateUser, UpdateTemplate, UpdateVisit
from typing import Optional, Literal

class SignInRequest(BaseModel):
    email: str
    password: str

class SignUpRequest(BaseModel):
    name: str
    email: str
    password: str

class GetUserRequest(BaseModel):
    session_id: str

class GetTemplateRequest(BaseModel):
    session_id: str
    template_id: str

class GetVisitRequest(BaseModel):
    session_id: str
    visit_id: str

class DeleteTemplateRequest(BaseModel):
    session_id: str
    template_id: str

class DeleteVisitRequest(BaseModel):
    session_id: str
    visit_id: str

class UpdateUserRequest(BaseModel):
    session_id: str
    update_user: UpdateUser

class DeleteUserRequest(BaseModel):
    session_id: str

class GetTemplatesRequest(BaseModel):
    session_id: str

class GetVisitsRequest(BaseModel):
    session_id: str

class UpdateTemplateRequest(BaseModel):
    session_id: str
    update_template: UpdateTemplate

class UpdateVisitRequest(BaseModel):
    session_id: str
    update_visit: UpdateVisit

class WebSocketMessage(BaseModel):
    type: Literal["create_template", "update_template", "delete_template", 
                 "create_visit", "update_visit", "delete_visit", "start_recording", "pause_recording", "resume_recording", "finish_recording", "audio_chunk"]
    session_id: str
    data: dict

class WebSocketResponse(BaseModel):
    type: Literal["create_template", "update_template", "delete_template", 
                 "create_visit", "update_visit", "delete_visit", "start_recording", "pause_recording", "resume_recording", "finish_recording", "audio_chunk"]
    data: dict 
    was_requested: bool