"""
Тесты для системы детектирования отказов двигателей и асимметричного управления тягой
"""

import unittest
from unittest.mock import Mock
from modules.engine_failure_detector import (
    EngineFailureDetector
)
from modules.autothrottle import AutothrottleController
from modules.control import MSFSControl


class TestEngineFailureDetector(unittest.TestCase):
    """Тесты детектора отказов двигателей"""

    def setUp(self):
        """Инициализация перед каждым тестом"""
        self.detector = EngineFailureDetector()
        self.detector.initialize(number_of_engines=2)

    def test_initialization(self):
        """Тест инициализации детектора"""
        self.assertEqual(self.detector.number_of_engines, 2)
        self.assertEqual(len(self.detector.engines), 2)
        self.assertIn(1, self.detector.engines)
        self.assertIn(2, self.detector.engines)
        self.assertEqual(len(self.detector.active_failures), 0)

    def test_no_failure_normal_operation(self):
        """Тест нормальной работы без отказов"""
        telemetry = {
            'aircraft_info': {'number_of_engines': 2},
            'engines': {
                'engine_1': {
                    'running': True,
                    'n1': 85.0,
                    'n2': 90.0,
                    'egt': 650.0,
                    'fuel_flow': 1500.0,
                    'oil_pressure': 45.0,
                    'throttle': 0.8
                },
                'engine_2': {
                    'running': True,
                    'n1': 85.0,
                    'n2': 90.0,
                    'egt': 650.0,
                    'fuel_flow': 1500.0,
                    'oil_pressure': 45.0,
                    'throttle': 0.8
                }
            }
        }

        self.detector.update_engine_data(telemetry)

        self.assertFalse(self.detector.has_engine_failure())
        self.assertEqual(len(self.detector.get_failed_engines()), 0)
        self.assertEqual(len(self.detector.get_working_engines()), 2)

    def test_engine_not_running_failure(self):
        """Тест отказа двигателя (не работает)"""
        telemetry = {
            'aircraft_info': {'number_of_engines': 2},
            'engines': {
                'engine_1': {
                    'running': False,  # Двигатель не работает
                    'n1': 0.0,
                    'n2': 0.0,
                    'egt': 200.0,
                    'fuel_flow': 0.0,
                    'oil_pressure': 0.0,
                    'throttle': 0.8
                },
                'engine_2': {
                    'running': True,
                    'n1': 85.0,
                    'n2': 90.0,
                    'egt': 650.0,
                    'fuel_flow': 1500.0,
                    'oil_pressure': 45.0,
                    'throttle': 0.8
                }
            }
        }

        # Несколько обновлений для подтверждения отказа
        for _ in range(5):
            self.detector.update_engine_data(telemetry)

        self.assertTrue(self.detector.has_engine_failure())
        self.assertIn(1, self.detector.get_failed_engines())
        self.assertEqual(len(self.detector.get_working_engines()), 1)

    def test_low_n1_failure(self):
        """Тест отказа из-за низкого N1"""
        telemetry = {
            'aircraft_info': {'number_of_engines': 2},
            'engines': {
                'engine_1': {
                    'running': True,
                    'n1': 10.0,  # Слишком низкий N1
                    'n2': 90.0,
                    'egt': 650.0,
                    'fuel_flow': 1500.0,
                    'oil_pressure': 45.0,
                    'throttle': 0.8  # РУД открыт
                },
                'engine_2': {
                    'running': True,
                    'n1': 85.0,
                    'n2': 90.0,
                    'egt': 650.0,
                    'fuel_flow': 1500.0,
                    'oil_pressure': 45.0,
                    'throttle': 0.8
                }
            }
        }

        # Несколько обновлений для подтверждения
        for _ in range(5):
            self.detector.update_engine_data(telemetry)

        self.assertTrue(self.detector.has_engine_failure())
        self.assertIn(1, self.detector.get_failed_engines())

    def test_overheat_failure(self):
        """Тест отказа из-за перегрева"""
        telemetry = {
            'aircraft_info': {'number_of_engines': 2},
            'engines': {
                'engine_1': {
                    'running': True,
                    'n1': 85.0,
                    'n2': 90.0,
                    'egt': 950.0,  # Перегрев
                    'fuel_flow': 1500.0,
                    'oil_pressure': 45.0,
                    'throttle': 0.8
                },
                'engine_2': {
                    'running': True,
                    'n1': 85.0,
                    'n2': 90.0,
                    'egt': 650.0,
                    'fuel_flow': 1500.0,
                    'oil_pressure': 45.0,
                    'throttle': 0.8
                }
            }
        }

        for _ in range(5):
            self.detector.update_engine_data(telemetry)

        self.assertTrue(self.detector.has_engine_failure())
        self.assertIn(1, self.detector.get_failed_engines())

    def test_asymmetric_thrust_correction_single_failure(self):
        """Тест расчёта асимметричной тяги при отказе одного двигателя"""
        # Симулируем отказ двигателя 1
        self.detector.engines[1].failed = True
        self.detector.active_failures = [1]

        corrections = self.detector.calculate_asymmetric_thrust_correction()

        # Двигатель 1 должен быть на 0%
        self.assertEqual(corrections['engine_1'], 0.0)

        # Двигатель 2 должен компенсировать (2 двигателя / 1 работающий = 2.0, но ограничено до 1.0)
        self.assertEqual(corrections['engine_2'], 1.0)

    def test_asymmetric_thrust_correction_no_failure(self):
        """Тест расчёта тяги без отказов"""
        corrections = self.detector.calculate_asymmetric_thrust_correction()

        # Все двигатели на 100%
        self.assertEqual(corrections['engine_1'], 1.0)
        self.assertEqual(corrections['engine_2'], 1.0)

    def test_four_engine_aircraft_two_failures(self):
        """Тест 4-двигательного самолёта с отказом двух двигателей"""
        detector = EngineFailureDetector()
        detector.initialize(number_of_engines=4)

        # Отказ двигателей 2 и 4
        detector.engines[2].failed = True
        detector.engines[4].failed = True
        detector.active_failures = [2, 4]

        corrections = detector.calculate_asymmetric_thrust_correction()

        # Отказавшие двигатели
        self.assertEqual(corrections['engine_2'], 0.0)
        self.assertEqual(corrections['engine_4'], 0.0)

        # Работающие двигатели (4 / 2 = 2.0, но ограничено до 1.0)
        self.assertEqual(corrections['engine_1'], 1.0)
        self.assertEqual(corrections['engine_3'], 1.0)


class TestMSFSControlAsymmetric(unittest.TestCase):
    """Тесты асимметричного управления тягой"""

    def setUp(self):
        """Инициализация перед каждым тестом"""
        self.mock_ae = Mock()
        self.control = MSFSControl(self.mock_ae)

    def test_set_throttle_symmetric(self):
        """Тест симметричной установки тяги"""
        self.control.set_throttle(0.75)

        self.mock_ae.event.assert_called_once_with("THROTTLE_SET", 12288)  # 0.75 * 16384

    def test_set_throttle_engine_individual(self):
        """Тест установки тяги на отдельный двигатель"""
        self.control.set_throttle_engine(1, 0.5)

        self.mock_ae.event.assert_called_once_with("THROTTLE1_SET", 8192)  # 0.5 * 16384

    def test_set_throttle_asymmetric(self):
        """Тест асимметричной установки тяги"""
        throttle_values = {
            1: 0.8,
            2: 0.0,  # Отказавший двигатель
            3: 0.8,
            4: 0.0   # Отказавший двигатель
        }

        self.control.set_throttle_asymmetric(throttle_values)

        # Проверяем что были вызваны команды для всех двигателей
        self.assertEqual(self.mock_ae.event.call_count, 4)

    def test_invalid_engine_index(self):
        """Тест некорректного индекса двигателя"""
        self.control.set_throttle_engine(5, 0.5)  # Индекс 5 недопустим

        # Не должно быть вызовов
        self.mock_ae.event.assert_not_called()


class TestAutothrottleWithFailureDetector(unittest.TestCase):
    """Тесты интеграции автомата тяги с детектором отказов"""

    def setUp(self):
        """Инициализация перед каждым тестом"""
        self.detector = EngineFailureDetector()
        self.detector.initialize(number_of_engines=2)
        self.autothrottle = AutothrottleController(engine_failure_detector=self.detector)
        self.autothrottle.activate()

    def test_normal_operation_symmetric(self):
        """Тест нормальной работы в симметричном режиме"""
        telemetry = {
            'speed': {'airspeed_indicated': 140},
            'attitude': {'bank': 0},
            'aircraft_info': {'number_of_engines': 2},
            'engines': {
                'engine_1': {'running': True, 'n1': 85.0, 'n2': 90.0, 'egt': 650.0,
                           'fuel_flow': 1500.0, 'oil_pressure': 45.0, 'throttle': 0.8},
                'engine_2': {'running': True, 'n1': 85.0, 'n2': 90.0, 'egt': 650.0,
                           'fuel_flow': 1500.0, 'oil_pressure': 45.0, 'throttle': 0.8}
            }
        }

        wind_data = {'headwind': 10, 'crosswind': 5}

        result = self.autothrottle.calculate_throttle(telemetry, 150, wind_data, 60000)

        self.assertTrue(result['active'])
        self.assertFalse(result['asymmetric_mode'])
        self.assertIsNone(result['engine_throttles'])
        self.assertFalse(result['has_engine_failure'])

    def test_engine_failure_switches_to_asymmetric(self):
        """Тест переключения на асимметричный режим при отказе двигателя"""
        # Первый вызов - нормальная работа
        telemetry_normal = {
            'speed': {'airspeed_indicated': 140},
            'attitude': {'bank': 0},
            'aircraft_info': {'number_of_engines': 2},
            'engines': {
                'engine_1': {'running': True, 'n1': 85.0, 'n2': 90.0, 'egt': 650.0,
                           'fuel_flow': 1500.0, 'oil_pressure': 45.0, 'throttle': 0.8},
                'engine_2': {'running': True, 'n1': 85.0, 'n2': 90.0, 'egt': 650.0,
                           'fuel_flow': 1500.0, 'oil_pressure': 45.0, 'throttle': 0.8}
            }
        }

        wind_data = {'headwind': 10, 'crosswind': 5}
        result1 = self.autothrottle.calculate_throttle(telemetry_normal, 150, wind_data, 60000)
        self.assertFalse(result1['asymmetric_mode'])

        # Симулируем отказ двигателя 1
        telemetry_failure = {
            'speed': {'airspeed_indicated': 135},  # Скорость упала
            'attitude': {'bank': 0},
            'aircraft_info': {'number_of_engines': 2},
            'engines': {
                'engine_1': {'running': False, 'n1': 0.0, 'n2': 0.0, 'egt': 200.0,
                           'fuel_flow': 0.0, 'oil_pressure': 0.0, 'throttle': 0.8},
                'engine_2': {'running': True, 'n1': 95.0, 'n2': 98.0, 'egt': 700.0,
                           'fuel_flow': 2000.0, 'oil_pressure': 50.0, 'throttle': 1.0}
            }
        }

        # Несколько вызовов для подтверждения отказа
        for _ in range(5):
            result = self.autothrottle.calculate_throttle(telemetry_failure, 150, wind_data, 60000)

        # Проверяем переключение на асимметричный режим
        self.assertTrue(result['asymmetric_mode'])
        self.assertTrue(result['has_engine_failure'])
        self.assertIsNotNone(result['engine_throttles'])
        self.assertEqual(result['engine_throttles'][1], 0.0)  # Отказавший двигатель
        self.assertGreater(result['engine_throttles'][2], 0.0)  # Работающий двигатель


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestEngineFailureDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestMSFSControlAsymmetric))
    suite.addTests(loader.loadTestsFromTestCase(TestAutothrottleWithFailureDetector))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
