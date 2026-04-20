"""
Система структурированного логирования для MSFS AutoLand
Создаёт детальные логи в JSON формате и сохраняет в базу данных
"""

import json
import logging
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from modules.log_database import init_log_database


class LogLevel(Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Категории событий"""
    SYSTEM = "SYSTEM"
    TELEMETRY = "TELEMETRY"
    NAVIGATION = "NAVIGATION"
    AUTOPILOT = "AUTOPILOT"
    CONTROL = "CONTROL"
    WIND_SHEAR = "WIND_SHEAR"
    AUDIO = "AUDIO"
    GUI = "GUI"
    PERFORMANCE = "PERFORMANCE"
    ERROR = "ERROR"


@dataclass
class LogEntry:
    """Структурированная запись лога"""
    timestamp: float
    datetime_str: str
    level: str
    category: str
    message: str
    module: str
    function: str
    line: int
    data: Optional[Dict[str, Any]] = None
    exception: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    session_id: Optional[str] = None


class StructuredLoggerBridge(logging.Handler):
    """Handler для перехвата стандартных логов и записи в структурированный формат"""

    def __init__(self, structured_logger):
        super().__init__()
        self.structured_logger = structured_logger

    def emit(self, record):
        """Обработка записи лога"""
        try:
            # Определение категории по имени модуля
            category = self._get_category_from_module(record.name)

            # Определение уровня
            level_map = {
                logging.DEBUG: LogLevel.DEBUG,
                logging.INFO: LogLevel.INFO,
                logging.WARNING: LogLevel.WARNING,
                logging.ERROR: LogLevel.ERROR,
                logging.CRITICAL: LogLevel.CRITICAL
            }
            level = level_map.get(record.levelno, LogLevel.INFO)

            # Извлечение данных
            data = None
            if hasattr(record, 'data'):
                data = record.data

            # Создание записи
            entry = LogEntry(
                timestamp=record.created,
                datetime_str=datetime.fromtimestamp(record.created).isoformat(),
                level=level.value,
                category=category.value,
                message=record.getMessage(),
                module=record.name,
                function=record.funcName,
                line=record.lineno,
                data=data,
                session_id=self.structured_logger.session_id
            )

            # Обработка исключения
            if record.exc_info:
                exc_type, exc_value, exc_tb = record.exc_info
                entry.exception = {
                    'type': exc_type.__name__ if exc_type else 'Unknown',
                    'message': str(exc_value) if exc_value else '',
                    'args': exc_value.args if exc_value else []
                }
                entry.stack_trace = ''.join(traceback.format_exception(*record.exc_info))

            # Запись в JSON файл
            with open(self.structured_logger.json_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + '\n')

            # Запись в базу данных
            try:
                self.structured_logger.db.add_log(self.structured_logger.session_id, asdict(entry))
            except Exception:
                # Не прерываем работу если БД недоступна
                pass

            # Запись ошибок в отдельный файл
            if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                with open(self.structured_logger.error_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(asdict(entry), ensure_ascii=False) + '\n')
                self.structured_logger.error_count += 1

            # Обновление счётчиков
            self.structured_logger.log_count += 1
            if level == LogLevel.WARNING:
                self.structured_logger.warning_count += 1

        except Exception:
            # Не прерываем работу при ошибках логирования
            self.handleError(record)

    def _get_category_from_module(self, module_name: str) -> LogCategory:
        """Определение категории по имени модуля"""
        if 'telemetry' in module_name:
            return LogCategory.TELEMETRY
        elif 'navigation' in module_name or 'ils' in module_name or 'dme' in module_name:
            return LogCategory.NAVIGATION
        elif 'autopilot' in module_name or 'aircraft_adapter' in module_name:
            return LogCategory.AUTOPILOT
        elif 'control' in module_name or 'autothrottle' in module_name or 'flare' in module_name:
            return LogCategory.CONTROL
        elif 'wind_shear' in module_name:
            return LogCategory.WIND_SHEAR
        elif 'audio' in module_name:
            return LogCategory.AUDIO
        elif 'gui' in module_name:
            return LogCategory.GUI
        else:
            return LogCategory.SYSTEM


class StructuredLogger:
    """Структурированный логгер с JSON выводом"""

    def __init__(self, log_dir: str = "logs", session_id: Optional[str] = None):
        """
        Args:
            log_dir: Директория для логов
            session_id: ID сессии (генерируется автоматически если не указан)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # ID сессии
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        # Инициализация базы данных
        self.db = init_log_database(str(self.log_dir / "logs.db"))
        self.db.create_session(self.session_id)

        # Файлы логов
        self.json_log_file = self.log_dir / f"session_{self.session_id}.jsonl"
        self.text_log_file = self.log_dir / f"session_{self.session_id}.log"
        self.error_log_file = self.log_dir / f"errors_{self.session_id}.jsonl"

        # Счётчики
        self.log_count = 0
        self.error_count = 0
        self.warning_count = 0

        # Метрики производительности
        self.performance_metrics = {}

        # Стандартный логгер Python
        self.logger = logging.getLogger("msfs_autoland")
        self._setup_standard_logger()

    def _setup_standard_logger(self):
        """Настройка стандартного логгера Python"""
        self.logger.setLevel(logging.DEBUG)

        # Обработчик для текстового файла
        file_handler = logging.FileHandler(self.text_log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Добавить bridge handler для перехвата всех логов
        bridge_handler = StructuredLoggerBridge(self)
        bridge_handler.setLevel(logging.DEBUG)

        # Добавить handler к root logger чтобы перехватывать все логи
        root_logger = logging.getLogger()
        root_logger.addHandler(bridge_handler)

    def log(self, level: LogLevel, category: LogCategory, message: str,
            data: Optional[Dict] = None, exception: Optional[Exception] = None):
        """
        Записать структурированный лог

        Args:
            level: Уровень логирования
            category: Категория события
            message: Сообщение
            data: Дополнительные данные
            exception: Исключение (если есть)
        """
        # Получение информации о вызывающем коде
        frame = sys._getframe(2)
        module = frame.f_globals.get('__name__', 'unknown')
        function = frame.f_code.co_name
        line = frame.f_lineno

        # Создание записи
        entry = LogEntry(
            timestamp=time.time(),
            datetime_str=datetime.now().isoformat(),
            level=level.value,
            category=category.value,
            message=message,
            module=module,
            function=function,
            line=line,
            data=data,
            session_id=self.session_id
        )

        # Обработка исключения
        if exception:
            entry.exception = {
                'type': type(exception).__name__,
                'message': str(exception),
                'args': exception.args
            }
            entry.stack_trace = traceback.format_exc()

        # Запись в JSON файл
        with open(self.json_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + '\n')

        # Запись в базу данных
        try:
            self.db.add_log(self.session_id, asdict(entry))
        except Exception as e:
            # Не прерываем работу если БД недоступна
            self.logger.error("Failed to write to database: %s", e)

        # Запись ошибок в отдельный файл
        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            with open(self.error_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + '\n')
            self.error_count += 1

        # Обновление счётчиков
        self.log_count += 1
        if level == LogLevel.WARNING:
            self.warning_count += 1

        # Запись в стандартный логгер
        log_level = getattr(logging, level.value)
        self.logger.log(log_level, f"[{category.value}] {message}")

    def debug(self, category: LogCategory, message: str, data: Optional[Dict] = None):
        """Лог уровня DEBUG"""
        self.log(LogLevel.DEBUG, category, message, data)

    def info(self, category: LogCategory, message: str, data: Optional[Dict] = None):
        """Лог уровня INFO"""
        self.log(LogLevel.INFO, category, message, data)

    def warning(self, category: LogCategory, message: str, data: Optional[Dict] = None):
        """Лог уровня WARNING"""
        self.log(LogLevel.WARNING, category, message, data)

    def error(self, category: LogCategory, message: str, data: Optional[Dict] = None,
              exception: Optional[Exception] = None):
        """Лог уровня ERROR"""
        self.log(LogLevel.ERROR, category, message, data, exception)

    def critical(self, category: LogCategory, message: str, data: Optional[Dict] = None,
                 exception: Optional[Exception] = None):
        """Лог уровня CRITICAL"""
        self.log(LogLevel.CRITICAL, category, message, data, exception)

    def log_performance(self, operation: str, duration: float, data: Optional[Dict] = None):
        """
        Логирование метрик производительности

        Args:
            operation: Название операции
            duration: Длительность в секундах
            data: Дополнительные данные
        """
        perf_data = {
            'operation': operation,
            'duration_ms': duration * 1000,
            **(data or {})
        }

        self.info(LogCategory.PERFORMANCE, f"Performance: {operation}", perf_data)

        # Запись в базу данных
        try:
            self.db.add_performance_metric(self.session_id, operation, duration * 1000, data)
        except Exception as e:
            self.logger.error("Failed to write performance metric to database: %s", e)

        # Сохранение в метрики
        if operation not in self.performance_metrics:
            self.performance_metrics[operation] = []
        self.performance_metrics[operation].append(duration)

    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику логирования"""
        return {
            'session_id': self.session_id,
            'total_logs': self.log_count,
            'errors': self.error_count,
            'warnings': self.warning_count,
            'json_log_file': str(self.json_log_file),
            'error_log_file': str(self.error_log_file),
            'performance_metrics': {
                op: {
                    'count': len(times),
                    'avg_ms': sum(times) / len(times) * 1000,
                    'min_ms': min(times) * 1000,
                    'max_ms': max(times) * 1000
                }
                for op, times in self.performance_metrics.items()
            }
        }


# Глобальный экземпляр
_structured_logger: Optional[StructuredLogger] = None


def get_logger() -> StructuredLogger:
    """Получить глобальный экземпляр логгера"""
    global _structured_logger
    if _structured_logger is None:
        _structured_logger = StructuredLogger()
    return _structured_logger


def init_logger(log_dir: str = "logs", session_id: Optional[str] = None) -> StructuredLogger:
    """
    Инициализировать глобальный логгер

    Args:
        log_dir: Директория для логов
        session_id: ID сессии

    Returns:
        Экземпляр StructuredLogger
    """
    global _structured_logger
    _structured_logger = StructuredLogger(log_dir, session_id)
    return _structured_logger
