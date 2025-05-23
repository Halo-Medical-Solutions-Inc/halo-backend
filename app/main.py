from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import user, audio, admin  
from app.services.connection import manager

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
    allow_origins=["*"], 
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

app.include_router(user.router, prefix="/user", tags=["User Operations"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Operations"])
app.include_router(audio.router, prefix="/audio", tags=["Audio Operations"])