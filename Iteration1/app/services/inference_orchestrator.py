"""Inference orchestrator: YOLO pose -> pose rendering -> ROI crop -> Qwen eval."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from app.core.runtime_config import RuntimeConfig
from app.services.algorithm_service import MockAlgorithmService
from app.services.qwen_service import QwenInferenceAdapter
from app.services.yolo_service import YoloPoseAdapter

CV2_OK = False
try:
    import cv2  # type: ignore

    CV2_OK = True
except Exception:
    CV2_OK = False


class V3InferenceOrchestrator:
    """Pipeline orchestration with safe fallback to legacy mock service."""

    def __init__(self, config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig.from_sources()
        self.yolo = YoloPoseAdapter(self.config)
        self.qwen = QwenInferenceAdapter(self.config)
        self.legacy_mock = MockAlgorithmService()
        self.qwen_interval_seconds = 5
        self._last_qwen_bucket = -1
        self._last_qwen_payload: Dict | None = None

    @staticmethod
    def _calculate_lower_limb_angles(points: List) -> Dict[str, float]:
        left_leg_angle = 0.0
        right_leg_angle = 0.0
        if len(points) >= 7:
            left_leg_angle = round(abs(points[4][1] - points[3][1]), 2)
            right_leg_angle = round(abs(points[6][1] - points[5][1]), 2)
        return {
            "left_leg_angle": left_leg_angle,
            "right_leg_angle": right_leg_angle,
            "trunk_forward_angle": round(abs(points[2][0] - points[1][0]) * 0.4, 2) if len(points) >= 3 else 8.0,
            "knee_valgus_angle": round(abs(left_leg_angle - right_leg_angle) * 0.22, 2),
        }

    def _draw_pose(self, frame_rgb, keypoints, roi_box):
        if frame_rgb is None or not CV2_OK:
            return None
        canvas = frame_rgb.copy()
        pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (2, 5), (5, 6)]
        for a, b in pairs:
            if a < len(keypoints) and b < len(keypoints):
                pa = (int(keypoints[a][0]), int(keypoints[a][1]))
                pb = (int(keypoints[b][0]), int(keypoints[b][1]))
                cv2.line(canvas, pa, pb, (30, 220, 230), 2)
        for x, y in keypoints:
            cv2.circle(canvas, (int(x), int(y)), 4, (40, 130, 255), -1)
        if roi_box:
            x, y, w, h = int(roi_box["x"]), int(roi_box["y"]), int(roi_box["w"]), int(roi_box["h"])
            cv2.rectangle(canvas, (x, y), (x + w, y + h), (255, 80, 80), 2)
        return canvas

    def _crop_roi(self, frame_rgb, roi_box):
        if frame_rgb is None or not roi_box:
            return None
        h = frame_rgb.shape[0]
        w = frame_rgb.shape[1]
        x = max(0, min(w - 1, int(roi_box.get("x", 0))))
        y = max(0, min(h - 1, int(roi_box.get("y", 0))))
        rw = max(1, int(roi_box.get("w", 1)))
        rh = max(1, int(roi_box.get("h", 1)))
        x2 = min(w, x + rw)
        y2 = min(h, y + rh)
        if y2 <= y or x2 <= x:
            return None
        return frame_rgb[y:y2, x:x2].copy()

    def extract_pose_features(self, frame_rgb=None, frame_index: int = 1, expected_action: str = "Seated Knee Raise") -> Dict:
        pose_payload = self.yolo.infer_pose(frame_rgb=frame_rgb, frame_index=frame_index, expected_action=expected_action)
        points: List = pose_payload.get("keypoints", [])
        roi = pose_payload.get("roi", {})
        pose_overlay = self._draw_pose(frame_rgb, points, roi)
        roi_crop = self._crop_roi(frame_rgb, roi)
        return {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "frame_index": frame_index,
            "pose_payload": pose_payload,
            "lower_limb_angles": self._calculate_lower_limb_angles(points),
            "roi_box": roi if roi else {"x": 150, "y": 70, "w": 360, "h": 300},
            "pose_frame_rgb": pose_overlay,
            "roi_frame_rgb": roi_crop,
        }

    def quick_assess_pose(self, pose_payload: Dict, expected_action: str, elapsed_seconds: int) -> Dict:
        return self.qwen.rule_based_eval(pose_payload, expected_action, elapsed_seconds)

    def evaluate_pose_with_qwen(
        self,
        pose_features: Dict,
        expected_action: str,
        elapsed_seconds: int = 0,
        original_frame_rgb=None,
    ) -> Dict:
        return self.qwen.evaluate(
            pose_payload=pose_features.get("pose_payload", {}),
            expected_action=expected_action,
            elapsed_seconds=elapsed_seconds,
            original_frame_rgb=original_frame_rgb,
            pose_frame_rgb=pose_features.get("pose_frame_rgb"),
            roi_rgb=pose_features.get("roi_frame_rgb"),
        )

    @staticmethod
    def compose_frame_result(
        pose_features: Dict,
        qwen_payload: Dict,
        expected_action: str,
        deployment_mode: str = "local",
        qwen_interval_seconds: int = 5,
    ) -> Dict:
        scores = qwen_payload.get("scores", {})
        pose_payload = pose_features.get("pose_payload", {})
        return {
            "timestamp": pose_features.get("timestamp", datetime.now().strftime("%H:%M:%S")),
            "frame_index": pose_features.get("frame_index", 1),
            "action_label": qwen_payload.get("action_label", expected_action),
            "action_phase": qwen_payload.get("action_phase", "Execution"),
            "lower_limb_angles": dict(pose_features.get("lower_limb_angles", {})),
            "roi_box": pose_features.get("roi_box", {"x": 150, "y": 70, "w": 360, "h": 300}),
            "pose_frame_rgb": pose_features.get("pose_frame_rgb"),
            "roi_frame_rgb": pose_features.get("roi_frame_rgb"),
            "accuracy_score": float(scores.get("accuracy_score", 78.0)),
            "stability_score": float(scores.get("stability_score", 78.0)),
            "range_score": float(scores.get("range_score", 78.0)),
            "rhythm_score": float(scores.get("rhythm_score", 78.0)),
            "symmetry_score": float(scores.get("symmetry_score", 78.0)),
            "total_score": float(scores.get("total_score", 78.0)),
            "errors": list(qwen_payload.get("errors", [])),
            "compensations": list(qwen_payload.get("compensations", [])),
            "feedbacks": list(qwen_payload.get("feedbacks", [])),
            "pipeline_meta": {
                "mode": deployment_mode,
                "yolo_provider": pose_payload.get("provider", "unknown"),
                "qwen_provider": qwen_payload.get("provider", "unknown"),
                "qwen_interval_seconds": qwen_interval_seconds,
            },
        }

    def analyze_frame(
        self,
        expected_action: str = "Seated Knee Raise",
        frame_index: int = 1,
        cycle_progress: float = 0.0,
        elapsed_seconds: int = 0,
        frame_rgb=None,
    ) -> Dict:
        try:
            pose_features = self.extract_pose_features(frame_rgb=frame_rgb, frame_index=frame_index, expected_action=expected_action)
            qwen_bucket = elapsed_seconds // self.qwen_interval_seconds
            should_query_qwen = self._last_qwen_payload is None or qwen_bucket > self._last_qwen_bucket
            if should_query_qwen:
                qwen_payload = self.evaluate_pose_with_qwen(
                    pose_features=pose_features,
                    expected_action=expected_action,
                    elapsed_seconds=elapsed_seconds,
                    original_frame_rgb=frame_rgb,
                )
                self._last_qwen_payload = qwen_payload
                self._last_qwen_bucket = qwen_bucket
            else:
                qwen_payload = dict(self._last_qwen_payload or {})
                qwen_payload["provider"] = f"{qwen_payload.get('provider', 'cached')}-cached"
            return self.compose_frame_result(
                pose_features=pose_features,
                qwen_payload=qwen_payload,
                expected_action=expected_action,
                deployment_mode=self.config.deployment_mode,
                qwen_interval_seconds=self.qwen_interval_seconds,
            )
        except Exception:
            result = self.legacy_mock.analyze_frame(expected_action, frame_index, cycle_progress, elapsed_seconds)
            result["pipeline_meta"] = {
                "mode": self.config.deployment_mode,
                "yolo_provider": "fallback-mock",
                "qwen_provider": "fallback-mock",
                "qwen_interval_seconds": self.qwen_interval_seconds,
            }
            result["pose_frame_rgb"] = frame_rgb
            result["roi_frame_rgb"] = None
            return result

    def summarize_session(self, expected_action: str, results: List[Dict], completion_rate: float) -> Dict:
        return self.legacy_mock.summarize_session(expected_action, results, completion_rate)
