from fastapi import APIRouter, HTTPException
from app.database.database import db
from app.models.requests import CreateDefaultTemplateRequest, DeleteDefaultTemplateRequest, GetDefaultTemplateRequest, DeleteAllVisitsForUserRequest, GetUserStatsRequest
from datetime import datetime

"""
Admin Router for managing default templates.

This module provides endpoints for creating, deleting, and retrieving default templates.
It includes functionality for CRUD operations on templates.
Get user statistics for a specific date range.

All database operations are encapsulated in the database class,
with proper error handling and logging.
"""

router = APIRouter()

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