"""Doctor workbench focused on review, intervention, and plan adjustment."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QGridLayout, QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget

from app.core.rehab_actions import DEFAULT_ACTION_NAME, get_action
from app.services.report_export_service import ReportExportService
from app.ui.base import BasePage
from app.ui.fluent_compat import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FormLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    PageTitleLabel,
    PillLabel,
    PrimaryPushButton,
    PushButton,
    TextEdit,
    ValueLabel,
)


class DoctorPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.export_service = ReportExportService(db)
        self.selected_patient_id = None
        self.selected_record_id = None
        self.current_adaptive = None
        self.current_info = {}
        self.worklist_map = {}
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.setContentsMargins(18, 14, 18, 14)
        self.main_layout.setSpacing(12)
        self.main_layout.addWidget(PageTitleLabel("Doctor Workbench"))

        hero_card, hero_layout = self.create_section_card()
        hero_top = QHBoxLayout()
        hero_top.setContentsMargins(0, 0, 0, 0)
        hero_top.setSpacing(10)
        self.hero_title = ValueLabel("Remote Rehab Control")
        self.hero_badge = PillLabel("Doctor", "blue")
        hero_top.addWidget(self.hero_title, 1)
        hero_top.addWidget(self.hero_badge)
        hero_layout.addLayout(hero_top)
        self.hero_note = BodyLabel("")
        hero_layout.addWidget(self.hero_note)

        hero_actions = QHBoxLayout()
        hero_actions.setContentsMargins(0, 0, 0, 0)
        hero_actions.setSpacing(8)
        self.refresh_btn = PrimaryPushButton("Refresh")
        self.export_pdf_btn = PushButton("Export PDF")
        self.export_json_btn = PushButton("Export JSON")
        self.backup_btn = PushButton("Create Backup")
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.export_pdf_btn.clicked.connect(self.export_pdf)
        self.export_json_btn.clicked.connect(self.export_json)
        self.backup_btn.clicked.connect(self.create_backup)
        hero_actions.addWidget(self.refresh_btn)
        hero_actions.addWidget(self.export_pdf_btn)
        hero_actions.addWidget(self.export_json_btn)
        hero_actions.addWidget(self.backup_btn)
        hero_actions.addStretch(1)
        hero_layout.addLayout(hero_actions)
        self.main_layout.addWidget(hero_card)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        left_column = QVBoxLayout()
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setSpacing(10)
        queue_card, queue_layout = self.create_section_card("Patient Queue", "High risk and pending review first.")
        self.queue_summary = CaptionLabel("")
        queue_layout.addWidget(self.queue_summary)
        self.patient_list = ListWidget()
        self.patient_list.currentItemChanged.connect(self._on_patient_changed)
        queue_layout.addWidget(self.patient_list, 1)
        left_column.addWidget(queue_card, 1)

        center_column = QVBoxLayout()
        center_column.setContentsMargins(0, 0, 0, 0)
        center_column.setSpacing(10)

        patient_card, patient_layout = self.create_section_card("Patient Snapshot")
        patient_top = QHBoxLayout()
        patient_top.setContentsMargins(0, 0, 0, 0)
        patient_top.setSpacing(8)
        self.patient_name = ValueLabel("-")
        self.patient_status = PillLabel("Pending", "orange")
        patient_top.addWidget(self.patient_name, 1)
        patient_top.addWidget(self.patient_status)
        patient_layout.addLayout(patient_top)
        self.patient_summary = BodyLabel("")
        patient_layout.addWidget(self.patient_summary)
        center_column.addWidget(patient_card)

        metric_grid = QGridLayout()
        metric_grid.setContentsMargins(0, 0, 0, 0)
        metric_grid.setHorizontalSpacing(10)
        metric_grid.setVerticalSpacing(10)
        self.metric_blocks = {}
        for idx, (key, title) in enumerate(
            [
                ("score", "Latest Score"),
                ("completion", "Completion"),
                ("risk", "Risk Level"),
                ("trend", "Trend"),
            ]
        ):
            card, layout = self.create_section_card()
            title_label = BodyLabel(title)
            title_label.setStyleSheet("font-weight: 700; color: #0F172A; background: transparent; border: none;")
            value_label = ValueLabel("-")
            note_label = CaptionLabel("-")
            layout.addWidget(title_label)
            layout.addWidget(value_label)
            layout.addWidget(note_label)
            self.metric_blocks[key] = (value_label, note_label)
            metric_grid.addWidget(card, idx // 2, idx % 2)
        center_column.addLayout(metric_grid)

        focus_grid = QGridLayout()
        focus_grid.setContentsMargins(0, 0, 0, 0)
        focus_grid.setHorizontalSpacing(10)
        focus_grid.setVerticalSpacing(10)
        trend_card, trend_layout = self.create_section_card("Trend & Risk")
        self.trend_text = BodyLabel("")
        trend_layout.addWidget(self.trend_text)
        focus_grid.addWidget(trend_card, 0, 0)

        process_card, process_layout = self.create_section_card("Care Process")
        self.process_text = BodyLabel("")
        process_layout.addWidget(self.process_text)
        focus_grid.addWidget(process_card, 0, 1)
        center_column.addLayout(focus_grid)

        notes_card, notes_layout = self.create_section_card("Session Review", "Result, doctor note, and recommendation in one place.")
        self.review_text = TextEdit()
        self.review_text.setReadOnly(True)
        notes_layout.addWidget(self.review_text)
        center_column.addWidget(notes_card, 1)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(10)
        intervention_card, intervention_layout = self.create_section_card("Intervention Panel")

        review_form = QFormLayout()
        review_form.setVerticalSpacing(8)
        review_form.setHorizontalSpacing(16)
        self.review_status_combo = ComboBox()
        for label, value in [
            ("Approve result", "approved"),
            ("Needs manual review", "needs_review"),
            ("Adjusted after review", "adjusted"),
        ]:
            self.review_status_combo.addItem(label, value)
        self.decision_combo = ComboBox()
        for label, value in [
            ("Keep current plan", "keep_current_plan"),
            ("Reduce load", "reduce_load"),
            ("Increase load", "increase_load"),
            ("Switch standard video action", "replace_action"),
            ("Unilateral corrective", "unilateral_corrective"),
        ]:
            self.decision_combo.addItem(label, value)
        self.note_edit = TextEdit()
        self.note_edit.setFixedHeight(96)
        review_form.addRow(FormLabel("Review status"), self.review_status_combo)
        review_form.addRow(FormLabel("Decision"), self.decision_combo)
        review_form.addRow(FormLabel("Doctor note"), self.note_edit)
        intervention_layout.addLayout(review_form)

        plan_form_card, plan_form_layout = self.create_section_card("Plan Parameters")
        plan_form = QFormLayout()
        plan_form.setVerticalSpacing(8)
        plan_form.setHorizontalSpacing(16)
        self.plan_name_edit = LineEdit()
        self.action_edit = LineEdit()
        self.difficulty_edit = LineEdit()
        self.sets_edit = LineEdit()
        self.reps_edit = LineEdit()
        self.duration_edit = LineEdit()
        self.rest_edit = LineEdit()
        self.desc_edit = TextEdit()
        self.desc_edit.setFixedHeight(80)
        plan_form.addRow(FormLabel("Plan name"), self.plan_name_edit)
        plan_form.addRow(FormLabel("Target action"), self.action_edit)
        plan_form.addRow(FormLabel("Difficulty"), self.difficulty_edit)
        plan_form.addRow(FormLabel("Sets"), self.sets_edit)
        plan_form.addRow(FormLabel("Reps"), self.reps_edit)
        plan_form.addRow(FormLabel("Duration"), self.duration_edit)
        plan_form.addRow(FormLabel("Rest sec"), self.rest_edit)
        plan_form.addRow(FormLabel("Description"), self.desc_edit)
        plan_form_layout.addLayout(plan_form)
        right_column.addWidget(intervention_card)
        right_column.addWidget(plan_form_card)

        action_card, action_layout = self.create_section_card("Intervention Actions")
        self.save_review_btn = PrimaryPushButton("Save Review")
        self.load_suggestion_btn = PushButton("Load Suggested Plan")
        self.apply_plan_btn = PrimaryPushButton("Apply Plan Update")
        self.save_review_btn.clicked.connect(self.save_review)
        self.load_suggestion_btn.clicked.connect(self.load_adaptive_suggestion)
        self.apply_plan_btn.clicked.connect(self.apply_plan_update)
        action_layout.addWidget(self.save_review_btn)
        action_layout.addWidget(self.load_suggestion_btn)
        action_layout.addWidget(self.apply_plan_btn)
        self.action_note = CaptionLabel("")
        action_layout.addWidget(self.action_note)
        right_column.addWidget(action_card)

        body.addLayout(left_column, 3)
        body.addLayout(center_column, 7)
        body.addLayout(right_column, 4)
        self.main_layout.addLayout(body, 1)

    def _set_metric(self, key: str, value: str, note: str) -> None:
        self.metric_blocks[key][0].setText(value)
        self.metric_blocks[key][1].setText(note)

    def _target_user_id(self):
        return self.selected_patient_id

    def _selected_work_item(self):
        return self.worklist_map.get(self.selected_patient_id)

    def _populate_worklist(self, worklist, selected_id) -> None:
        self.worklist_map = {int(item["id"]): item for item in worklist}
        pending = sum(1 for item in worklist if item.get("needs_review"))
        high_risk = sum(1 for item in worklist if item.get("risk_level") == "high")
        self.queue_summary.setText(f"Patients {len(worklist)} | Pending {pending} | High risk {high_risk}")

        self.patient_list.blockSignals(True)
        self.patient_list.clear()
        selected_row = -1
        for row, item in enumerate(worklist):
            risk = item.get("risk_level", "low").upper()
            state = "Review" if item.get("needs_review") else item.get("latest_review_status", "done")
            text = (
                f"{item.get('full_name', 'Patient')}\n"
                f"{risk} | {item.get('top_issue', 'Stable')} | {state}"
            )
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, int(item["id"]))
            self.patient_list.addItem(list_item)
            if int(item["id"]) == int(selected_id or 0):
                selected_row = row
        if self.patient_list.count() > 0:
            self.patient_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
            current = self.patient_list.currentItem()
            self.selected_patient_id = current.data(Qt.UserRole) if current else None
        else:
            self.selected_patient_id = None
        self.patient_list.blockSignals(False)

    def _populate_plan_fields(self, plan) -> None:
        plan = plan or {}
        self.plan_name_edit.setText(str(plan.get("plan_name", "Doctor Adjusted Plan")))
        self.action_edit.setText(str(plan.get("target_action", DEFAULT_ACTION_NAME)))
        self.difficulty_edit.setText(str(plan.get("difficulty_level", "Low")))
        self.sets_edit.setText(str(plan.get("sets_count", 3)))
        self.reps_edit.setText(str(plan.get("reps_count", 10)))
        self.duration_edit.setText(str(plan.get("duration_minutes", 15)))
        self.rest_edit.setText(str(plan.get("rest_seconds", 30)))
        self.desc_edit.setPlainText(str(plan.get("description", "")))

    def _review_tone(self, status: str) -> str:
        return {
            "approved": "green",
            "adjusted": "blue",
            "needs_review": "red",
            "pending": "orange",
        }.get(status, "orange")

    def _on_patient_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        del previous
        if current is None:
            self.selected_patient_id = None
            return
        self.selected_patient_id = int(current.data(Qt.UserRole))
        self.refresh_data()

    def refresh_data(self) -> None:
        info = self.db.get_doctor_dashboard(self.user["id"], self.selected_patient_id)
        self.current_info = info
        self.current_adaptive = info.get("adaptive")
        worklist = info.get("worklist") or self.db.get_doctor_worklist(self.user["id"])
        self._populate_worklist(worklist, info.get("selected_user_id"))

        security = self.db.get_security_overview(self.user["id"], self.selected_patient_id)
        self.hero_note.setText(
            f"Linked patients {len(worklist)} | Storage {security.get('storage_backend', '-')} | "
            f"Backups {security.get('backup_count', 0)} | Latest audit {security.get('latest_audit_action', '-')}"
        )

        user = info.get("user") or {}
        profile = info.get("profile") or {}
        summary = info.get("summary") or {}
        records = info.get("recent_records") or []
        active_plan = info.get("active_plan") or {}
        latest_details = info.get("latest_record_details") or {}
        latest_intervention = info.get("latest_intervention") or {}
        self.selected_record_id = int(records[0]["id"]) if records else None

        if not user:
            self.patient_name.setText("No linked patient")
            self.patient_status.setText("Idle")
            self.patient_status.setTone("slate")
            self.patient_summary.setText("Bind a patient to start doctor-side review.")
            for key in self.metric_blocks:
                self._set_metric(key, "-", "No data")
            self.trend_text.setText("No trend data.")
            self.process_text.setText("No care process available.")
            self.review_text.setPlainText("")
            self._populate_plan_fields({})
            self.action_note.setText("No patient selected.")
            return

        work_item = self._selected_work_item() or {}
        review_status = latest_intervention.get("review_status", "pending")
        self.patient_name.setText(user.get("full_name", "-"))
        self.patient_status.setText(review_status.replace("_", " ").title())
        self.patient_status.setTone(self._review_tone(review_status))
        self.patient_summary.setText(
            "\n".join(
                [
                    f"Stage: {user.get('rehab_stage', '-')}",
                    f"Diagnosis: {profile.get('diagnosis', '-')}",
                    f"Affected side: {user.get('affected_side', '-') or profile.get('affected_side', '-')}",
                    f"Current plan: {active_plan.get('target_action', '-')}",
                ]
            )
        )
        active_action = get_action(active_plan.get("target_action", DEFAULT_ACTION_NAME))

        latest_score = work_item.get("latest_score", summary.get("avg_score", 0))
        latest_completion = work_item.get("completion_rate", summary.get("avg_completion", 0))
        risk_level = work_item.get("risk_level", "low").upper()
        trend = summary.get("trend", "No data")

        self._set_metric("score", str(latest_score if latest_score is not None else "-"), "Newest completed session")
        self._set_metric("completion", f"{latest_completion}%" if latest_completion is not None else "-", "Execution quality and target volume")
        self._set_metric("risk", risk_level, work_item.get("top_issue", "Stable"))
        self._set_metric("trend", trend, f"Pain avg {summary.get('avg_pain', 0)}")

        errors = latest_details.get("errors") or []
        compensations = latest_details.get("compensations") or []
        top_error = errors[0]["error_type"] if errors else "None"
        top_comp = compensations[0]["compensation_type"] if compensations else "None"
        recommendation = info.get("recommendation", "No recommendation available.")
        doctor_note = latest_intervention.get("note", "") if latest_intervention else ""

        self.trend_text.setText(
            "\n".join(
                [
                    f"Trend: {trend}",
                    f"Top error: {top_error}",
                    f"Top compensation: {top_comp}",
                    f"Average pain: {summary.get('avg_pain', 0)}",
                ]
            )
        )
        self.process_text.setText(
            "\n".join(
                [
                    f"1 Plan: {active_action.plan_name}",
                    f"2 Train: record #{self.selected_record_id or '-'}",
                    f"3 Review: {review_status}",
                    f"4 Intervene: {latest_intervention.get('decision_type', 'pending') if latest_intervention else 'pending'}",
                    f"Key cue: {active_action.first_cue}",
                ]
            )
        )

        notes = [
            "[Assessment Summary]",
            f"- Recommendation: {recommendation}",
            f"- Latest action: {records[0].get('action_name', '-') if records else '-'}",
            f"- Latest session score: {latest_score}",
            "",
            "[Doctor Review]",
            f"- Status: {review_status}",
            f"- Note: {doctor_note or 'No doctor note yet.'}",
        ]
        interventions = info.get("interventions") or []
        if interventions:
            notes.extend(["", "[Recent Interventions]"])
            for item in interventions[:3]:
                notes.append(
                    f"- {item.get('created_at', '-')} | {item.get('review_status', '-')} | "
                    f"{item.get('decision_type', '-')}"
                )
        self.review_text.setPlainText("\n".join(notes))

        self._populate_plan_fields(active_plan)
        self.action_note.setText(
            "Suggested plan is ready to load." if self.current_adaptive and self.current_adaptive.get("new_plan") else "Review and adjust parameters before applying."
        )

    def save_review(self) -> None:
        if not self._target_user_id():
            InfoBar.warning("No Patient", "Select a patient first.", position=InfoBarPosition.TOP, parent=self)
            return
        try:
            review_status = self.review_status_combo.currentData()
            decision_type = self.decision_combo.currentData()
            note = self.note_edit.toPlainText().strip()
            self.db.save_doctor_intervention(
                viewer_user_id=self.user["id"],
                target_user_id=int(self._target_user_id()),
                training_record_id=self.selected_record_id,
                review_status=review_status,
                decision_type=decision_type,
                note=note,
            )
            InfoBar.success("Saved", "Doctor review has been recorded.", position=InfoBarPosition.TOP, parent=self)
            self.refresh_data()
        except Exception as exc:
            InfoBar.error("Save Failed", str(exc), position=InfoBarPosition.TOP, parent=self)

    def load_adaptive_suggestion(self) -> None:
        suggestion = self.current_adaptive or {}
        new_plan = suggestion.get("new_plan")
        if not new_plan:
            InfoBar.warning("No Suggestion", "No adaptive suggestion is available for this patient.", position=InfoBarPosition.TOP, parent=self)
            return
        self._populate_plan_fields(
            {
                "plan_name": f"{new_plan.get('plan_name', 'Doctor Adjusted Plan')} - Suggested",
                "target_action": new_plan.get("target_action", DEFAULT_ACTION_NAME),
                "difficulty_level": new_plan.get("difficulty_level", "Low"),
                "sets_count": new_plan.get("sets_count", 3),
                "reps_count": new_plan.get("reps_count", 10),
                "duration_minutes": new_plan.get("duration_minutes", 15),
                "rest_seconds": new_plan.get("rest_seconds", 30),
                "description": "Loaded from adaptive suggestion.",
            }
        )
        basis = suggestion.get("basis", "Suggested plan loaded.")
        self.note_edit.setPlainText(basis)
        self.review_status_combo.setCurrentIndex(max(self.review_status_combo.findData("adjusted"), 0))
        InfoBar.success("Loaded", "Suggested plan parameters have been loaded into the editor.", position=InfoBarPosition.TOP, parent=self)

    def apply_plan_update(self) -> None:
        if not self._target_user_id():
            InfoBar.warning("No Patient", "Select a patient first.", position=InfoBarPosition.TOP, parent=self)
            return
        try:
            plan_data = {
                "plan_name": self.plan_name_edit.text().strip() or "Doctor Adjusted Plan",
                "target_action": get_action(self.action_edit.text().strip() or DEFAULT_ACTION_NAME).name,
                "difficulty_level": self.difficulty_edit.text().strip() or "Low",
                "sets_count": int(self.sets_edit.text().strip() or 3),
                "reps_count": int(self.reps_edit.text().strip() or 10),
                "duration_minutes": int(self.duration_edit.text().strip() or 15),
                "rest_seconds": int(self.rest_edit.text().strip() or 30),
                "description": self.desc_edit.toPlainText().strip(),
            }
        except ValueError:
            InfoBar.warning("Input Error", "Sets, reps, duration, and rest must be numeric.", position=InfoBarPosition.TOP, parent=self)
            return

        try:
            decision_type = self.decision_combo.currentText()
            note = self.note_edit.toPlainText().strip()
            new_plan_id = self.db.apply_doctor_plan_update(
                viewer_user_id=self.user["id"],
                target_user_id=int(self._target_user_id()),
                plan_data=plan_data,
                reason=f"Doctor intervention: {decision_type}",
                note=note,
                training_record_id=self.selected_record_id,
            )
            self.review_status_combo.setCurrentIndex(max(self.review_status_combo.findData("adjusted"), 0))
            InfoBar.success("Applied", f"New active plan #{new_plan_id} has been created and activated.", position=InfoBarPosition.TOP, parent=self)
            self.refresh_data()
        except Exception as exc:
            InfoBar.error("Apply Failed", str(exc), position=InfoBarPosition.TOP, parent=self)

    def export_pdf(self) -> None:
        try:
            result = self.export_service.export_pdf(
                viewer_user_id=self.user["id"],
                target_user_id=self._target_user_id(),
            )
            InfoBar.success("Exported", f"PDF report exported to: {result['path']}", position=InfoBarPosition.TOP, parent=self)
            self.refresh_data()
        except Exception as exc:
            InfoBar.error("Export Failed", str(exc), position=InfoBarPosition.TOP, parent=self)

    def export_json(self) -> None:
        try:
            result = self.export_service.export_json(
                viewer_user_id=self.user["id"],
                target_user_id=self._target_user_id(),
            )
            InfoBar.success("Exported", f"JSON exported to: {result['path']}", position=InfoBarPosition.TOP, parent=self)
            self.refresh_data()
        except Exception as exc:
            InfoBar.error("Export Failed", str(exc), position=InfoBarPosition.TOP, parent=self)

    def create_backup(self) -> None:
        try:
            result = self.db.create_backup_snapshot(
                requester_user_id=self.user["id"],
                target_user_id=self._target_user_id(),
            )
            InfoBar.success("Backup Created", f"Backup saved to: {result['path']}", position=InfoBarPosition.TOP, parent=self)
            self.refresh_data()
        except Exception as exc:
            InfoBar.error("Backup Failed", str(exc), position=InfoBarPosition.TOP, parent=self)
