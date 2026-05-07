from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # minio settings
    minio_root_user: str
    minio_root_password: str
    minio_endpoint: str
    minio_bucket_bronze: str = "bronze"
    minio_bucket_silver: str = "silver"
    minio_bucket_gold: str = "gold"

    # prefect settings
    prefect_server_ui_api_url: str

    # load environment variables from .env file
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=(".env"), env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
