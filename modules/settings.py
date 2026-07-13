"""
Модуль для работы с настройками приложения
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Settings:
    """Класс для работы с настройками приложения"""

    DEFAULT_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.json"

    def __init__(self, settings_path: Optional[Path] = None):
        """
        Args:
            settings_path: Путь к файлу настроек (опционально)
        """
        self.settings_path = settings_path or self.DEFAULT_SETTINGS_PATH
        self.settings = self._load_settings()

    def _load_settings(self) -> dict:
        """
        Загрузить настройки из файла

        Returns:
            Словарь с настройками
        """
        try:
            if not self.settings_path.exists():
                logger.warning(f"Settings file not found: {self.settings_path}, using defaults")
                return self._get_default_settings()

            with open(self.settings_path, encoding='utf-8') as f:
                settings = json.load(f)
                logger.info(f"Settings loaded from {self.settings_path}")
                return settings

        except Exception as e:
            logger.error(f"Failed to load settings: {e}, using defaults")
            return self._get_default_settings()

    def _get_default_settings(self) -> dict:
        """
        Получить настройки по умолчанию

        Returns:
            Словарь с настройками по умолчанию
        """
        return {
            "navigraph": {
                "database_path": None,
                "auto_refresh": False,
                "cache_enabled": False,
                "cache_ttl_seconds": 3600
            },
            "gui": {
                "theme": "default",
                "window_width": 1200,
                "window_height": 800
            },
            "logging": {
                "level": "INFO",
                "console_output": True,
                "file_output": True
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Получить значение настройки

        Args:
            key: Ключ настройки (поддерживает точечную нотацию, например "navigraph.database_path")
            default: Значение по умолчанию

        Returns:
            Значение настройки или default
        """
        keys = key.split('.')
        value = self.settings

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """
        Установить значение настройки

        Args:
            key: Ключ настройки (поддерживает точечную нотацию)
            value: Новое значение
        """
        keys = key.split('.')
        current = self.settings

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def save(self):
        """Сохранить настройки в файл"""
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)

            logger.info(f"Settings saved to {self.settings_path}")

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get_navigraph_db_path(self) -> Optional[Path]:
        """
        Получить путь к базе данных Navigraph

        Returns:
            Path или None (если используется путь по умолчанию)
        """
        db_path = self.get('navigraph.database_path')
        if db_path:
            return Path(db_path)
        return None


# Глобальный экземпляр настроек
_settings_instance = None


def get_settings() -> Settings:
    """
    Получить глобальный экземпляр настроек

    Returns:
        Экземпляр Settings
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
