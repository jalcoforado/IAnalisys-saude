from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "IAnalisys Saúde"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Conta Azul
    CONTAAZUL_CLIENT_ID: str = ""
    CONTAAZUL_CLIENT_SECRET: str = ""
    CONTAAZUL_REDIRECT_URI: str = "http://localhost:8000/api/v1/contaazul/callback"

    # Clinicorp
    CLINICORP_API_URL: str = "https://api.clinicorp.com/rest/v1"
    CLINICORP_API_USER: str = ""
    CLINICORP_API_TOKEN: str = ""
    CLINICORP_SUBSCRIBER_ID: str = ""
    CLINICORP_BUSINESS_ID: str = ""

    # SMTP — para reset de senha e notificações via email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "IAnalisys Saúde"
    SMTP_FROM_EMAIL: str = ""

    # URL pública do app — usada em links enviados por email
    APP_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
