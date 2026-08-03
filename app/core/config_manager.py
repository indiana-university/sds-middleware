"""Configuration management utilities for the project ``.env`` file."""
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import shutil

from dotenv import set_key

from app.core.config import ENV_FILE, settings


CONFIG_SECTIONS = {
    "webserver": (
        "url_base_path", "debug_level", "port", "env", "use_ssl", "cert_file",
        "key_file", "ssl_hostname", "client_secret", "site_secrets",
    ),
    "sds_sync": ("hsi_bin_path", "hsi_keytab_path", "hsi_user", "firewall_flag", "timeout_in_secs"),
    "sds_async": (
        "message_broker_host", "message_broker_port", "work_queue",
        "same_job_minimum_interval_in_min", "black_list",
    ),
    "worker": (
        "staging_dir", "smtp_server", "email_sender", "contact_email",
        "http_download_server", "staging_usage_threshold_in_gb",
    ),
    "database": ("host", "user", "password", "db", "job_table"),
    "logging": ("api_log_file", "worker_log_file"),
}


def get_config_file_path() -> Path:
    """Get the absolute path to the project .env file."""
    return ENV_FILE


def read_config_file() -> Dict[str, Dict[str, str]]:
    """Return the effective configuration, including environment overrides."""
    result = OrderedDict()
    for section, fields in CONFIG_SECTIONS.items():
        section_settings = getattr(settings, section)
        result[section] = OrderedDict(
            (
                field,
                json.dumps(getattr(section_settings, field))
                if field == "site_secrets"
                else str(getattr(section_settings, field)),
            )
            for field in fields
        )
    return dict(result)


def get_config_structure() -> List[Dict[str, Any]]:
    """Get the effective environment configuration with field metadata."""
    return [
        {
            "section": section_name,
            "fields": [
                {"key": key, "value": value, "type": infer_field_type(key, value)}
                for key, value in section_data.items()
            ],
        }
        for section_name, section_data in read_config_file().items()
    ]


def infer_field_type(key: str, value: str) -> str:
    """Infer a display type for an environment setting."""
    if "password" in key.lower() or "secret" in key.lower():
        return "password"
    if value.lower() in ["true", "false", "on", "off", "yes", "no"]:
        return "boolean"
    try:
        int(value)
        return "integer"
    except ValueError:
        return "string"


def update_config_file(updates: Dict[str, Dict[str, str]]) -> bool:
    """Write updates to .env using SECTION__FIELD variable names."""
    try:
        config_path = get_config_file_path()
        config_path.touch(exist_ok=True)
        for section, fields in updates.items():
            for key, value in fields.items():
                set_key(config_path, f"{section.upper()}__{key.upper()}", str(value), quote_mode="auto")
        return True
    except Exception as exc:
        print(f"Error updating .env file: {exc}")
        return False


def backup_config_file() -> Path:
    """Back up the current .env file before it is updated."""
    config_path = get_config_file_path()
    backup_dir = config_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f".env.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if config_path.exists():
        shutil.copy2(config_path, backup_path)
    return backup_path


def validate_config_updates(updates: Dict[str, Dict[str, str]]) -> List[str]:
    """Validate update keys and integer settings before writing .env."""
    errors = []
    integer_fields = {
        "port", "message_broker_port", "timeout_in_secs",
        "same_job_minimum_interval_in_min", "staging_usage_threshold_in_gb",
    }
    for section, fields in updates.items():
        if section not in CONFIG_SECTIONS:
            errors.append(f"Section '{section}' does not exist in configuration")
            continue
        for key, value in fields.items():
            if key not in CONFIG_SECTIONS[section]:
                errors.append(f"Key '{key}' does not exist in section '{section}'")
            elif key in integer_fields:
                try:
                    int(value)
                except (TypeError, ValueError):
                    errors.append(f"'{key}' must be an integer, got '{value}'")
    return errors
