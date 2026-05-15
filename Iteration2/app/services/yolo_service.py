"""YOLOv11/26 pose adapter with local model placeholder integration."""

from __future__ import annotations

import math
import os
from typing import Dict, List, Tuple

from app.core.runtime_config import DATA_DIR, RuntimeConfig

os.makedirs(os.path.join(DATA_DIR, "ultralytics"), exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", os.path.join(DATA_DIR, "ultralytics"))

ULTRALYTICS_OK = False
try:
    from ultralytics import YOLO  # type: ignore

    ULTRALYTICS_OK = True
except Exception:
    ULTRALYTICS_OK = False


Point = Tuple[float, float]


class _KeypointSmoother:
    def __init__(self, alpha: float = 0.35):
        self.alpha = alpha
        self.state: List[Point] | None = None

    def reset(self) -> None:
        self.state = None

    def apply(self, points: List[Point]) -> List[Point]:
        if self.state is None or len(self.state) != len(points):
            self.state = list(points)
            return list(points)
        out: List[Point] = []
        for (px, py), (sx, sy) in zip(points, self.state):
            nx = self.alpha * px + (1 - self.alpha) * sx
            ny = self.alpha * py + (1 - self.alpha) * sy
            out.append((nx, ny))
        self.state = out
        return out


class YoloPoseAdapter:
    """Adapter layer for local YOLO pose model.

    Priority:
    1. local `ultralytics` backend with `yolo26s-pose.pt` (or configured path)
    2. fallback synthetic output
    """

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.model = None
        self.backend_used = "mock"
        self.smoother = _KeypointSmoother(alpha=0.35)
        self._init_backend()

    def _init_backend(self) -> None:
        if self.config.yolo_backend == "ultralytics" and ULTRALYTICS_OK:
            model_path = self.config.yolo_model_path or "yolo26s-pose.pt"
            try:
                if os.path.exists(model_path):
                    self.model = YOLO(model_path)
                    self.backend_used = f"ultralytics:{os.path.basename(model_path)}"
                    return
                # try load official model by name if local path missing
                self.model = YOLO(model_path)
                self.backend_used = f"ultralytics:{model_path}"
                return
            except Exception:
                self.model = None
        elif self.config.yolo_backend == "remote":
            self.backend_used = "remote-placeholder"
            return
        self.backend_used = "mock"

    def _mock_keypoints(self, frame_index: int) -> List[Point]:
        cx, cy = 320.0, 220.0
        t = frame_index / 7.0
        sway = math.sin(t) * 8.0
        lift = (math.sin(t) + 1.0) * 24.0
        return [
            (cx + sway, cy - 170),  # head
            (cx + sway, cy - 130),  # shoulder
            (cx + sway, cy - 85),   # hip
            (cx - 38 + sway, cy + 42 - lift * 0.5),  # left knee
            (cx - 35 + sway, cy + 130 - lift),       # left ankle
            (cx + 38 + sway, cy + 48),               # right knee
            (cx + 35 + sway, cy + 130),              # right ankle
        ]

    def _roi_from_xyxy(self, x1: float, y1: float, x2: float, y2: float, frame_w: int, frame_h: int) -> Dict[str, int]:
        bw = x2 - x1
        bh = y2 - y1
        ex = bw * self.config.roi_expand_ratio
        ey = bh * self.config.roi_expand_ratio
        rx1 = int(max(0, x1 - ex))
        ry1 = int(max(0, y1 - ey))
        rx2 = int(min(frame_w - 1, x2 + ex))
        ry2 = int(min(frame_h - 1, y2 + ey))
        return {"x": rx1, "y": ry1, "w": max(10, rx2 - rx1), "h": max(10, ry2 - ry1)}

    def _roi_from_points(self, points: List[Point], frame_w: int, frame_h: int) -> Dict[str, int]:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x_min = int(max(0, min(xs) - 70))
        y_min = int(max(0, min(ys) - 55))
        x_max = int(min(frame_w - 1, max(xs) + 70))
        y_max = int(min(frame_h - 1, max(ys) + 55))
        return {"x": x_min, "y": y_min, "w": max(10, x_max - x_min), "h": max(10, y_max - y_min)}

    def _infer_ultralytics(self, frame_rgb, expected_action: str) -> Dict | None:
        if self.model is None:
            return None
        try:
            results = self.model(frame_rgb, verbose=False)
            if not results:
                return None
            result = results[0]
            if result.keypoints is None or result.keypoints.xy is None:
                return None
            keypoints_xy = result.keypoints.xy
            if keypoints_xy is None or len(keypoints_xy) == 0:
                return None

            person_idx = 0
            if getattr(result, "boxes", None) is not None and result.boxes.conf is not None:
                confs = result.boxes.conf.tolist()
                if confs:
                    person_idx = int(max(range(len(confs)), key=lambda i: confs[i]))
            pts_raw = keypoints_xy[person_idx].tolist()
            points = [(float(p[0]), float(p[1])) for p in pts_raw]
            points = self.smoother.apply(points)

            frame_h = frame_rgb.shape[0]
            frame_w = frame_rgb.shape[1]
            roi = self._roi_from_points(points, frame_w=frame_w, frame_h=frame_h)
            if getattr(result, "boxes", None) is not None and len(result.boxes.xyxy) > person_idx:
                x1, y1, x2, y2 = [float(v) for v in result.boxes.xyxy[person_idx].tolist()]
                roi = self._roi_from_xyxy(x1, y1, x2, y2, frame_w=frame_w, frame_h=frame_h)

            return {
                "provider": self.backend_used,
                "action_hint": expected_action,
                "confidence": 0.9,
                "keypoints": points,
                "roi": roi,
            }
        except Exception:
            return None

    def infer_pose(self, frame_rgb, frame_index: int, expected_action: str) -> Dict:
        if frame_rgb is not None and self.backend_used.startswith("ultralytics"):
            out = self._infer_ultralytics(frame_rgb, expected_action)
            if out is not None:
                return out

        # fallback
        frame_h, frame_w = (420, 640)
        if frame_rgb is not None:
            frame_h, frame_w = frame_rgb.shape[0], frame_rgb.shape[1]
        points = self.smoother.apply(self._mock_keypoints(frame_index))
        roi = self._roi_from_points(points, frame_w=frame_w, frame_h=frame_h)
        return {
            "provider": "mock-fallback" if self.backend_used != "mock" else "mock",
            "action_hint": expected_action,
            "confidence": 0.86,
            "keypoints": points,
            "roi": roi,
        }
