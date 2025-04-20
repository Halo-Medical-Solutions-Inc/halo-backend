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
                 "create_visit", "update_visit", "delete_visit"]
    session_id: str
    data: dict

class WebSocketResponse(BaseModel):
    type: Literal["create_template", "update_template", "delete_template", 
                 "create_visit", "update_visit", "delete_visit"]
    data: dict 
    was_requested: bool