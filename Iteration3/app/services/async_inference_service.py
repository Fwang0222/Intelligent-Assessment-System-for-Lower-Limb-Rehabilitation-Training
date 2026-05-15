"""Background workers for realtime pose and multimodal inference."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from app.core.rehab_actions import DEFAULT_ACTION_NAME
from app.core.runtime_config import RuntimeConfig
from app.services.inference_orchestrator import V3InferenceOrchestrator
from app.services.qwen_service import QwenInferenceAdapter


class PoseInferenceWorker(QObject):
    result_ready = Signal(object)
    error = Signal(str)

    def __init__(self, config: RuntimeConfig | None = None):
        super().__init__()
        self.config = config or RuntimeConfig.from_sources()
        self.orchestrator: V3InferenceOrchestrator | None = None

    def _get_orchestrator(self) -> V3InferenceOrchestrator:
        if self.orchestrator is None:
            self.orchestrator = V3InferenceOrchestrator(self.config)
        return self.orchestrator

    @Slot(object)
    def process(self, packet) -> None:
        try:
            orchestrator = self._get_orchestrator()
            frame_rgb = packet.get("frame_rgb")
            if frame_rgb is not None and hasattr(frame_rgb, "copy"):
                frame_rgb = frame_rgb.copy()
            pose_features = orchestrator.extract_pose_features(
                frame_rgb=frame_rgb,
                frame_index=int(packet.get("frame_index", 1)),
                expected_action=packet.get("expected_action", DEFAULT_ACTION_NAME),
            )
            fast_assessment = orchestrator.quick_assess_pose(
                pose_payload=pose_features.get("pose_payload", {}),
                expected_action=packet.get("expected_action", DEFAULT_ACTION_NAME),
                elapsed_seconds=int(packet.get("elapsed_seconds", 0)),
            )
            out = dict(packet)
            out["pose_features"] = pose_features
            out["fast_assessment"] = fast_assessment
            self.result_ready.emit(out)
        except Exception as exc:
            self.error.emit(f"Pose worker failed: {exc}")


class QwenInferenceWorker(QObject):
    result_ready = Signal(object)
    error = Signal(str)

    def __init__(self, config: RuntimeConfig | None = None):
        super().__init__()
        self.config = config or RuntimeConfig.from_sources()
        self.qwen: QwenInferenceAdapter | None = None

    def _get_qwen(self) -> QwenInferenceAdapter:
        if self.qwen is None:
            self.qwen = QwenInferenceAdapter(self.config)
        return self.qwen

    @Slot(object)
    def process(self, packet) -> None:
        try:
            qwen = self._get_qwen()
            frame_rgb = packet.get("frame_rgb")
            if frame_rgb is not None and hasattr(frame_rgb, "copy"):
                frame_rgb = frame_rgb.copy()
            pose_features = packet.get("pose_features") or {}
            qwen_payload = qwen.evaluate(
                pose_payload=pose_features.get("pose_payload", {}),
                expected_action=packet.get("expected_action", DEFAULT_ACTION_NAME),
                elapsed_seconds=int(packet.get("elapsed_seconds", 0)),
                original_frame_rgb=frame_rgb,
                pose_frame_rgb=pose_features.get("pose_frame_rgb"),
                roi_rgb=pose_features.get("roi_frame_rgb"),
            )
            out = dict(packet)
            out["qwen_payload"] = qwen_payload
            self.result_ready.emit(out)
        except Exception as exc:
            self.error.emit(f"Qwen worker failed: {exc}")
