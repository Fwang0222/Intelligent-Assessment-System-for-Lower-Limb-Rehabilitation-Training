"""Doctor dashboard page for decision support and remote access."""

from PySide6.QtWidgets import QGridLayout, QHBoxLayout

from app.services.report_export_service import ReportExportService
from app.ui.base import BasePage
from app.ui.fluent_compat import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    PageTitleLabel,
    PrimaryPushButton,
    PushButton,
    TextEdit,
)


class DoctorPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.export_service = ReportExportService(db)
        self.selected_patient_id = None
        self._patient_map = {}
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("Doctor Decision Support"))

        toolbar_card, toolbar_layout = self.create_section_card(
            "Remote Access & Export",
            "Cloud-stored medical data, local AI inference, export, backup, and doctor-side review.",
        )
        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(8)

        self.patient_selector = ComboBox()
        self.patient_selector.setMinimumWidth(220)
        self.patient_selector.currentIndexChanged.connect(self._on_patient_changed)
        self.refresh_btn = PrimaryPushButton("Refresh Summary")
        self.export_pdf_btn = PrimaryPushButton("Export PDF")
        self.export_json_btn = PushButton("Export API JSON")
        self.backup_btn = PushButton("Create Backup")

        self.refresh_btn.clicked.connect(self.refresh_data)
        self.export_pdf_btn.clicked.connect(self.export_pdf)
        self.export_json_btn.clicked.connect(self.export_json)
        self.backup_btn.clicked.connect(self.create_backup)

        if self.user.get("role") == "doctor":
            toolbar_row.addWidget(BodyLabel("Patient:"))
            toolbar_row.addWidget(self.patient_selector)
        toolbar_row.addWidget(self.refresh_btn)
        toolbar_row.addWidget(self.export_pdf_btn)
        toolbar_row.addWidget(self.export_json_btn)
        toolbar_row.addWidget(self.backup_btn)
        toolbar_row.addStretch(1)
        toolbar_layout.addLayout(toolbar_row)
        self.main_layout.addWidget(toolbar_card)

        overview_card, overview_layout = self.create_section_card(
            "Clinical Summary",
            "Profile, trend, risk, recommendation, and security status for the currently selected patient.",
        )
        summary_grid = QGridLayout()
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(10)
        summary_grid.setVerticalSpacing(10)
        self.patient_label = self._create_summary_card(summary_grid, 0, 0, "Patient")
        self.trend_label = self._create_summary_card(summary_grid, 0, 1, "Trend")
        self.risk_label = self._create_summary_card(summary_grid, 1, 0, "Risk Focus")
        self.recommendation_label = self._create_summary_card(summary_grid, 1, 1, "Decision")
        self.security_label = self._create_summary_card(summary_grid, 2, 0, "Security")
        self.backup_label = self._create_summary_card(summary_grid, 2, 1, "Backup & Audit")
        overview_layout.addLayout(summary_grid)
        self.main_layout.addWidget(overview_card)

        card, layout = self.create_section_card(
            "Detailed Clinical Notes",
            "Structured notes for patient profile, latest session, high-frequency risks, and adjustment direction.",
        )
        self.report_text = TextEdit()
        self.report_text.setReadOnly(True)
        layout.addWidget(self.report_text)
        self.main_layout.addWidget(card, 1)

    def _create_summary_card(self, grid: QGridLayout, row: int, column: int, title: str):
        card, layout = self.create_section_card(title)
        label = BodyLabel("-")
        label.setWordWrap(True)
        label.setStyleSheet("font-weight: 600; color: #0F172A; background: transparent; border: none; line-height: 1.45;")
        layout.addWidget(label)
        grid.addWidget(card, row, column)
        return label

    def _populate_patient_selector(self, patients) -> None:
        if self.user.get("role") != "doctor":
            return
        current_target = self.selected_patient_id
        self.patient_selector.blockSignals(True)
        self.patient_selector.clear()
        self._patient_map = {}
        for patient in patients:
            label = f"{patient.get('full_name', 'Patient')} | {patient.get('rehab_stage', '-')}"
            self.patient_selector.addItem(label, int(patient["id"]))
            self._patient_map[int(patient["id"])] = patient
        if self.patient_selector.count() > 0:
            target = current_target if current_target in self._patient_map else int(self.patient_selector.itemData(0))
            index = self.patient_selector.findData(target)
            self.patient_selector.setCurrentIndex(max(index, 0))
            self.selected_patient_id = int(self.patient_selector.currentData())
        else:
            self.selected_patient_id = None
        self.patient_selector.blockSignals(False)

    def _target_user_id(self):
        if self.user.get("role") == "doctor":
            return self.selected_patient_id
        return self.user["id"]

    def _on_patient_changed(self) -> None:
        if self.user.get("role") != "doctor":
            return
        data = self.patient_selector.currentData()
        self.selected_patient_id = int(data) if data is not None else None
        self.refresh_data()

    def refresh_data(self) -> None:
        info = self.db.get_doctor_dashboard(self.user["id"], self.selected_patient_id)
        self._populate_patient_selector(info.get("patients") or [])
        selected_user_id = info.get("selected_user_id")
        self.selected_patient_id = selected_user_id
        security = self.db.get_security_overview(self.user["id"], selected_user_id)

        user = info.get("user") or {}
        profile = info.get("profile") or {}
        summary = info.get("summary") or {}
        recent = info.get("recent_records") or []
        errors = info.get("errors") or []
        comps = info.get("compensations") or []

        top_error = errors[0]["label"] if errors else "None"
        top_comp = comps[0]["label"] if comps else "None"
        latest = recent[0] if recent else None
        self.patient_label.setText(
            f"{user.get('full_name', '-')}\n"
            f"Stage: {user.get('rehab_stage', '-')}\n"
            f"Diagnosis: {profile.get('diagnosis', '-')}"
        )
        self.trend_label.setText(
            f"Trend: {summary.get('trend', '-')}\n"
            f"Avg Score: {summary.get('avg_score', 0)}\n"
            f"Completion: {summary.get('avg_completion', 0)}%"
        )
        self.risk_label.setText(
            f"Top error: {top_error}\n"
            f"Top compensation: {top_comp}\n"
            f"Pain avg: {summary.get('avg_pain', 0)}"
        )
        self.recommendation_label.setText(info.get("recommendation", "No recommendation available."))
        self.security_label.setText(
            f"Storage: {security.get('storage_backend', '-')}\n"
            f"DB/TLS: {security.get('ssl_mode', '-')}\n"
            f"AI policy: {security.get('ai_policy', '-')}"
        )
        self.backup_label.setText(
            f"Remote doctor access: {'Enabled' if security.get('remote_doctor_access') else 'Disabled'}\n"
            f"Backups: {security.get('backup_count', 0)} | Latest: {security.get('latest_backup_at', '-')}\n"
            f"Audit events: {security.get('audit_event_count', 0)} | Latest: {security.get('latest_audit_action', '-')}"
        )

        lines = [
            "[Clinical Overview]",
            f"- Patient: {user.get('full_name', '-')} | Stage: {user.get('rehab_stage', '-')}",
            f"- Diagnosis: {profile.get('diagnosis', '-')}",
            f"- Active recommendation: {info.get('recommendation', 'No recommendation available.')}",
            "",
            "[Trend & Risk]",
            f"- Trend: {summary.get('trend', '-')} | Avg score: {summary.get('avg_score', 0)} | Completion: {summary.get('avg_completion', 0)}%",
            f"- Top error: {top_error}",
            f"- Top compensation: {top_comp}",
            "",
            "[Latest Session]",
        ]
        if not latest:
            lines.append("- No recent session.")
        else:
            lines.extend(
                [
                    f"- Session #{latest['id']} | {latest['action_name']}",
                    f"- Score: {latest['avg_score']} | Completion: {round((latest['completion_rate'] or 0) * 100, 2)}%",
                    f"- Summary: {latest.get('summary', '-')}",
                ]
            )
        lines.extend(
            [
                "",
                "[Security & Backup]",
                f"- Storage backend: {security.get('storage_backend', '-')}",
                f"- TLS/SSL mode: {security.get('ssl_mode', '-')}",
                f"- Latest backup: {security.get('latest_backup_at', '-')}",
                f"- Recent audit action: {security.get('latest_audit_action', '-')}",
            ]
        )
        self.report_text.setPlainText("\n".join(lines))

    def export_pdf(self) -> None:
        try:
            result = self.export_service.export_pdf(
                viewer_user_id=self.user["id"],
                target_user_id=self._target_user_id(),
            )
            InfoBar.success(
                "Exported",
                f"PDF report exported to: {result['path']}",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            self.refresh_data()
        except Exception as exc:
            InfoBar.error("Export Failed", str(exc), position=InfoBarPosition.TOP, parent=self)

    def export_json(self) -> None:
        try:
            result = self.export_service.export_json(
                viewer_user_id=self.user["id"],
                target_user_id=self._target_user_id(),
            )
            InfoBar.success(
                "Exported",
                f"API JSON exported to: {result['path']}",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            self.refresh_data()
        except Exception as exc:
            InfoBar.error("Export Failed", str(exc), position=InfoBarPosition.TOP, parent=self)

    def create_backup(self) -> None:
        try:
            result = self.db.create_backup_snapshot(
                requester_user_id=self.user["id"],
                target_user_id=self._target_user_id(),
            )
            InfoBar.success(
                "Backup Created",
                f"Backup saved to: {result['path']}",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            self.refresh_data()
        except Exception as exc:
            InfoBar.error("Backup Failed", str(exc), position=InfoBarPosition.TOP, parent=self)
