import os
from pydantic import BaseModel
from typing import Optional

class Settings(BaseModel):
    app_name: str = "Gaming Second Brain"
    version: str = "1.0.0"
    db_path: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gaming_brain.db")
    gemini_api_key: Optional[str] = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    gemini_model: str = "gemini-2.0-flash"
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", 8000))

settings = Settings()
