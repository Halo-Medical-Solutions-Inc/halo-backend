from pydantic import BaseModel

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