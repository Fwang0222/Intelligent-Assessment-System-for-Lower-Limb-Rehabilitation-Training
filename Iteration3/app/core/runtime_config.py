"""Runtime configuration for local AI + cloud medical-data deployment."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from typing import Any, Dict


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_CONFIG_PATH = os.path.join(DATA_DIR, "runtime_config.json")


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class RuntimeConfig:
    deployment_mode: str = "local"  # local | cloud | auto
    data_backend: str = "sqlite"  # sqlite | postgres
    sqlite_cache_path: str = os.path.join(DATA_DIR, "rehab_system.db")
    postgres_host: str = ""
    postgres_port: int = 5432
    postgres_db: str = ""
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_ssl_mode: str = "require"
    postgres_ssl_root_cert: str = ""
    postgres_connect_timeout: float = 5.0
    allow_insecure_db: bool = False
    remote_doctor_access_enabled: bool = True
    backup_dir: str = os.path.join(DATA_DIR, "backups")
    report_export_dir: str = os.path.join(DATA_DIR, "exports")
    audit_retention_days: int = 90
    workstation_id: str = socket.gethostname()

    yolo_backend: str = "mock"  # mock | ultralytics | remote
    yolo_model_path: str = "yolo26s-pose.pt"
    yolo_device: str = "cpu"
    qwen_backend: str = "mock"  # mock | local | cloud
    qwen_endpoint: str = ""
    qwen_api_key: str = ""
    qwen_model: str = "qwen-vl-max-latest"
    request_timeout_seconds: float = 3.0
    video_source_path: str = ""
    roi_expand_ratio: float = 0.18

    @classmethod
    def from_sources(cls, config_path: str = DEFAULT_CONFIG_PATH) -> "RuntimeConfig":
        payload: Dict[str, Any] = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_payload = json.load(f)
                if isinstance(file_payload, dict):
                    payload.update(file_payload)
            except Exception:
                pass

        env_map = {
            "deployment_mode": os.getenv("REHAB_DEPLOYMENT_MODE"),
            "data_backend": os.getenv("REHAB_DATA_BACKEND"),
            "sqlite_cache_path": os.getenv("REHAB_SQLITE_CACHE_PATH"),
            "postgres_host": os.getenv("REHAB_PG_HOST"),
            "postgres_port": os.getenv("REHAB_PG_PORT"),
            "postgres_db": os.getenv("REHAB_PG_DB"),
            "postgres_user": os.getenv("REHAB_PG_USER"),
            "postgres_password": os.getenv("REHAB_PG_PASSWORD"),
            "postgres_ssl_mode": os.getenv("REHAB_PG_SSLMODE"),
            "postgres_ssl_root_cert": os.getenv("REHAB_PG_SSLROOTCERT"),
            "postgres_connect_timeout": os.getenv("REHAB_PG_CONNECT_TIMEOUT"),
            "allow_insecure_db": os.getenv("REHAB_ALLOW_INSECURE_DB"),
            "remote_doctor_access_enabled": os.getenv("REHAB_REMOTE_DOCTOR_ACCESS"),
            "backup_dir": os.getenv("REHAB_BACKUP_DIR"),
            "report_export_dir": os.getenv("REHAB_REPORT_EXPORT_DIR"),
            "audit_retention_days": os.getenv("REHAB_AUDIT_RETENTION_DAYS"),
            "workstation_id": os.getenv("REHAB_WORKSTATION_ID"),
            "yolo_backend": os.getenv("REHAB_YOLO_BACKEND"),
            "yolo_model_path": os.getenv("REHAB_YOLO_MODEL_PATH"),
            "yolo_device": os.getenv("REHAB_YOLO_DEVICE"),
            "qwen_backend": os.getenv("REHAB_QWEN_BACKEND"),
            "qwen_endpoint": os.getenv("REHAB_QWEN_ENDPOINT"),
            "qwen_api_key": os.getenv("REHAB_QWEN_API_KEY"),
            "qwen_model": os.getenv("REHAB_QWEN_MODEL"),
            "request_timeout_seconds": os.getenv("REHAB_REQUEST_TIMEOUT_SECONDS"),
            "video_source_path": os.getenv("REHAB_VIDEO_SOURCE_PATH"),
            "roi_expand_ratio": os.getenv("REHAB_ROI_EXPAND_RATIO"),
        }
        for key, value in env_map.items():
            if value not in (None, ""):
                payload[key] = value

        cfg = cls()
        for field_name in cfg.__dataclass_fields__.keys():
            if field_name in payload:
                setattr(cfg, field_name, payload[field_name])

        cfg.deployment_mode = str(cfg.deployment_mode).lower()
        cfg.data_backend = str(cfg.data_backend).lower()
        cfg.yolo_backend = str(cfg.yolo_backend).lower()
        cfg.yolo_device = str(cfg.yolo_device or "cpu").lower()
        cfg.qwen_backend = str(cfg.qwen_backend).lower()
        cfg.postgres_ssl_mode = str(cfg.postgres_ssl_mode).lower()

        try:
            cfg.request_timeout_seconds = float(cfg.request_timeout_seconds)
        except Exception:
            cfg.request_timeout_seconds = 3.0
        try:
            cfg.roi_expand_ratio = float(cfg.roi_expand_ratio)
        except Exception:
            cfg.roi_expand_ratio = 0.18
        try:
            cfg.postgres_connect_timeout = float(cfg.postgres_connect_timeout)
        except Exception:
            cfg.postgres_connect_timeout = 5.0
        try:
            cfg.postgres_port = int(cfg.postgres_port)
        except Exception:
            cfg.postgres_port = 5432
        try:
            cfg.audit_retention_days = int(cfg.audit_retention_days)
        except Exception:
            cfg.audit_retention_days = 90

        cfg.allow_insecure_db = _as_bool(cfg.allow_insecure_db, default=False)
        cfg.remote_doctor_access_enabled = _as_bool(cfg.remote_doctor_access_enabled, default=True)
        cfg.backup_dir = cfg.backup_dir or os.path.join(DATA_DIR, "backups")
        cfg.report_export_dir = cfg.report_export_dir or os.path.join(DATA_DIR, "exports")
        cfg.sqlite_cache_path = cfg.sqlite_cache_path or os.path.join(DATA_DIR, "rehab_system.db")
        cfg.workstation_id = str(cfg.workstation_id or socket.gethostname())
        return cfg

    def is_cloud_enabled(self) -> bool:
        if self.deployment_mode == "cloud":
            return True
        if self.deployment_mode == "local":
            return False
        return self.qwen_backend == "cloud" or self.yolo_backend == "remote" or self.is_cloud_storage_enabled()

    def is_cloud_storage_enabled(self) -> bool:
        return self.data_backend == "postgres"

    def summary_text(self) -> str:
        storage_text = "cloud-postgres" if self.is_cloud_storage_enabled() else "local-sqlite"
        return (
            f"mode={self.deployment_mode}, data={storage_text}, "
            f"yolo={self.yolo_backend}, qwen={self.qwen_backend}, "
            f"yolo_model={self.yolo_model_path}, device={self.yolo_device}, ai=local-first"
        )
