from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str
    database_url_admin: str
    secret_key: str

    oci_endpoint_url: str
    oci_bucket: str
    oci_access_key_id: str
    oci_secret_access_key: str
    oci_admin_access_key_id: str
    oci_admin_secret_access_key: str

    environment: str = "development"

    frontend_origin: str = "http://localhost:5173"


settings = Settings()
