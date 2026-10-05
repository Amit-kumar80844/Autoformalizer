import sqlite3
import hashlib
import json
from typing import Optional
from app.schema.ast import TrialFormalization
import os

# Default local SQLite cache
DB_PATH = os.path.join(os.path.dirname(__file__), "formalizer_cache.db")

class CacheManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS formalizations (
                    trial_id TEXT,
                    source_hash TEXT,
                    schema_version TEXT,
                    result_json TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (trial_id, source_hash, schema_version)
                )
            ''')
            
    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
        
    def get_cached(self, trial_id: str, criterion_text: str, schema_version: str = "1.0") -> Optional[TrialFormalization]:
        source_hash = self._compute_hash(criterion_text)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT result_json FROM formalizations WHERE trial_id = ? AND source_hash = ? AND schema_version = ?",
                (trial_id, source_hash, schema_version)
            )
            row = cursor.fetchone()
            if row:
                return TrialFormalization.model_validate_json(row[0])
        return None
        
    def save(self, result: TrialFormalization, criterion_text: str, schema_version: str = "1.0"):
        source_hash = self._compute_hash(criterion_text)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO formalizations 
                (trial_id, source_hash, schema_version, result_json)
                VALUES (?, ?, ?, ?)
            ''', (result.trial_id, source_hash, schema_version, result.model_dump_json()))
