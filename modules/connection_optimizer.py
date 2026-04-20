"""
Оптимизатор подключения к самолёту
Автоматически определяет лучший метод взаимодействия: SimConnect, WASM, L:Vars
"""

import logging
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ConnectionMethod(Enum):
    """Методы подключения к самолёту"""
    SIMCONNECT = "SimConnect"
    WASM = "WASM"
    LVARS = "L:Vars"


class TestResult(Enum):
    """Результат теста"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass
class MethodPerformance:
    """Метрики производительности метода"""
    method: str
    available: bool
    read_time_ms: float
    write_time_ms: float
    reliability: float  # 0.0 - 1.0
    test_result: str
    error_message: Optional[str] = None

    def get_score(self) -> float:
        """
        Вычисление общего балла метода

        Returns:
            Балл от 0 до 100
        """
        if not self.available:
            return 0.0

        # Веса факторов
        SPEED_WEIGHT = 0.4
        RELIABILITY_WEIGHT = 0.6

        # Нормализация скорости (чем меньше время, тем лучше)
        # Предполагаем что 100ms - это плохо (0 баллов), 1ms - отлично (100 баллов)
        avg_time = (self.read_time_ms + self.write_time_ms) / 2
        speed_score = max(0, min(100, 100 - avg_time))

        # Надёжность уже в процентах
        reliability_score = self.reliability * 100

        # Итоговый балл
        total_score = (speed_score * SPEED_WEIGHT +
                      reliability_score * RELIABILITY_WEIGHT)

        return total_score


class ConnectionOptimizer:
    """Оптимизатор подключения к самолёту"""

    def __init__(self, telemetry, control, wasm_interface=None):
        """
        Args:
            telemetry: Экземпляр MSFSTelemetry
            control: Экземпляр MSFSControl
            wasm_interface: Экземпляр MobiFlightWASM (опционально)
        """
        self.telemetry = telemetry
        self.control = control
        self.wasm = wasm_interface

        self.test_results: Dict[str, MethodPerformance] = {}
        self.recommended_method: Optional[str] = None

        # Параметры тестирования
        self.test_iterations = 5  # Количество итераций для каждого теста
        self.test_timeout = 2.0  # Таймаут теста в секундах

    def test_all_methods(self) -> Dict[str, MethodPerformance]:
        """
        Тестирование всех доступных методов

        Returns:
            Словарь с результатами тестирования
        """
        logger.info("Starting connection methods testing...")

        # Тест SimConnect
        self.test_results['SimConnect'] = self._test_simconnect()

        # Тест WASM (если доступен)
        if self.wasm and self.wasm.connected:
            self.test_results['WASM'] = self._test_wasm()
            self.test_results['L:Vars'] = self._test_lvars()
        else:
            logger.info("WASM not available, skipping WASM and L:Vars tests")
            self.test_results['WASM'] = MethodPerformance(
                method='WASM',
                available=False,
                read_time_ms=0,
                write_time_ms=0,
                reliability=0,
                test_result=TestResult.NOT_AVAILABLE.value,
                error_message="WASM module not connected"
            )
            self.test_results['L:Vars'] = MethodPerformance(
                method='L:Vars',
                available=False,
                read_time_ms=0,
                write_time_ms=0,
                reliability=0,
                test_result=TestResult.NOT_AVAILABLE.value,
                error_message="WASM module not connected"
            )

        # Определение рекомендуемого метода
        self._determine_recommended_method()

        # Логирование результатов
        self._log_results()

        return self.test_results

    def _test_simconnect(self) -> MethodPerformance:
        """
        Тестирование SimConnect

        Returns:
            Метрики производительности
        """
        logger.info("Testing SimConnect method...")

        read_times = []
        write_times = []
        success_count = 0

        try:
            for i in range(self.test_iterations):
                # Тест чтения
                start = time.perf_counter()
                try:
                    data = self.telemetry.get_all_data()
                    if data and 'position' in data:
                        read_time = (time.perf_counter() - start) * 1000
                        read_times.append(read_time)
                        success_count += 1
                except Exception as e:
                    logger.debug("SimConnect read test %s failed: %s", i+1, e)

                # Тест записи (установка автопилота)
                start = time.perf_counter()
                try:
                    # Читаем текущее состояние автопилота
                    current_state = self.control.get_autopilot_master()
                    # Устанавливаем то же состояние (безопасная операция)
                    self.control.set_autopilot_master(current_state)
                    write_time = (time.perf_counter() - start) * 1000
                    write_times.append(write_time)
                except Exception as e:
                    logger.debug("SimConnect write test %s failed: %s", i+1, e)

                time.sleep(0.1)  # Небольшая задержка между тестами

            # Вычисление средних значений
            avg_read = sum(read_times) / len(read_times) if read_times else 999
            avg_write = sum(write_times) / len(write_times) if write_times else 999
            reliability = success_count / self.test_iterations

            return MethodPerformance(
                method='SimConnect',
                available=True,
                read_time_ms=avg_read,
                write_time_ms=avg_write,
                reliability=reliability,
                test_result=TestResult.SUCCESS.value if reliability > 0.5 else TestResult.FAILED.value
            )

        except Exception as e:
            logger.error("SimConnect test failed: %s", e)
            return MethodPerformance(
                method='SimConnect',
                available=False,
                read_time_ms=0,
                write_time_ms=0,
                reliability=0,
                test_result=TestResult.FAILED.value,
                error_message=str(e)
            )

    def _test_wasm(self) -> MethodPerformance:
        """
        Тестирование WASM (общая доступность)

        Returns:
            Метрики производительности
        """
        logger.info("Testing WASM method...")

        if not self.wasm or not self.wasm.connected:
            return MethodPerformance(
                method='WASM',
                available=False,
                read_time_ms=0,
                write_time_ms=0,
                reliability=0,
                test_result=TestResult.NOT_AVAILABLE.value,
                error_message="WASM not connected"
            )

        # WASM доступен, но реальное тестирование через L:Vars
        return MethodPerformance(
            method='WASM',
            available=True,
            read_time_ms=0,
            write_time_ms=0,
            reliability=1.0,
            test_result=TestResult.SUCCESS.value
        )

    def _test_lvars(self) -> MethodPerformance:
        """
        Тестирование L:Vars через WASM

        Returns:
            Метрики производительности
        """
        logger.info("Testing L:Vars method...")

        if not self.wasm or not self.wasm.connected:
            return MethodPerformance(
                method='L:Vars',
                available=False,
                read_time_ms=0,
                write_time_ms=0,
                reliability=0,
                test_result=TestResult.NOT_AVAILABLE.value,
                error_message="WASM not connected"
            )

        read_times = []
        write_times = []
        success_count = 0

        # Тестовые L:Vars (безопасные для чтения/записи)
        test_lvars = [
            "AUTOPILOT_MASTER",  # Стандартная переменная
            "AUTOPILOT_HEADING_LOCK",
            "AUTOPILOT_ALTITUDE_LOCK"
        ]

        try:
            for i in range(self.test_iterations):
                # Тест чтения
                start = time.perf_counter()
                try:
                    value = self.wasm.read_lvar(test_lvars[i % len(test_lvars)])
                    if value is not None:
                        read_time = (time.perf_counter() - start) * 1000
                        read_times.append(read_time)
                        success_count += 1
                except Exception as e:
                    logger.debug("L:Var read test %s failed: %s", i+1, e)

                # Тест записи (записываем то же значение обратно)
                start = time.perf_counter()
                try:
                    if value is not None:
                        self.wasm.write_lvar(test_lvars[i % len(test_lvars)], value)
                        write_time = (time.perf_counter() - start) * 1000
                        write_times.append(write_time)
                except Exception as e:
                    logger.debug("L:Var write test %s failed: %s", i+1, e)

                time.sleep(0.1)

            # Вычисление средних значений
            avg_read = sum(read_times) / len(read_times) if read_times else 999
            avg_write = sum(write_times) / len(write_times) if write_times else 999
            reliability = success_count / self.test_iterations

            return MethodPerformance(
                method='L:Vars',
                available=True,
                read_time_ms=avg_read,
                write_time_ms=avg_write,
                reliability=reliability,
                test_result=TestResult.SUCCESS.value if reliability > 0.5 else TestResult.FAILED.value
            )

        except Exception as e:
            logger.error("L:Vars test failed: %s", e)
            return MethodPerformance(
                method='L:Vars',
                available=False,
                read_time_ms=0,
                write_time_ms=0,
                reliability=0,
                test_result=TestResult.FAILED.value,
                error_message=str(e)
            )

    def _determine_recommended_method(self):
        """Определение рекомендуемого метода на основе результатов"""
        best_score = 0
        best_method = None

        for method_name, performance in self.test_results.items():
            score = performance.get_score()
            logger.info("%s score: %s", method_name, score)

            if score > best_score:
                best_score = score
                best_method = method_name

        self.recommended_method = best_method
        logger.info("Recommended method: %s (score: %s)", best_method, best_score)

    def _log_results(self):
        """Детальное логирование результатов"""
        logger.info("=" * 80)
        logger.info("CONNECTION METHODS TEST RESULTS")
        logger.info("=" * 80)

        for method_name, perf in self.test_results.items():
            logger.info("\n%s:", method_name)
            logger.info("  Available: %s", perf.available)
            logger.info("  Read Time: %sms", perf.read_time_ms)
            logger.info("  Write Time: %sms", perf.write_time_ms)
            logger.info("  Reliability: %s%", perf.reliability*100)
            logger.info("  Score: %s/100", perf.get_score())
            logger.info("  Result: %s", perf.test_result)
            if perf.error_message:
                logger.info("  Error: %s", perf.error_message)

        logger.info("\nRECOMMENDED METHOD: %s", self.recommended_method)
        logger.info("=" * 80)

    def get_recommended_method(self) -> Optional[str]:
        """
        Получить рекомендуемый метод

        Returns:
            Название метода или None
        """
        return self.recommended_method

    def get_method_performance(self, method: str) -> Optional[MethodPerformance]:
        """
        Получить метрики производительности метода

        Args:
            method: Название метода

        Returns:
            Метрики или None
        """
        return self.test_results.get(method)

    def export_results(self) -> Dict:
        """
        Экспорт результатов в словарь

        Returns:
            Словарь с результатами
        """
        return {
            'recommended_method': self.recommended_method,
            'test_results': {
                method: asdict(perf)
                for method, perf in self.test_results.items()
            },
            'timestamp': time.time()
        }

    def should_use_lvars(self) -> bool:
        """
        Проверка, стоит ли использовать L:Vars

        Returns:
            True если L:Vars рекомендуется
        """
        return self.recommended_method == 'L:Vars'

    def should_use_wasm(self) -> bool:
        """
        Проверка, стоит ли использовать WASM

        Returns:
            True если WASM рекомендуется
        """
        return self.recommended_method in ['WASM', 'L:Vars']

    def get_performance_report(self) -> str:
        """
        Получить текстовый отчёт о производительности

        Returns:
            Форматированный отчёт
        """
        report = []
        report.append("CONNECTION PERFORMANCE REPORT")
        report.append("=" * 60)

        for method_name, perf in self.test_results.items():
            report.append(f"\n{method_name}:")
            report.append(f"  Status: {'✅ Available' if perf.available else '❌ Not Available'}")
            if perf.available:
                report.append(f"  Read:  {perf.read_time_ms:6.2f}ms")
                report.append(f"  Write: {perf.write_time_ms:6.2f}ms")
                report.append(f"  Reliability: {perf.reliability*100:5.1f}%")
                report.append(f"  Score: {perf.get_score():5.1f}/100")

        report.append(f"\n{'='*60}")
        report.append(f"RECOMMENDED: {self.recommended_method}")
        report.append("=" * 60)

        return "\n".join(report)
