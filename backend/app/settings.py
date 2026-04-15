# from pathlib import Path
# from pydantic import field_validator
# from pydantic_settings import BaseSettings, SettingsConfigDict


# BACKEND_ROOT = Path(__file__).resolve().parents[1]


# class Settings(BaseSettings):
#     model_config = SettingsConfigDict(
#         env_file=BACKEND_ROOT / ".env",
#         env_file_encoding="utf-8",
#         extra="ignore",
#     )

#     APP_SECRET: str
#     JWT_EXPIRE_MIN: int = 1440

#     COHERE_API_KEY: str | None = None
#     KIE_API_KEY: str | None = None
#     CLOUDINARY_CLOUD_NAME: str | None = None
#     CLOUDINARY_API_KEY: str | None = None
#     CLOUDINARY_API_SECRET: str | None = None

#     PIPELINE1_DIR: str = "../Interior_Design"
#     PIPELINE1_CUSTOM_DIR: str = "../Interior_Design_pipeline_1_part_2"
#     PIPELINE2_DIR: str = "../Interior_Design_pipeline_2_furniture_uploaded"
#     STORAGE_DIR: str = "./storage"

#     MONGODB_URI: str

#     SMTP_HOST: str
#     SMTP_PORT: int
#     SMTP_USER: str
#     SMTP_PASS: str

#     GOOGLE_CLIENT_ID: str | None = None
#     GOOGLE_CLIENT_SECRET: str | None = None

#     BACKEND_BASE_URL: str
#     FRONTEND_URL: str

#     @field_validator("BACKEND_BASE_URL", "FRONTEND_URL", mode="before")
#     @classmethod
#     def clean_urls(cls, v: str) -> str:
#         if not isinstance(v, str):
#             return v
#         return v.strip().rstrip("/")

#     @property
#     def GOOGLE_REDIRECT_URI(self) -> str:
#         return f"{self.BACKEND_BASE_URL}/auth/google/callback"


# settings = Settings()

from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_SECRET: str
    JWT_EXPIRE_MIN: int = 1440

    COHERE_API_KEY: str | None = None
    KIE_API_KEY: str | None = None
    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = None

    PIPELINE1_DIR: str = "../Interior_Design"
    PIPELINE1_CUSTOM_DIR: str = "../Interior_Design_pipeline_1_part_2"
    PIPELINE2_DIR: str = "../Interior_Design_pipeline_2_furniture_uploaded"
    STORAGE_DIR: str = "./storage"

    MONGODB_URI: str

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASS: str

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    BACKEND_BASE_URL: str
    FRONTEND_URL: str

    @field_validator("BACKEND_BASE_URL", "FRONTEND_URL", mode="before")
    @classmethod
    def clean_urls(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        return v.strip().rstrip("/")

    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        return f"{self.BACKEND_BASE_URL}/auth/google/callback"


settings = Settings()