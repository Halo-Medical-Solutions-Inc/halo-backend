from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import template, user, visit, record


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

@app.get("/")
async def root():
    return {"message": "Welcome to the Halo AI Scribe API"}

app.include_router(user.router, prefix="/user", tags=["User Operations"])
app.include_router(template.router, prefix="/template", tags=["Template Operations"])
app.include_router(visit.router, prefix="/visit", tags=["Visit Operations"])
app.include_router(record.router, prefix="/record", tags=["Record Operations"])
