from app.models.requests import (
    GetTemplateRequest, DeleteTemplateRequest, GetUserRequest,
    UpdateTemplateRequest
)
from fastapi import APIRouter, HTTPException
from app.database.database import database

router = APIRouter()
db = database()

@router.post("/get")
def get_template(request: GetTemplateRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        template = db.get_template(request.template_id)
        return template
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/create")
def create_template(request: GetUserRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        template = db.create_template(user_id)
        return template
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/update")
def update_template(request: UpdateTemplateRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        template = db.update_template(request.update_template.template_id, request.update_template.name, request.update_template.instructions, request.update_template.print)
        return template
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/delete")
def delete_template(request: DeleteTemplateRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        db.delete_template(request.template_id, user_id)
        return None
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/generate_notes")
def extract_template(request: GetUserRequest):
    return None

@router.post("/ask_ai")
def ask_ai(request: GetUserRequest):
    return None
