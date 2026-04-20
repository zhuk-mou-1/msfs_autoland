"""
Модуль управления через виртуальный джойстик (vJoy)
Обеспечивает прямое управление рулями самолёта
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pyvjoy
    VJOY_AVAILABLE = True
except ImportError:
    VJOY_AVAILABLE = False
    logger.warning("pyvjoy not installed. Virtual joystick control disabled.")


class VirtualJoystick:
    """Класс для управления через виртуальный джойстик vJoy"""

    def __init__(self, device_id: int = 1):
        """
        Инициализация виртуального джойстика

        Args:
            device_id: ID устройства vJoy (обычно 1)
        """
        self.device_id = device_id
        self.joystick: Optional[pyvjoy.VJoyDevice] = None
        self.enabled = False

        # Диапазоны осей (0-32768, центр = 16384)
        self.axis_min = 0x1
        self.axis_max = 0x8000
        self.axis_center = 0x4000

        # Текущие значения осей для мониторинга
        self.current_values = {
            'aileron': 0.0,
            'elevator': 0.0,
            'rudder': 0.0,
            'throttle': 0.0
        }

        # Счётчики команд
        self.command_count = {
            'aileron': 0,
            'elevator': 0,
            'rudder': 0,
            'throttle': 0
        }

    def connect(self) -> bool:
        """Подключение к vJoy устройству"""
        if not VJOY_AVAILABLE:
            logger.error("pyvjoy library not available. Install with: pip install pyvjoy")
            return False

        try:
            self.joystick = pyvjoy.VJoyDevice(self.device_id)
            self.enabled = True
            logger.info("Connected to vJoy device %s", self.device_id)

            # Центрирование всех осей
            self.center_all_axes()
            return True
        except Exception as e:
            logger.error("Failed to connect to vJoy: %s", e)
            logger.error("Make sure vJoy driver is installed: https://sourceforge.net/projects/vjoystick/")
            self.enabled = False
            return False

    def disconnect(self):
        """Отключение от vJoy"""
        if self.joystick:
            self.center_all_axes()
            self.joystick = None
            self.enabled = False
            logger.info("Disconnected from vJoy")

    def center_all_axes(self):
        """Центрирование всех осей"""
        if not self.enabled:
            return

        try:
            self.joystick.set_axis(pyvjoy.HID_USAGE_X, self.axis_center)  # Aileron
            self.joystick.set_axis(pyvjoy.HID_USAGE_Y, self.axis_center)  # Elevator
            self.joystick.set_axis(pyvjoy.HID_USAGE_Z, self.axis_center)  # Rudder
            self.joystick.set_axis(pyvjoy.HID_USAGE_RZ, self.axis_center) # Throttle
            logger.debug("All axes centered")
        except Exception as e:
            logger.error("Error centering axes: %s", e)

    def set_aileron(self, value: float):
        """
        Установить элероны (крен)

        Args:
            value: -1.0 (полный левый крен) до +1.0 (полный правый крен)
        """
        if not self.enabled:
            return

        # Преобразование -1.0..+1.0 в 0..32768
        axis_value = int(self.axis_center + (value * (self.axis_max - self.axis_center)))
        axis_value = max(self.axis_min, min(self.axis_max, axis_value))

        try:
            self.joystick.set_axis(pyvjoy.HID_USAGE_X, axis_value)
            self.current_values['aileron'] = value
            self.command_count['aileron'] += 1
            logger.debug("Aileron set to %s", value)
        except Exception as e:
            logger.error("Error setting aileron: %s", e)

    def set_elevator(self, value: float):
        """
        Установить руль высоты (тангаж)

        Args:
            value: -1.0 (полный вниз) до +1.0 (полный вверх)
        """
        if not self.enabled:
            return

        # Инвертируем, так как в MSFS вверх = отрицательное значение
        axis_value = int(self.axis_center - (value * (self.axis_max - self.axis_center)))
        axis_value = max(self.axis_min, min(self.axis_max, axis_value))

        try:
            self.joystick.set_axis(pyvjoy.HID_USAGE_Y, axis_value)
            self.current_values['elevator'] = value
            self.command_count['elevator'] += 1
            logger.debug("Elevator set to %s", value)
        except Exception as e:
            logger.error("Error setting elevator: %s", e)

    def set_rudder(self, value: float):
        """
        Установить руль направления (рысканье)

        Args:
            value: -1.0 (полный влево) до +1.0 (полный вправо)
        """
        if not self.enabled:
            return

        axis_value = int(self.axis_center + (value * (self.axis_max - self.axis_center)))
        axis_value = max(self.axis_min, min(self.axis_max, axis_value))

        try:
            self.joystick.set_axis(pyvjoy.HID_USAGE_Z, axis_value)
            self.current_values['rudder'] = value
            self.command_count['rudder'] += 1
            logger.debug("Rudder set to %s", value)
        except Exception as e:
            logger.error("Error setting rudder: %s", e)

    def get_status(self) -> dict:
        """
        Получить текущий статус vJoy для мониторинга

        Returns:
            Dict с текущими значениями осей и статистикой
        """
        return {
            'enabled': self.enabled,
            'device_id': self.device_id,
            'current_values': self.current_values.copy(),
            'command_count': self.command_count.copy(),
            'total_commands': sum(self.command_count.values())
        }

    def set_throttle(self, value: float):
        """
        Установить газ

        Args:
            value: 0.0 (минимум) до 1.0 (максимум)
        """
        if not self.enabled:
            return

        # Throttle от минимума до максимума
        axis_value = int(self.axis_min + (value * (self.axis_max - self.axis_min)))
        axis_value = max(self.axis_min, min(self.axis_max, axis_value))

        try:
            self.joystick.set_axis(pyvjoy.HID_USAGE_RZ, axis_value)
            logger.debug("Throttle set to %s", value)
        except Exception as e:
            logger.error("Error setting throttle: %s", e)

    def apply_control_inputs(self, aileron: float = 0.0, elevator: float = 0.0,
                            rudder: float = 0.0, throttle: Optional[float] = None):
        """
        Применить все управляющие входы одновременно

        Args:
            aileron: Крен (-1.0 до +1.0)
            elevator: Тангаж (-1.0 до +1.0)
            rudder: Рысканье (-1.0 до +1.0)
            throttle: Газ (0.0 до 1.0), None = не изменять
        """
        if not self.enabled:
            return

        self.set_aileron(aileron)
        self.set_elevator(elevator)
        self.set_rudder(rudder)

        if throttle is not None:
            self.set_throttle(throttle)

    def calculate_bank_correction(self, current_bank: float, target_bank: float,
                                  max_input: float = 0.3) -> float:
        """
        Расчёт коррекции элеронов для достижения целевого крена

        Args:
            current_bank: Текущий крен (градусы)
            target_bank: Целевой крен (градусы)
            max_input: Максимальный вход элеронов (0.0-1.0)

        Returns:
            Значение для элеронов (-1.0 до +1.0)
        """
        error = target_bank - current_bank

        # Пропорциональный контроллер
        # 1° ошибки = 0.01 входа
        aileron_input = error * 0.01

        # Ограничение
        aileron_input = max(-max_input, min(max_input, aileron_input))

        return aileron_input

    def calculate_pitch_correction(self, current_pitch: float, target_pitch: float,
                                   max_input: float = 0.2) -> float:
        """
        Расчёт коррекции руля высоты для достижения целевого тангажа

        Args:
            current_pitch: Текущий тангаж (градусы)
            target_pitch: Целевой тангаж (градусы)
            max_input: Максимальный вход руля высоты (0.0-1.0)

        Returns:
            Значение для руля высоты (-1.0 до +1.0)
        """
        error = target_pitch - current_pitch

        # Пропорциональный контроллер
        elevator_input = error * 0.02

        # Ограничение
        elevator_input = max(-max_input, min(max_input, elevator_input))

        return elevator_input

    def calculate_heading_correction(self, current_heading: float, target_heading: float,
                                    current_bank: float, max_bank: float = 15.0) -> float:
        """
        Расчёт целевого крена для коррекции курса

        Args:
            current_heading: Текущий курс (градусы)
            target_heading: Целевой курс (градусы)
            current_bank: Текущий крен (градусы)
            max_bank: Максимальный крен (градусы)

        Returns:
            Целевой крен (градусы)
        """
        # Расчёт ошибки курса (-180 до +180)
        heading_error = target_heading - current_heading
        while heading_error > 180:
            heading_error -= 360
        while heading_error < -180:
            heading_error += 360

        # Целевой крен пропорционален ошибке курса
        # 10° ошибки = 5° крена
        target_bank = heading_error * 0.5

        # Ограничение крена
        target_bank = max(-max_bank, min(max_bank, target_bank))

        return target_bank
