"""Export structured doctor reports to PDF or JSON."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument


class ReportExportService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _safe_slug(value: str) -> str:
        text = re.sub(r"[^A-Za-z0-9_-]+", "_", value or "report").strip("_")
        return text or "report"

    def _build_base_path(self, patient_name: str, suffix: str) -> str:
        export_dir = self.db.config.report_export_dir
        os.makedirs(export_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{self._safe_slug(patient_name)}_{suffix}_{stamp}"
        return os.path.join(export_dir, file_name)

    @staticmethod
    def _to_lines(items, key_name: str, count_name: str) -> str:
        if not items:
            return "<li>None</li>"
        parts = []
        for item in items[:8]:
            parts.append(
                f"<li><b>{item.get(key_name, '-')}</b>: {item.get(count_name, 0)}</li>"
            )
        return "".join(parts)

    def _build_html(self, payload: Dict[str, Any]) -> str:
        patient = payload.get("patient") or {}
        profile = payload.get("profile") or {}
        summary = payload.get("analysis_summary") or {}
        security = payload.get("security_overview") or {}
        selected_record = payload.get("selected_record") or {}
        details = payload.get("record_details") or {}
        errors = details.get("errors") or []
        compensations = details.get("compensations") or []
        report = details.get("report") or {}
        active_plan = payload.get("active_plan") or {}

        latest_score = selected_record.get("avg_score", "-")
        latest_completion = round((selected_record.get("completion_rate") or 0) * 100, 2) if selected_record else "-"

        return f"""
        <html>
          <head>
            <meta charset="utf-8">
            <style>
              body {{ font-family: 'Segoe UI', 'Microsoft YaHei'; color: #0F172A; font-size: 12px; }}
              h1 {{ font-size: 22px; margin-bottom: 6px; }}
              h2 {{ font-size: 15px; margin: 18px 0 8px 0; color: #1D4ED8; }}
              .muted {{ color: #64748B; }}
              .grid {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
              .grid td {{ border: 1px solid #D9E2EC; padding: 8px; vertical-align: top; }}
              .metric {{ background: #F8FAFC; }}
              ul {{ margin: 6px 0 0 18px; }}
            </style>
          </head>
          <body>
            <h1>Lower-Limb Rehabilitation Doctor Report</h1>
            <div class="muted">Generated at: {payload.get("generated_at", "-")} | Storage: {payload.get("storage_backend", "-")}</div>

            <h2>Patient Overview</h2>
            <table class="grid">
              <tr>
                <td class="metric"><b>Patient</b><br>{patient.get("full_name", "-")}</td>
                <td class="metric"><b>Stage</b><br>{patient.get("rehab_stage", "-")}</td>
                <td class="metric"><b>Diagnosis</b><br>{profile.get("diagnosis", "-")}</td>
              </tr>
              <tr>
                <td><b>Affected Side</b><br>{patient.get("affected_side", "-")}</td>
                <td><b>Injured Part</b><br>{patient.get("injured_part", "-")}</td>
                <td><b>Rehab Goal</b><br>{patient.get("rehab_goal", "-")}</td>
              </tr>
            </table>

            <h2>Training Summary</h2>
            <table class="grid">
              <tr>
                <td class="metric"><b>Session Count</b><br>{summary.get("session_count", 0)}</td>
                <td class="metric"><b>Average Score</b><br>{summary.get("avg_score", 0)}</td>
                <td class="metric"><b>Trend</b><br>{summary.get("trend", "-")}</td>
              </tr>
              <tr>
                <td><b>Best Score</b><br>{summary.get("best_score", 0)}</td>
                <td><b>Average Completion</b><br>{summary.get("avg_completion", 0)}%</td>
                <td><b>Average Pain</b><br>{summary.get("avg_pain", 0)}</td>
              </tr>
            </table>

            <h2>Latest Session</h2>
            <table class="grid">
              <tr>
                <td class="metric"><b>Action</b><br>{selected_record.get("action_name", "-")}</td>
                <td class="metric"><b>Score</b><br>{latest_score}</td>
                <td class="metric"><b>Completion</b><br>{latest_completion}%</td>
              </tr>
              <tr>
                <td><b>Start</b><br>{selected_record.get("session_start", "-")}</td>
                <td><b>End</b><br>{selected_record.get("session_end", "-")}</td>
                <td><b>Duration</b><br>{selected_record.get("duration_seconds", "-")} sec</td>
              </tr>
            </table>

            <h2>Risk Highlights</h2>
            <table class="grid">
              <tr>
                <td><b>Error Actions</b><ul>{self._to_lines(errors, "error_type", "error_count")}</ul></td>
                <td><b>Compensation Actions</b><ul>{self._to_lines(compensations, "compensation_type", "detected_count")}</ul></td>
              </tr>
            </table>

            <h2>Plan & Recommendation</h2>
            <table class="grid">
              <tr>
                <td><b>Active Plan</b><br>{active_plan.get("plan_name", "-")} / {active_plan.get("target_action", "-")}</td>
                <td><b>Difficulty</b><br>{active_plan.get("difficulty_level", "-")}</td>
                <td><b>Volume</b><br>{active_plan.get("sets_count", "-")} x {active_plan.get("reps_count", "-")}</td>
              </tr>
              <tr>
                <td colspan="3"><b>Doctor Recommendation</b><br>{report.get("recommendation", "No recommendation available.")}</td>
              </tr>
              <tr>
                <td colspan="3"><b>Session Summary</b><br>{selected_record.get("summary", "-")}</td>
              </tr>
            </table>

            <h2>Security & Access</h2>
            <table class="grid">
              <tr>
                <td class="metric"><b>Storage Backend</b><br>{security.get("storage_backend", "-")}</td>
                <td class="metric"><b>DB/TLS</b><br>{security.get("ssl_mode", "-")}</td>
                <td class="metric"><b>Remote Doctor Access</b><br>{'Enabled' if security.get("remote_doctor_access") else 'Disabled'}</td>
              </tr>
              <tr>
                <td><b>AI Policy</b><br>{security.get("ai_policy", "-")}</td>
                <td><b>Backup Count</b><br>{security.get("backup_count", 0)}</td>
                <td><b>Latest Backup</b><br>{security.get("latest_backup_at", "-")}</td>
              </tr>
            </table>
          </body>
        </html>
        """

    def export_json(
        self,
        viewer_user_id: int,
        target_user_id: Optional[int] = None,
        training_record_id: Optional[int] = None,
        include_full_history: bool = True,
    ) -> Dict[str, Any]:
        payload = self.db.build_report_export_payload(
            viewer_user_id=viewer_user_id,
            target_user_id=target_user_id,
            training_record_id=training_record_id,
            include_full_history=include_full_history,
        )
        patient_name = (payload.get("patient") or {}).get("full_name", "patient")
        path = self._build_base_path(patient_name, "doctor_report") + ".json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.db.record_export_event(viewer_user_id, int(payload["target_user_id"]), "json", path, success=True)
        return {"path": path, "target_user_id": int(payload["target_user_id"])}

    def export_pdf(
        self,
        viewer_user_id: int,
        target_user_id: Optional[int] = None,
        training_record_id: Optional[int] = None,
        include_full_history: bool = False,
    ) -> Dict[str, Any]:
        payload = self.db.build_report_export_payload(
            viewer_user_id=viewer_user_id,
            target_user_id=target_user_id,
            training_record_id=training_record_id,
            include_full_history=include_full_history,
        )
        patient_name = (payload.get("patient") or {}).get("full_name", "patient")
        path = self._build_base_path(patient_name, "doctor_report") + ".pdf"
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setResolution(120)

        document = QTextDocument()
        document.setHtml(self._build_html(payload))
        document.setPageSize(QSizeF(writer.width(), writer.height()))
        document.print_(writer)

        self.db.record_export_event(viewer_user_id, int(payload["target_user_id"]), "pdf", path, success=True)
        return {"path": path, "target_user_id": int(payload["target_user_id"])}
