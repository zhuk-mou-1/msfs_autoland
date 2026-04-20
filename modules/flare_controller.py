"""
Модуль автоматического выравнивания при посадке (Flare)
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional

from .thresholds_config import get_thresholds

logger = logging.getLogger(__name__)


@dataclass
class FlareConfig:
    """Конфигурация выравнивания"""
    # Высоты
    flare_start_height: float
    flare_end_height: float

    # Тангаж
    initial_pitch: float
    target_pitch: float
    max_pitch_rate: float

    # Вертикальная скорость
    initial_vs: float = -600.0
    target_vs: float = -100.0

    # Газ
    throttle_reduction_start: float

    @classmethod
    def from_thresholds(cls) -> 'FlareConfig':
        """Создать конфиг из централизованных порогов"""
        config = get_thresholds().flare
        return cls(
            flare_start_height=config.start_height,
            flare_end_height=config.end_height,
            initial_pitch=config.initial_pitch,
            target_pitch=config.target_pitch,
            max_pitch_rate=config.max_pitch_rate,
            throttle_reduction_start=config.throttle_reduction_start
        )
    min_throttle: float = 0.05        # минимальный газ (idle)


class FlareController:
    """Контроллер автоматического выравнивания"""

    def __init__(self, config: Optional[FlareConfig] = None):
        self.config = config or FlareConfig()
        self.flare_active = False
        self.flare_start_time = None
        self.initial_height = None

    def should_start_flare(self, radio_height: float, vertical_speed: float) -> bool:
        """
        Определение момента начала выравнивания

        Args:
            radio_height: Высота над землёй (футы)
            vertical_speed: Вертикальная скорость (футы/мин)

        Returns:
            True если нужно начинать выравнивание
        """
        # Начинаем выравнивание на заданной высоте
        if radio_height <= self.config.flare_start_height and not self.flare_active:
            # Дополнительная проверка: вертикальная скорость должна быть отрицательной
            if vertical_speed < 0:
                return True
        return False

    def calculate_flare_parameters(self, radio_height: float,
                                   current_pitch: float,
                                   current_vs: float,
                                   ground_speed: float,
                                   dt: float = 0.5) -> Dict[str, float]:
        """
        Расчёт параметров выравнивания

        Args:
            radio_height: Высота над землёй (футы)
            current_pitch: Текущий тангаж (градусы)
            current_vs: Текущая вертикальная скорость (футы/мин)
            ground_speed: Путевая скорость (узлы)
            dt: Временной шаг (секунды)

        Returns:
            Dict с командами управления
        """
        if not self.flare_active:
            return {
                'flare_active': False,
                'target_pitch': current_pitch,
                'target_vs': current_vs,
                'throttle': None
            }

        # Прогресс выравнивания (0.0 = начало, 1.0 = конец)
        height_range = self.config.flare_start_height - self.config.flare_end_height
        if height_range > 0:
            progress = 1.0 - ((radio_height - self.config.flare_end_height) / height_range)
            progress = max(0.0, min(1.0, progress))
        else:
            progress = 1.0

        # Расчёт целевого тангажа (экспоненциальная кривая для плавности)
        pitch_range = self.config.target_pitch - self.config.initial_pitch
        # Используем квадратичную функцию для более плавного начала
        target_pitch = self.config.initial_pitch + pitch_range * (progress ** 0.7)

        # Ограничение скорости изменения тангажа
        max_pitch_change = self.config.max_pitch_rate * dt
        pitch_change = target_pitch - current_pitch
        if abs(pitch_change) > max_pitch_change:
            target_pitch = current_pitch + math.copysign(max_pitch_change, pitch_change)

        # Расчёт целевой вертикальной скорости
        vs_range = self.config.target_vs - self.config.initial_vs
        target_vs = self.config.initial_vs + vs_range * (progress ** 0.5)

        # Расчёт газа (постепенное снижение)
        if radio_height < self.config.throttle_reduction_start:
            throttle_progress = 1.0 - (radio_height / self.config.throttle_reduction_start)
            throttle = 0.3 * (1.0 - throttle_progress) + self.config.min_throttle * throttle_progress
        else:
            throttle = 0.3  # Поддерживаем небольшой газ

        # Финальная фаза (очень близко к земле)
        if radio_height < 10:
            throttle = self.config.min_throttle
            target_pitch = self.config.target_pitch

        logger.debug(f"Flare: h={radio_height:.1f}ft, progress={progress:.2f}, "
                    f"pitch={current_pitch:.1f}°→{target_pitch:.1f}°, "
                    f"VS={current_vs:.0f}→{target_vs:.0f}fpm, throttle={throttle:.2f}")

        return {
            'flare_active': True,
            'target_pitch': target_pitch,
            'target_vs': target_vs,
            'throttle': throttle,
            'progress': progress
        }

    def calculate_pitch_input(self, current_pitch: float, target_pitch: float,
                             pitch_rate: float = 0.0) -> float:
        """
        Расчёт управляющего входа для достижения целевого тангажа

        Args:
            current_pitch: Текущий тангаж (градусы)
            target_pitch: Целевой тангаж (градусы)
            pitch_rate: Скорость изменения тангажа (градусы/сек)

        Returns:
            Управляющий вход для руля высоты (-1.0 до +1.0)
        """
        # Пропорциональный контроллер с демпфированием
        error = target_pitch - current_pitch

        # P-коэффициент (пропорциональный)
        Kp = 0.15

        # D-коэффициент (демпфирование)
        Kd = 0.05

        # PD контроллер
        elevator_input = Kp * error - Kd * pitch_rate

        # Ограничение входа
        elevator_input = max(-0.3, min(0.3, elevator_input))

        return elevator_input

    def calculate_vs_correction(self, current_vs: float, target_vs: float) -> float:
        """
        Расчёт коррекции для достижения целевой вертикальной скорости

        Args:
            current_vs: Текущая VS (футы/мин)
            target_vs: Целевая VS (футы/мин)

        Returns:
            Коррекция тангажа (градусы)
        """
        vs_error = target_vs - current_vs

        # Коррекция тангажа на основе ошибки VS
        # 100 fpm ошибки = 0.5° коррекции
        pitch_correction = vs_error / 200.0

        # Ограничение коррекции
        pitch_correction = max(-2.0, min(2.0, pitch_correction))

        return pitch_correction

    def start_flare(self, radio_height: float):
        """Начать выравнивание"""
        self.flare_active = True
        self.initial_height = radio_height
        logger.info("FLARE STARTED at %sft", radio_height)

    def reset(self):
        """Сброс состояния контроллера"""
        self.flare_active = False
        self.flare_start_time = None
        self.initial_height = None
        logger.debug("Flare controller reset")

    def get_flare_status(self, radio_height: float) -> str:
        """Получить статус выравнивания"""
        if not self.flare_active:
            if radio_height > self.config.flare_start_height:
                return f"Awaiting flare ({radio_height:.0f}ft > {self.config.flare_start_height:.0f}ft)"
            else:
                return "Ready for flare"
        else:
            if radio_height > self.config.flare_end_height:
                return f"FLARE ACTIVE ({radio_height:.1f}ft)"
            else:
                return "FLARE COMPLETE - TOUCHDOWN"

    def adjust_for_wind(self, headwind: float, config: FlareConfig) -> FlareConfig:
        """
        Корректировка параметров выравнивания с учётом ветра

        Args:
            headwind: Встречный ветер (узлы, + встречный, - попутный)
            config: Базовая конфигурация

        Returns:
            Скорректированная конфигурация
        """
        adjusted = FlareConfig(
            flare_start_height=config.flare_start_height,
            flare_end_height=config.flare_end_height,
            initial_pitch=config.initial_pitch,
            target_pitch=config.target_pitch,
            max_pitch_rate=config.max_pitch_rate,
            initial_vs=config.initial_vs,
            target_vs=config.target_vs,
            throttle_reduction_start=config.throttle_reduction_start,
            min_throttle=config.min_throttle
        )

        # При сильном встречном ветре начинаем выравнивание чуть выше
        if headwind > 15:
            adjusted.flare_start_height += 5
            logger.info("Flare height adjusted for strong headwind: %sft", adjusted.flare_start_height)

        # При попутном ветре начинаем чуть ниже
        elif headwind < -5:
            adjusted.flare_start_height -= 3
            logger.info("Flare height adjusted for tailwind: %sft", adjusted.flare_start_height)

        return adjusted
