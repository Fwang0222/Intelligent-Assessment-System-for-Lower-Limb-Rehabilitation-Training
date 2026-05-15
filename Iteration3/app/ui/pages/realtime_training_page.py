"""Real-time training page for V3 configurable inference workflow."""

from time import monotonic

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from app.core.rehab_actions import DEFAULT_ACTION_NAME, get_action, get_action_video_path
from app.core.runtime_config import RuntimeConfig
from app.services.async_inference_service import PoseInferenceWorker, QwenInferenceWorker
from app.services.inference_orchestrator import V3InferenceOrchestrator
from app.services.training_service import TrainingSessionManager
from app.services.vision_pipeline_service import VisionPipelineService
from app.ui.base import BasePage
from app.ui.fluent_compat import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PageTitleLabel,
    PrimaryPushButton,
    ProgressBar,
    TextEdit,
)


class RealtimeTrainingPage(BasePage):
    pose_request = Signal(object)
    qwen_request = Signal(object)

    def __init__(self, db, user, refresh_callback=None, parent=None):
        self.refresh_callback = refresh_callback
        super().__init__(db, user, parent)
        self.runtime_config = RuntimeConfig.from_sources()
        self._auto_video_path = ""
        self.session_manager = TrainingSessionManager()
        self.vision_pipeline = VisionPipelineService()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer_tick)
        self.latest_session_payload = None
        self.session_token = 0
        self._reset_inference_state()
        self._init_inference_threads()
        self.setup_ui()
        self.refresh_data()

    def _reset_inference_state(self) -> None:
        self.pose_pending = False
        self.qwen_pending = False
        self.latest_qwen_payload = None
        self.latest_pose_features = None
        self.latest_pose_keypoints = []
        self.latest_roi_box = None
        self.last_qwen_bucket = -1
        self.last_rendered_result = None
        self.last_yolo_provider = "-"
        self.last_qwen_provider = "-"
        self.last_feedback_text = ""
        self.pending_feedback_text = ""
        self.last_feedback_update_at = 0.0
        self.feedback_hold_seconds = 2.4

    def _init_inference_threads(self) -> None:
        self.pose_thread = QThread(self)
        self.pose_worker = PoseInferenceWorker(self.runtime_config)
        self.pose_worker.moveToThread(self.pose_thread)
        self.pose_request.connect(self.pose_worker.process)
        self.pose_worker.result_ready.connect(self.on_pose_result)
        self.pose_worker.error.connect(self.on_worker_error)
        self.pose_thread.start()

        self.qwen_thread = QThread(self)
        self.qwen_worker = QwenInferenceWorker(self.runtime_config)
        self.qwen_worker.moveToThread(self.qwen_thread)
        self.qwen_request.connect(self.qwen_worker.process)
        self.qwen_worker.result_ready.connect(self.on_qwen_result)
        self.qwen_worker.error.connect(self.on_worker_error)
        self.qwen_thread.start()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("Real-Time Training"))
        header_card, header_layout = self.create_section_card(
            "Runtime",
            "Source, plan, and training controls.",
        )
        header_layout.addWidget(BodyLabel(f"Runtime: {self.runtime_config.summary_text()}"))

        top_layout = QHBoxLayout()
        self.action_combo = ComboBox()
        self.action_combo.currentIndexChanged.connect(self.on_plan_changed)
        self.video_path_edit = LineEdit()
        self.video_path_edit.setText(self.runtime_config.video_source_path or "")
        self.video_browse_btn = PrimaryPushButton("Select Video")
        self.start_btn = PrimaryPushButton("Start Training")
        self.stop_btn = PrimaryPushButton("Stop and Save")
        self.stop_btn.setEnabled(False)
        self.video_browse_btn.clicked.connect(self.select_video)
        self.start_btn.clicked.connect(self.start_training)
        self.stop_btn.clicked.connect(self.stop_training)
        top_layout.addWidget(BodyLabel("Action:"))
        top_layout.addWidget(self.action_combo)
        top_layout.addWidget(BodyLabel("Video:"))
        top_layout.addWidget(self.video_path_edit, 1)
        top_layout.addWidget(self.video_browse_btn)
        top_layout.addWidget(self.start_btn)
        top_layout.addWidget(self.stop_btn)
        top_layout.addStretch(1)
        header_layout.addLayout(top_layout)

        guide_layout = QHBoxLayout()
        self.demo_video_label = BodyLabel("Demo video: -")
        self.action_cue_label = BodyLabel("Cue: -")
        self.action_focus_label = BodyLabel("Focus: -")
        for label in (self.demo_video_label, self.action_cue_label, self.action_focus_label):
            label.setWordWrap(True)
            guide_layout.addWidget(label, 1)
        header_layout.addLayout(guide_layout)
        self.main_layout.addWidget(header_card)

        grid = QGridLayout()
        self.camera_label = QLabel(
            "Video stream\nSelect a local training video to start."
        )
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumHeight(420)
        self.camera_label.setStyleSheet(
            "QLabel {"
            "background: #F8FAFC;"
            "border: 1px solid #D7E1F0;"
            "border-radius: 8px;"
            "font-size: 16px;"
            "padding: 16px;"
            "color: #475569;"
            "}"
        )

        right_widget = QVBoxLayout()
        self.current_action_label = BodyLabel("Action: -")
        self.phase_label = BodyLabel("Phase: -")
        self.rep_label = BodyLabel("Reps: 0")
        self.completion_label = BodyLabel("Status: -")
        self.score_label = BodyLabel("Score: -")
        self.progress = ProgressBar()
        self.progress.setRange(0, 100)
        self.subscore_label = BodyLabel("Subscores: -")
        self.error_text = TextEdit()
        self.error_text.setReadOnly(True)
        self.feedback_text = TextEdit()
        self.feedback_text.setReadOnly(True)
        self.risk_text = TextEdit()
        self.risk_text.setReadOnly(True)
        self.group_feedback_text = TextEdit()
        self.group_feedback_text.setReadOnly(True)
        self.error_text.setFixedHeight(68)
        self.risk_text.setFixedHeight(58)
        self.feedback_text.setFixedHeight(68)
        self.group_feedback_text.setFixedHeight(68)
        self.camera_status_label = BodyLabel("Source: idle")
        self.provider_status_label = BodyLabel("Pipeline: -")
        self.inference_status_label = BodyLabel("Inference: idle")

        right_widget.addWidget(self.current_action_label)
        right_widget.addWidget(self.phase_label)
        right_widget.addWidget(self.rep_label)
        right_widget.addWidget(self.completion_label)
        right_widget.addWidget(self.score_label)
        right_widget.addWidget(BodyLabel("Quality score:"))
        right_widget.addWidget(self.progress)
        right_widget.addWidget(self.subscore_label)
        right_widget.addWidget(BodyLabel("Issues:"))
        right_widget.addWidget(self.error_text)
        right_widget.addWidget(BodyLabel("Alerts:"))
        right_widget.addWidget(self.risk_text)
        right_widget.addWidget(BodyLabel("Coaching:"))
        right_widget.addWidget(self.feedback_text)
        right_widget.addWidget(BodyLabel("Set feedback:"))
        right_widget.addWidget(self.group_feedback_text)
        right_widget.addWidget(self.camera_status_label)
        right_widget.addWidget(self.provider_status_label)
        right_widget.addWidget(self.inference_status_label)

        grid.addWidget(self.camera_label, 0, 0)
        grid.addLayout(right_widget, 0, 1)
        grid.setColumnStretch(0, 7)
        grid.setColumnStretch(1, 5)
        content_card, content_layout = self.create_section_card("Realtime Monitor")
        content_layout.addLayout(grid)
        self.main_layout.addWidget(content_card, 1)

    def refresh_data(self) -> None:
        self.action_combo.clear()
        plans = self.db.get_plans(self.user["id"])
        if plans:
            for plan in plans:
                self.action_combo.addItem(f"{plan['plan_name']} - {plan['target_action']}", plan)
            active_plan = self.db.get_active_plan(self.user["id"])
            if active_plan:
                for i, plan in enumerate(plans):
                    if plan["id"] == active_plan["id"]:
                        self.action_combo.setCurrentIndex(i)
                        break
        else:
            self.action_combo.addItem(
                f"Default Plan - {DEFAULT_ACTION_NAME}",
                {"id": None, "target_action": DEFAULT_ACTION_NAME, "sets_count": 3, "reps_count": 10},
            )
        self.on_plan_changed()

    def on_plan_changed(self, *_args) -> None:
        plan = self.action_combo.currentData() or {}
        action = get_action(plan.get("target_action", DEFAULT_ACTION_NAME))
        video_path = get_action_video_path(action.name)
        current_path = self.video_path_edit.text().strip()
        should_auto_fill = not current_path or current_path == self._auto_video_path
        if video_path and should_auto_fill:
            self.video_path_edit.setText(video_path)
            self._auto_video_path = video_path
        self.demo_video_label.setText(
            f"Demo video: {action.video_filename if video_path else 'missing video file'}"
        )
        self.action_cue_label.setText(f"Cue: {action.first_cue}")
        self.action_focus_label.setText(f"Focus: {action.focus_text}")

    def start_training(self) -> None:
        plan = self.action_combo.currentData()
        expected_action = get_action(plan["target_action"] if plan else DEFAULT_ACTION_NAME).name
        self.session_token += 1
        self._reset_inference_state()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.error_text.setPlainText("")
        self.feedback_text.setPlainText("")
        self.risk_text.setPlainText("")
        self.group_feedback_text.setPlainText("")
        self.last_feedback_text = ""
        self.pending_feedback_text = ""
        self.last_feedback_update_at = 0.0
        self.current_action_label.setText(f"Action: {expected_action}")
        self.phase_label.setText("Phase: Start")
        self.rep_label.setText("Reps: 0")
        self.completion_label.setText("Status: In progress")
        self.score_label.setText("Score: collecting...")
        self.subscore_label.setText("Details: -")
        self.progress.setValue(0)
        self.session_manager.start(
            expected_action=expected_action,
            sets_count=int(plan.get("sets_count", 3)) if plan else 3,
            reps_per_set=int(plan.get("reps_count", 10)) if plan else 10,
            hold_seconds=2,
        )
        source = self.video_path_edit.text().strip()
        source_ok = self.vision_pipeline.start(video_path=source, allow_camera_fallback=False)
        self.camera_status_label.setText(
            f"Source: {self.vision_pipeline.mode}" if source_ok else "Source: mock stream"
        )
        self.provider_status_label.setText("Pipeline: YOLO=- | Qwen=- | interval=5s")
        self.inference_status_label.setText("Inference: YOLO idle | Qwen idle")
        self.timer.start(80)
        InfoBar.success("Training Started", f"Training has started for {expected_action}.", position=InfoBarPosition.TOP, parent=self)

    def select_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Training Video", "", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if path:
            self.video_path_edit.setText(path)
            self._auto_video_path = ""

    def _draw_visual_overlay(self, frame_rgb, frame_size=(640, 420), keypoints=None, roi_box=None) -> None:
        fw, fh = frame_size
        if frame_rgb is not None:
            h, w, c = frame_rgb.shape
            qimg = QImage(frame_rgb.data, w, h, c * w, QImage.Format_RGB888).copy()
            pix = QPixmap.fromImage(qimg)
        else:
            pix = QPixmap(fw, fh)
            pix.fill(QColor("#F3F7FF"))
            bg = QPainter(pix)
            bg.setPen(QPen(QColor("#D4DCEC"), 1))
            for x in range(0, fw, 40):
                bg.drawLine(x, 0, x, fh)
            for y in range(0, fh, 40):
                bg.drawLine(0, y, fw, y)
            bg.end()
        if keypoints:
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor("#22C1DC"), 2))
            skeleton_pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (2, 5), (5, 6)]
            for a, b in skeleton_pairs:
                if a < len(keypoints) and b < len(keypoints):
                    painter.drawLine(int(keypoints[a][0]), int(keypoints[a][1]), int(keypoints[b][0]), int(keypoints[b][1]))
            painter.setPen(QPen(QColor("#2563EB"), 2))
            painter.setBrush(QColor("#60A5FA"))
            for x, y in keypoints:
                painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
            if roi_box:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor("#EF4444"), 2))
                painter.drawRect(
                    int(roi_box.get("x", 0)),
                    int(roi_box.get("y", 0)),
                    int(roi_box.get("w", 0)),
                    int(roi_box.get("h", 0)),
                )
            painter.end()
        self.camera_label.setPixmap(pix.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _compose_live_result(self, pose_features: dict, assessment: dict, expected_action: str) -> dict:
        return V3InferenceOrchestrator.compose_frame_result(
            pose_features=pose_features,
            qwen_payload=assessment,
            expected_action=expected_action,
            deployment_mode=self.runtime_config.deployment_mode,
            qwen_interval_seconds=5,
        )

    def _thread_status_text(self) -> str:
        yolo_state = "busy" if self.pose_pending else "idle"
        qwen_state = "busy" if self.qwen_pending else "idle"
        return f"Inference: YOLO {yolo_state} | Qwen {qwen_state}"

    @staticmethod
    def _set_plain_text_if_changed(widget, text: str) -> None:
        if widget.toPlainText() != text:
            widget.setPlainText(text)

    @staticmethod
    def _feedback_is_urgent(result: dict) -> bool:
        has_high_error = any(err.get("severity") == "high" for err in result.get("errors", []))
        has_high_comp = any(comp.get("risk_level") == "high" for comp in result.get("compensations", []))
        return has_high_error or has_high_comp

    def _apply_feedback_text(self, text: str, force: bool = False) -> None:
        now = monotonic()
        if force or text != self.last_feedback_text:
            self._set_plain_text_if_changed(self.feedback_text, text)
            self.last_feedback_text = text
            self.last_feedback_update_at = now

    def _update_feedback_display(self, result: dict, force: bool = False) -> None:
        now = monotonic()
        new_text = "\n".join(result.get("feedbacks", []) or ["Monitoring in progress... focus on smooth and symmetric movement."])
        if not self.last_feedback_text:
            self._apply_feedback_text(new_text, force=True)
            self.pending_feedback_text = ""
            return
        if new_text == self.last_feedback_text:
            if self.pending_feedback_text and (now - self.last_feedback_update_at) >= self.feedback_hold_seconds:
                self._apply_feedback_text(self.pending_feedback_text, force=True)
                self.pending_feedback_text = ""
            return
        if force or self._feedback_is_urgent(result) or (now - self.last_feedback_update_at) >= self.feedback_hold_seconds:
            self._apply_feedback_text(new_text, force=True)
            self.pending_feedback_text = ""
        else:
            self.pending_feedback_text = new_text

    def _render_result(self, result: dict) -> None:
        self.last_rendered_result = dict(result)
        self.current_action_label.setText(f"Action: {result['action_label']}  |  Time: {result['timestamp']}")
        pipeline_meta = result.get("pipeline_meta", {})
        if pipeline_meta:
            self.provider_status_label.setText(
                f"Pipeline: YOLO={pipeline_meta.get('yolo_provider', '-')} | "
                f"Qwen={pipeline_meta.get('qwen_provider', '-')} | "
                f"interval={pipeline_meta.get('qwen_interval_seconds', 5)}s"
            )
        self.phase_label.setText(f"Phase: {result.get('action_phase', '-')}")
        self.rep_label.setText(
            f"Reps: {result.get('rep_count', 0)}  |  Set {result.get('set_index', 1)}/{self.session_manager.sets_count}"
        )
        self.completion_label.setText(f"Status: {result.get('completion_status', 'In Progress')}")
        self.score_label.setText(
            f"Score: {result['total_score']}  "
            f"(accuracy {result['accuracy_score']}, stability {result['stability_score']})"
        )
        self.subscore_label.setText(
            f"Details: range {result['range_score']} | rhythm {result['rhythm_score']} | "
            f"symmetry {result.get('symmetry_score', 0)}"
        )
        self.progress.setValue(int(result["total_score"]))

        lines = []
        risk_lines = []
        for err in result["errors"]:
            lines.append(f"{err['error_type']} | {err['suggestion']}")
            if err.get("severity") == "high":
                risk_lines.append(f"HIGH RISK: {err['error_type']}")
        for comp in result["compensations"]:
            lines.append(f"{comp['compensation_type']} | {comp['suggestion']}")
            if comp.get("risk_level") in {"high", "medium"}:
                risk_lines.append(f"{comp.get('risk_level', '').upper()} RISK: {comp['compensation_type']}")
        if not lines:
            lines.append("No obvious error or compensation has been detected so far.")
        if not risk_lines:
            risk_lines.append("No active high-risk alert.")
        self._set_plain_text_if_changed(self.error_text, "\n".join(lines))
        self._set_plain_text_if_changed(self.risk_text, "\n".join(risk_lines))
        self._update_feedback_display(result)
        set_progress = int(result.get("set_progress", 0) * 100)
        self._set_plain_text_if_changed(
            self.group_feedback_text,
            f"Set progress: {set_progress}%\n"
            f"Completion: {round(result.get('completion_rate', 0) * 100, 2)}%\n"
            f"Focus: {get_action(result.get('action_label')).focus_text}.",
        )
        self.inference_status_label.setText(self._thread_status_text())

    def on_timer_tick(self) -> None:
        source_frame = self.vision_pipeline.next(self.session_manager.frame_index + 1)
        frame_rgb = source_frame.get("frame_rgb")
        self.camera_status_label.setText(f"Source: {source_frame.get('source_mode', self.vision_pipeline.mode)}")
        self._draw_visual_overlay(
            frame_rgb,
            frame_size=source_frame.get("frame_size", (640, 420)),
            keypoints=self.latest_pose_keypoints,
            roi_box=self.latest_roi_box,
        )
        if not self.session_manager.is_running:
            return
        if not self.pose_pending:
            context = self.session_manager.next_frame_context()
            packet = {
                "token": self.session_token,
                "expected_action": self.session_manager.expected_action,
                "frame_index": context["frame_index"],
                "elapsed_seconds": context["elapsed_seconds"],
                "frame_rgb": frame_rgb.copy() if frame_rgb is not None and hasattr(frame_rgb, "copy") else frame_rgb,
            }
            self.pose_pending = True
            self.inference_status_label.setText(self._thread_status_text())
            self.pose_request.emit(packet)

    def on_pose_result(self, packet) -> None:
        if packet.get("token") != self.session_token or not self.session_manager.is_running:
            self.pose_pending = False
            self.inference_status_label.setText(self._thread_status_text())
            return

        self.pose_pending = False
        pose_features = packet.get("pose_features") or {}
        pose_payload = pose_features.get("pose_payload", {})
        self.latest_pose_features = pose_features
        self.latest_pose_keypoints = list(pose_payload.get("keypoints", []))
        self.latest_roi_box = pose_features.get("roi_box")
        self.last_yolo_provider = pose_payload.get("provider", "-")

        active_assessment = self.latest_qwen_payload or packet.get("fast_assessment") or {}
        self.last_qwen_provider = active_assessment.get("provider", self.last_qwen_provider)
        live_result = self._compose_live_result(pose_features, active_assessment, packet.get("expected_action", self.session_manager.expected_action))
        live_result = self.session_manager.consume_external_result(live_result, frame_index=packet.get("frame_index"))
        self._render_result(live_result)

        qwen_bucket = int(packet.get("elapsed_seconds", 0)) // 5
        if not self.qwen_pending and qwen_bucket > self.last_qwen_bucket:
            self.qwen_pending = True
            self.last_qwen_bucket = qwen_bucket
            self.inference_status_label.setText(self._thread_status_text())
            self.qwen_request.emit(
                {
                    "token": self.session_token,
                    "expected_action": packet.get("expected_action", self.session_manager.expected_action),
                    "elapsed_seconds": packet.get("elapsed_seconds", 0),
                    "frame_rgb": packet.get("frame_rgb"),
                    "pose_features": pose_features,
                }
            )
        else:
            self.inference_status_label.setText(self._thread_status_text())

    def on_qwen_result(self, packet) -> None:
        if packet.get("token") != self.session_token or not self.session_manager.is_running:
            self.qwen_pending = False
            self.inference_status_label.setText(self._thread_status_text())
            return

        self.qwen_pending = False
        qwen_payload = packet.get("qwen_payload") or {}
        if qwen_payload:
            self.latest_qwen_payload = qwen_payload
            self.last_qwen_provider = qwen_payload.get("provider", self.last_qwen_provider)
            if self.latest_pose_features and self.last_rendered_result:
                refined = self._compose_live_result(
                    self.latest_pose_features,
                    self.latest_qwen_payload,
                    packet.get("expected_action", self.session_manager.expected_action),
                )
                preview = dict(self.last_rendered_result)
                for key in [
                    "action_label",
                    "action_phase",
                    "accuracy_score",
                    "stability_score",
                    "range_score",
                    "rhythm_score",
                    "symmetry_score",
                    "total_score",
                    "errors",
                    "compensations",
                    "feedbacks",
                    "pipeline_meta",
                ]:
                    preview[key] = refined.get(key)
                self._render_result(preview)
        self.inference_status_label.setText(self._thread_status_text())

    def on_worker_error(self, message: str) -> None:
        self.pose_pending = False
        self.qwen_pending = False
        self.inference_status_label.setText(self._thread_status_text())
        InfoBar.warning("Inference Warning", message, position=InfoBarPosition.TOP, parent=self)

    def stop_training(self) -> None:
        self.timer.stop()
        self.vision_pipeline.stop()
        self.session_token += 1
        self.pose_pending = False
        self.qwen_pending = False
        payload = self.session_manager.stop()
        self.latest_session_payload = payload

        selected_plan = self.action_combo.currentData()
        plan_id = selected_plan["id"] if selected_plan else None
        record_id = self.db.save_training_session(self.user["id"], plan_id, payload)

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.score_label.setText(f"Saved: record #{record_id}, avg score {payload['avg_score']}")
        self.completion_label.setText(
            f"Status: {'Completed' if payload.get('completion_rate', 0) >= 1.0 else 'Partially completed'}"
        )
        self._apply_feedback_text(payload["summary"] + "\n\nTraining suggestion:\n" + payload["doctor_recommendation"], force=True)
        self._set_plain_text_if_changed(
            self.group_feedback_text,
            f"Session summary:\n"
            f"Total repetitions: {payload.get('total_reps', 0)}\n"
            f"Sets target: {payload.get('sets_count', 0)} x {payload.get('reps_per_set', 0)}\n"
            f"Completion rate: {round(payload.get('completion_rate', 0) * 100, 2)}%",
        )
        self.camera_status_label.setText("Source: idle")
        self.provider_status_label.setText("Pipeline: idle")
        self.inference_status_label.setText("Inference: idle")
        if self.refresh_callback:
            self.refresh_callback()
        InfoBar.success("Saved", f"Training record #{record_id} has been saved.", position=InfoBarPosition.TOP, parent=self)

    def _shutdown_workers(self) -> None:
        wait_ms = max(1500, int(getattr(self.runtime_config, "request_timeout_seconds", 5) * 1000) + 1000)
        for thread in (getattr(self, "pose_thread", None), getattr(self, "qwen_thread", None)):
            if thread is not None:
                thread.quit()
                thread.wait(wait_ms)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self.vision_pipeline.stop()
        self._shutdown_workers()
        super().closeEvent(event)
