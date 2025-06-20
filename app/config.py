from pydantic_settings import BaseSettings

"""
Config class for the Halo AI Scribe application.

This class contains the configuration for the application, including the MongoDB URL,
Anthropic API key, Deepgram API key, and cipher.
"""

class Settings(BaseSettings):
    """
    Settings class for the Halo AI Scribe application.

    MONGODB_URL: The MongoDB URL for the application.
    ANTHROPIC_API_KEY: The Anthropic API key for the application.
    ASSEMBLY_API_KEY: The AssemblyAI API key for the application.
    DEEPGRAM_API_KEY: The Deepgram API key for the application.
    CIPHER: The cipher for the application.
    """
    MONGODB_URL: str
    ANTHROPIC_API_KEY: str
    ASSEMBLY_API_KEY: str
    DEEPGRAM_API_KEY: str
    CIPHER: str
    class Config:
        env_file = ".env"

settings = Settings()
