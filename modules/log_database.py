"""
База данных для хранения логов проекта
SQLite база с методами для записи и чтения логов
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional


class LogDatabase:
    """База данных для хранения логов"""

    def __init__(self, db_path: str = "logs/logs.db"):
        """
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Инициализация структуры базы данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Таблица сессий
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    total_logs INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    warning_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            """)

            # Таблица логов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    datetime_str TEXT NOT NULL,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT NOT NULL,
                    module TEXT,
                    function TEXT,
                    line INTEGER,
                    data TEXT,
                    exception_type TEXT,
                    exception_message TEXT,
                    stack_trace TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Таблица ошибок (для быстрого доступа)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    error_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    module TEXT,
                    function TEXT,
                    count INTEGER DEFAULT 1,
                    first_occurrence REAL NOT NULL,
                    last_occurrence REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Таблица метрик производительности
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    operation TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    data TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Индексы для быстрого поиска
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_session ON logs(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_category ON logs(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_session ON errors(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_session ON performance(session_id)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_session(self, session_id: str) -> bool:
        """
        Создать новую сессию

        Args:
            session_id: ID сессии

        Returns:
            True если успешно
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sessions (session_id, start_time, status)
                    VALUES (?, ?, 'active')
                """, (session_id, time.time()))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def close_session(self, session_id: str):
        """
        Закрыть сессию

        Args:
            session_id: ID сессии
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions
                SET end_time = ?, status = 'completed'
                WHERE session_id = ?
            """, (time.time(), session_id))
            conn.commit()

    def add_log(self, session_id: str, log_entry: Dict[str, Any]):
        """
        Добавить запись лога

        Args:
            session_id: ID сессии
            log_entry: Запись лога
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Добавление лога
            cursor.execute("""
                INSERT INTO logs (
                    session_id, timestamp, datetime_str, level, category,
                    message, module, function, line, data,
                    exception_type, exception_message, stack_trace
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                log_entry.get('timestamp'),
                log_entry.get('datetime_str'),
                log_entry.get('level'),
                log_entry.get('category'),
                log_entry.get('message'),
                log_entry.get('module'),
                log_entry.get('function'),
                log_entry.get('line'),
                json.dumps(log_entry.get('data')) if log_entry.get('data') else None,
                log_entry.get('exception', {}).get('type') if log_entry.get('exception') else None,
                log_entry.get('exception', {}).get('message') if log_entry.get('exception') else None,
                log_entry.get('stack_trace')
            ))

            # Обновление счётчиков сессии
            cursor.execute("""
                UPDATE sessions
                SET total_logs = total_logs + 1,
                    error_count = error_count + CASE WHEN ? IN ('ERROR', 'CRITICAL') THEN 1 ELSE 0 END,
                    warning_count = warning_count + CASE WHEN ? = 'WARNING' THEN 1 ELSE 0 END
                WHERE session_id = ?
            """, (log_entry.get('level'), log_entry.get('level'), session_id))

            # Если это ошибка, добавить в таблицу ошибок
            if log_entry.get('level') in ['ERROR', 'CRITICAL'] and log_entry.get('exception'):
                self._add_error(cursor, session_id, log_entry)

            conn.commit()

    def _add_error(self, cursor, session_id: str, log_entry: Dict[str, Any]):
        """Добавить ошибку в таблицу ошибок"""
        error_type = log_entry.get('exception', {}).get('type', 'Unknown')
        message = log_entry.get('message')
        module = log_entry.get('module')
        function = log_entry.get('function')
        timestamp = log_entry.get('timestamp')

        # Проверить существует ли такая ошибка
        cursor.execute("""
            SELECT id, count FROM errors
            WHERE session_id = ? AND error_type = ? AND message = ?
        """, (session_id, error_type, message))

        row = cursor.fetchone()

        if row:
            # Обновить существующую
            cursor.execute("""
                UPDATE errors
                SET count = count + 1, last_occurrence = ?
                WHERE id = ?
            """, (timestamp, row['id']))
        else:
            # Добавить новую
            cursor.execute("""
                INSERT INTO errors (
                    session_id, timestamp, error_type, message,
                    module, function, first_occurrence, last_occurrence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, timestamp, error_type, message, module, function, timestamp, timestamp))

    def add_performance_metric(self, session_id: str, operation: str, duration_ms: float, data: Optional[Dict] = None):
        """
        Добавить метрику производительности

        Args:
            session_id: ID сессии
            operation: Название операции
            duration_ms: Длительность в миллисекундах
            data: Дополнительные данные
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO performance (session_id, timestamp, operation, duration_ms, data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id,
                time.time(),
                operation,
                duration_ms,
                json.dumps(data) if data else None
            ))
            conn.commit()

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        Получить информацию о сессии

        Args:
            session_id: ID сессии

        Returns:
            Информация о сессии или None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_session_logs(self, session_id: str, level: Optional[str] = None,
                        category: Optional[str] = None, limit: int = 1000) -> List[Dict]:
        """
        Получить логи сессии

        Args:
            session_id: ID сессии
            level: Фильтр по уровню (ERROR, WARNING, и т.д.)
            category: Фильтр по категории
            limit: Максимальное количество записей

        Returns:
            Список логов
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM logs WHERE session_id = ?"
            params = [session_id]

            if level:
                query += " AND level = ?"
                params.append(level)

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_session_errors(self, session_id: str) -> List[Dict]:
        """
        Получить ошибки сессии

        Args:
            session_id: ID сессии

        Returns:
            Список ошибок
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM errors
                WHERE session_id = ?
                ORDER BY count DESC, last_occurrence DESC
            """, (session_id,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_performance_stats(self, session_id: str, operation: Optional[str] = None) -> Dict:
        """
        Получить статистику производительности

        Args:
            session_id: ID сессии
            operation: Фильтр по операции

        Returns:
            Статистика
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    operation,
                    COUNT(*) as count,
                    AVG(duration_ms) as avg_ms,
                    MIN(duration_ms) as min_ms,
                    MAX(duration_ms) as max_ms
                FROM performance
                WHERE session_id = ?
            """
            params = [session_id]

            if operation:
                query += " AND operation = ?"
                params.append(operation)

            query += " GROUP BY operation"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return {row['operation']: dict(row) for row in rows}

    def get_all_sessions(self, limit: int = 50) -> List[Dict]:
        """
        Получить список всех сессий

        Args:
            limit: Максимальное количество

        Returns:
            Список сессий
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sessions
                ORDER BY start_time DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_latest_session(self) -> Optional[Dict]:
        """
        Получить последнюю сессию

        Returns:
            Информация о последней сессии или None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sessions
                ORDER BY start_time DESC
                LIMIT 1
            """)
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def search_logs(self, search_text: str, session_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Поиск в логах

        Args:
            search_text: Текст для поиска
            session_id: Фильтр по сессии
            limit: Максимальное количество

        Returns:
            Найденные логи
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM logs WHERE message LIKE ?"
            params = [f"%{search_text}%"]

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_database_stats(self) -> Dict:
        """
        Получить статистику базы данных

        Returns:
            Статистика
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Количество сессий
            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            stats['total_sessions'] = cursor.fetchone()['count']

            # Количество логов
            cursor.execute("SELECT COUNT(*) as count FROM logs")
            stats['total_logs'] = cursor.fetchone()['count']

            # Количество ошибок
            cursor.execute("SELECT COUNT(*) as count FROM errors")
            stats['total_errors'] = cursor.fetchone()['count']

            # Размер базы данных
            stats['db_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)

            return stats


# Глобальный экземпляр
_log_database: Optional[LogDatabase] = None


def get_log_database() -> LogDatabase:
    """Получить глобальный экземпляр базы данных"""
    global _log_database
    if _log_database is None:
        _log_database = LogDatabase()
    return _log_database


def init_log_database(db_path: str = "logs/logs.db") -> LogDatabase:
    """
    Инициализировать базу данных логов

    Args:
        db_path: Путь к файлу базы данных

    Returns:
        Экземпляр LogDatabase
    """
    global _log_database
    _log_database = LogDatabase(db_path)
    return _log_database
