"""
Тесты для системы компенсации асимметричной тяги рулём направления
"""

import unittest
from unittest.mock import Mock
from modules.rudder_compensation import (
    RudderCompensation
)
from modules.control import MSFSControl


class TestRudderCompensation(unittest.TestCase):
    """Тесты компенсатора рулём направления"""

    def setUp(self):
        """Инициализация перед каждым тестом"""
        self.compensator = RudderCompensation()
        self.compensator.set_aircraft_geometry(engine_arm=10.0, number_of_engines=2)
        self.compensator.activate()

    def test_initialization(self):
        """Тест инициализации компенсатора"""
        self.assertEqual(self.compensator.number_of_engines, 2)
        self.assertEqual(self.compensator.engine_arm, 10.0)
        self.assertTrue(self.compensator.active)
        self.assertEqual(self.compensator.current_rudder, 0.0)

    def test_no_asymmetry_no_compensation(self):
        """Тест отсутствия компенсации при симметричной тяге"""
        engine_throttles = {1: 0.8, 2: 0.8}
        current_speed = 140.0

        rudder = self.compensator.calculate_rudder_input(engine_throttles, current_speed)

        self.assertEqual(rudder, 0.0)

    def test_right_engine_failure_left_rudder(self):
        """Тест компенсации при отказе правого двигателя (нужен левый руль)"""
        # Правый двигатель отказал
        engine_throttles = {1: 0.8, 2: 0.0}
        current_speed = 140.0

        rudder = self.compensator.calculate_rudder_input(engine_throttles, current_speed)

        # Больше тяги слева → нужен правый руль (отрицательное значение)
        self.assertLess(rudder, 0.0)
        self.assertGreaterEqual(rudder, -1.0)

    def test_left_engine_failure_right_rudder(self):
        """Тест компенсации при отказе левого двигателя (нужен правый руль)"""
        # Левый двигатель отказал
        engine_throttles = {1: 0.0, 2: 0.8}
        current_speed = 140.0

        rudder = self.compensator.calculate_rudder_input(engine_throttles, current_speed)

        # Больше тяги справа → нужен левый руль (положительное значение)
        self.assertGreater(rudder, 0.0)
        self.assertLessEqual(rudder, 1.0)

    def test_speed_correction_low_speed(self):
        """Тест увеличения компенсации при низкой скорости"""
        engine_throttles = {1: 0.0, 2: 0.8}

        # Высокая скорость
        rudder_high_speed = self.compensator.calculate_rudder_input(engine_throttles, 180.0)

        # Низкая скорость
        rudder_low_speed = self.compensator.calculate_rudder_input(engine_throttles, 100.0)

        # При низкой скорости требуется больше руля
        self.assertGreater(abs(rudder_low_speed), abs(rudder_high_speed))

    def test_deadzone(self):
        """Тест мёртвой зоны - малая асимметрия игнорируется"""
        # Малая асимметрия (< 5%)
        engine_throttles = {1: 0.80, 2: 0.82}
        current_speed = 140.0

        rudder = self.compensator.calculate_rudder_input(engine_throttles, current_speed)

        self.assertEqual(rudder, 0.0)

    def test_four_engine_asymmetry(self):
        """Тест компенсации для 4-двигательного самолёта"""
        compensator = RudderCompensation()
        compensator.set_aircraft_geometry(engine_arm=15.0, number_of_engines=4)
        compensator.activate()

        # Отказ двигателей 2 и 4 (один левый внутренний, один правый внешний)
        engine_throttles = {1: 0.8, 2: 0.0, 3: 0.8, 4: 0.0}
        current_speed = 140.0

        rudder = compensator.calculate_rudder_input(engine_throttles, current_speed)

        # Должна быть компенсация (внешний двигатель имеет больший момент)
        self.assertNotEqual(rudder, 0.0)

    def test_three_engine_asymmetry(self):
        """Тест компенсации для 3-двигательного самолёта"""
        compensator = RudderCompensation()
        compensator.set_aircraft_geometry(engine_arm=12.0, number_of_engines=3)
        compensator.activate()

        # Отказ левого двигателя, центральный и правый работают
        engine_throttles = {1: 0.0, 2: 0.8, 3: 0.8}
        current_speed = 140.0

        rudder = compensator.calculate_rudder_input(engine_throttles, current_speed)

        # Больше тяги справа → нужен левый руль
        self.assertGreater(rudder, 0.0)

    def test_max_rudder_limit(self):
        """Тест ограничения максимального отклонения руля"""
        # Экстремальная асимметрия
        engine_throttles = {1: 0.0, 2: 1.0}
        current_speed = 80.0  # Низкая скорость

        rudder = self.compensator.calculate_rudder_input(engine_throttles, current_speed)

        # Не должно превышать максимум
        self.assertLessEqual(abs(rudder), 1.0)

    def test_rate_limiting(self):
        """Тест ограничения скорости изменения руля"""
        engine_throttles = {1: 0.0, 2: 1.0}
        current_speed = 140.0

        # Первый вызов
        rudder1 = self.compensator.calculate_rudder_input(
            engine_throttles, current_speed, current_rudder=0.0
        )

        # Второй вызов с тем же входом
        rudder2 = self.compensator.calculate_rudder_input(
            engine_throttles, current_speed, current_rudder=rudder1
        )

        # Изменение должно быть ограничено
        change = abs(rudder2 - rudder1)
        self.assertLessEqual(change, self.compensator.config.max_rudder_rate)

    def test_apply_compensation_with_control(self):
        """Тест применения компенсации через MSFSControl"""
        mock_ae = Mock()
        control = MSFSControl(mock_ae)

        engine_throttles = {1: 0.0, 2: 0.8}
        current_speed = 140.0

        success = self.compensator.apply_compensation(
            engine_throttles,
            current_speed,
            control
        )

        self.assertTrue(success)
        self.assertGreater(self.compensator.total_compensations, 0)
        # Проверяем что был вызван set_rudder
        mock_ae.event.assert_called()

    def test_inactive_compensator(self):
        """Тест что неактивный компенсатор не применяет коррекцию"""
        self.compensator.deactivate()

        engine_throttles = {1: 0.0, 2: 0.8}
        current_speed = 140.0

        rudder = self.compensator.calculate_rudder_input(engine_throttles, current_speed)

        self.assertEqual(rudder, 0.0)

    def test_calculate_thrust_asymmetry_two_engines(self):
        """Тест расчёта асимметрии для 2-двигательного самолёта"""
        # Правый двигатель сильнее
        engine_throttles = {1: 0.5, 2: 0.8}
        asymmetry = self.compensator.calculate_thrust_asymmetry(engine_throttles)

        # Положительная асимметрия (больше справа)
        self.assertAlmostEqual(asymmetry, 0.3, places=2)

    def test_calculate_thrust_asymmetry_four_engines(self):
        """Тест расчёта асимметрии для 4-двигательного самолёта"""
        compensator = RudderCompensation()
        compensator.set_aircraft_geometry(engine_arm=15.0, number_of_engines=4)

        # Внешние двигатели имеют больший вес
        engine_throttles = {1: 1.0, 2: 0.5, 3: 0.5, 4: 0.0}
        asymmetry = compensator.calculate_thrust_asymmetry(engine_throttles)

        # Должна быть отрицательная асимметрия (больше слева)
        self.assertLess(asymmetry, 0.0)


class TestRudderCompensationIntegration(unittest.TestCase):
    """Интеграционные тесты компенсации руля"""

    def test_full_compensation_cycle(self):
        """Тест полного цикла компенсации"""
        mock_ae = Mock()
        control = MSFSControl(mock_ae)
        compensator = RudderCompensation()
        compensator.set_aircraft_geometry(engine_arm=10.0, number_of_engines=2)
        compensator.activate()

        # Симуляция отказа правого двигателя
        engine_throttles = {1: 0.8, 2: 0.0}
        current_speed = 140.0

        # Применяем компенсацию несколько раз
        for _ in range(5):
            compensator.apply_compensation(engine_throttles, current_speed, control)

        # Проверяем что руль был установлен
        self.assertGreater(compensator.total_compensations, 0)
        self.assertNotEqual(compensator.current_rudder, 0.0)

        # Проверяем что вызывался RUDDER_SET
        calls = [call for call in mock_ae.event.call_args_list if call[0][0] == "RUDDER_SET"]
        self.assertGreater(len(calls), 0)


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestRudderCompensation))
    suite.addTests(loader.loadTestsFromTestCase(TestRudderCompensationIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
