import sqlite3
import os
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

class StateDatabase:
    """Thread-safe SQLite manager for tracking processed files and resuming operations."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_records (
                        rel_path TEXT PRIMARY KEY,
                        source_path TEXT,
                        output_path TEXT,
                        media_type TEXT,
                        source_mtime REAL,
                        original_size INTEGER,
                        compressed_size INTEGER,
                        status TEXT,
                        error_message TEXT,
                        duration_sec REAL,
                        processed_at TEXT
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON processed_records(status);")

    def is_already_processed(self, rel_path: str, source_size: int, source_mtime: float) -> bool:
        """Returns True if the file has been successfully processed and unchanged."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT original_size, source_mtime, status FROM processed_records WHERE rel_path = ?",
                    (rel_path,)
                )
                row = cursor.fetchone()
                if not row:
                    return False
                orig_size, mtime, status = row
                # If it succeeded or was intentionally kept as original because it was smaller
                if status in ("SUCCESS", "SKIPPED_LARGER", "COPIED"):
                    if orig_size == source_size and abs(mtime - source_mtime) < 1.0:
                        return True
                return False

    def record_result(
        self,
        rel_path: str,
        source_path: str,
        output_path: str,
        media_type: str,
        source_mtime: float,
        original_size: int,
        compressed_size: int,
        status: str,
        error_message: Optional[str] = None,
        duration_sec: float = 0.0
    ):
        with self._lock:
            with self._get_connection() as conn:
                now_str = datetime.now().isoformat()
                conn.execute("""
                    INSERT OR REPLACE INTO processed_records (
                        rel_path, source_path, output_path, media_type,
                        source_mtime, original_size, compressed_size,
                        status, error_message, duration_sec, processed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rel_path, source_path, output_path, media_type,
                    source_mtime, original_size, compressed_size,
                    status, error_message or "", duration_sec, now_str
                ))

    def get_summary_stats(self) -> Dict[str, Any]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        status,
                        COUNT(*),
                        COALESCE(SUM(original_size), 0),
                        COALESCE(SUM(compressed_size), 0)
                    FROM processed_records
                    GROUP BY status
                """)
                rows = cursor.fetchall()
                
                stats = {
                    "total_count": 0,
                    "success_count": 0,
                    "skipped_larger_count": 0,
                    "copied_count": 0,
                    "failed_count": 0,
                    "total_original_bytes": 0,
                    "total_compressed_bytes": 0,
                    "total_saved_bytes": 0
                }

                for status, count, orig_sum, comp_sum in rows:
                    stats["total_count"] += count
                    stats["total_original_bytes"] += orig_sum
                    stats["total_compressed_bytes"] += comp_sum

                    if status == "SUCCESS":
                        stats["success_count"] += count
                    elif status == "SKIPPED_LARGER":
                        stats["skipped_larger_count"] += count
                    elif status == "COPIED":
                        stats["copied_count"] += count
                    elif status == "FAILED":
                        stats["failed_count"] += count

                stats["total_saved_bytes"] = max(0, stats["total_original_bytes"] - stats["total_compressed_bytes"])
                return stats
