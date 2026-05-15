"""Database layer for V5 local-AI + cloud-medical-data architecture."""

from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from app.core.rehab_actions import DEMO_ACTIONS, DEFAULT_ACTION_NAME, build_default_plan_payload, get_action
from app.core.runtime_config import DATA_DIR, RuntimeConfig

POSTGRES_OK = False
POSTGRES_DRIVER = ""
try:
    import psycopg  # type: ignore

    POSTGRES_OK = True
    POSTGRES_DRIVER = "psycopg"
except Exception:
    try:
        import psycopg2  # type: ignore

        POSTGRES_OK = True
        POSTGRES_DRIVER = "psycopg2"
    except Exception:
        POSTGRES_OK = False
        POSTGRES_DRIVER = ""


DB_PATH = os.path.join(DATA_DIR, "rehab_system.db")


class DatabaseManager:
    def __init__(self, config: RuntimeConfig | None = None, db_path: str | None = None):
        self.config = config or RuntimeConfig.from_sources()
        self.db_path = db_path or self.config.sqlite_cache_path or DB_PATH
        self.backend = "postgres" if self.config.is_cloud_storage_enabled() else "sqlite"
        self._ensure_runtime_directories()
        self._ensure_secure_configuration()
        if self.backend == "postgres" and not POSTGRES_OK:
            raise RuntimeError(
                "PostgreSQL backend requested, but neither psycopg nor psycopg2 is installed. "
                "Please install a PostgreSQL driver first."
            )

    def _ensure_runtime_directories(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        os.makedirs(self.config.backup_dir, exist_ok=True)
        os.makedirs(self.config.report_export_dir, exist_ok=True)

    def _ensure_secure_configuration(self) -> None:
        if self.backend != "postgres":
            return
        insecure_modes = {"disable", "allow", "prefer"}
        if self.config.postgres_ssl_mode in insecure_modes and not self.config.allow_insecure_db:
            raise RuntimeError(
                "Insecure PostgreSQL sslmode is blocked. Set sslmode=require/verify-ca/verify-full, "
                "or explicitly enable allow_insecure_db for a development-only environment."
            )

    def is_cloud_backend(self) -> bool:
        return self.backend == "postgres"

    def storage_label(self) -> str:
        return "Cloud PostgreSQL" if self.is_cloud_backend() else "Local SQLite"

    def _adapt_query(self, query: str) -> str:
        if self.backend != "postgres":
            return query
        return query.replace("?", "%s")

    def _get_sqlite_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _get_postgres_connection(self):
        kwargs = {
            "host": self.config.postgres_host,
            "port": self.config.postgres_port,
            "dbname": self.config.postgres_db,
            "user": self.config.postgres_user,
            "password": self.config.postgres_password,
            "sslmode": self.config.postgres_ssl_mode,
            "connect_timeout": self.config.postgres_connect_timeout,
        }
        if self.config.postgres_ssl_root_cert:
            kwargs["sslrootcert"] = self.config.postgres_ssl_root_cert
        if POSTGRES_DRIVER == "psycopg":
            return psycopg.connect(**kwargs)  # type: ignore[name-defined]
        return psycopg2.connect(**kwargs)  # type: ignore[name-defined]

    def get_connection(self):
        return self._get_postgres_connection() if self.backend == "postgres" else self._get_sqlite_connection()

    def initialize(self) -> None:
        if self.backend == "postgres":
            self._initialize_postgres()
        else:
            self._initialize_sqlite()
        self._initialize_indexes()
        self.prune_audit_logs()

    def _initialize_sqlite(self) -> None:
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
                height_cm REAL,
                weight_kg REAL,
                injured_part TEXT,
                affected_side TEXT,
                rehab_stage TEXT,
                rehab_goal TEXT,
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
                symmetry_score REAL DEFAULT 0,
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

            CREATE TABLE IF NOT EXISTS doctor_interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                training_record_id INTEGER,
                review_status TEXT DEFAULT 'pending',
                decision_type TEXT NOT NULL,
                note TEXT,
                override_json TEXT,
                old_plan_id INTEGER,
                new_plan_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(target_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(training_record_id) REFERENCES training_records(id) ON DELETE SET NULL,
                FOREIGN KEY(old_plan_id) REFERENCES training_plans(id) ON DELETE SET NULL,
                FOREIGN KEY(new_plan_id) REFERENCES training_plans(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS doctor_patient_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_user_id INTEGER NOT NULL,
                patient_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(doctor_user_id, patient_user_id),
                FOREIGN KEY(doctor_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(patient_user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                target_user_id INTEGER,
                action_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                success INTEGER DEFAULT 1,
                client_node TEXT,
                ip_address TEXT,
                detail_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(target_user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS backup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_user_id INTEGER,
                target_user_id INTEGER,
                backup_path TEXT NOT NULL,
                backup_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(requester_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(target_user_id) REFERENCES users(id) ON DELETE SET NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def _initialize_postgres(self) -> None:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                username VARCHAR(128) UNIQUE NOT NULL,
                password VARCHAR(512) NOT NULL,
                role VARCHAR(32) DEFAULT 'patient',
                full_name VARCHAR(255) NOT NULL,
                gender VARCHAR(32),
                age INTEGER,
                height_cm DOUBLE PRECISION,
                weight_kg DOUBLE PRECISION,
                injured_part VARCHAR(255),
                affected_side VARCHAR(64),
                rehab_stage VARCHAR(128),
                rehab_goal TEXT,
                phone VARCHAR(64),
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rehab_profiles (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                diagnosis TEXT,
                affected_side VARCHAR(64),
                rehab_stage VARCHAR(128),
                pain_level INTEGER DEFAULT 0,
                rom_goal TEXT,
                contraindications TEXT,
                doctor_name VARCHAR(255),
                notes TEXT,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS training_plans (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                plan_name VARCHAR(255) NOT NULL,
                target_action VARCHAR(255) NOT NULL,
                difficulty_level VARCHAR(64) NOT NULL,
                sets_count INTEGER DEFAULT 3,
                reps_count INTEGER DEFAULT 10,
                duration_minutes INTEGER DEFAULT 20,
                rest_seconds INTEGER DEFAULT 30,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS training_records (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                plan_id BIGINT REFERENCES training_plans(id) ON DELETE SET NULL,
                action_name VARCHAR(255) NOT NULL,
                session_start TIMESTAMP NOT NULL,
                session_end TIMESTAMP,
                duration_seconds INTEGER DEFAULT 0,
                avg_score DOUBLE PRECISION DEFAULT 0,
                completion_rate DOUBLE PRECISION DEFAULT 0,
                pain_feedback INTEGER DEFAULT 0,
                summary TEXT,
                status VARCHAR(32) DEFAULT 'completed',
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS action_scores (
                id BIGSERIAL PRIMARY KEY,
                training_record_id BIGINT NOT NULL REFERENCES training_records(id) ON DELETE CASCADE,
                frame_index INTEGER,
                action_label VARCHAR(255) NOT NULL,
                accuracy_score DOUBLE PRECISION DEFAULT 0,
                stability_score DOUBLE PRECISION DEFAULT 0,
                range_score DOUBLE PRECISION DEFAULT 0,
                rhythm_score DOUBLE PRECISION DEFAULT 0,
                symmetry_score DOUBLE PRECISION DEFAULT 0,
                total_score DOUBLE PRECISION DEFAULT 0,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS error_actions (
                id BIGSERIAL PRIMARY KEY,
                training_record_id BIGINT NOT NULL REFERENCES training_records(id) ON DELETE CASCADE,
                error_type VARCHAR(255) NOT NULL,
                error_count INTEGER DEFAULT 1,
                severity VARCHAR(32) DEFAULT 'medium',
                suggestion TEXT,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS compensation_actions (
                id BIGSERIAL PRIMARY KEY,
                training_record_id BIGINT NOT NULL REFERENCES training_records(id) ON DELETE CASCADE,
                compensation_type VARCHAR(255) NOT NULL,
                detected_count INTEGER DEFAULT 1,
                risk_level VARCHAR(32) DEFAULT 'medium',
                suggestion TEXT,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_records (
                id BIGSERIAL PRIMARY KEY,
                training_record_id BIGINT NOT NULL REFERENCES training_records(id) ON DELETE CASCADE,
                feedback_type VARCHAR(64) NOT NULL,
                feedback_content TEXT NOT NULL,
                source VARCHAR(64) DEFAULT 'LLM',
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_adjustment_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                old_plan_id BIGINT REFERENCES training_plans(id) ON DELETE SET NULL,
                new_plan_id BIGINT REFERENCES training_plans(id) ON DELETE SET NULL,
                adjustment_reason TEXT,
                adjustment_detail TEXT,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS doctor_reports (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                training_record_id BIGINT REFERENCES training_records(id) ON DELETE SET NULL,
                report_title VARCHAR(255) NOT NULL,
                report_content TEXT NOT NULL,
                recommendation TEXT,
                created_by VARCHAR(128) DEFAULT 'system',
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS doctor_interventions (
                id BIGSERIAL PRIMARY KEY,
                actor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                target_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                training_record_id BIGINT REFERENCES training_records(id) ON DELETE SET NULL,
                review_status VARCHAR(32) DEFAULT 'pending',
                decision_type VARCHAR(64) NOT NULL,
                note TEXT,
                override_json TEXT,
                old_plan_id BIGINT REFERENCES training_plans(id) ON DELETE SET NULL,
                new_plan_id BIGINT REFERENCES training_plans(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS doctor_patient_links (
                id BIGSERIAL PRIMARY KEY,
                doctor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                patient_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(doctor_user_id, patient_user_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id BIGSERIAL PRIMARY KEY,
                actor_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                target_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                action_type VARCHAR(128) NOT NULL,
                entity_type VARCHAR(128),
                entity_id BIGINT,
                success INTEGER DEFAULT 1,
                client_node VARCHAR(255),
                ip_address VARCHAR(64),
                detail_json TEXT,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS backup_history (
                id BIGSERIAL PRIMARY KEY,
                requester_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                target_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                backup_path TEXT NOT NULL,
                backup_hash VARCHAR(128) NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def _initialize_indexes(self) -> None:
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_training_records_user_created ON training_records (user_id, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_training_plans_user_active ON training_plans (user_id, is_active, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_action_scores_record ON action_scores (training_record_id)",
            "CREATE INDEX IF NOT EXISTS idx_error_actions_record ON error_actions (training_record_id)",
            "CREATE INDEX IF NOT EXISTS idx_comp_actions_record ON compensation_actions (training_record_id)",
            "CREATE INDEX IF NOT EXISTS idx_feedback_record ON feedback_records (training_record_id)",
            "CREATE INDEX IF NOT EXISTS idx_doctor_interventions_target_time ON doctor_interventions (target_user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_doctor_interventions_record_time ON doctor_interventions (training_record_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_doctor_links_doctor_patient ON doctor_patient_links (doctor_user_id, patient_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_target_time ON audit_logs (target_user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_backup_history_target_time ON backup_history (target_user_id, created_at DESC)",
        ]
        conn = self.get_connection()
        cur = conn.cursor()
        for statement in index_statements:
            cur.execute(statement)
        conn.commit()
        conn.close()

    @staticmethod
    def _now_text() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def prune_audit_logs(self) -> None:
        retention_days = max(1, int(self.config.audit_retention_days or 90))
        cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
        self.execute("DELETE FROM audit_logs WHERE created_at < ?", (cutoff,))

    @staticmethod
    def _hash_password(password: str, salt_hex: str | None = None, iterations: int = 260000) -> str:
        salt = salt_hex or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations)
        return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, stored: str) -> bool:
        if not stored:
            return False
        if stored.startswith("pbkdf2_sha256$"):
            try:
                _, iter_s, salt, expected = stored.split("$", 3)
                digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iter_s)).hex()
                return hmac.compare_digest(digest, expected)
            except Exception:
                return False
        return hmac.compare_digest(password, stored)

    @staticmethod
    def _strip_secret_fields(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not user:
            return None
        data = dict(user)
        data.pop("password", None)
        return data

    @staticmethod
    def _json_dumps(data: Any) -> str:
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _normalize_db_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value

    def _dictify_row(self, cursor, row) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        if isinstance(row, sqlite3.Row):
            return dict(row)
        if isinstance(row, dict):
            return row
        columns = [col[0] for col in cursor.description] if cursor.description else []
        return {col: value for col, value in zip(columns, row)}

    def _dictify_rows(self, cursor, rows) -> List[Dict[str, Any]]:
        return [self._dictify_row(cursor, row) for row in rows if row is not None]

    def _fetch_one_raw(self, query: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(self._adapt_query(query), tuple(self._normalize_db_value(v) for v in params))
        row = cur.fetchone()
        result = self._dictify_row(cur, row)
        conn.close()
        return result

    def _fetch_all_raw(self, query: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(self._adapt_query(query), tuple(self._normalize_db_value(v) for v in params))
        rows = cur.fetchall()
        result = self._dictify_rows(cur, rows)
        conn.close()
        return result

    def _execute_raw(self, query: str, params: Sequence[Any] = ()) -> int:
        conn = self.get_connection()
        cur = conn.cursor()
        sql = self._adapt_query(query)
        lower_sql = sql.lstrip().lower()
        is_insert = lower_sql.startswith("insert")
        if self.backend == "postgres" and is_insert and " returning " not in lower_sql:
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        cur.execute(sql, tuple(self._normalize_db_value(v) for v in params))
        if self.backend == "postgres" and is_insert:
            row = cur.fetchone()
            last_id = int(row[0]) if row else 0
        else:
            last_id = int(getattr(cur, "lastrowid", 0) or 0)
        conn.commit()
        conn.close()
        return last_id

    def _execute_many_raw(self, query: str, params_list: List[tuple]) -> None:
        if not params_list:
            return
        conn = self.get_connection()
        cur = conn.cursor()
        normalized = [tuple(self._normalize_db_value(v) for v in row) for row in params_list]
        cur.executemany(self._adapt_query(query), normalized)
        conn.commit()
        conn.close()

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        return self._fetch_one_raw(query, params)

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        return self._fetch_all_raw(query, params)

    def execute(self, query: str, params: tuple = ()) -> int:
        return self._execute_raw(query, params)

    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        self._execute_many_raw(query, params_list)

    def log_audit_event(
        self,
        action_type: str,
        actor_user_id: Optional[int] = None,
        target_user_id: Optional[int] = None,
        entity_type: str = "",
        entity_id: Optional[int] = None,
        success: bool = True,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._execute_raw(
            """
            INSERT INTO audit_logs (
                actor_user_id, target_user_id, action_type, entity_type,
                entity_id, success, client_node, ip_address, detail_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                actor_user_id,
                target_user_id,
                action_type,
                entity_type,
                entity_id,
                1 if success else 0,
                self.config.workstation_id,
                "desktop-client",
                self._json_dumps(detail or {}),
                self._now_text(),
            ),
        )

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self._strip_secret_fields(self.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,)))

    def get_backup_history(self, target_user_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
        if target_user_id is None:
            return self.fetch_all(
                "SELECT * FROM backup_history ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        return self.fetch_all(
            "SELECT * FROM backup_history WHERE target_user_id = ? ORDER BY id DESC LIMIT ?",
            (target_user_id, limit),
        )

    def get_audit_logs(
        self,
        actor_user_id: Optional[int] = None,
        target_user_id: Optional[int] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if actor_user_id is not None and target_user_id is not None:
            return self.fetch_all(
                """
                SELECT * FROM audit_logs
                WHERE actor_user_id = ? OR target_user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (actor_user_id, target_user_id, limit),
            )
        if actor_user_id is not None:
            return self.fetch_all(
                "SELECT * FROM audit_logs WHERE actor_user_id = ? ORDER BY id DESC LIMIT ?",
                (actor_user_id, limit),
            )
        if target_user_id is not None:
            return self.fetch_all(
                "SELECT * FROM audit_logs WHERE target_user_id = ? ORDER BY id DESC LIMIT ?",
                (target_user_id, limit),
            )
        return self.fetch_all("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))

    def initialize_demo_link(self, doctor_user_id: int, patient_user_id: int) -> None:
        existing = self.fetch_one(
            "SELECT id FROM doctor_patient_links WHERE doctor_user_id = ? AND patient_user_id = ?",
            (doctor_user_id, patient_user_id),
        )
        if existing:
            return
        self._execute_raw(
            """
            INSERT INTO doctor_patient_links (doctor_user_id, patient_user_id, created_at)
            VALUES (?, ?, ?)
            """,
            (doctor_user_id, patient_user_id, self._now_text()),
        )

    def seed_demo_data(self) -> None:
        now = self._now_text()

        def upsert_user(profile: Dict[str, Any]) -> Dict[str, Any]:
            existing = self.fetch_one("SELECT * FROM users WHERE username = ?", (profile["username"],))
            user_values = (
                profile["full_name"],
                profile.get("gender"),
                profile.get("age"),
                profile.get("height_cm"),
                profile.get("weight_kg"),
                profile.get("injured_part"),
                profile.get("affected_side"),
                profile.get("rehab_stage"),
                profile.get("rehab_goal"),
                profile.get("phone"),
                now,
                profile["username"],
            )
            if existing:
                self._execute_raw(
                    """
                    UPDATE users
                    SET full_name = ?, gender = ?, age = ?, height_cm = ?, weight_kg = ?,
                        injured_part = ?, affected_side = ?, rehab_stage = ?, rehab_goal = ?,
                        phone = ?, updated_at = ?
                    WHERE username = ?
                    """,
                    user_values,
                )
                return self.fetch_one("SELECT * FROM users WHERE username = ?", (profile["username"],))
            user_id = self._execute_raw(
                """
                INSERT INTO users (
                    username, password, role, full_name, gender, age, height_cm, weight_kg,
                    injured_part, affected_side, rehab_stage, rehab_goal, phone, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile["username"],
                    self._hash_password(profile.get("password", "123456")),
                    profile.get("role", "patient"),
                    profile["full_name"],
                    profile.get("gender"),
                    profile.get("age"),
                    profile.get("height_cm"),
                    profile.get("weight_kg"),
                    profile.get("injured_part"),
                    profile.get("affected_side"),
                    profile.get("rehab_stage"),
                    profile.get("rehab_goal"),
                    profile.get("phone"),
                    now,
                    now,
                ),
            )
            return self.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))

        def ensure_rehab_profile(user_id: int, data: Dict[str, Any]) -> None:
            existing = self.fetch_one("SELECT * FROM rehab_profiles WHERE user_id = ?", (user_id,))
            values = (
                data.get("diagnosis"),
                data.get("affected_side"),
                data.get("rehab_stage"),
                int(data.get("pain_level", 2)),
                data.get("rom_goal"),
                data.get("contraindications"),
                data.get("doctor_name", "Dr. Remote"),
                data.get("notes", ""),
                now,
                user_id,
            )
            if existing:
                self._execute_raw(
                    """
                    UPDATE rehab_profiles
                    SET diagnosis = ?, affected_side = ?, rehab_stage = ?, pain_level = ?,
                        rom_goal = ?, contraindications = ?, doctor_name = ?, notes = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    values,
                )
                return
            self._execute_raw(
                """
                INSERT INTO rehab_profiles (
                    diagnosis, affected_side, rehab_stage, pain_level,
                    rom_goal, contraindications, doctor_name, notes, updated_at, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

        def ensure_plan(user_id: int, action_name: str, is_active: bool = False) -> int:
            action = get_action(action_name)
            existing = self.fetch_one(
                "SELECT * FROM training_plans WHERE user_id = ? AND target_action = ? ORDER BY id DESC LIMIT 1",
                (user_id, action.name),
            )
            payload = build_default_plan_payload(action, is_active=1 if is_active else 0)
            if existing:
                plan_id = int(existing["id"])
                self._execute_raw(
                    """
                    UPDATE training_plans
                    SET plan_name = ?, difficulty_level = ?, sets_count = ?, reps_count = ?,
                        duration_minutes = ?, rest_seconds = ?, description = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload["plan_name"],
                        payload["difficulty_level"],
                        payload["sets_count"],
                        payload["reps_count"],
                        payload["duration_minutes"],
                        payload["rest_seconds"],
                        payload["description"],
                        now,
                        plan_id,
                    ),
                )
            else:
                plan_id = self._execute_raw(
                    """
                    INSERT INTO training_plans (
                        user_id, plan_name, target_action, difficulty_level,
                        sets_count, reps_count, duration_minutes, rest_seconds,
                        description, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        payload["plan_name"],
                        payload["target_action"],
                        payload["difficulty_level"],
                        payload["sets_count"],
                        payload["reps_count"],
                        payload["duration_minutes"],
                        payload["rest_seconds"],
                        payload["description"],
                        payload["is_active"],
                        now,
                        now,
                    ),
                )
            active = self.get_active_plan(user_id)
            active_name = active.get("target_action") if active else ""
            if is_active or active_name not in {action.name for action in DEMO_ACTIONS}:
                self._execute_raw("UPDATE training_plans SET is_active = 0, updated_at = ? WHERE user_id = ?", (now, user_id))
                self._execute_raw("UPDATE training_plans SET is_active = 1, updated_at = ? WHERE id = ?", (now, plan_id))
            return int(plan_id)

        def ensure_demo_records(user_id: int, plan_id: int, action_name: str, scores: List[int], pain: int) -> Optional[int]:
            action = get_action(action_name)
            existing = self.fetch_one(
                "SELECT COUNT(*) AS c FROM training_records WHERE user_id = ? AND action_name = ?",
                (user_id, action.name),
            )
            if existing and int(existing.get("c", 0)) > 0:
                latest = self.fetch_one(
                    "SELECT id FROM training_records WHERE user_id = ? AND action_name = ? ORDER BY session_start DESC, id DESC LIMIT 1",
                    (user_id, action.name),
                )
                return int(latest["id"]) if latest else None
            latest_record_id = None
            for index, avg_score in enumerate(scores, start=1):
                start_dt = datetime.now() - timedelta(days=len(scores) - index + 1)
                end_dt = start_dt + timedelta(minutes=action.duration_minutes)
                completion = min(0.98, 0.78 + index * 0.04)
                record_id = self._execute_raw(
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
                        action.name,
                        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        action.duration_minutes * 60,
                        avg_score,
                        completion,
                        max(1, pain - index // 2),
                        f"{action.name} followed the standard demo path. Main focus: {action.focus_text}.",
                        "completed",
                        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
                latest_record_id = int(record_id)
                for frame_idx, delta in enumerate([-2, 0, 2], start=1):
                    frame_score = max(70, min(96, avg_score + delta))
                    self._execute_raw(
                        """
                        INSERT INTO action_scores (
                            training_record_id, frame_index, action_label, accuracy_score,
                            stability_score, range_score, rhythm_score, symmetry_score, total_score, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record_id,
                            frame_idx,
                            action.name,
                            frame_score,
                            max(70, frame_score - 1),
                            max(70, frame_score - 2),
                            min(96, frame_score + 1),
                            max(70, frame_score - 1),
                            frame_score,
                            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                if avg_score < 86:
                    self._execute_raw(
                        """
                        INSERT INTO error_actions (
                            training_record_id, error_type, error_count, severity, suggestion, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record_id,
                            action.common_errors[0],
                            1,
                            "low" if avg_score >= 80 else "medium",
                            action.first_cue,
                            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                if avg_score < 83:
                    self._execute_raw(
                        """
                        INSERT INTO compensation_actions (
                            training_record_id, compensation_type, detected_count, risk_level, suggestion, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record_id,
                            action.compensation_risks[0],
                            1,
                            "low",
                            "Reduce speed and keep the body aligned before increasing range.",
                            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                self._execute_raw(
                    """
                    INSERT INTO feedback_records (
                        training_record_id, feedback_type, feedback_content, source, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        "realtime",
                        f"Keep the standard cue: {action.first_cue}",
                        "Qwen-guided-rule",
                        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
                self._execute_raw(
                    """
                    INSERT INTO doctor_reports (
                        user_id, training_record_id, report_title, report_content,
                        recommendation, created_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        record_id,
                        f"{action.name} Training Report #{index}",
                        f"Average score {avg_score}. The patient is practicing from the standard demo video and shows a controlled trend.",
                        f"Continue {action.plan_name}; monitor {action.focus_text}.",
                        "system",
                        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
            return latest_record_id

        doctor = upsert_user(
            {
                "username": "dr_remote",
                "password": "123456",
                "role": "doctor",
                "full_name": "Dr. Remote",
                "gender": "Female",
                "age": 38,
                "phone": "13900000000",
            }
        )
        doctor_id = int(doctor["id"]) if doctor else 0
        demo_patients = [
            {
                "username": "admin",
                "password": "123456",
                "role": "patient",
                "full_name": "Alex Zhang",
                "gender": "Male",
                "age": 23,
                "height_cm": 176,
                "weight_kg": 72,
                "injured_part": "Left knee",
                "affected_side": "Left",
                "rehab_stage": "Mid recovery stage",
                "rehab_goal": "Improve hip-knee coordination and lower-limb stability",
                "phone": "13800000000",
                "primary_action": DEFAULT_ACTION_NAME,
                "scores": [78, 82, 85, 88],
                "profile": {
                    "diagnosis": "Post-operative rehabilitation after left knee surgery",
                    "affected_side": "Left",
                    "rehab_stage": "Mid recovery stage",
                    "pain_level": 3,
                    "rom_goal": "Practice hip-knee flexion with stable trunk and controlled return",
                    "contraindications": "Avoid high-impact training",
                    "doctor_name": "Dr. Remote",
                    "notes": "Demo patient for Hip and Knee Flexion video-guided training.",
                },
            },
            {
                "username": "patient_li",
                "password": "123456",
                "role": "patient",
                "full_name": "Wei Li",
                "gender": "Male",
                "age": 56,
                "height_cm": 172,
                "weight_kg": 78,
                "injured_part": "Right knee",
                "affected_side": "Right",
                "rehab_stage": "Early recovery stage",
                "rehab_goal": "Recover terminal knee extension and toe-lift control",
                "phone": "13800000001",
                "primary_action": "Knee Extension with Toe Lift",
                "scores": [75, 79, 82, 84],
                "profile": {
                    "diagnosis": "Right knee stiffness after conservative treatment",
                    "affected_side": "Right",
                    "rehab_stage": "Early recovery stage",
                    "pain_level": 4,
                    "rom_goal": "Improve terminal knee extension and ankle dorsiflexion control",
                    "contraindications": "Stop if sharp knee pain appears",
                    "doctor_name": "Dr. Remote",
                    "notes": "Needs slower return and clearer toe-lift hold.",
                },
            },
            {
                "username": "patient_wang",
                "password": "123456",
                "role": "patient",
                "full_name": "Nora Wang",
                "gender": "Female",
                "age": 45,
                "height_cm": 165,
                "weight_kg": 61,
                "injured_part": "Left hip",
                "affected_side": "Left",
                "rehab_stage": "Strengthening stage",
                "rehab_goal": "Improve hip abductor control and pelvis stability",
                "phone": "13800000002",
                "primary_action": "Lateral Leg Lift",
                "scores": [80, 83, 86, 89],
                "profile": {
                    "diagnosis": "Left hip abductor weakness with mild pelvis instability",
                    "affected_side": "Left",
                    "rehab_stage": "Strengthening stage",
                    "pain_level": 2,
                    "rom_goal": "Lift laterally with pelvis level and no trunk side-lean",
                    "contraindications": "Avoid fast ballistic lateral lifts",
                    "doctor_name": "Dr. Remote",
                    "notes": "Good demo case for comparing pelvis stability before and after cueing.",
                },
            },
            {
                "username": "patient_liu",
                "password": "123456",
                "role": "patient",
                "full_name": "David Liu",
                "gender": "Male",
                "age": 64,
                "height_cm": 170,
                "weight_kg": 74,
                "injured_part": "Left hamstring",
                "affected_side": "Left",
                "rehab_stage": "Balance rebuild stage",
                "rehab_goal": "Improve standing hamstring curl control and balance",
                "phone": "13800000003",
                "primary_action": "Standing Hamstring Curl",
                "scores": [76, 80, 83, 85],
                "profile": {
                    "diagnosis": "Standing knee-flexion control deficit after lower-limb rehab",
                    "affected_side": "Left",
                    "rehab_stage": "Balance rebuild stage",
                    "pain_level": 3,
                    "rom_goal": "Bend knee backward with steady thigh and controlled lowering",
                    "contraindications": "Use support if balance feels unstable",
                    "doctor_name": "Dr. Remote",
                    "notes": "Doctor can demonstrate balance-related intervention and parameter changes.",
                },
            },
        ]

        for patient_payload in demo_patients:
            patient = upsert_user(patient_payload)
            if not patient:
                continue
            patient_id = int(patient["id"])
            if doctor_id:
                self.initialize_demo_link(doctor_id, patient_id)
            ensure_rehab_profile(patient_id, patient_payload["profile"])
            primary_action = get_action(patient_payload["primary_action"])
            active_plan_id = ensure_plan(patient_id, primary_action.name, is_active=True)
            for action in DEMO_ACTIONS:
                ensure_plan(patient_id, action.name, is_active=False)
            latest_record_id = ensure_demo_records(
                patient_id,
                active_plan_id,
                primary_action.name,
                patient_payload.get("scores", [78, 82, 86, 88]),
                int(patient_payload["profile"].get("pain_level", 3)),
            )
            if doctor_id and latest_record_id and patient_payload["username"] in {"admin", "patient_wang"}:
                existing_intervention = self.get_latest_doctor_intervention(
                    viewer_user_id=doctor_id,
                    target_user_id=patient_id,
                    training_record_id=latest_record_id,
                )
                if not existing_intervention:
                    self.save_doctor_intervention(
                        viewer_user_id=doctor_id,
                        target_user_id=patient_id,
                        training_record_id=latest_record_id,
                        review_status="reviewed",
                        decision_type="manual_feedback",
                        note=f"Reviewed standard {primary_action.name} video session. Keep current volume and reinforce cue: {primary_action.first_cue}",
                        override_payload={"focus": primary_action.focus_text, "action": primary_action.name},
                    )

    def login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        username = (username or "").strip()
        user = self.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
        if not user or not self._verify_password(password, str(user.get("password", ""))):
            self.log_audit_event(
                "LOGIN_FAILURE",
                actor_user_id=None,
                target_user_id=None,
                entity_type="user",
                entity_id=int(user["id"]) if user else None,
                success=False,
                detail={"username": username},
            )
            return None
        if not str(user.get("password", "")).startswith("pbkdf2_sha256$"):
            self._execute_raw(
                "UPDATE users SET password = ?, updated_at = ? WHERE id = ?",
                (self._hash_password(password), self._now_text(), int(user["id"])),
            )
            user = self.fetch_one("SELECT * FROM users WHERE id = ?", (int(user["id"]),))
        public_user = self._strip_secret_fields(user)
        self.log_audit_event(
            "LOGIN_SUCCESS",
            actor_user_id=int(user["id"]),
            target_user_id=int(user["id"]),
            entity_type="user",
            entity_id=int(user["id"]),
            success=True,
            detail={"role": user.get("role", "patient")},
        )
        return public_user

    def register_user(self, data: Dict[str, Any]) -> Optional[int]:
        now = self._now_text()
        username = (data.get("username") or "").strip()
        if not username:
            return None
        existing = self.fetch_one("SELECT id FROM users WHERE username = ?", (username,))
        if existing:
            self.log_audit_event(
                "REGISTER_REJECTED",
                success=False,
                entity_type="user",
                detail={"username": username, "reason": "duplicate_username"},
            )
            return None
        user_id = self.execute(
            """
            INSERT INTO users (
                username, password, role, full_name, gender, age, height_cm, weight_kg,
                injured_part, affected_side, rehab_stage, rehab_goal, phone, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                self._hash_password(data.get("password", "123456")),
                data.get("role", "patient"),
                data.get("full_name", username),
                data.get("gender", ""),
                data.get("age"),
                data.get("height_cm"),
                data.get("weight_kg"),
                data.get("injured_part", ""),
                data.get("affected_side", ""),
                data.get("rehab_stage", ""),
                data.get("rehab_goal", ""),
                data.get("phone", ""),
                now,
                now,
            ),
        )
        self.log_audit_event(
            "REGISTER_USER",
            actor_user_id=user_id,
            target_user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            success=True,
            detail={"username": username, "role": data.get("role", "patient")},
        )
        return user_id

    def update_user_basic_info(self, user_id: int, data: Dict[str, Any]) -> None:
        now = self._now_text()
        self.execute(
            """
            UPDATE users
            SET full_name = ?, gender = ?, age = ?, height_cm = ?, weight_kg = ?,
                injured_part = ?, affected_side = ?, rehab_stage = ?, rehab_goal = ?, phone = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                data.get("full_name", ""),
                data.get("gender", ""),
                data.get("age"),
                data.get("height_cm"),
                data.get("weight_kg"),
                data.get("injured_part", ""),
                data.get("affected_side", ""),
                data.get("rehab_stage", ""),
                data.get("rehab_goal", ""),
                data.get("phone", ""),
                now,
                user_id,
            ),
        )
        self.log_audit_event(
            "UPDATE_USER_PROFILE",
            actor_user_id=user_id,
            target_user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            success=True,
        )

    def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.fetch_one("SELECT * FROM rehab_profiles WHERE user_id = ?", (user_id,))

    def save_user_profile(self, user_id: int, data: Dict[str, Any]) -> None:
        now = self._now_text()
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
        self.log_audit_event(
            "SAVE_REHAB_PROFILE",
            actor_user_id=user_id,
            target_user_id=user_id,
            entity_type="rehab_profile",
            entity_id=user_id,
            success=True,
        )

    def get_plans(self, user_id: int) -> List[Dict[str, Any]]:
        return self.fetch_all(
            "SELECT * FROM training_plans WHERE user_id = ? ORDER BY is_active DESC, id DESC",
            (user_id,),
        )

    def get_active_plan(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.fetch_one(
            "SELECT * FROM training_plans WHERE user_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
            (user_id,),
        )

    def create_plan(self, user_id: int, data: Dict[str, Any]) -> int:
        now = self._now_text()
        plan_id = self.execute(
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
                get_action(data.get("target_action", DEFAULT_ACTION_NAME)).name,
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
        self.log_audit_event(
            "CREATE_PLAN",
            actor_user_id=user_id,
            target_user_id=user_id,
            entity_type="training_plan",
            entity_id=plan_id,
            success=True,
        )
        return plan_id

    def activate_plan(self, user_id: int, plan_id: int, reason: str = "Manual plan switch") -> None:
        now = self._now_text()
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
        self.log_audit_event(
            "ACTIVATE_PLAN",
            actor_user_id=user_id,
            target_user_id=user_id,
            entity_type="training_plan",
            entity_id=plan_id,
            success=True,
            detail={"reason": reason},
        )

    def save_training_session(self, user_id: int, plan_id: Optional[int], session_data: Dict[str, Any]) -> int:
        now = self._now_text()
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
                item.get("symmetry_score", 0),
                item["total_score"],
                now,
            )
            for idx, item in enumerate(session_data.get("scores", []), start=1)
        ]
        self.execute_many(
            """
            INSERT INTO action_scores (
                training_record_id, frame_index, action_label, accuracy_score,
                stability_score, range_score, rhythm_score, symmetry_score, total_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        self.execute_many(
            """
            INSERT INTO feedback_records (
                training_record_id, feedback_type, feedback_content,
                source, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            feedback_rows,
        )

        report_id = self.execute(
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
        self.log_audit_event(
            "SAVE_TRAINING_SESSION",
            actor_user_id=user_id,
            target_user_id=user_id,
            entity_type="training_record",
            entity_id=record_id,
            success=True,
            detail={"doctor_report_id": report_id, "plan_id": plan_id},
        )
        return record_id

    def get_latest_record(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.fetch_one(
            "SELECT * FROM training_records WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )

    def get_records(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        return self.fetch_all(
            "SELECT * FROM training_records WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )

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
        interventions = self.fetch_all(
            "SELECT * FROM doctor_interventions WHERE training_record_id = ? ORDER BY id DESC",
            (record_id,),
        )
        return {
            "record": record,
            "scores": scores,
            "errors": errors,
            "compensations": compensations,
            "feedbacks": feedbacks,
            "report": report,
            "interventions": interventions,
        }

    def get_plan_adjustments(self, user_id: int) -> List[Dict[str, Any]]:
        return self.fetch_all(
            "SELECT * FROM plan_adjustment_history WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )

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

    def get_score_trend(self, user_id: int, limit: int = 12) -> List[Dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT id, action_name, session_end, avg_score, completion_rate, pain_feedback
            FROM training_records
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows.reverse()
        return rows

    def get_error_distribution(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT e.error_type AS label, SUM(e.error_count) AS count
            FROM error_actions e
            JOIN training_records r ON e.training_record_id = r.id
            WHERE r.user_id = ?
            GROUP BY e.error_type
            ORDER BY count DESC
            LIMIT ?
            """,
            (user_id, limit),
        )

    def get_compensation_distribution(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT c.compensation_type AS label, SUM(c.detected_count) AS count
            FROM compensation_actions c
            JOIN training_records r ON c.training_record_id = r.id
            WHERE r.user_id = ?
            GROUP BY c.compensation_type
            ORDER BY count DESC
            LIMIT ?
            """,
            (user_id, limit),
        )

    def build_adaptive_plan_suggestion(self, user_id: int) -> Dict[str, Any]:
        active_plan = self.get_active_plan(user_id)
        records = self.get_records(user_id, limit=5)
        if not active_plan:
            return {"basis": "No active plan available.", "decision": "Keep current plan", "new_plan": None, "diff": []}
        if not records:
            return {
                "basis": "No historical training record. Keep the baseline plan first.",
                "decision": "Keep current plan",
                "new_plan": active_plan,
                "current_plan": active_plan,
                "diff": [],
            }

        avg_score = sum((r["avg_score"] or 0) for r in records) / len(records)
        avg_completion = sum((r["completion_rate"] or 0) for r in records) / len(records)
        avg_pain = sum((r["pain_feedback"] or 0) for r in records) / len(records)
        err_dist = self.get_error_distribution(user_id, limit=1)
        comp_dist = self.get_compensation_distribution(user_id, limit=1)
        top_error = err_dist[0]["label"] if err_dist else "none"
        top_comp = comp_dist[0]["label"] if comp_dist else "none"

        decision = "Keep current plan"
        new_plan = dict(active_plan)
        new_plan["is_active"] = 0
        if avg_score >= 88 and avg_completion >= 0.9 and avg_pain <= 3:
            decision = "Increase hold time"
            new_plan["duration_minutes"] = min(60, int(active_plan["duration_minutes"]) + 3)
            new_plan["reps_count"] = min(30, int(active_plan["reps_count"]) + 2)
            new_plan["difficulty_level"] = "High" if active_plan["difficulty_level"] == "Medium" else active_plan["difficulty_level"]
        elif avg_score < 78 or avg_completion < 0.7 or avg_pain >= 5:
            decision = "Lower difficulty"
            new_plan["sets_count"] = max(2, int(active_plan["sets_count"]) - 1)
            new_plan["reps_count"] = max(6, int(active_plan["reps_count"]) - 2)
            new_plan["difficulty_level"] = "Low"
            if "asymmetry" in top_error.lower():
                decision = "Add unilateral training"
                new_plan["target_action"] = f"{active_plan['target_action']} (Unilateral corrective)"
        elif "trunk" in top_error.lower() or "compensation" in top_comp.lower():
            decision = "Reinforce current action cues"
            action = get_action(active_plan["target_action"])
            new_plan["target_action"] = action.name
            new_plan["difficulty_level"] = "Low"
            new_plan["description"] = (
                f"{active_plan.get('description', '')} Reinforce standard cue: {action.first_cue}"
            ).strip()

        basis = (
            f"Recent 5 sessions: avg score {round(avg_score, 2)}, "
            f"avg completion {round(avg_completion * 100, 2)}%, avg pain {round(avg_pain, 2)}. "
            f"Top error: {top_error}; top compensation: {top_comp}."
        )
        diff = []
        for key, title in [
            ("target_action", "Action"),
            ("difficulty_level", "Difficulty"),
            ("sets_count", "Sets"),
            ("reps_count", "Reps/Set"),
            ("duration_minutes", "Duration (min)"),
            ("rest_seconds", "Rest (sec)"),
        ]:
            old_value = active_plan.get(key)
            new_value = new_plan.get(key)
            if old_value != new_value:
                diff.append(f"{title}: {old_value} -> {new_value}")

        return {
            "basis": basis,
            "decision": decision,
            "new_plan": new_plan,
            "current_plan": active_plan,
            "diff": diff,
        }

    def apply_adaptive_plan_suggestion(self, user_id: int, suggestion: Dict[str, Any]) -> Optional[int]:
        new_plan = suggestion.get("new_plan")
        current = suggestion.get("current_plan")
        if not new_plan or not current:
            return None
        now = self._now_text()
        new_id = self.create_plan(
            user_id,
            {
                "plan_name": f"{current['plan_name']} - Adaptive",
                "target_action": new_plan.get("target_action", current["target_action"]),
                "difficulty_level": new_plan.get("difficulty_level", current["difficulty_level"]),
                "sets_count": int(new_plan.get("sets_count", current["sets_count"])),
                "reps_count": int(new_plan.get("reps_count", current["reps_count"])),
                "duration_minutes": int(new_plan.get("duration_minutes", current["duration_minutes"])),
                "rest_seconds": int(new_plan.get("rest_seconds", current["rest_seconds"])),
                "description": f"Auto-adjusted from recent performance. Basis: {suggestion.get('basis', '')}",
                "is_active": 0,
            },
        )
        self.activate_plan(user_id, new_id, reason=f"Auto-adjustment: {suggestion.get('decision', 'Keep current plan')}")
        self.execute(
            """
            INSERT INTO plan_adjustment_history (
                user_id, old_plan_id, new_plan_id, adjustment_reason,
                adjustment_detail, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                current["id"],
                new_id,
                f"Adaptive adjustment: {suggestion.get('decision', 'Keep current plan')}",
                "\n".join(suggestion.get("diff", [])) or suggestion.get("basis", ""),
                now,
            ),
        )
        self.log_audit_event(
            "APPLY_ADAPTIVE_PLAN",
            actor_user_id=user_id,
            target_user_id=user_id,
            entity_type="training_plan",
            entity_id=new_id,
            success=True,
        )
        return new_id

    def get_doctor_interventions(
        self,
        viewer_user_id: int,
        target_user_id: Optional[int] = None,
        training_record_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        resolved_user_id = self._resolve_target_user(viewer_user_id, target_user_id)
        if resolved_user_id is None:
            return []
        if training_record_id is not None:
            return self.fetch_all(
                """
                SELECT * FROM doctor_interventions
                WHERE target_user_id = ? AND training_record_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (resolved_user_id, training_record_id, limit),
            )
        return self.fetch_all(
            """
            SELECT * FROM doctor_interventions
            WHERE target_user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (resolved_user_id, limit),
        )

    def get_latest_doctor_intervention(
        self,
        viewer_user_id: int,
        target_user_id: Optional[int] = None,
        training_record_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        rows = self.get_doctor_interventions(
            viewer_user_id=viewer_user_id,
            target_user_id=target_user_id,
            training_record_id=training_record_id,
            limit=1,
        )
        return rows[0] if rows else None

    def save_doctor_intervention(
        self,
        viewer_user_id: int,
        target_user_id: int,
        training_record_id: Optional[int],
        review_status: str,
        decision_type: str,
        note: str = "",
        override_payload: Optional[Dict[str, Any]] = None,
        old_plan_id: Optional[int] = None,
        new_plan_id: Optional[int] = None,
    ) -> int:
        viewer = self.fetch_one("SELECT * FROM users WHERE id = ?", (viewer_user_id,))
        if not viewer or viewer.get("role") != "doctor":
            raise PermissionError("Only doctor accounts can create interventions.")
        resolved_user_id = self._resolve_target_user(viewer_user_id, target_user_id)
        if resolved_user_id is None:
            raise ValueError("No accessible patient is available.")
        intervention_id = self.execute(
            """
            INSERT INTO doctor_interventions (
                actor_user_id, target_user_id, training_record_id, review_status,
                decision_type, note, override_json, old_plan_id, new_plan_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                viewer_user_id,
                resolved_user_id,
                training_record_id,
                review_status,
                decision_type,
                note.strip(),
                self._json_dumps(override_payload or {}),
                old_plan_id,
                new_plan_id,
                self._now_text(),
            ),
        )
        self.log_audit_event(
            "SAVE_DOCTOR_INTERVENTION",
            actor_user_id=viewer_user_id,
            target_user_id=resolved_user_id,
            entity_type="doctor_intervention",
            entity_id=intervention_id,
            success=True,
            detail={
                "training_record_id": training_record_id,
                "review_status": review_status,
                "decision_type": decision_type,
                "old_plan_id": old_plan_id,
                "new_plan_id": new_plan_id,
            },
        )
        return intervention_id

    def apply_doctor_plan_update(
        self,
        viewer_user_id: int,
        target_user_id: int,
        plan_data: Dict[str, Any],
        reason: str,
        note: str = "",
        training_record_id: Optional[int] = None,
    ) -> int:
        viewer = self.fetch_one("SELECT * FROM users WHERE id = ?", (viewer_user_id,))
        if not viewer or viewer.get("role") != "doctor":
            raise PermissionError("Only doctor accounts can adjust patient plans.")
        resolved_user_id = self._resolve_target_user(viewer_user_id, target_user_id)
        if resolved_user_id is None:
            raise ValueError("No accessible patient is available.")

        current_plan = self.get_active_plan(resolved_user_id)
        now = self._now_text()
        new_plan_id = self.execute(
            """
            INSERT INTO training_plans (
                user_id, plan_name, target_action, difficulty_level,
                sets_count, reps_count, duration_minutes, rest_seconds,
                description, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_user_id,
                plan_data.get("plan_name", "Doctor Adjusted Plan"),
                get_action(plan_data.get("target_action", DEFAULT_ACTION_NAME)).name,
                plan_data.get("difficulty_level", "Low"),
                int(plan_data.get("sets_count", 3)),
                int(plan_data.get("reps_count", 10)),
                int(plan_data.get("duration_minutes", 15)),
                int(plan_data.get("rest_seconds", 30)),
                plan_data.get("description", ""),
                0,
                now,
                now,
            ),
        )

        self.execute("UPDATE training_plans SET is_active = 0, updated_at = ? WHERE user_id = ?", (now, resolved_user_id))
        self.execute("UPDATE training_plans SET is_active = 1, updated_at = ? WHERE id = ?", (now, new_plan_id))
        self.execute(
            """
            INSERT INTO plan_adjustment_history (
                user_id, old_plan_id, new_plan_id, adjustment_reason,
                adjustment_detail, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_user_id,
                current_plan["id"] if current_plan else None,
                new_plan_id,
                reason,
                note.strip() or "Doctor adjusted the training parameters and activated the new plan.",
                now,
            ),
        )
        self.log_audit_event(
            "DOCTOR_APPLY_PLAN_UPDATE",
            actor_user_id=viewer_user_id,
            target_user_id=resolved_user_id,
            entity_type="training_plan",
            entity_id=new_plan_id,
            success=True,
            detail={
                "reason": reason,
                "training_record_id": training_record_id,
                "old_plan_id": current_plan["id"] if current_plan else None,
            },
        )
        self.save_doctor_intervention(
            viewer_user_id=viewer_user_id,
            target_user_id=resolved_user_id,
            training_record_id=training_record_id,
            review_status="adjusted",
            decision_type="plan_updated",
            note=note or reason,
            override_payload=plan_data,
            old_plan_id=current_plan["id"] if current_plan else None,
            new_plan_id=new_plan_id,
        )
        return new_plan_id

    def get_doctor_worklist(self, doctor_user_id: int) -> List[Dict[str, Any]]:
        patients = self.get_patient_list_for_doctor(doctor_user_id)
        worklist: List[Dict[str, Any]] = []
        for patient in patients:
            patient_id = int(patient["id"])
            latest = self.get_latest_record(patient_id)
            summary = self.get_analysis_summary(patient_id)
            errors = self.get_error_distribution(patient_id, limit=1)
            comps = self.get_compensation_distribution(patient_id, limit=1)
            latest_review = self.get_latest_doctor_intervention(
                viewer_user_id=doctor_user_id,
                target_user_id=patient_id,
                training_record_id=int(latest["id"]) if latest else None,
            )

            risk_level = "low"
            latest_score = float(latest.get("avg_score", 0) or 0) if latest else 0.0
            avg_pain = float(summary.get("avg_pain", 0) or 0)
            if latest_score < 75 or avg_pain >= 5:
                risk_level = "high"
            elif latest_score < 85 or errors or comps:
                risk_level = "medium"

            needs_review = bool(latest) and not latest_review
            top_issue = errors[0]["label"] if errors else (comps[0]["label"] if comps else "Stable")
            worklist.append(
                {
                    **patient,
                    "latest_record_id": int(latest["id"]) if latest else None,
                    "latest_score": round(latest_score, 2) if latest else None,
                    "completion_rate": round((latest.get("completion_rate", 0) or 0) * 100, 2) if latest else None,
                    "trend": summary.get("trend", "No data"),
                    "risk_level": risk_level,
                    "needs_review": needs_review,
                    "top_issue": top_issue,
                    "latest_review_status": latest_review.get("review_status") if latest_review else "pending",
                }
            )
        return worklist

    def get_patient_list_for_doctor(self, doctor_user_id: int) -> List[Dict[str, Any]]:
        doctor = self.fetch_one("SELECT * FROM users WHERE id = ?", (doctor_user_id,))
        if not doctor or doctor.get("role") != "doctor":
            return []
        rows = self.fetch_all(
            """
            SELECT u.id, u.full_name, u.rehab_stage, u.injured_part, u.affected_side
            FROM doctor_patient_links l
            JOIN users u ON l.patient_user_id = u.id
            WHERE l.doctor_user_id = ?
            ORDER BY u.full_name
            """,
            (doctor_user_id,),
        )
        return rows

    def _resolve_target_user(self, viewer_user_id: int, target_user_id: Optional[int] = None) -> Optional[int]:
        viewer = self.fetch_one("SELECT * FROM users WHERE id = ?", (viewer_user_id,))
        if not viewer:
            return None
        if viewer.get("role") == "doctor":
            patients = self.get_patient_list_for_doctor(viewer_user_id)
            patient_ids = [int(p["id"]) for p in patients]
            if not patient_ids:
                return None
            resolved = int(target_user_id) if target_user_id else patient_ids[0]
            if resolved not in patient_ids:
                raise PermissionError("Doctor is not authorized to access this patient.")
            return resolved
        return int(viewer_user_id)

    def get_doctor_dashboard(self, viewer_user_id: int, target_user_id: Optional[int] = None) -> Dict[str, Any]:
        viewer = self.get_user_by_id(viewer_user_id)
        patients = self.get_patient_list_for_doctor(viewer_user_id) if viewer and viewer.get("role") == "doctor" else []
        try:
            resolved_user_id = self._resolve_target_user(viewer_user_id, target_user_id)
        except PermissionError:
            self.log_audit_event(
                "DOCTOR_ACCESS_DENIED",
                actor_user_id=viewer_user_id,
                target_user_id=target_user_id,
                entity_type="patient_record",
                success=False,
            )
            return {
                "viewer": viewer,
                "patients": patients,
                "selected_user_id": None,
                "user": None,
                "profile": None,
                "recent_records": [],
                "summary": {},
                "errors": [],
                "compensations": [],
                "recommendation": "Access denied.",
            }
        if resolved_user_id is None:
            return {
                "viewer": viewer,
                "patients": patients,
                "selected_user_id": None,
                "user": None,
                "profile": None,
                "recent_records": [],
                "summary": {},
                "errors": [],
                "compensations": [],
                "recommendation": "No linked patient available.",
            }

        user = self.get_user_by_id(resolved_user_id)
        profile = self.get_user_profile(resolved_user_id)
        records = self.get_records(resolved_user_id, limit=10)
        summary = self.get_analysis_summary(resolved_user_id)
        errors = self.get_error_distribution(resolved_user_id, limit=5)
        compensations = self.get_compensation_distribution(resolved_user_id, limit=5)
        active_plan = self.get_active_plan(resolved_user_id)
        adaptive = self.build_adaptive_plan_suggestion(resolved_user_id)
        latest_record = records[0] if records else None
        latest_record_details = self.get_record_details(int(latest_record["id"])) if latest_record else {"record": None, "scores": [], "errors": [], "compensations": [], "feedbacks": [], "report": None, "interventions": []}
        latest_intervention = self.get_latest_doctor_intervention(
            viewer_user_id=viewer_user_id,
            target_user_id=resolved_user_id,
            training_record_id=int(latest_record["id"]) if latest_record else None,
        )
        interventions = self.get_doctor_interventions(
            viewer_user_id=viewer_user_id,
            target_user_id=resolved_user_id,
            limit=8,
        )
        recommendation = "Keep current plan and monitor weekly."
        if summary.get("trend") == "Declining" or summary.get("avg_score", 0) < 78:
            recommendation = "Recommend reducing intensity and reassessing movement pattern."
        elif summary.get("avg_score", 0) >= 88 and summary.get("avg_completion", 0) >= 90:
            recommendation = "Recommend controlled progression in training difficulty."
        self.log_audit_event(
            "VIEW_DOCTOR_DASHBOARD",
            actor_user_id=viewer_user_id,
            target_user_id=resolved_user_id,
            entity_type="doctor_dashboard",
            entity_id=resolved_user_id,
            success=True,
        )
        return {
            "viewer": viewer,
            "patients": patients,
            "selected_user_id": resolved_user_id,
            "user": user,
            "profile": profile,
            "recent_records": records,
            "summary": summary,
            "errors": errors,
            "compensations": compensations,
            "active_plan": active_plan,
            "adaptive": adaptive,
            "latest_record_details": latest_record_details,
            "latest_intervention": latest_intervention,
            "interventions": interventions,
            "worklist": self.get_doctor_worklist(viewer_user_id) if viewer and viewer.get("role") == "doctor" else [],
            "recommendation": recommendation,
        }

    def get_security_overview(self, viewer_user_id: int, target_user_id: Optional[int] = None) -> Dict[str, Any]:
        resolved_user_id = self._resolve_target_user(viewer_user_id, target_user_id)
        if resolved_user_id is None:
            return {
                "storage_backend": self.storage_label(),
                "ssl_mode": self.config.postgres_ssl_mode if self.is_cloud_backend() else "n/a",
                "ai_policy": "Local YOLO + Local/edge Qwen",
                "remote_doctor_access": bool(self.config.remote_doctor_access_enabled),
                "backup_count": 0,
                "latest_backup_at": "-",
                "audit_event_count": 0,
                "latest_audit_action": "-",
            }
        backup_rows = self.get_backup_history(target_user_id=resolved_user_id, limit=5)
        audit_rows = self.get_audit_logs(target_user_id=resolved_user_id, limit=8)
        return {
            "storage_backend": self.storage_label(),
            "ssl_mode": self.config.postgres_ssl_mode if self.is_cloud_backend() else "local-only",
            "ai_policy": "Local YOLO + Local/edge Qwen",
            "remote_doctor_access": bool(self.config.remote_doctor_access_enabled),
            "backup_count": len(backup_rows),
            "latest_backup_at": backup_rows[0]["created_at"] if backup_rows else "-",
            "audit_event_count": len(audit_rows),
            "latest_audit_action": audit_rows[0]["action_type"] if audit_rows else "-",
        }

    def build_report_export_payload(
        self,
        viewer_user_id: int,
        target_user_id: Optional[int] = None,
        training_record_id: Optional[int] = None,
        include_full_history: bool = False,
    ) -> Dict[str, Any]:
        resolved_user_id = self._resolve_target_user(viewer_user_id, target_user_id)
        if resolved_user_id is None:
            raise ValueError("No accessible patient data is available for export.")
        patient = self.get_user_by_id(resolved_user_id)
        profile = self.get_user_profile(resolved_user_id)
        active_plan = self.get_active_plan(resolved_user_id)
        summary = self.get_analysis_summary(resolved_user_id)
        if training_record_id:
            selected_record = self.fetch_one(
                "SELECT * FROM training_records WHERE id = ? AND user_id = ?",
                (training_record_id, resolved_user_id),
            )
        else:
            selected_record = self.get_latest_record(resolved_user_id)
        details = self.get_record_details(int(selected_record["id"])) if selected_record else {"record": None, "scores": [], "errors": [], "compensations": [], "feedbacks": [], "report": None}
        payload = {
            "generated_at": self._now_text(),
            "storage_backend": self.storage_label(),
            "viewer_user_id": viewer_user_id,
            "target_user_id": resolved_user_id,
            "security_overview": self.get_security_overview(viewer_user_id, resolved_user_id),
            "patient": patient,
            "profile": profile,
            "active_plan": active_plan,
            "analysis_summary": summary,
            "selected_record": details.get("record"),
            "record_details": details,
            "latest_intervention": self.get_latest_doctor_intervention(
                viewer_user_id=viewer_user_id,
                target_user_id=resolved_user_id,
                training_record_id=int(selected_record["id"]) if selected_record else None,
            ),
        }
        if include_full_history:
            payload["history_records"] = self.get_records(resolved_user_id, limit=50)
            payload["plan_adjustments"] = self.get_plan_adjustments(resolved_user_id)
            payload["doctor_interventions"] = self.get_doctor_interventions(
                viewer_user_id=viewer_user_id,
                target_user_id=resolved_user_id,
                limit=30,
            )
        return payload

    def record_export_event(
        self,
        viewer_user_id: int,
        target_user_id: int,
        export_format: str,
        path: str,
        success: bool = True,
    ) -> None:
        self.log_audit_event(
            "EXPORT_DOCTOR_REPORT",
            actor_user_id=viewer_user_id,
            target_user_id=target_user_id,
            entity_type=f"report_{export_format}",
            success=success,
            detail={"path": path, "format": export_format},
        )

    def create_backup_snapshot(
        self,
        requester_user_id: int,
        target_user_id: Optional[int] = None,
        destination_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = self.build_report_export_payload(
            viewer_user_id=requester_user_id,
            target_user_id=target_user_id,
            include_full_history=True,
        )
        backup_dir = destination_dir or self.config.backup_dir
        os.makedirs(backup_dir, exist_ok=True)
        target_id = int(payload["target_user_id"])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"rehab_backup_user_{target_id}_{timestamp}.json.gz")
        content = self._json_dumps(payload)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with gzip.open(backup_path, "wt", encoding="utf-8") as f:
            f.write(content)
        self.execute(
            """
            INSERT INTO backup_history (
                requester_user_id, target_user_id, backup_path, backup_hash, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (requester_user_id, target_id, backup_path, digest, self._now_text()),
        )
        self.log_audit_event(
            "CREATE_BACKUP",
            actor_user_id=requester_user_id,
            target_user_id=target_id,
            entity_type="backup_snapshot",
            success=True,
            detail={"path": backup_path, "sha256": digest},
        )
        return {"path": backup_path, "sha256": digest}
