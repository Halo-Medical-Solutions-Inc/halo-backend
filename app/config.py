from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URL: str
    ANTHROPIC_API_KEY: str
    ASSEMBLY_API_KEY: str
    CIPHER: str
    class Config:
        env_file = ".env"

settings = Settings()
