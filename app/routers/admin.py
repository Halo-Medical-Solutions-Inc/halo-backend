from fastapi import APIRouter, HTTPException
from app.database.database import db
from app.models.requests import CreateDefaultTemplateRequest, DeleteDefaultTemplateRequest, GetDefaultTemplateRequest, DeleteAllVisitsForUserRequest, GetUserStatsRequest, AdminSigninRequest, AdminSignupRequest, GetAdminRequest, UpdateAdminRequest
from datetime import datetime
from pydantic import BaseModel

"""
Admin Router for managing default templates and admin operations.

This module provides endpoints for creating, deleting, and retrieving default templates.
It includes functionality for CRUD operations on templates and admin management.
Get user statistics for a specific date range.

All database operations are encapsulated in the database class,
with proper error handling and logging.
"""

router = APIRouter()

@router.post("/get_user_stats")
def get_user_stats(request: GetUserStatsRequest):
    """
    Get user statistics for a specific date range.

    This endpoint allows the admin to retrieve statistics for users based on a specified date range.

    Args:
        user_emails (list[str], optional): List of user email addresses to filter statistics.
        start_date (str, optional): Start date for the statistics period (format: YYYY-MM-DD).
        end_date (str, optional): End date for the statistics period (format: YYYY-MM-DD).

    Returns:
        dict: Statistics for users within the specified date range.
    """
    user_ids = ([str(user["_id"]) for user in db.users.find({})] 
                if not request.user_emails or "all" in request.user_emails
                else [user['user_id'] for email in request.user_emails 
                      if (user := db.get_user_by_email(email))])
    
    end_date = request.end_date or datetime.utcnow().strftime('%Y-%m-%d')
    start_date = request.start_date or "1970-01-01"
    
    total_visits = total_audio_time = 0
    user_breakdowns = {}
    
    for user_id in user_ids:
        try:
            user = db.get_user(user_id)
            if not user or 'daily_statistics' not in user:
                continue
                
            user_stats = {date: stats for date, stats in user['daily_statistics'].items() 
                         if start_date <= date <= end_date}
            user_visits = sum(stats.get('visits', 0) for stats in user_stats.values())
            user_audio_time = sum(stats.get('audio_time', 0) for stats in user_stats.values())
            
            total_visits += user_visits
            total_audio_time += user_audio_time
            user_breakdowns[user_id] = {
                'name': user['name'],
                'email': user['email'],
                'total_visits': user_visits,
                'total_audio_time': user_audio_time,
            }
        except Exception:
            continue
    
    return {
        'total_visits': total_visits,
        'total_audio_time': total_audio_time,
        'users': user_breakdowns
    }

@router.post("/signin")
async def admin_signin(request: AdminSigninRequest):
    """
    Authenticate an admin user.

    This endpoint allows an admin to sign in with their email and password credentials.

    Args:
        email (str): The admin's email address.
        password (str): The admin's password.

    Returns:
        dict: The authenticated admin information and session data.
        
    Raises:
        HTTPException: If credentials are invalid.
    """
    admin = db.verify_admin(email=request.email, password=request.password)
    if admin:
        return admin
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.post("/signup")
async def admin_signup(request: AdminSignupRequest):
    """
    Create a new admin account.

    This endpoint allows the creation of a new admin account with the specified credentials and settings.

    Args:
        name (str): The admin's name.
        email (str): The admin's email address.
        password (str): The admin's password.
        master_note_generation_instructions (str, optional): Master instructions for note generation.
        master_template_polish_instructions (str, optional): Master instructions for template polishing.

    Returns:
        dict: The newly created admin information.
        
    Raises:
        HTTPException: If admin creation fails or email already exists.
    """
    admin = db.create_admin(
        name=request.name,
        email=request.email,
        password=request.password,
        master_note_generation_instructions=request.master_note_generation_instructions,
        master_template_polish_instructions=request.master_template_polish_instructions
    )
    if admin:
        return admin
    else:
        raise HTTPException(status_code=400, detail="Admin creation failed - email may already exist")

@router.post("/get_admin")
async def get_admin(request: GetAdminRequest):
    """
    Retrieve an admin by their ID.

    This endpoint allows retrieval of admin information by specifying the admin ID.

    Args:
        admin_id (str): The ID of the admin to retrieve.

    Returns:
        dict: The admin information.
        
    Raises:
        HTTPException: If admin is not found.
    """
    admin = db.get_admin(admin_id=request.admin_id)
    if admin:
        return admin
    else:
        raise HTTPException(status_code=404, detail="Admin not found")

@router.post("/update_admin")
async def update_admin(request: UpdateAdminRequest):
    """
    Update an admin's settings.

    This endpoint allows updating an admin's master instructions for note generation and template polishing.

    Args:
        admin_id (str): The ID of the admin to update.
        master_note_generation_instructions (str, optional): Updated master instructions for note generation.
        master_template_polish_instructions (str, optional): Updated master instructions for template polishing.

    Returns:
        dict: The updated admin information.
        
    Raises:
        HTTPException: If admin update fails or admin is not found.
    """
    admin = db.update_admin(
        admin_id=request.admin_id,
        master_note_generation_instructions=request.master_note_generation_instructions,
        master_template_polish_instructions=request.master_template_polish_instructions
    )
    if admin:
        return admin
    else:
        raise HTTPException(status_code=404, detail="Admin update failed - admin may not exist")
        
@router.post("/create_default_template")
async def create_default_template(request: CreateDefaultTemplateRequest):
    """
    Create a new default template.

    This endpoint allows the admin to create a new default template with a specified name and instructions.

    Args:
        name (str): The name of the template.
        instructions (str): The instructions for the template.

    Returns:
        dict: The created template.
    """
    template = db.create_default_template(name=request.name, instructions=request.instructions)
    return template

@router.post("/delete_default_template")
async def delete_default_template(request: DeleteDefaultTemplateRequest):
    """
    Delete a default template.

    This endpoint allows the admin to delete a default template by specifying its ID.

    Args:
        template_id (str): The ID of the default template to delete.

    Returns:
        dict: A message indicating the template has been deleted.
    """
    db.delete_default_template(template_id=request.template_id)
    return {"message": "Default Template Deleted"}

@router.get("/get_default_template")
async def get_default_template(request: GetDefaultTemplateRequest):
    """
    Retrieve a default template by its ID.

    This endpoint allows the admin to retrieve a default template by specifying its ID.

    Args:
        template_id (str): The ID of the default template to retrieve.

    Returns:
        dict: The retrieved template.
    """
    template = db.get_default_template(template_id=request.template_id)
    return template

@router.get("/get_all_default_templates")
async def get_all_default_templates():
    """
    Retrieve all default templates.

    This endpoint allows the admin to retrieve all default templates.

    Args:
        None

    Returns:
        list: A list of all default templates.
    """
    templates = db.get_all_default_templates()
    return templates

    
@router.post("/delete_all_visits_for_user")
def delete_all_visits_for_user(request: DeleteAllVisitsForUserRequest):
    """
    Delete all visits for a specific user.

    This endpoint allows the admin to delete all visits for a specific user by specifying their ID.

    Args:
        user_id (str): The ID of the user whose visits should be deleted.

    Returns:
        dict: A message indicating the visits have been deleted.
    """
    user = db.get_user_by_email(request.user_email)
    if user:
        for visit_id in user['visit_ids']:
            db.delete_visit(visit_id, user['user_id'])
        return {"message": "All visits deleted"}
    else:
        raise HTTPException(status_code=401, detail="Invalid user")
