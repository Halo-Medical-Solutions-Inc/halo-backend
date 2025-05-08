from fastapi import APIRouter
from app.database.database import database
from app.models.requests import CreateDefaultTemplateRequest, DeleteDefaultTemplateRequest, GetDefaultTemplateRequest
router = APIRouter()
db = database()

@router.post("/create_default_template")
async def create_default_template(request: CreateDefaultTemplateRequest):
    template = db.create_default_template(name=request.name, instructions=request.instructions)
    return template

@router.post("/delete_default_template")
async def delete_default_template(request: DeleteDefaultTemplateRequest):
    db.delete_default_template(template_id=request.template_id)
    return {"message": "Default Template Deleted"}

@router.get("/get_default_template")
async def get_default_template(request: GetDefaultTemplateRequest):
    template = db.get_default_template(template_id=request.template_id)
    return template