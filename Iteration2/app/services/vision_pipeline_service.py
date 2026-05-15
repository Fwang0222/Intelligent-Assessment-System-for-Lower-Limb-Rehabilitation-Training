"""V3 visual source pipeline: video-first stream provider."""

from __future__ import annotations

import os
from typing import Dict, Optional

CV2_OK = False
NP_OK = False
try:
    import cv2  # type: ignore

    CV2_OK = True
except Exception:
    CV2_OK = False
try:
    import numpy as np  # type: ignore

    NP_OK = True
except Exception:
    NP_OK = False


class VisionPipelineService:
    """Provide frame source for realtime training.

    Priority:
    1. Local video file stream (loop playback)
    2. Optional camera fallback
    3. Synthetic fallback frame
    """

    def __init__(self):
        self.cap = None
        self.mode = "idle"
        self.frame_w = 640
        self.frame_h = 420
        self.source_path: Optional[str] = None

    def start(self, video_path: str = "", allow_camera_fallback: bool = True) -> bool:
        self.stop()
        if CV2_OK and video_path and os.path.exists(video_path):
            cap = cv2.VideoCapture(video_path)
            if cap is not None and cap.isOpened():
                self.cap = cap
                self.mode = "video"
                self.source_path = video_path
                return True
        if CV2_OK and allow_camera_fallback:
            cap = cv2.VideoCapture(0)
            if cap is not None and cap.isOpened():
                self.cap = cap
                self.mode = "camera-fallback"
                self.source_path = None
                return True
        self.mode = "mock"
        self.source_path = None
        return False

    def stop(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.mode = "idle"
        self.source_path = None

    def _mock_frame(self):
        if not (CV2_OK and NP_OK):
            return None
        frame = np.zeros((self.frame_h, self.frame_w, 3), dtype=np.uint8)
        frame[:, :] = (243, 247, 255)
        for x in range(0, frame.shape[1], 40):
            frame[:, x:x + 1] = (220, 228, 240)
        for y in range(0, frame.shape[0], 40):
            frame[y:y + 1, :] = (220, 228, 240)
        return frame

    def next(self, frame_index: int) -> Dict:
        frame_rgb = None
        if self.cap is not None and CV2_OK:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                if self.mode == "video":
                    # loop playback
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = self.cap.read()
            if ok and frame is not None:
                frame = cv2.resize(frame, (self.frame_w, self.frame_h))
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if frame_rgb is None:
            frame_rgb = self._mock_frame()
        return {
            "source_mode": self.mode if self.mode != "idle" else "mock",
            "frame_rgb": frame_rgb,
            "frame_size": (self.frame_w, self.frame_h),
            "source_path": self.source_path,
        }
