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

    # Anthropic Claude — IA narrativa da agenda (Sub-PR 17b)
    ANTHROPIC_API_KEY: str = ""
    # Haiku 4.5 — barato e rápido. Sonnet 4.6 (`claude-sonnet-4-6`) tem mais
    # depth pra análise mas custa ~5x mais. Trocar via env sem redeploy.
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"

    # Meta Graph API — Sub-PR 21b/c. Token + IDs por tenant ficam em
    # `stg_meta_tokens` (multi-tenant); aqui só fica versão da Graph.
    META_GRAPH_API_VERSION: str = "v19.0"

    @property
    def META_GRAPH_URL(self) -> str:
        return f"https://graph.facebook.com/{self.META_GRAPH_API_VERSION}"

    # DeepSeek — IA narrativa da SonIA (FAB de insights por página).
    # API compatível com OpenAI. ~13× mais barato que Sonnet 4.6.
    # Modelos: `deepseek-chat` (V3, padrão) ou `deepseek-reasoner` (R1, raciocínio).
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
