# config_manager.py
import json
from typing import Dict, Any


class ConfigManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._cache = {}

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        if key in self._cache:
            return self._cache[key]

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT c_value FROM t_config WHERE c_key = %s", (key,))
                result = cursor.fetchone()

                if result:
                    value = json.loads(result[0])
                    self._cache[key] = value
                    return value
                else:
                    self._cache[key] = default
                    return default
        except Exception:
            return default

    def set_config(self, key: str, value: Any) -> bool:
        """Set configuration value"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO t_config (c_key, c_value) 
                    VALUES (%s, %s) 
                    ON DUPLICATE KEY UPDATE c_value = %s, c_updated_at = NOW()
                """, (key, json.dumps(value), json.dumps(value)))
                conn.commit()

                self._cache[key] = value
                return True
        except Exception:
            return False

    def get_posting_limits(self) -> Dict[str, int]:
        """Get current posting limits"""
        return {
            'daily_limit': self.get_config('daily_posting_limit', 24),
            'hourly_limit': self.get_config('hourly_posting_limit', 3),
            'min_rating_threshold': self.get_config('min_rating_threshold', 60),
            'min_lurkable_threshold': self.get_config('min_lurkable_threshold', 70)
        }
