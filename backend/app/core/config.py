from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str
    jwt_secret: str
    token_minutes: int = 60

    @field_validator('database_url')
    @classmethod
    def postgres_only(cls, value):
        if not value.startswith('postgresql+psycopg://'):
            raise ValueError('Only PostgreSQL with psycopg is supported')
        return value

    @field_validator('jwt_secret')
    @classmethod
    def secret_length(cls, value):
        if len(value) < 32 or value.startswith('REPLACE_'):
            raise ValueError('JWT_SECRET must be a random secret of at least 32 characters')
        return value


@lru_cache
def settings():
    return Settings()
