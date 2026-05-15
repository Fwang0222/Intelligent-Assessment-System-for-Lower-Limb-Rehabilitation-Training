"""Dashboard page focused on key rehab priorities and next actions."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.core.rehab_actions import DEFAULT_ACTION_NAME, DEMO_ACTIONS, get_action, get_action_image_path
from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, CaptionLabel, PageTitleLabel, PillLabel, ValueLabel


class HomePage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.metric_values = {}
        self.metric_notes = {}
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.setContentsMargins(18, 14, 18, 14)
        self.main_layout.setSpacing(12)
        self.main_layout.addWidget(PageTitleLabel("Dashboard"))

        hero_card, hero_layout = self.create_section_card()
        hero_top = QHBoxLayout()
        hero_top.setContentsMargins(0, 0, 0, 0)
        hero_top.setSpacing(10)
        self.hero_title = ValueLabel("Care Overview")
        self.hero_title.setStyleSheet("background: transparent; border: none; color: #0F172A;")
        self.hero_badge = PillLabel("Live", "blue")
        hero_top.addWidget(self.hero_title, 1)
        hero_top.addWidget(self.hero_badge, 0)
        hero_layout.addLayout(hero_top)
        self.hero_summary = BodyLabel("")
        self.hero_summary.setStyleSheet("background: transparent; border: none; color: #475569;")
        hero_layout.addWidget(self.hero_summary)
        self.main_layout.addWidget(hero_card)

        visual_card, visual_layout = self.create_section_card()
        visual_layout.setSpacing(10)
        visual_head = QHBoxLayout()
        visual_head.setContentsMargins(0, 0, 0, 0)
        self.visual_title = ValueLabel("Today's Training")
        self.visual_badge = PillLabel("Standard Video", "green")
        visual_head.addWidget(self.visual_title, 1)
        visual_head.addWidget(self.visual_badge)
        visual_layout.addLayout(visual_head)

        visual_body = QHBoxLayout()
        visual_body.setContentsMargins(0, 0, 0, 0)
        visual_body.setSpacing(14)
        self.current_action_image = QLabel()
        self.current_action_image.setMinimumSize(360, 210)
        self.current_action_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.current_action_image.setAlignment(Qt.AlignCenter)
        self.current_action_image.setStyleSheet(
            "QLabel { background: #EAF2FF; border: 1px solid #D7E1F0; border-radius: 8px; }"
        )
        visual_body.addWidget(self.current_action_image, 5)

        visual_info = QVBoxLayout()
        visual_info.setContentsMargins(0, 0, 0, 0)
        visual_info.setSpacing(8)
        self.current_action_title = ValueLabel("-")
        self.current_action_cue = BodyLabel("")
        self.current_action_focus = BodyLabel("")
        self.current_action_meta = CaptionLabel("")
        for label in (self.current_action_cue, self.current_action_focus, self.current_action_meta):
            label.setWordWrap(True)
        visual_info.addWidget(self.current_action_title)
        visual_info.addWidget(self.current_action_cue)
        visual_info.addWidget(self.current_action_focus)
        visual_info.addWidget(self.current_action_meta)
        visual_info.addStretch(1)
        visual_body.addLayout(visual_info, 4)
        visual_layout.addLayout(visual_body)

        gallery_row = QHBoxLayout()
        gallery_row.setContentsMargins(0, 0, 0, 0)
        gallery_row.setSpacing(8)
        self.action_thumb_labels = []
        for action in DEMO_ACTIONS:
            tile = QWidget()
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(0, 0, 0, 0)
            tile_layout.setSpacing(4)
            image_label = QLabel()
            image_label.setFixedHeight(86)
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setStyleSheet(
                "QLabel { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; }"
            )
            name_label = CaptionLabel(action.name)
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setWordWrap(False)
            tile_layout.addWidget(image_label)
            tile_layout.addWidget(name_label)
            gallery_row.addWidget(tile, 1)
            self.action_thumb_labels.append((image_label, action))
        visual_layout.addLayout(gallery_row)
        self.main_layout.addWidget(visual_card)

        metric_grid = QGridLayout()
        metric_grid.setContentsMargins(0, 0, 0, 0)
        metric_grid.setHorizontalSpacing(10)
        metric_grid.setVerticalSpacing(10)
        for idx, key in enumerate(["m1", "m2", "m3", "m4"]):
            card, layout = self.create_section_card()
            title = BodyLabel("-")
            title.setStyleSheet("font-weight: 700; color: #0F172A; background: transparent; border: none;")
            value = ValueLabel("-")
            note = CaptionLabel("-")
            layout.addWidget(title)
            layout.addWidget(value)
            layout.addWidget(note)
            self.metric_values[key] = {"title": title, "value": value, "note": note}
            metric_grid.addWidget(card, 0, idx)
        self.main_layout.addLayout(metric_grid)

        lower_grid = QGridLayout()
        lower_grid.setContentsMargins(0, 0, 0, 0)
        lower_grid.setHorizontalSpacing(10)
        lower_grid.setVerticalSpacing(10)

        process_card, process_layout = self.create_section_card("Care Process")
        self.process_labels = []
        process_row = QHBoxLayout()
        process_row.setContentsMargins(0, 0, 0, 0)
        process_row.setSpacing(8)
        for _ in range(4):
            step = PillLabel("-", "slate")
            process_row.addWidget(step)
            self.process_labels.append(step)
        process_row.addStretch(1)
        process_layout.addLayout(process_row)
        lower_grid.addWidget(process_card, 0, 0, 1, 2)

        focus_card, focus_layout = self.create_section_card("Current Focus")
        self.focus_text = BodyLabel("")
        focus_layout.addWidget(self.focus_text)
        lower_grid.addWidget(focus_card, 1, 0)

        activity_card, activity_layout = self.create_section_card("Recent Activity")
        self.activity_text = BodyLabel("")
        activity_layout.addWidget(self.activity_text)
        lower_grid.addWidget(activity_card, 2, 0, 1, 2)

        next_card, next_layout = self.create_section_card("Next Actions")
        self.next_text = BodyLabel("")
        next_layout.addWidget(self.next_text)
        lower_grid.addWidget(next_card, 1, 1)

        self.main_layout.addLayout(lower_grid, 1)

    def _set_process_steps(self, labels) -> None:
        tones = ["blue", "blue", "orange", "green"]
        for idx, step in enumerate(self.process_labels):
            step.setText(labels[idx] if idx < len(labels) else "-")
            step.setTone(tones[idx] if idx < len(tones) else "slate")

    def _set_metric(self, key: str, title: str, value: str, note: str) -> None:
        block = self.metric_values[key]
        block["title"].setText(title)
        block["value"].setText(value)
        block["note"].setText(note)

    def _fallback_pixmap(self, action, width: int, height: int) -> QPixmap:
        pix = QPixmap(width, height)
        pix.fill(QColor("#EAF2FF"))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#BFD2EA"), 1))
        for y in range(24, height, 24):
            painter.drawLine(0, y, width, y)
        for x in range(32, width, 32):
            painter.drawLine(x, 0, x, height)
        painter.setPen(QPen(QColor("#2563EB"), 5))
        cx = width // 2
        cy = height // 2
        painter.drawLine(cx - 42, cy - 34, cx, cy - 6)
        painter.drawLine(cx, cy - 6, cx + 48, cy - 24)
        painter.drawLine(cx, cy - 6, cx - 24, cy + 48)
        painter.drawLine(cx - 24, cy + 48, cx + 30, cy + 60)
        painter.setBrush(QColor("#2563EB"))
        painter.drawEllipse(cx - 56, cy - 58, 18, 18)
        font = QFont("Segoe UI", 11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#0F172A"))
        painter.drawText(12, height - 18, action.name)
        painter.end()
        return pix

    def _image_pixmap(self, action_name: str, width: int, height: int) -> QPixmap:
        action = get_action(action_name)
        path = get_action_image_path(action.name)
        if path:
            pix = QPixmap(path)
            if not pix.isNull():
                return pix.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        return self._fallback_pixmap(action, width, height)

    def _set_visual_action(self, action_name: str, plan=None, doctor_mode: bool = False) -> None:
        action = get_action(action_name or DEFAULT_ACTION_NAME)
        self.visual_title.setText("Standard Action Library" if doctor_mode else "Today's Standard Demo")
        self.visual_badge.setText("Care Reference" if doctor_mode else "Assigned")
        self.visual_badge.setTone("blue" if doctor_mode else "green")
        self.current_action_image.setPixmap(self._image_pixmap(action.name, 620, 360))
        self.current_action_title.setText(action.name)
        self.current_action_cue.setText(f"Cue: {action.first_cue}")
        self.current_action_focus.setText(f"Focus: {action.focus_text}")
        if plan:
            self.current_action_meta.setText(
                f"Volume: {plan.get('sets_count', '-')} sets x {plan.get('reps_count', '-')} reps | "
                f"Rest {plan.get('rest_seconds', '-')} sec"
            )
        else:
            self.current_action_meta.setText("Four standard rehab images are available for training and review.")
        for image_label, gallery_action in self.action_thumb_labels:
            image_label.setPixmap(self._image_pixmap(gallery_action.name, 220, 124))

    def _doctor_dashboard(self) -> None:
        worklist = self.db.get_doctor_worklist(self.user["id"])
        security = self.db.get_security_overview(self.user["id"])
        pending = sum(1 for item in worklist if item.get("needs_review"))
        high_risk = sum(1 for item in worklist if item.get("risk_level") == "high")
        reviewed = sum(1 for item in worklist if item.get("latest_review_status") in {"approved", "adjusted"})

        self.hero_title.setText(f"Doctor Workbench | {self.user.get('full_name', 'Doctor')}")
        self.hero_badge.setText("Remote")
        self.hero_badge.setTone("blue")
        self.hero_summary.setText(
            f"Linked patients {len(worklist)} | Pending review {pending} | "
            f"High risk {high_risk} | Storage {security.get('storage_backend', '-')}"
        )
        first_action = DEFAULT_ACTION_NAME
        if worklist:
            first_patient_id = int(worklist[0]["id"])
            plan = self.db.get_active_plan(first_patient_id)
            first_action = plan.get("target_action", DEFAULT_ACTION_NAME) if plan else DEFAULT_ACTION_NAME
        self._set_visual_action(first_action, doctor_mode=True)

        self._set_metric("m1", "Linked Patients", str(len(worklist)), "Current remote care scope")
        self._set_metric("m2", "Pending Review", str(pending), "Latest session not yet reviewed")
        self._set_metric("m3", "High Risk", str(high_risk), "Immediate follow-up candidates")
        self._set_metric("m4", "Reviewed", str(reviewed), "Doctor-reviewed latest sessions")

        if worklist:
            top = worklist[0]
            risk_line = "\n".join(
                [
                    f"Patient: {top.get('full_name', '-')}",
                    f"Risk: {top.get('risk_level', 'low').upper()} | Issue: {top.get('top_issue', 'Stable')}",
                    f"Trend: {top.get('trend', 'No data')} | Latest score: {top.get('latest_score', '-')}",
                ]
            )
            activity_lines = [
                f"- {item.get('full_name', '-')} | {item.get('risk_level', 'low').upper()} | {item.get('top_issue', 'Stable')}"
                for item in worklist[:4]
            ]
        else:
            risk_line = "No linked patient is available."
            activity_lines = ["- No doctor work items."]

        audits = self.db.get_audit_logs(actor_user_id=self.user["id"], limit=4)
        audit_lines = [
            f"- {item.get('created_at', '-')} | {item.get('action_type', '-')}"
            for item in audits[:3]
        ] or ["- No audit activity."]

        self.focus_text.setText(risk_line)
        self.activity_text.setText("\n".join(activity_lines))
        self.next_text.setText(
            "\n".join(
                [
                    f"- Review queue: {pending}",
                    f"- Latest backup: {security.get('latest_backup_at', '-')}",
                    *audit_lines,
                ]
            )
        )
        self._set_process_steps(["1 Review", "2 Decide", "3 Adjust", "4 Follow up"])

    def _patient_dashboard(self) -> None:
        latest = self.db.get_latest_record(self.user["id"])
        plan = self.db.get_active_plan(self.user["id"])
        profile = self.db.get_user_profile(self.user["id"]) or {}
        summary = self.db.get_analysis_summary(self.user["id"])
        trend_rows = self.db.get_score_trend(self.user["id"], limit=4)
        errors = self.db.get_error_distribution(self.user["id"], limit=1)
        comps = self.db.get_compensation_distribution(self.user["id"], limit=1)
        adjustments = self.db.get_plan_adjustments(self.user["id"])

        latest_score = "-" if not latest else str(round(float(latest.get("avg_score", 0) or 0), 1))
        latest_completion = "-" if not latest else f"{round((latest.get('completion_rate', 0) or 0) * 100, 1)}%"
        pain_value = str(profile.get("pain_level", summary.get("avg_pain", 0)))
        trend_value = summary.get("trend", "No data")
        top_issue = errors[0]["label"] if errors else (comps[0]["label"] if comps else "Stable")

        self.hero_title.setText(f"Welcome back, {self.user.get('full_name', 'User')}")
        self.hero_badge.setText(trend_value)
        self.hero_badge.setTone("green" if trend_value == "Improving" else "orange" if trend_value == "Stable" else "red")
        self.hero_summary.setText(
            f"Current plan {plan.get('target_action', '-') if plan else '-'} | "
            f"Latest score {latest_score} | Completion {latest_completion} | "
            f"Pain {pain_value}"
        )
        self._set_visual_action(plan.get("target_action", DEFAULT_ACTION_NAME) if plan else DEFAULT_ACTION_NAME, plan=plan)

        self._set_metric("m1", "Latest Score", latest_score, "Most recent completed session")
        self._set_metric("m2", "Completion", latest_completion, "How much of the target volume was finished")
        self._set_metric("m3", "Pain", pain_value, "Current self-reported pain level")
        self._set_metric("m4", "Trend", trend_value, "Compared with recent sessions")

        focus_lines = [
            f"Stage: {profile.get('rehab_stage', self.user.get('rehab_stage', '-'))}",
            f"Top issue: {top_issue}",
            f"Current action: {plan.get('target_action', '-') if plan else '-'}",
            f"Target volume: {plan.get('sets_count', '-')} sets x {plan.get('reps_count', '-')} reps" if plan else "Target volume: -",
        ]

        if latest:
            activity_lines = [
                f"- {row.get('session_end', '-') or '-'} | Score {round(float(row.get('avg_score', 0) or 0), 1)} | "
                f"Completion {round((row.get('completion_rate', 0) or 0) * 100, 1)}%"
                for row in self.db.get_records(self.user["id"], limit=3)
            ]
        else:
            activity_lines = ["- No training session yet."]

        next_lines = [
            f"- Next focus: {top_issue}",
            f"- Plan decision: {adjustments[0]['adjustment_reason']}" if adjustments else "- Plan decision: keep monitoring",
            f"- Recent sessions tracked: {len(trend_rows)}",
        ]

        self.focus_text.setText("\n".join(focus_lines))
        self.activity_text.setText("\n".join(activity_lines))
        self.next_text.setText("\n".join(next_lines))
        self._set_process_steps(["1 Plan", "2 Train", "3 Review", "4 Update"])

    def refresh_data(self) -> None:
        if self.user.get("role") == "doctor":
            self._doctor_dashboard()
        else:
            self._patient_dashboard()
