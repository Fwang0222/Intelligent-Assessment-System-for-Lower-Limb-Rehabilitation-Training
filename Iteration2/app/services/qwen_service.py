"""Qwen multimodal wrapper: original frame + pose frame + ROI crop."""

from __future__ import annotations

import base64
import json
import re
from typing import Dict, List, Optional

from app.core.runtime_config import RuntimeConfig

REQUESTS_OK = False
CV2_OK = False
try:
    import requests  # type: ignore

    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

try:
    import cv2  # type: ignore

    CV2_OK = True
except Exception:
    CV2_OK = False


DEFAULT_QWEN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


class QwenInferenceAdapter:
    """Encapsulate Qwen multimodal evaluation call."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.provider = "rule-based"
        if self.config.qwen_backend in {"cloud", "local"}:
            self.provider = f"qwen-{self.config.qwen_backend}"

    def _b64_image_url(self, image_rgb) -> Optional[str]:
        if image_rgb is None or not CV2_OK:
            return None
        try:
            image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
            ok, buf = cv2.imencode(".jpg", image_bgr)
            if not ok:
                return None
            encoded = base64.b64encode(buf.tobytes()).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded}"
        except Exception:
            return None

    def rule_based_eval(self, pose_payload: Dict, expected_action: str, elapsed_seconds: int) -> Dict:
        kps = pose_payload.get("keypoints", [])
        if len(kps) < 7:
            return {
                "action_label": expected_action,
                "action_phase": "Execution",
                "scores": {
                    "accuracy_score": 75.0,
                    "stability_score": 75.0,
                    "range_score": 75.0,
                    "rhythm_score": 75.0,
                    "symmetry_score": 75.0,
                    "total_score": 75.0,
                },
                "errors": [],
                "compensations": [],
                "feedbacks": ["Pose data is limited; keep movement controlled."],
                "provider": "rule-based-fallback",
            }

        hip = kps[2]
        lk = kps[3]
        la = kps[4]
        rk = kps[5]
        ra = kps[6]
        left_leg_angle = abs(la[1] - lk[1])
        right_leg_angle = abs(ra[1] - rk[1])
        symmetry_delta = abs(left_leg_angle - right_leg_angle)

        phase = "Execution"
        cycle = elapsed_seconds % 8
        if cycle <= 1:
            phase = "Start"
        elif cycle <= 4:
            phase = "Execution"
        elif cycle <= 5:
            phase = "Peak/Hold"
        else:
            phase = "Recovery"

        range_score = max(55.0, min(98.0, 62 + max(left_leg_angle, right_leg_angle) * 0.5))
        symmetry_score = max(55.0, min(96.0, 96 - symmetry_delta * 1.6))
        stability_score = max(58.0, min(95.0, 88 - abs(hip[0] - 320) * 0.6))
        rhythm_score = 88.0 if phase in {"Execution", "Peak/Hold"} else 82.0
        accuracy_score = (range_score + symmetry_score + stability_score) / 3
        total = round((accuracy_score + stability_score + range_score + rhythm_score + symmetry_score) / 5, 2)

        errors: List[Dict] = []
        compensations: List[Dict] = []
        feedbacks: List[str] = []
        if range_score < 72:
            errors.append({
                "error_type": "Insufficient leg raise height",
                "error_count": 1,
                "severity": "medium",
                "suggestion": "Raise the leg slightly higher while keeping pain-free control.",
            })
        if symmetry_score < 78:
            errors.append({
                "error_type": "Left-right asymmetry",
                "error_count": 1,
                "severity": "medium",
                "suggestion": "Balance movement amplitude on both sides.",
            })
            compensations.append({
                "compensation_type": "Support-side shift",
                "detected_count": 1,
                "risk_level": "medium",
                "suggestion": "Center pelvis and avoid overloading one side.",
            })
        if abs(hip[0] - 320) > 12:
            compensations.append({
                "compensation_type": "Body side-lean compensation",
                "detected_count": 1,
                "risk_level": "high",
                "suggestion": "Control trunk alignment and keep core engaged.",
            })

        if errors:
            feedbacks.append(f"Detected {errors[0]['error_type']}. {errors[0]['suggestion']}")
        if compensations:
            feedbacks.append(f"Detected {compensations[0]['compensation_type']}. {compensations[0]['suggestion']}")
        if not feedbacks:
            feedbacks.append("Good movement quality. Keep current rhythm.")

        return {
            "action_label": expected_action,
            "action_phase": phase,
            "scores": {
                "accuracy_score": round(accuracy_score, 2),
                "stability_score": round(stability_score, 2),
                "range_score": round(range_score, 2),
                "rhythm_score": round(rhythm_score, 2),
                "symmetry_score": round(symmetry_score, 2),
                "total_score": total,
            },
            "errors": errors,
            "compensations": compensations,
            "feedbacks": feedbacks,
            "provider": "rule-based-fallback",
        }

    def _extract_json(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        text = text.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data
            except Exception:
                return None
        return None

    def _call_qwen(
        self,
        expected_action: str,
        pose_payload: Dict,
        original_frame_rgb=None,
        pose_frame_rgb=None,
        roi_rgb=None,
    ) -> Optional[Dict]:
        if not REQUESTS_OK:
            return None
        endpoint = self.config.qwen_endpoint or DEFAULT_QWEN_ENDPOINT
        api_key = self.config.qwen_api_key
        if not endpoint or not api_key:
            return None

        original_url = self._b64_image_url(original_frame_rgb)
        pose_url = self._b64_image_url(pose_frame_rgb)
        roi_url = self._b64_image_url(roi_rgb)

        content = [{
            "type": "text",
            "text": (
                "You are a lower-limb rehabilitation evaluator. "
                "Given original frame, pose-overlay frame, and ROI crop, return JSON only with fields: "
                "action_label, action_phase, scores{accuracy_score,stability_score,range_score,rhythm_score,symmetry_score,total_score}, "
                "errors(list of {error_type,error_count,severity,suggestion}), "
                "compensations(list of {compensation_type,detected_count,risk_level,suggestion}), "
                "feedbacks(list of short coaching strings). "
                f"Expected action: {expected_action}. "
                f"Pose metadata: {json.dumps(pose_payload, ensure_ascii=False)}"
            ),
        }]
        if original_url:
            content.append({"type": "image_url", "image_url": {"url": original_url}})
        if pose_url:
            content.append({"type": "image_url", "image_url": {"url": pose_url}})
        if roi_url:
            content.append({"type": "image_url", "image_url": {"url": roi_url}})

        body = {
            "model": self.config.qwen_model,
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
            "temperature": 0.2,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        try:
            resp = requests.post(endpoint, json=body, headers=headers, timeout=self.config.request_timeout_seconds)
            resp.raise_for_status()
            payload = resp.json()
            choices = payload.get("choices", [])
            if not choices:
                return None
            message = choices[0].get("message", {})
            content_text = message.get("content", "")
            if isinstance(content_text, list):
                text_parts = []
                for item in content_text:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                content_text = "\n".join(text_parts)
            parsed = self._extract_json(str(content_text))
            return parsed
        except Exception:
            return None

    def evaluate(
        self,
        pose_payload: Dict,
        expected_action: str,
        elapsed_seconds: int = 0,
        original_frame_rgb=None,
        pose_frame_rgb=None,
        roi_rgb=None,
    ) -> Dict:
        if self.config.qwen_backend in {"cloud", "local"}:
            remote = self._call_qwen(
                expected_action=expected_action,
                pose_payload=pose_payload,
                original_frame_rgb=original_frame_rgb,
                pose_frame_rgb=pose_frame_rgb,
                roi_rgb=roi_rgb,
            )
            if isinstance(remote, dict):
                remote.setdefault("provider", self.provider)
                return remote
        local = self.rule_based_eval(pose_payload, expected_action, elapsed_seconds)
        local["provider"] = "rule-based-fallback"
        return local
