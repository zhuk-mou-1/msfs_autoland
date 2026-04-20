"""
Детектор сдвига ветра (Wind Shear Detector)
Обнаруживает опасные изменения ветра во время захода на посадку
"""

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional

from .thresholds_config import get_thresholds

logger = logging.getLogger(__name__)


@dataclass
class WindShearAlert:
    """Предупреждение о сдвиге ветра"""
    detected: bool
    severity: str  # 'NONE', 'CAUTION', 'WARNING', 'CRITICAL'
    type: str  # 'HEADWIND_LOSS', 'TAILWIND_GAIN', 'CROSSWIND_CHANGE', 'DOWNDRAFT', 'UPDRAFT'
    magnitude: float  # Величина изменения
    recommendation: str  # Рекомендация пилоту
    timestamp: float


class WindShearDetector:
    """Детектор сдвига ветра"""

    def __init__(self, history_size: int = 20):
        """
        Args:
            history_size: Размер истории для анализа (количество измерений)
        """
        self.history_size = history_size

        # История параметров
        self.wind_speed_history = deque(maxlen=history_size)
        self.wind_direction_history = deque(maxlen=history_size)
        self.headwind_history = deque(maxlen=history_size)
        self.crosswind_history = deque(maxlen=history_size)
        self.airspeed_history = deque(maxlen=history_size)
        self.vertical_speed_history = deque(maxlen=history_size)
        self.altitude_history = deque(maxlen=history_size)
        self.timestamp_history = deque(maxlen=history_size)

        # Пороги обнаружения из централизованного конфига
        config = get_thresholds().wind_shear
        self.headwind_loss_threshold = config.headwind_loss_threshold
        self.crosswind_change_threshold = config.crosswind_change_threshold
        self.vertical_speed_change_threshold = config.vertical_speed_change_threshold
        self.airspeed_loss_threshold = config.airspeed_loss_threshold

        # Текущее предупреждение
        self.current_alert: Optional[WindShearAlert] = None
        self.last_alert_time = 0
        self.alert_cooldown = 5.0  # секунды между повторными предупреждениями

    def update(self, telemetry: Dict, wind_data: Dict) -> Optional[WindShearAlert]:
        """
        Обновить данные и проверить наличие сдвига ветра

        Args:
            telemetry: Телеметрия самолёта
            wind_data: Данные о ветре

        Returns:
            WindShearAlert если обнаружен сдвиг, иначе None
        """
        current_time = time.time()

        # Извлечение данных
        wind_speed = telemetry.get('weather', {}).get('ambient_wind_velocity', 0)
        wind_direction = telemetry.get('weather', {}).get('ambient_wind_direction', 0)
        headwind = wind_data.get('headwind', 0)
        crosswind = wind_data.get('crosswind', 0)
        airspeed = telemetry.get('speed', {}).get('airspeed_indicated', 0)
        vertical_speed = telemetry.get('speed', {}).get('vertical_speed', 0)
        altitude = telemetry.get('position', {}).get('altitude_agl', 0)

        # Добавление в историю
        self.wind_speed_history.append(wind_speed)
        self.wind_direction_history.append(wind_direction)
        self.headwind_history.append(headwind)
        self.crosswind_history.append(crosswind)
        self.airspeed_history.append(airspeed)
        self.vertical_speed_history.append(vertical_speed)
        self.altitude_history.append(altitude)
        self.timestamp_history.append(current_time)

        # Нужно минимум 10 измерений для анализа
        if len(self.timestamp_history) < 10:
            return None

        # Проверка различных типов сдвига ветра
        alert = None

        # 1. Потеря встречного ветра (опасно!)
        headwind_loss_alert = self._check_headwind_loss()
        if headwind_loss_alert:
            alert = headwind_loss_alert

        # 2. Резкое изменение бокового ветра
        if not alert:
            crosswind_alert = self._check_crosswind_change()
            if crosswind_alert:
                alert = crosswind_alert

        # 3. Нисходящий поток (downdraft)
        if not alert:
            downdraft_alert = self._check_downdraft()
            if downdraft_alert:
                alert = downdraft_alert

        # 4. Восходящий поток (updraft)
        if not alert:
            updraft_alert = self._check_updraft()
            if updraft_alert:
                alert = updraft_alert

        # 5. Неожиданная потеря скорости
        if not alert:
            airspeed_loss_alert = self._check_airspeed_loss()
            if airspeed_loss_alert:
                alert = airspeed_loss_alert

        # Обновление текущего предупреждения
        if alert:
            # Проверка cooldown
            if current_time - self.last_alert_time > self.alert_cooldown:
                self.current_alert = alert
                self.last_alert_time = current_time
                logger.warning("WIND SHEAR DETECTED: %s - %s - %s", alert.type, alert.severity, alert.recommendation)
                return alert
        else:
            self.current_alert = None

        return None

    def _check_headwind_loss(self) -> Optional[WindShearAlert]:
        """Проверка потери встречного ветра"""
        if len(self.headwind_history) < 10:
            return None

        # Сравнение текущего значения со средним за последние 5 секунд
        recent_headwind = list(self.headwind_history)[-10:]
        recent_times = list(self.timestamp_history)[-10:]

        time_span = recent_times[-1] - recent_times[0]
        if time_span < 3.0:
            return None

        # Изменение встречного ветра
        headwind_change = recent_headwind[-1] - recent_headwind[0]

        # Потеря встречного ветра (отрицательное изменение)
        if headwind_change < -self.headwind_loss_threshold:
            severity = 'CRITICAL' if abs(headwind_change) > 15 else 'WARNING'

            return WindShearAlert(
                detected=True,
                severity=severity,
                type='HEADWIND_LOSS',
                magnitude=abs(headwind_change),
                recommendation='INCREASE THRUST - GO AROUND IF NECESSARY',
                timestamp=time.time()
            )

        return None

    def _check_crosswind_change(self) -> Optional[WindShearAlert]:
        """Проверка резкого изменения бокового ветра"""
        if len(self.crosswind_history) < 10:
            return None

        recent_crosswind = list(self.crosswind_history)[-10:]
        recent_times = list(self.timestamp_history)[-10:]

        time_span = recent_times[-1] - recent_times[0]
        if time_span < 3.0:
            return None

        # Изменение бокового ветра
        crosswind_change = abs(recent_crosswind[-1] - recent_crosswind[0])

        if crosswind_change > self.crosswind_change_threshold:
            severity = 'WARNING' if crosswind_change < 20 else 'CRITICAL'

            return WindShearAlert(
                detected=True,
                severity=severity,
                type='CROSSWIND_CHANGE',
                magnitude=crosswind_change,
                recommendation='ADJUST CRAB ANGLE - MONITOR DRIFT',
                timestamp=time.time()
            )

        return None

    def _check_downdraft(self) -> Optional[WindShearAlert]:
        """Проверка нисходящего потока"""
        if len(self.vertical_speed_history) < 10:
            return None

        recent_vs = list(self.vertical_speed_history)[-10:]
        recent_times = list(self.timestamp_history)[-10:]

        time_span = recent_times[-1] - recent_times[0]
        if time_span < 2.0:
            return None

        # Резкое увеличение скорости снижения
        vs_change = recent_vs[-1] - recent_vs[0]

        # Если вертикальная скорость стала более отрицательной (быстрее снижение)
        if vs_change < -self.vertical_speed_change_threshold:
            severity = 'CRITICAL' if abs(vs_change) > 1000 else 'WARNING'

            return WindShearAlert(
                detected=True,
                severity=severity,
                type='DOWNDRAFT',
                magnitude=abs(vs_change),
                recommendation='INCREASE PITCH - INCREASE THRUST',
                timestamp=time.time()
            )

        return None

    def _check_updraft(self) -> Optional[WindShearAlert]:
        """Проверка восходящего потока"""
        if len(self.vertical_speed_history) < 10:
            return None

        recent_vs = list(self.vertical_speed_history)[-10:]
        recent_times = list(self.timestamp_history)[-10:]

        time_span = recent_times[-1] - recent_times[0]
        if time_span < 2.0:
            return None

        # Резкое уменьшение скорости снижения или набор высоты
        vs_change = recent_vs[-1] - recent_vs[0]

        # Если вертикальная скорость стала менее отрицательной или положительной
        if vs_change > self.vertical_speed_change_threshold:
            severity = 'CAUTION'

            return WindShearAlert(
                detected=True,
                severity=severity,
                type='UPDRAFT',
                magnitude=abs(vs_change),
                recommendation='REDUCE PITCH - MONITOR ALTITUDE',
                timestamp=time.time()
            )

        return None

    def _check_airspeed_loss(self) -> Optional[WindShearAlert]:
        """Проверка неожиданной потери скорости"""
        if len(self.airspeed_history) < 10:
            return None

        recent_ias = list(self.airspeed_history)[-10:]
        recent_times = list(self.timestamp_history)[-10:]

        time_span = recent_times[-1] - recent_times[0]
        if time_span < 2.0:
            return None

        # Потеря скорости
        ias_change = recent_ias[-1] - recent_ias[0]

        if ias_change < -self.airspeed_loss_threshold:
            severity = 'WARNING' if abs(ias_change) < 15 else 'CRITICAL'

            return WindShearAlert(
                detected=True,
                severity=severity,
                type='AIRSPEED_LOSS',
                magnitude=abs(ias_change),
                recommendation='INCREASE THRUST IMMEDIATELY',
                timestamp=time.time()
            )

        return None

    def get_current_alert(self) -> Optional[WindShearAlert]:
        """Получить текущее предупреждение"""
        return self.current_alert

    def reset(self):
        """Сброс детектора"""
        self.wind_speed_history.clear()
        self.wind_direction_history.clear()
        self.headwind_history.clear()
        self.crosswind_history.clear()
        self.airspeed_history.clear()
        self.vertical_speed_history.clear()
        self.altitude_history.clear()
        self.timestamp_history.clear()
        self.current_alert = None
        logger.info("Wind shear detector reset")

    def get_statistics(self) -> Dict:
        """Получить статистику"""
        if len(self.timestamp_history) < 2:
            return {}

        return {
            'samples': len(self.timestamp_history),
            'time_span': self.timestamp_history[-1] - self.timestamp_history[0],
            'current_headwind': self.headwind_history[-1] if self.headwind_history else 0,
            'current_crosswind': self.crosswind_history[-1] if self.crosswind_history else 0,
            'headwind_trend': self._calculate_trend(self.headwind_history),
            'crosswind_trend': self._calculate_trend(self.crosswind_history),
            'alert_active': self.current_alert is not None
        }

    @staticmethod
    def _calculate_trend(data: deque) -> str:
        """Расчёт тренда (увеличение/уменьшение/стабильно)"""
        if len(data) < 5:
            return 'UNKNOWN'

        recent = list(data)[-5:]
        change = recent[-1] - recent[0]

        if abs(change) < 2.0:
            return 'STABLE'
        elif change > 0:
            return 'INCREASING'
        else:
            return 'DECREASING'
