import secrets

from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, computed_field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )
    LOG_FILE_PATH_DIR: str = "/opt/apps/logs/traffic_mide/"
    LOG_FILE_NAME: str = "main.log"

    AUTH_TOKEN_URL: str = "api/v1/auth/token"
    AUTH_SECRET_KEY: str = ""
    AUTH_ALGORITHM: str = "HS256"
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgresql"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "traffic_mind"
    
    @computed_field 
    @property
    def sqlalchemy_database_uri(self) -> PostgresDsn:
        url = MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
            query="sslmode=disable"
        )
        return PostgresDsn(url)

    @computed_field
    @property
    def postgres_database_uri(self) -> PostgresDsn:
        url = MultiHostUrl.build(
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
            query="sslmode=disable"
        )
        return PostgresDsn(url)

    WCO_HSCODE_MAIN_URL: str = "https://www.wcotradetools.org"
    HTS_CURRENT_RELEASE_URL: str = "https://hts.usitc.gov/reststop/currentRelease"
    HTS_EXPORT_CURRENT_JSON_URL: str = "https://hts.usitc.gov/reststop/exportList"

    DASHSCOPE_API_KEY: str

    VECTOR_STORE_INDEX_DIR: str
    VECTOR_STORE_INDEX_NAME: str

    OPEN_SEARCH_HOSTS: list[str]
    OPEN_SEARCH_USERNAME: str
    OPEN_SEARCH_PASSWORD: str

settings = Settings()