"""MySQL persistence for completed exercise sessions."""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class DatabaseSettings:
    enabled: bool
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        return cls(
            enabled=os.environ.get("DB_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "vr_fitness"),
            charset=os.environ.get("DB_CHARSET", "utf8mb4"),
        )


class ExerciseSessionRepository:
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self.available = False
        self.last_error: Optional[str] = None
        self._driver = None

        if not settings.enabled:
            self.last_error = "DB_ENABLED=false"
            return

        try:
            import pymysql

            self._driver = pymysql
            self.init_schema()
            self.available = True
        except Exception as exc:
            self.last_error = str(exc)
            print(f"[DB] Disabled: {self.last_error}")

    def _try_reconnect(self) -> bool:
        if not self.settings.enabled:
            self.last_error = "DB_ENABLED=false"
            return False

        try:
            if self._driver is None:
                import pymysql

                self._driver = pymysql
            self.init_schema()
            self.available = True
            self.last_error = None
            return True
        except Exception as exc:
            self.available = False
            self.last_error = str(exc)
            return False

    def _connect(self, include_database: bool = True):
        kwargs = {
            "host": self.settings.host,
            "port": self.settings.port,
            "user": self.settings.user,
            "password": self.settings.password,
            "charset": self.settings.charset,
            "autocommit": True,
            "cursorclass": self._driver.cursors.DictCursor,
        }
        if include_database:
            kwargs["database"] = self.settings.database
        return self._driver.connect(**kwargs)

    def init_schema(self) -> None:
        with self._connect(include_database=False) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.settings.database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )

        with self._connect(include_database=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS exercise_sessions (
                        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        session_id VARCHAR(64) NOT NULL UNIQUE,
                        user_id VARCHAR(64) NOT NULL,
                        exercise_type VARCHAR(64) NOT NULL,
                        started_at DATETIME(6) NOT NULL,
                        ended_at DATETIME(6) NOT NULL,
                        duration_ms INT UNSIGNED NOT NULL,
                        frame_count INT UNSIGNED NOT NULL,
                        avg_score FLOAT NOT NULL,
                        best_score FLOAT NOT NULL,
                        worst_score FLOAT NOT NULL,
                        final_label VARCHAR(255) NOT NULL,
                        summary_json JSON NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_started (user_id, started_at),
                        INDEX idx_exercise_started (exercise_type, started_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )

    def health(self) -> Dict[str, Any]:
        if not self.available:
            if self._try_reconnect():
                return {"enabled": True, "available": True, "database": self.settings.database}
            return {"enabled": self.settings.enabled, "available": False, "error": self.last_error}

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS ok")
                    cur.fetchone()
            return {"enabled": True, "available": True, "database": self.settings.database}
        except Exception as exc:
            self.last_error = str(exc)
            self.available = False
            return {"enabled": True, "available": False, "error": self.last_error}

    def save_session(self, summary: Dict[str, Any]) -> bool:
        if not self.available:
            if not self._try_reconnect():
                print(f"[DB] Skipping save; database unavailable: {self.last_error}")
                return False

        try:
            started_at = _to_mysql_datetime(summary["started_at"])
            ended_at = _to_mysql_datetime(summary["ended_at"])
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO exercise_sessions (
                            session_id, user_id, exercise_type, started_at, ended_at,
                            duration_ms, frame_count, avg_score, best_score, worst_score,
                            final_label, summary_json
                        ) VALUES (
                            %(session_id)s, %(user_id)s, %(exercise_type)s, %(started_at)s, %(ended_at)s,
                            %(duration_ms)s, %(frame_count)s, %(avg_score)s, %(best_score)s, %(worst_score)s,
                            %(final_label)s, %(summary_json)s
                        )
                        ON DUPLICATE KEY UPDATE
                            ended_at = VALUES(ended_at),
                            duration_ms = VALUES(duration_ms),
                            frame_count = VALUES(frame_count),
                            avg_score = VALUES(avg_score),
                            best_score = VALUES(best_score),
                            worst_score = VALUES(worst_score),
                            final_label = VALUES(final_label),
                            summary_json = VALUES(summary_json)
                        """,
                        {
                            "session_id": summary["session_id"],
                            "user_id": summary["user_id"],
                            "exercise_type": summary["exercise_type"],
                            "started_at": started_at,
                            "ended_at": ended_at,
                            "duration_ms": int(summary["duration_ms"]),
                            "frame_count": int(summary["frame_count"]),
                            "avg_score": float(summary["avg_score"]),
                            "best_score": float(summary["best_score"]),
                            "worst_score": float(summary["worst_score"]),
                            "final_label": summary["final_label"],
                            "summary_json": json.dumps(summary, ensure_ascii=False, default=str),
                        },
                    )
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self.available = False
            print(f"[DB] Save failed: {self.last_error}")
            return False


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_mysql_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
    return str(value)
