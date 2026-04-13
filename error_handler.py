# error_handler.py
import traceback
from typing import Dict, Any
from datetime import datetime
from config import Config


class ErrorHandler:
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        self.error_counts = {}
        self.last_notification = {}

    def handle_error(self, error: Exception, context: Dict[str, Any] = None):
        """Handle errors with appropriate logging and notifications"""
        error_type = type(error).__name__
        error_message = str(error)

        # Log error
        self.logger.error(f"Error: {error_type} - {error_message}")
        if context:
            self.logger.error(f"Context: {context}")

        # Log stack trace
        self.logger.debug(traceback.format_exc())

        # Track error frequency
        self._track_error_frequency(error_type)

        # Send notification for critical errors
        if self._is_critical_error(error_type):
            self._send_error_notification(error_type, error_message, context)

    def _track_error_frequency(self, error_type: str):
        """Track error frequency for pattern detection"""
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0

        self.error_counts[error_type] += 1

        # Alert if error occurs too frequently
        if self.error_counts[error_type] > 5:
            self.logger.warning(
                f"Error {error_type} has occurred {self.error_counts[error_type]} times"
            )

    def _is_critical_error(self, error_type: str) -> bool:
        """Determine if error is critical and needs immediate attention"""
        critical_errors = [
            'DatabaseError',
            'ConnectionError',
            'AuthenticationError',
            'QuotaExceededError'
        ]
        return error_type in critical_errors

    def _send_error_notification(self, error_type: str, message: str, context: Dict = None):
        """Send error notification (implement based on preferred method)"""
        # Implement notification logic (email, Slack, etc.)
        pass


# health_monitor.py
class HealthMonitor:
    def __init__(self, config: config, db_manager: DatabaseManager, logger):
        self.config = config
        self.db = db_manager
        self.logger = logger
        self.health_stats = {
            'last_successful_run': None,
            'total_articles_processed': 0,
            'total_articles_posted': 0,
            'error_count': 0,
            'api_usage': 0
        }

    def record_successful_run(self):
        """Record successful processing cycle"""
        self.health_stats['last_successful_run'] = datetime.now()

    def record_article_processed(self):
        """Record article processing"""
        self.health_stats['total_articles_processed'] += 1

    def record_article_posted(self):
        """Record successful article posting"""
        self.health_stats['total_articles_posted'] += 1

    def record_error(self):
        """Record error occurrence"""
        self.health_stats['error_count'] += 1

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            **self.health_stats,
            'database_connectivity': self._check_database_connection(),
            'api_limits': self._check_api_limits(),
            'disk_space': self._check_disk_space()
        }

    def _check_database_connection(self) -> bool:
        """Check database connectivity"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception:
            return False

    def _check_api_limits(self) -> Dict[str, Any]:
        """Check API usage limits"""
        # Implement API limit checking
        return {
            'openai_requests_today': 0,
            'telegram_requests_today': 0,
            'near_limit': False
        }

    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space"""
        import shutil

        total, used, free = shutil.disk_usage('/')
        return {
            'total_gb': total // (1024 ** 3),
            'used_gb': used // (1024 ** 3),
            'free_gb': free // (1024 ** 3),
            'usage_percent': (used / total) * 100
        }
