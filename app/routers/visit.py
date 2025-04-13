from fastapi import APIRouter, HTTPException
from app.models.requests import (
    GetVisitRequest, DeleteVisitRequest, GetUserRequest,
    UpdateVisitRequest
)
from app.database.database import database

router = APIRouter()
db = database()

@router.post("/get")
def get_visit(request: GetVisitRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        visit = db.get_visit(request.visit_id)
        return visit
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/create")
def create_visit(request: GetUserRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        visit = db.create_visit(user_id)
        return visit
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/update")
def update_visit(request: UpdateVisitRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        visit = db.update_visit(request.update_visit.visit_id, request.update_visit.name, request.update_visit.template_id, request.update_visit.language, request.update_visit.additional_context, request.update_visit.recording_started_at, request.update_visit.recording_duration, request.update_visit.recording_finished_at, request.update_visit.transcript, request.update_visit.note)
        return visit
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/delete")
def delete_visit(request: DeleteVisitRequest):
    user_id = db.is_session_valid(request.session_id)
    if user_id:
        db.delete_visit(request.visit_id, user_id)
        return None
    else:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.post("/generate_notes")
def generate_notes(request: GetUserRequest):
    return None

@router.post("/transcribe_audio")
def transcribe_audio(request: GetUserRequest):
    return None

@router.post("/ask_ai")
def ask_ai(request: GetUserRequest):
    return None