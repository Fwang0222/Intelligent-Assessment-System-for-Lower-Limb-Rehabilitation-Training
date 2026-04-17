"""Runtime configuration for local/cloud inference switching."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "data", "runtime_config.json")


@dataclass
class RuntimeConfig:
    deployment_mode: str = "local"  # local | cloud | auto
    yolo_backend: str = "mock"  # mock | ultralytics | remote
    yolo_model_path: str = "yolo26s-pose.pt"
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
            "yolo_backend": os.getenv("REHAB_YOLO_BACKEND"),
            "yolo_model_path": os.getenv("REHAB_YOLO_MODEL_PATH"),
            "qwen_backend": os.getenv("REHAB_QWEN_BACKEND"),
            "qwen_endpoint": os.getenv("REHAB_QWEN_ENDPOINT"),
            "qwen_api_key": os.getenv("REHAB_QWEN_API_KEY"),
            "qwen_model": os.getenv("REHAB_QWEN_MODEL"),
            "request_timeout_seconds": os.getenv("REHAB_REQUEST_TIMEOUT_SECONDS"),
            "video_source_path": os.getenv("REHAB_VIDEO_SOURCE_PATH"),
            "roi_expand_ratio": os.getenv("REHAB_ROI_EXPAND_RATIO"),
        }
        for k, v in env_map.items():
            if v not in (None, ""):
                payload[k] = v

        cfg = cls()
        for field_name in cfg.__dataclass_fields__.keys():
            if field_name in payload:
                setattr(cfg, field_name, payload[field_name])

        try:
            cfg.request_timeout_seconds = float(cfg.request_timeout_seconds)
        except Exception:
            cfg.request_timeout_seconds = 3.0
        try:
            cfg.roi_expand_ratio = float(cfg.roi_expand_ratio)
        except Exception:
            cfg.roi_expand_ratio = 0.18
        cfg.deployment_mode = str(cfg.deployment_mode).lower()
        cfg.yolo_backend = str(cfg.yolo_backend).lower()
        cfg.qwen_backend = str(cfg.qwen_backend).lower()
        return cfg

    def is_cloud_enabled(self) -> bool:
        if self.deployment_mode == "cloud":
            return True
        if self.deployment_mode == "local":
            return False
        return self.qwen_backend == "cloud" or self.yolo_backend == "remote"

    def summary_text(self) -> str:
        return (
            f"mode={self.deployment_mode}, yolo={self.yolo_backend}, "
            f"qwen={self.qwen_backend}, yolo_model={self.yolo_model_path}, "
            f"cloud={'on' if self.is_cloud_enabled() else 'off'}"
        )
