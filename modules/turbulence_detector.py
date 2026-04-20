"""
Детектор турбулентности (Turbulence Detector)
Обнаруживает турбулентность любого типа, включая CAT (Clear Air Turbulence)
"""

import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional

from .thresholds_config import get_thresholds

logger = logging.getLogger(__name__)


@dataclass
class TurbulenceAlert:
    """Предупреждение о турбулентности"""
    detected: bool
    intensity: str  # 'SMOOTH', 'LIGHT', 'MODERATE', 'SEVERE'
    type: str  # 'CAT', 'CONVECTIVE', 'MECHANICAL', 'UNKNOWN'
    g_force_std: float  # Стандартное отклонение G-force
    bank_oscillation: float  # Амплитуда колебаний крена
    pitch_oscillation: float  # Амплитуда колебаний тангажа
    wind_variability: float  # Изменчивость ветра
    recommendation: str  # Рекомендация
    timestamp: float


class TurbulenceDetector:
    """Детектор турбулентности"""

    def __init__(self, history_size: int = 100):
        """
        Args:
            history_size: Размер истории для анализа (количество измерений)
        """
        self.history_size = history_size

        # История параметров (10 секунд при 10Hz)
        self.g_force_history = deque(maxlen=history_size)
        self.bank_angle_history = deque(maxlen=history_size)
        self.pitch_angle_history = deque(maxlen=history_size)
        self.wind_velocity_history = deque(maxlen=history_size)
        self.wind_direction_history = deque(maxlen=history_size)
        self.airspeed_history = deque(maxlen=history_size)
        self.altitude_history = deque(maxlen=history_size)
        self.temperature_history = deque(maxlen=history_size)
        self.timestamp_history = deque(maxlen=history_size)

        # Пороги интенсивности из централизованного конфига
        config = get_thresholds().turbulence
        self.light_turbulence_threshold = config.light_threshold
        self.moderate_turbulence_threshold = config.moderate_threshold
        self.severe_turbulence_threshold = config.severe_threshold

        # Пороги для колебаний углов
        self.light_bank_oscillation = 3.0  # градусы
        self.moderate_bank_oscillation = 8.0  # градусы
        self.severe_bank_oscillation = 15.0  # градусы

        # Текущее предупреждение
        self.current_alert: Optional[TurbulenceAlert] = None
        self.last_alert_time = 0
        self.alert_cooldown = 3.0  # секунды между обновлениями

        # Статистика
        self.total_turbulence_time = 0
        self.max_g_force_std = 0
        self.turbulence_events = []

    def update(self, telemetry: Dict) -> Optional[TurbulenceAlert]:
        """
        Обновить данные и проверить наличие турбулентности

        Args:
            telemetry: Телеметрия самолёта

        Returns:
            TurbulenceAlert если обнаружена турбулентность, иначе None
        """
        current_time = time.time()

        # Извлечение данных
        # G-force (вертикальная перегрузка)
        g_force = telemetry.get('g_force', 1.0)

        # Углы ориентации
        bank_angle = telemetry.get('orientation', {}).get('bank', 0)
        pitch_angle = telemetry.get('orientation', {}).get('pitch', 0)

        # Ветер
        wind_velocity = telemetry.get('weather', {}).get('ambient_wind_velocity', 0)
        wind_direction = telemetry.get('weather', {}).get('ambient_wind_direction', 0)

        # Скорость и высота
        airspeed = telemetry.get('speed', {}).get('airspeed_indicated', 0)
        altitude = telemetry.get('position', {}).get('altitude_agl', 0)

        # Температура
        temperature = telemetry.get('weather', {}).get('ambient_temperature', 15)

        # Добавление в историю
        self.g_force_history.append(g_force)
        self.bank_angle_history.append(bank_angle)
        self.pitch_angle_history.append(pitch_angle)
        self.wind_velocity_history.append(wind_velocity)
        self.wind_direction_history.append(wind_direction)
        self.airspeed_history.append(airspeed)
        self.altitude_history.append(altitude)
        self.temperature_history.append(temperature)
        self.timestamp_history.append(current_time)

        # Нужно минимум 30 измерений для анализа (3 секунды при 10Hz)
        if len(self.timestamp_history) < 30:
            return None

        # Анализ турбулентности
        alert = self._analyze_turbulence()

        # Обновление текущего предупреждения
        if alert and alert.intensity != 'SMOOTH':
            # Проверка cooldown
            if current_time - self.last_alert_time > self.alert_cooldown:
                self.current_alert = alert
                self.last_alert_time = current_time

                # Обновление статистики
                if alert.g_force_std > self.max_g_force_std:
                    self.max_g_force_std = alert.g_force_std

                logger.warning(
                    f"TURBULENCE DETECTED: {alert.intensity} {alert.type} - "
                    f"G-std: {alert.g_force_std:.3f}, Bank osc: {alert.bank_oscillation:.1f}°"
                )

                # Запись события
                self.turbulence_events.append({
                    'timestamp': current_time,
                    'intensity': alert.intensity,
                    'type': alert.type,
                    'g_force_std': alert.g_force_std
                })

                return alert
        else:
            self.current_alert = None

        return None

    def _analyze_turbulence(self) -> TurbulenceAlert:
        """Анализ турбулентности по всем параметрам"""

        # 1. Анализ G-force (главный индикатор)
        g_force_std = self._calculate_std(self.g_force_history, window=50)

        # 2. Анализ колебаний крена
        bank_oscillation = self._calculate_oscillation(self.bank_angle_history, window=50)

        # 3. Анализ колебаний тангажа
        pitch_oscillation = self._calculate_oscillation(self.pitch_angle_history, window=50)

        # 4. Анализ изменчивости ветра
        wind_variability = self._calculate_wind_variability()

        # 5. Определение интенсивности
        intensity = self._determine_intensity(g_force_std, bank_oscillation, pitch_oscillation)

        # 6. Определение типа турбулентности
        turb_type = self._determine_type(wind_variability, g_force_std)

        # 7. Рекомендация
        recommendation = self._get_recommendation(intensity, turb_type)

        return TurbulenceAlert(
            detected=(intensity != 'SMOOTH'),
            intensity=intensity,
            type=turb_type,
            g_force_std=g_force_std,
            bank_oscillation=bank_oscillation,
            pitch_oscillation=pitch_oscillation,
            wind_variability=wind_variability,
            recommendation=recommendation,
            timestamp=time.time()
        )

    def _calculate_std(self, data: deque, window: int = 50) -> float:
        """Расчёт стандартного отклонения"""
        if len(data) < window:
            window = len(data)

        recent_data = list(data)[-window:]

        if len(recent_data) < 2:
            return 0.0

        mean = sum(recent_data) / len(recent_data)
        variance = sum((x - mean) ** 2 for x in recent_data) / len(recent_data)
        return math.sqrt(variance)

    def _calculate_oscillation(self, data: deque, window: int = 50) -> float:
        """Расчёт амплитуды колебаний (размах)"""
        if len(data) < window:
            window = len(data)

        recent_data = list(data)[-window:]

        if len(recent_data) < 2:
            return 0.0

        return max(recent_data) - min(recent_data)

    def _calculate_wind_variability(self) -> float:
        """Расчёт изменчивости ветра"""
        if len(self.wind_velocity_history) < 20:
            return 0.0

        recent_wind = list(self.wind_velocity_history)[-50:]

        # Максимальное изменение скорости ветра
        wind_changes = [abs(recent_wind[i] - recent_wind[i-1])
                       for i in range(1, len(recent_wind))]

        if not wind_changes:
            return 0.0

        return max(wind_changes)

    def _determine_intensity(self, g_std: float, bank_osc: float, pitch_osc: float) -> str:
        """Определение интенсивности турбулентности"""

        # Комбинированная оценка
        # G-force имеет наибольший вес (60%), углы - 40%
        combined_score = (
            g_std * 0.6 +
            (bank_osc / 20.0) * 0.3 +  # Нормализация к 0-1
            (pitch_osc / 15.0) * 0.1
        )

        if combined_score >= self.severe_turbulence_threshold:
            return 'SEVERE'
        elif combined_score >= self.moderate_turbulence_threshold:
            return 'MODERATE'
        elif combined_score >= self.light_turbulence_threshold:
            return 'LIGHT'
        else:
            return 'SMOOTH'

    def _determine_type(self, wind_var: float, g_std: float) -> str:
        """Определение типа турбулентности"""

        # Если высокая изменчивость ветра - конвективная турбулентность
        if wind_var > 5.0:
            return 'CONVECTIVE'

        # Если низкая высота (из истории) - механическая турбулентность
        if len(self.altitude_history) > 0:
            avg_altitude = sum(list(self.altitude_history)[-20:]) / min(20, len(self.altitude_history))
            if avg_altitude < 1000:  # Ниже 1000 футов
                return 'MECHANICAL'

        # Если колебания G-force без явных изменений ветра - возможно CAT
        if g_std > self.light_turbulence_threshold and wind_var < 2.0:
            return 'CAT'

        return 'UNKNOWN'

    def _get_recommendation(self, intensity: str, turb_type: str) -> str:
        """Получить рекомендацию по действиям"""

        if intensity == 'SEVERE':
            return 'REDUCE SPEED - FASTEN SEATBELTS - CONSIDER DIVERSION'
        elif intensity == 'MODERATE':
            if turb_type == 'CAT':
                return 'REDUCE SPEED - REQUEST ALTITUDE CHANGE'
            else:
                return 'REDUCE SPEED - MAINTAIN CONTROL'
        elif intensity == 'LIGHT':
            return 'MONITOR CONDITIONS - FASTEN SEATBELTS'
        else:
            return 'NORMAL OPERATIONS'

    def get_current_alert(self) -> Optional[TurbulenceAlert]:
        """Получить текущее предупреждение"""
        return self.current_alert

    def reset(self):
        """Сброс детектора"""
        self.g_force_history.clear()
        self.bank_angle_history.clear()
        self.pitch_angle_history.clear()
        self.wind_velocity_history.clear()
        self.wind_direction_history.clear()
        self.airspeed_history.clear()
        self.altitude_history.clear()
        self.temperature_history.clear()
        self.timestamp_history.clear()
        self.current_alert = None
        self.turbulence_events.clear()
        logger.info("Turbulence detector reset")

    def get_statistics(self) -> Dict:
        """Получить статистику"""
        if len(self.timestamp_history) < 2:
            return {}

        # Текущие значения
        current_g_std = self._calculate_std(self.g_force_history, window=50) if len(self.g_force_history) >= 10 else 0
        current_bank_osc = self._calculate_oscillation(self.bank_angle_history, window=50) if len(self.bank_angle_history) >= 10 else 0

        return {
            'samples': len(self.timestamp_history),
            'time_span': self.timestamp_history[-1] - self.timestamp_history[0],
            'current_g_force_std': current_g_std,
            'current_bank_oscillation': current_bank_osc,
            'max_g_force_std': self.max_g_force_std,
            'turbulence_events_count': len(self.turbulence_events),
            'alert_active': self.current_alert is not None,
            'current_intensity': self.current_alert.intensity if self.current_alert else 'SMOOTH'
        }

    def get_intensity_color(self, intensity: str) -> str:
        """Получить цвет для отображения интенсивности"""
        colors = {
            'SMOOTH': 'green',
            'LIGHT': 'yellow',
            'MODERATE': 'orange',
            'SEVERE': 'red'
        }
        return colors.get(intensity, 'gray')
