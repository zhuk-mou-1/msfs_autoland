"""
Базовый класс для всех контроллеров в системе AutoLand

Определяет единый интерфейс для контроллеров:
- update() - обновление состояния на основе телеметрии
- reset() - сброс внутреннего состояния
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class Controller(ABC):
    """
    Абстрактный базовый класс для контроллеров

    Все контроллеры (autothrottle, flare_controller, wind_correction и т.д.)
    должны наследоваться от этого класса и реализовывать методы update() и reset()

    Это обеспечивает:
    - Единообразный интерфейс для всех контроллеров
    - Возможность полиморфного использования
    - Упрощение тестирования
    """

    @abstractmethod
    def update(self, telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обновить состояние контроллера на основе телеметрии

        Args:
            telemetry_data: Словарь с данными телеметрии

        Returns:
            Словарь с результатами работы контроллера

        Raises:
            NotImplementedError: Если метод не реализован в подклассе
        """
        raise NotImplementedError("Метод update() должен быть реализован в подклассе")

    @abstractmethod
    def reset(self) -> None:
        """
        Сбросить внутреннее состояние контроллера

        Вызывается при:
        - Инициализации нового захода
        - Прерывании захода (go-around)
        - Переключении режимов

        Raises:
            NotImplementedError: Если метод не реализован в подклассе
        """
        raise NotImplementedError("Метод reset() должен быть реализован в подклассе")
