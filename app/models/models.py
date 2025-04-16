from pydantic import BaseModel
from typing import Optional, List

class User(BaseModel):
    user_id: Optional[str]
    created_at: Optional[str]
    modified_at: Optional[str]
    status: Optional[str]
    name: Optional[str]
    email: Optional[str]
    password: Optional[str]
    default_template_id: Optional[str]
    default_language: Optional[str]
    template_ids: Optional[List[str]]
    visit_ids: Optional[List[str]]

class UpdateUser(BaseModel):
    user_id: str = None
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    default_template_id: Optional[str] = None
    default_language: Optional[str] = None
    template_ids: Optional[List[str]] = None
    visit_ids: Optional[List[str]] = None

class Visit(BaseModel):
    visit_id: Optional[str]
    user_id: Optional[str]
    created_at: Optional[str]
    modified_at: Optional[str]
    status: Optional[str]
    name: Optional[str]
    template_id: Optional[str]
    language: Optional[str]
    additional_context: Optional[str]
    recording_started_at: Optional[str]
    recording_duration: Optional[str]
    recording_finished_at: Optional[str]
    transcript: Optional[str]
    note: Optional[str]

class UpdateVisit(BaseModel):
    visit_id: str = None
    name: Optional[str] = None
    template_id: Optional[str] = None
    language: Optional[str] = None
    additional_context: Optional[str] = None
    recording_started_at: Optional[str] = None
    recording_duration: Optional[str] = None
    recording_finished_at: Optional[str] = None
    transcript: Optional[str] = None
    note: Optional[str] = None

class Template(BaseModel):
    template_id: Optional[str]
    user_id: Optional[str]
    created_at: Optional[str]
    modified_at: Optional[str]
    status: Optional[str]
    name: Optional[str]
    instructions: Optional[str]
    print: Optional[str]

class UpdateTemplate(BaseModel):
    template_id: str = None
    name: Optional[str] = None
    instructions: Optional[str] = None
    print: Optional[str] = None

class Session(BaseModel):
    session_id: Optional[str]
    user_id: Optional[str]
    date: Optional[str]
