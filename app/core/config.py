"""Application settings loaded from environment variables and the project .env file."""
from pathlib import Path
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class WebServerSettings(BaseSettings):
    url_base_path: str = "/"
    debug_level: str = "DEBUG"
    port: int = 8080
    env: str = "dev"
    use_ssl: str = "on"
    cert_file: str = "</path/to/fullchain.pem>"
    key_file: str = "</path/to/privkey.pem>"
    ssl_hostname: str = "<hostname>"
    client_secret: str = "<your-client-secret-here>"
    site_secrets: Dict[str, str] = Field(default_factory=dict)


class SdsSyncSettings(BaseSettings):
    hsi_bin_path: str = "/usr/local/bin"
    hsi_keytab_path: str = "</path/to/xxx.keytab>"
    hsi_user: str = "<hsi username>"
    firewall_flag: str = "on"
    timeout_in_secs: int = 3300


class SdsAsyncSettings(BaseSettings):
    message_broker_host: str = "localhost"
    message_broker_port: int = 5672
    work_queue: str = "isdp_task_queue"
    same_job_minimum_interval_in_min: int = 360
    black_list: str = "</path/to/black_list.txt>"


class WorkerSettings(BaseSettings):
    staging_dir: str = "staging"
    smtp_server: str = "localhost"
    email_sender: str = "<email_sender>"
    contact_email: str = "<contact_email>"
    http_download_server: str = "https://<hostname>/staging"
    staging_usage_threshold_in_gb: int = 1


class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 3306
    user: str = "dbtester"
    password: str = "<database-password>"
    db: str = "my_app_db"
    job_table: str = "user_jobs"


class LoggingSettings(BaseSettings):
    api_log_file: str = "api.log"
    worker_log_file: str = "worker.log"


class Settings(BaseSettings):
    """Nested settings populated by ``SECTION__FIELD`` environment variables."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    webserver: WebServerSettings = Field(default_factory=WebServerSettings)
    sds_sync: SdsSyncSettings = Field(default_factory=SdsSyncSettings)
    sds_async: SdsAsyncSettings = Field(default_factory=SdsAsyncSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


settings = Settings()
