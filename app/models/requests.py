from pydantic import BaseModel
from typing import Literal
from fastapi import File

"""
Pydantic models for request validation in the Halo Application.

This module defines all the request models used for validating incoming requests
to the API endpoints. These models leverage Pydantic's validation capabilities
to ensure that all requests contain the required fields in the correct format.

Each model corresponds to a specific API endpoint or WebSocket message type,
with field definitions that match the expected request payload.
"""

class SignInRequest(BaseModel):
    """
    Request model for user sign-in.
    
    Fields:
        email (str): The user's email address.
        password (str): The user's password.
    """
    email: str
    password: str

class SignUpRequest(BaseModel):
    """
    Request model for user registration.
    
    Fields:
        name (str): The new user's full name.
        email (str): The new user's email address.
        password (str): The new user's password.
    """
    name: str
    email: str
    password: str

class GetUserRequest(BaseModel):
    """
    Request model to retrieve user information.
    
    Fields:
        session_id (str): The active session identifier.
    """
    session_id: str

class GetUserStatsRequest(BaseModel):
    """
    Request model to retrieve user statistics.
    
    Fields:
        user_emails (list[str], optional): List of user email addresses to filter statistics.
        start_date (str, optional): Start date for the statistics period (format: YYYY-MM-DD).
        end_date (str, optional): End date for the statistics period (format: YYYY-MM-DD).
    """
    user_emails: list[str] = None
    start_date: str = None
    end_date: str = None

class GetTemplatesRequest(BaseModel):
    """
    Request model to retrieve templates associated with a user.
    
    Fields:
        session_id (str): The active session identifier.
    """
    session_id: str

class CreateDefaultTemplateRequest(BaseModel):
    """
    Request model to create a new default template.
    
    Fields:
        name (str): The name of the template.
        instructions (str): The instructions for the template.
    """
    name: str
    instructions: str

class UpdateDefaultTemplateRequest(BaseModel):
    """
    Request model to update a default template.
    
    Fields:
        template_id (str): The ID of the default template to update.
        name (str, optional): The template's new name.
        instructions (str): The new instructions for the template.
        print (str, optional): The template's new print format.
        header (str, optional): The template's new header.
        footer (str, optional): The template's new footer.
    """
    template_id: str
    name: str = None
    instructions: str
    print: str = None
    header: str = None
    footer: str = None

class DeleteDefaultTemplateRequest(BaseModel):
    """
    Request model to delete a default template.
    
    Fields:
        template_id (str): The ID of the default template to delete.
    """
    template_id: str

class GetDefaultTemplateRequest(BaseModel):
    """
    Request model to retrieve a default template by ID.
    
    Fields:
        template_id (str): The ID of the default template to retrieve.
    """
    template_id: str

class GetVisitsRequest(BaseModel):
    """
    Request model to retrieve visits associated with a user.
    
    Fields:
        session_id (str): The active session identifier.
    """
    session_id: str
    subset: bool = False

class DeleteAllVisitsForUserRequest(BaseModel):
    """
    Request model to delete all visits for a specific user.
    
    Fields:
        user_email (str): The email of the user whose visits should be deleted.
    """
    user_email: str

class WebSocketMessage(BaseModel):
    """
    Model for messages sent through WebSocket connections.
    
    Fields:
        type (str): The type of message, defining the action to be performed.
        session_id (str): The active session identifier.
        data (dict): The payload data for the message.
    
    Note:
        The 'type' field is constrained to a predefined set of allowed values.
    """
    type: Literal["create_template", "update_template", "delete_template", "duplicate_template", "polish_template", "template_generated", "create_visit", "update_visit", "delete_visit", "generate_note", "generate_note", "polish_note", "update_user", "start_recording", "pause_recording", "resume_recording", "finish_recording", "transcribe_audio", "error"]
    session_id: str
    data: dict

class WebSocketResponse(BaseModel):
    """
    Model for responses sent back through WebSocket connections.
    
    Fields:
        type (str): The type of response, matching the action that was performed.
        data (dict): The payload data for the response.
        was_requested (bool): Indicates whether this response was directly requested.
    
    Note:
        The 'type' field is constrained to the same set of values as in WebSocketMessage.
    """
    type: Literal["create_template", "update_template", "delete_template", "duplicate_template", "polish_template", "template_generated", "create_visit", "update_visit", "delete_visit", "note_generated", "generate_note", "update_user", "start_recording", "pause_recording", "resume_recording", "finish_recording", "transcribe_audio", "error"]
    data: dict
    was_requested: bool

class AdminSigninRequest(BaseModel):
    """
    Request model for admin sign-in.
    
    Fields:
        email (str): The admin's email address.
        password (str): The admin's password.
    
    Note:
        The admin is created automatically when the first admin signs up.
    """
    email: str
    password: str

class AdminSignupRequest(BaseModel):
    """
    Request model for admin sign-up.
    
    Fields:
        name (str): The admin's name.
        email (str): The admin's email address.
        password (str): The admin's password.
        master_note_generation_instructions (str, optional): The admin's master note generation instructions.
        master_template_polish_instructions (str, optional): The admin's master template polish instructions.

    Note:
        The admin is created automatically when the first admin signs up.
    """
    name: str
    email: str
    password: str
    master_note_generation_instructions: str = ""
    master_template_polish_instructions: str = ""

class GetAdminRequest(BaseModel):
    """
    Request model to retrieve an admin by ID.
    
    Fields:
        admin_id (str): The ID of the admin to retrieve.

    Note:
        The admin is created automatically when the first admin signs up.
    """
    admin_id: str

class UpdateAdminRequest(BaseModel):
    """
    Request model to update an admin's information.
    
    Fields:
        admin_id (str): The ID of the admin to update.
        master_note_generation_instructions (str, optional): The admin's master note generation instructions.
        master_template_polish_instructions (str, optional): The admin's master template polish instructions.

    Note:
        The admin is created automatically when the first admin signs up.
    """
    admin_id: str
    master_note_generation_instructions: str = None
    master_template_polish_instructions: str = None

class VerifyEMRIntegrationRequest(BaseModel):
    """
    Request model to verify EMR integration for a user.
    
    Fields:
        session_id (str): The active session identifier.
        emr_name (str): The name of the EMR system (e.g., "OFFICE_ALLY", "ADVANCEMD").
        credentials (dict): The credentials required for the specific EMR system.
                           For OFFICE_ALLY: {"username": str, "password": str}
    """
    session_id: str
    emr_name: Literal["OFFICE_ALLY", "ADVANCEMD"]
    credentials: dict
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_123",
                "emr_name": "OFFICE_ALLY",
                "credentials": {
                    "username": "john.doe@example.com",
                    "password": "secure_password"
                }
            }
        }