"""Database layer for the local development version.

SQLite is used here for a simple course-project workflow. The schema is intentionally
close to a production design so it can later be migrated to MySQL or PostgreSQL.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "rehab_system.db")


class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'patient',
                full_name TEXT NOT NULL,
                gender TEXT,
                age INTEGER,
                phone TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rehab_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                diagnosis TEXT,
                affected_side TEXT,
                rehab_stage TEXT,
                pain_level INTEGER DEFAULT 0,
                rom_goal TEXT,
                contraindications TEXT,
                doctor_name TEXT,
                notes TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS training_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_name TEXT NOT NULL,
                target_action TEXT NOT NULL,
                difficulty_level TEXT NOT NULL,
                sets_count INTEGER DEFAULT 3,
                reps_count INTEGER DEFAULT 10,
                duration_minutes INTEGER DEFAULT 20,
                rest_seconds INTEGER DEFAULT 30,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS training_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_id INTEGER,
                action_name TEXT NOT NULL,
                session_start TEXT NOT NULL,
                session_end TEXT,
                duration_seconds INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0,
                completion_rate REAL DEFAULT 0,
                pain_feedback INTEGER DEFAULT 0,
                summary TEXT,
                status TEXT DEFAULT 'completed',
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(plan_id) REFERENCES training_plans(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS action_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_record_id INTEGER NOT NULL,
                frame_index INTEGER,
                action_label TEXT NOT NULL,
                accuracy_score REAL DEFAULT 0,
                stability_score REAL DEFAULT 0,
                range_score REAL DEFAULT 0,
                rhythm_score REAL DEFAULT 0,
                total_score REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(training_record_id) REFERENCES training_records(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS error_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_record_id INTEGER NOT NULL,
                error_type TEXT NOT NULL,
                error_count INTEGER DEFAULT 1,
                severity TEXT DEFAULT 'medium',
                suggestion TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(training_record_id) REFERENCES training_records(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS compensation_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_record_id INTEGER NOT NULL,
                compensation_type TEXT NOT NULL,
                detected_count INTEGER DEFAULT 1,
                risk_level TEXT DEFAULT 'medium',
                suggestion TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(training_record_id) REFERENCES training_records(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS feedback_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_record_id INTEGER NOT NULL,
                feedback_type TEXT NOT NULL,
                feedback_content TEXT NOT NULL,
                source TEXT DEFAULT 'LLM',
                created_at TEXT NOT NULL,
                FOREIGN KEY(training_record_id) REFERENCES training_records(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS plan_adjustment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                old_plan_id INTEGER,
                new_plan_id INTEGER,
                adjustment_reason TEXT,
                adjustment_detail TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(old_plan_id) REFERENCES training_plans(id) ON DELETE SET NULL,
                FOREIGN KEY(new_plan_id) REFERENCES training_plans(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS doctor_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                training_record_id INTEGER,
                report_title TEXT NOT NULL,
                report_content TEXT NOT NULL,
                recommendation TEXT,
                created_by TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(training_record_id) REFERENCES training_records(id) ON DELETE SET NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def seed_demo_data(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self.get_connection()
        cur = conn.cursor()

        user = cur.execute("SELECT * FROM users WHERE username = ?", ("admin",)).fetchone()
        if not user:
            cur.execute(
                """
                INSERT INTO users (username, password, role, full_name, gender, age, phone, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("admin", "123456", "patient", "Alex Zhang", "Male", 23, "13800000000", now, now),
            )
            user_id = cur.lastrowid
        else:
            user_id = user["id"]

        profile = cur.execute("SELECT * FROM rehab_profiles WHERE user_id = ?", (user_id,)).fetchone()
        if not profile:
            cur.execute(
                """
                INSERT INTO rehab_profiles (
                    user_id, diagnosis, affected_side, rehab_stage, pain_level,
                    rom_goal, contraindications, doctor_name, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    "Post-operative rehabilitation after left knee surgery",
                    "Left",
                    "Mid recovery stage",
                    3,
                    "Increase knee flexion to 120 degrees and improve lower-limb stability",
                    "Avoid high-impact training",
                    "Dr. Lee",
                    "Current focus: sit-to-stand, seated knee raise, and half squat training.",
                    now,
                ),
            )

        plans = cur.execute("SELECT COUNT(*) AS c FROM training_plans WHERE user_id = ?", (user_id,)).fetchone()["c"]
        if plans == 0:
            default_plans = [
                ("Basic Lower-Limb Activation", "Seated Knee Raise", "Low", 3, 10, 15, 30, "Suitable for the early-to-middle post-operative stage and emphasizes movement stability.", 1),
                ("Knee Stability Training", "Half Squat", "Medium", 4, 12, 20, 40, "Strengthens knee control and force generation.", 0),
                ("Gait Assistance Training", "Step-Up March", "Medium", 3, 15, 18, 35, "Improves gait rhythm and left-right balance.", 0),
            ]
            for plan in default_plans:
                cur.execute(
                    """
                    INSERT INTO training_plans (
                        user_id, plan_name, target_action, difficulty_level,
                        sets_count, reps_count, duration_minutes, rest_seconds,
                        description, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, *plan, now, now),
                )

        records = cur.execute("SELECT COUNT(*) AS c FROM training_records WHERE user_id = ?", (user_id,)).fetchone()["c"]
        if records == 0:
            active_plan = self.get_active_plan(user_id)
            for i in range(1, 6):
                start_dt = datetime.now() - timedelta(days=6 - i)
                end_dt = start_dt + timedelta(minutes=18)
                avg_score = 72 + i * 3
                record_id = cur.execute(
                    """
                    INSERT INTO training_records (
                        user_id, plan_id, action_name, session_start, session_end,
                        duration_seconds, avg_score, completion_rate, pain_feedback,
                        summary, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        active_plan["id"] if active_plan else None,
                        active_plan["target_action"] if active_plan else "Seated Knee Raise",
                        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        1080,
                        avg_score,
                        0.86 + i * 0.02,
                        max(1, 4 - i // 2),
                        f"Session {i} was stable overall with good completion quality.",
                        "completed",
                        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                ).lastrowid
                cur.execute(
                    """
                    INSERT INTO doctor_reports (
                        user_id, training_record_id, report_title, report_content,
                        recommendation, created_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        record_id,
                        f"Training Report #{i}",
                        f"Average score {avg_score}. The patient shows an improving trend in movement control.",
                        "Recommend continuing the current training intensity.",
                        "system",
                        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )

        conn.commit()
        conn.close()

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        conn = self.get_connection()
        cur = conn.cursor()
        row = cur.execute(query, params).fetchone()
        conn.close()
        return row

    def fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        conn = self.get_connection()
        cur = conn.cursor()
        rows = cur.execute(query, params).fetchall()
        conn.close()
        return rows

    def execute(self, query: str, params: tuple = ()) -> int:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        last_id = cur.lastrowid
        conn.commit()
        conn.close()
        return last_id

    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.executemany(query, params_list)
        conn.commit()
        conn.close()

    def login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        row = self.fetch_one(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        return dict(row) if row else None

    def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.fetch_one("SELECT * FROM rehab_profiles WHERE user_id = ?", (user_id,))
        return dict(row) if row else None

    def save_user_profile(self, user_id: int, data: Dict[str, Any]) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = self.fetch_one("SELECT id FROM rehab_profiles WHERE user_id = ?", (user_id,))
        if existing:
            self.execute(
                """
                UPDATE rehab_profiles
                SET diagnosis = ?, affected_side = ?, rehab_stage = ?, pain_level = ?,
                    rom_goal = ?, contraindications = ?, doctor_name = ?, notes = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    data.get("diagnosis", ""),
                    data.get("affected_side", ""),
                    data.get("rehab_stage", ""),
                    data.get("pain_level", 0),
                    data.get("rom_goal", ""),
                    data.get("contraindications", ""),
                    data.get("doctor_name", ""),
                    data.get("notes", ""),
                    now,
                    user_id,
                ),
            )
        else:
            self.execute(
                """
                INSERT INTO rehab_profiles (
                    user_id, diagnosis, affected_side, rehab_stage, pain_level,
                    rom_goal, contraindications, doctor_name, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    data.get("diagnosis", ""),
                    data.get("affected_side", ""),
                    data.get("rehab_stage", ""),
                    data.get("pain_level", 0),
                    data.get("rom_goal", ""),
                    data.get("contraindications", ""),
                    data.get("doctor_name", ""),
                    data.get("notes", ""),
                    now,
                ),
            )

    def get_plans(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.fetch_all(
            "SELECT * FROM training_plans WHERE user_id = ? ORDER BY is_active DESC, id DESC",
            (user_id,),
        )
        return [dict(row) for row in rows]

    def get_active_plan(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.fetch_one(
            "SELECT * FROM training_plans WHERE user_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        return dict(row) if row else None

    def create_plan(self, user_id: int, data: Dict[str, Any]) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.execute(
            """
            INSERT INTO training_plans (
                user_id, plan_name, target_action, difficulty_level,
                sets_count, reps_count, duration_minutes, rest_seconds,
                description, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                data.get("plan_name", "New Plan"),
                data.get("target_action", "Seated Knee Raise"),
                data.get("difficulty_level", "Low"),
                int(data.get("sets_count", 3)),
                int(data.get("reps_count", 10)),
                int(data.get("duration_minutes", 15)),
                int(data.get("rest_seconds", 30)),
                data.get("description", ""),
                int(data.get("is_active", 0)),
                now,
                now,
            ),
        )

    def activate_plan(self, user_id: int, plan_id: int, reason: str = "Manual plan switch") -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        old_plan = self.get_active_plan(user_id)
        self.execute("UPDATE training_plans SET is_active = 0, updated_at = ? WHERE user_id = ?", (now, user_id))
        self.execute("UPDATE training_plans SET is_active = 1, updated_at = ? WHERE id = ?", (now, plan_id))
        self.execute(
            """
            INSERT INTO plan_adjustment_history (
                user_id, old_plan_id, new_plan_id, adjustment_reason,
                adjustment_detail, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                old_plan["id"] if old_plan else None,
                plan_id,
                reason,
                "The selected plan was set as the active training plan.",
                now,
            ),
        )

    def save_training_session(self, user_id: int, plan_id: Optional[int], session_data: Dict[str, Any]) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record_id = self.execute(
            """
            INSERT INTO training_records (
                user_id, plan_id, action_name, session_start, session_end,
                duration_seconds, avg_score, completion_rate, pain_feedback,
                summary, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                plan_id,
                session_data["action_name"],
                session_data["session_start"],
                session_data["session_end"],
                session_data["duration_seconds"],
                session_data["avg_score"],
                session_data["completion_rate"],
                session_data.get("pain_feedback", 0),
                session_data["summary"],
                "completed",
                now,
            ),
        )

        score_rows = [
            (
                record_id,
                item.get("frame_index", idx),
                item["action_label"],
                item["accuracy_score"],
                item["stability_score"],
                item["range_score"],
                item["rhythm_score"],
                item["total_score"],
                now,
            )
            for idx, item in enumerate(session_data.get("scores", []), start=1)
        ]
        if score_rows:
            self.execute_many(
                """
                INSERT INTO action_scores (
                    training_record_id, frame_index, action_label, accuracy_score,
                    stability_score, range_score, rhythm_score, total_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                score_rows,
            )

        error_rows = [
            (
                record_id,
                item["error_type"],
                item.get("error_count", 1),
                item.get("severity", "medium"),
                item.get("suggestion", ""),
                now,
            )
            for item in session_data.get("errors", [])
        ]
        if error_rows:
            self.execute_many(
                """
                INSERT INTO error_actions (
                    training_record_id, error_type, error_count,
                    severity, suggestion, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                error_rows,
            )

        compensation_rows = [
            (
                record_id,
                item["compensation_type"],
                item.get("detected_count", 1),
                item.get("risk_level", "medium"),
                item.get("suggestion", ""),
                now,
            )
            for item in session_data.get("compensations", [])
        ]
        if compensation_rows:
            self.execute_many(
                """
                INSERT INTO compensation_actions (
                    training_record_id, compensation_type, detected_count,
                    risk_level, suggestion, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                compensation_rows,
            )

        feedback_rows = [
            (record_id, item.get("feedback_type", "realtime"), item["feedback_content"], item.get("source", "LLM"), now)
            for item in session_data.get("feedbacks", [])
        ]
        if feedback_rows:
            self.execute_many(
                """
                INSERT INTO feedback_records (
                    training_record_id, feedback_type, feedback_content,
                    source, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                feedback_rows,
            )

        self.execute(
            """
            INSERT INTO doctor_reports (
                user_id, training_record_id, report_title, report_content,
                recommendation, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                record_id,
                f"Training Result Report #{record_id}",
                session_data["summary"],
                session_data.get("doctor_recommendation", "Maintain the current pace and pay attention to movement symmetry."),
                "system",
                now,
            ),
        )

        adjustment_detail = session_data.get("plan_adjustment")
        if adjustment_detail:
            self.execute(
                """
                INSERT INTO plan_adjustment_history (
                    user_id, old_plan_id, new_plan_id, adjustment_reason,
                    adjustment_detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    plan_id,
                    plan_id,
                    adjustment_detail.get("reason", "Automatic adjustment suggestion"),
                    adjustment_detail.get("detail", "Suggestion generated from the current training session."),
                    now,
                ),
            )
        return record_id

    def get_latest_record(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.fetch_one(
            "SELECT * FROM training_records WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        return dict(row) if row else None

    def get_records(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.fetch_all(
            "SELECT * FROM training_records WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        return [dict(row) for row in rows]

    def get_record_details(self, record_id: int) -> Dict[str, Any]:
        record = self.fetch_one("SELECT * FROM training_records WHERE id = ?", (record_id,))
        scores = self.fetch_all("SELECT * FROM action_scores WHERE training_record_id = ? ORDER BY id", (record_id,))
        errors = self.fetch_all("SELECT * FROM error_actions WHERE training_record_id = ? ORDER BY id", (record_id,))
        compensations = self.fetch_all("SELECT * FROM compensation_actions WHERE training_record_id = ? ORDER BY id", (record_id,))
        feedbacks = self.fetch_all("SELECT * FROM feedback_records WHERE training_record_id = ? ORDER BY id", (record_id,))
        report = self.fetch_one(
            "SELECT * FROM doctor_reports WHERE training_record_id = ? ORDER BY id DESC LIMIT 1",
            (record_id,),
        )
        return {
            "record": dict(record) if record else None,
            "scores": [dict(score) for score in scores],
            "errors": [dict(item) for item in errors],
            "compensations": [dict(item) for item in compensations],
            "feedbacks": [dict(item) for item in feedbacks],
            "report": dict(report) if report else None,
        }

    def get_plan_adjustments(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.fetch_all(
            "SELECT * FROM plan_adjustment_history WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )
        return [dict(row) for row in rows]

    def get_analysis_summary(self, user_id: int) -> Dict[str, Any]:
        records = self.get_records(user_id, limit=20)
        if not records:
            return {
                "session_count": 0,
                "avg_score": 0,
                "best_score": 0,
                "trend": "No data",
                "avg_completion": 0,
                "avg_pain": 0,
            }

        scores = [record["avg_score"] or 0 for record in records]
        completions = [record["completion_rate"] or 0 for record in records]
        pains = [record["pain_feedback"] or 0 for record in records]
        trend = "Improving"
        if len(scores) >= 2 and scores[0] < scores[-1]:
            trend = "Declining"
        elif len(scores) >= 2 and abs(scores[0] - scores[-1]) <= 2:
            trend = "Stable"

        return {
            "session_count": len(records),
            "avg_score": round(sum(scores) / len(scores), 2),
            "best_score": round(max(scores), 2),
            "trend": trend,
            "avg_completion": round(sum(completions) / len(completions) * 100, 2),
            "avg_pain": round(sum(pains) / len(pains), 2),
        }
