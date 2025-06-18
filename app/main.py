from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from app.routers import user, audio, admin, chat, integration
from app.services.connection import manager
import os
from datetime import datetime
from pathlib import Path

"""
Main module for the Halo AI Scribe application.

This module sets up the FastAPI application and includes middleware for CORS,
startup and shutdown events, and a root endpoint.
"""

app = FastAPI(
    title="Halo AI Scribe",
    description="Halo AI Scribe backend.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://www.halohealth.app",
        "https://scribe.halohealth.app",
        "https://halo-frontend-test.up.railway.app",
    ], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],  
)

@app.on_event("startup")
async def startup_event():
    """
    Startup event for the FastAPI application.
    """

@app.on_event("shutdown")
async def shutdown_event():
    """
    Shutdown event for the FastAPI application.
    """
    if manager.health_check_task:
        manager.health_check_task.cancel()

@app.get("/")
async def root():
    """
    Root endpoint for the FastAPI application.
    """
    return {"message": "Welcome to the Halo AI Scribe API"}

@app.get("/logs", response_class=PlainTextResponse)
async def logs():
    """
    Logs endpoint for the FastAPI application.
    Returns today's log entries from the logs folder in a clean format.
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file_path = Path("logs") / f"errors_{today}.log"
        if not log_file_path.exists():
            return f"No log file found for {today}"
        with open(log_file_path, "r", encoding="utf-8") as file:
            log_lines = file.readlines()
        log_entries = [line.strip() for line in log_lines if line.strip()]
        return "\n".join(log_entries)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

app.include_router(user.router, prefix="/user", tags=["User Operations"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Operations"])
app.include_router(audio.router, prefix="/audio", tags=["Audio Operations"])
app.include_router(chat.router, prefix="/chat", tags=["Chat Operations"])
app.include_router(integration.router, prefix="/integration", tags=["Integration Operations"])