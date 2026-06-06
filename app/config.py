from pydantic_settings import BaseSettings


class Configuracoes(BaseSettings):
    SECRET_KEY: str = "chave-padrao-insegura-troque-no-dotenv"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


config = Configuracoes()
