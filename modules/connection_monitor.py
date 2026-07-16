"""
Система непрерывного мониторинга методов подключения
Отслеживает производительность SimConnect, WASM и L:Vars в реальном времени
Автоматически переключается на оптимальный метод
"""

import json
import logging
import math
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ConnectionMethod(Enum):
    """Методы подключения к самолёту"""
    SIMCONNECT = "SimConnect"
    WASM = "WASM"
    LVARS = "L:Vars"


class FlightPhase(Enum):
    """Фазы полёта"""
    GROUND = "ground"
    TAKEOFF = "takeoff"
    CLIMB = "climb"
    CRUISE = "cruise"
    DESCENT = "descent"
    APPROACH = "approach"
    LANDING = "landing"


@dataclass
class LiveMetrics:
    """Метрики производительности в реальном времени"""
    method: str = ""

    # Счётчики операций
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0

    # Время отклика (в миллисекундах)
    read_times: deque = field(default_factory=lambda: deque(maxlen=100))
    write_times: deque = field(default_factory=lambda: deque(maxlen=100))

    # Текущие средние значения
    avg_read_ms: float = 0.0
    avg_write_ms: float = 0.0

    # Надёжность
    reliability: float = 1.0

    # Временные метки
    last_success_time: float = 0.0
    last_failure_time: float = 0.0
    last_update_time: float = 0.0

    # Статус
    available: bool = True
    error_count: int = 0
    consecutive_errors: int = 0

    def add_operation(self, operation_type: str, time_ms: float, success: bool):
        """
        Добавить результат операции

        Args:
            operation_type: 'read' или 'write'
            time_ms: Время выполнения в миллисекундах
            success: Успешность операции
        """
        self.total_operations += 1
        self.last_update_time = time.time()

        if success:
            self.successful_operations += 1
            self.last_success_time = time.time()
            self.consecutive_errors = 0

            if operation_type == 'read':
                self.read_times.append(time_ms)
                if self.read_times:
                    self.avg_read_ms = sum(self.read_times) / len(self.read_times)
            elif operation_type == 'write':
                self.write_times.append(time_ms)
                if self.write_times:
                    self.avg_write_ms = sum(self.write_times) / len(self.write_times)
        else:
            self.failed_operations += 1
            self.error_count += 1
            self.consecutive_errors += 1
            self.last_failure_time = time.time()

        # Обновление надёжности
        if self.total_operations > 0:
            self.reliability = self.successful_operations / self.total_operations

    def get_score(self) -> float:
        """
        Вычисление общего балла метода

        Returns:
            Балл от 0 до 100
        """
        if not self.available or self.total_operations == 0:
            return 0.0

        # Веса факторов
        SPEED_WEIGHT = 0.3
        RELIABILITY_WEIGHT = 0.5
        STABILITY_WEIGHT = 0.2

        # Нормализация скорости
        avg_time = (self.avg_read_ms + self.avg_write_ms) / 2
        speed_score = max(0, min(100, 100 - avg_time))

        # Надёжность в процентах
        reliability_score = self.reliability * 100

        # Стабильность (штраф за последовательные ошибки)
        stability_score = max(0, 100 - (self.consecutive_errors * 20))

        # Итоговый балл
        total_score = (speed_score * SPEED_WEIGHT +
                      reliability_score * RELIABILITY_WEIGHT +
                      stability_score * STABILITY_WEIGHT)

        return total_score

    def is_degraded(self) -> bool:
        """
        Проверка деградации производительности

        Returns:
            True если метод работает плохо
        """
        # Критерии деградации
        if self.consecutive_errors >= 3:
            return True
        if self.reliability < 0.8 and self.total_operations > 10:
            return True
        if self.avg_read_ms > 100 or self.avg_write_ms > 100:
            return True

        return False

    def reset(self):
        """Сброс метрик"""
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.read_times.clear()
        self.write_times.clear()
        self.avg_read_ms = 0.0
        self.avg_write_ms = 0.0
        self.reliability = 1.0
        self.error_count = 0
        self.consecutive_errors = 0


@dataclass
class SwitchEvent:
    """Событие переключения метода"""
    timestamp: float
    from_method: str
    to_method: str
    reason: str
    from_score: float
    to_score: float
    flight_phase: str


@dataclass
class AircraftProfile:
    """Профиль производительности самолёта"""
    aircraft_title: str
    recommended_method: str
    total_flight_time: float = 0.0

    # История производительности
    performance_history: Dict[str, Dict] = field(default_factory=dict)

    # Рекомендации по фазам полёта
    phase_recommendations: Dict[str, str] = field(default_factory=dict)

    # Статистика
    total_switches: int = 0
    last_tested: float = 0.0

    def update_from_metrics(self, method: str, metrics: LiveMetrics):
        """Обновить профиль из текущих метрик"""
        if method not in self.performance_history:
            self.performance_history[method] = {}

        self.performance_history[method] = {
            'avg_read_ms': metrics.avg_read_ms,
            'avg_write_ms': metrics.avg_write_ms,
            'reliability': metrics.reliability,
            'total_operations': metrics.total_operations,
            'score': metrics.get_score()
        }

        self.last_tested = time.time()


class ConnectionMonitor:
    """Система непрерывного мониторинга методов подключения"""

    def __init__(self, optimizer, telemetry, control, wasm_interface=None):
        """
        Args:
            optimizer: Экземпляр ConnectionOptimizer
            telemetry: Экземпляр MSFSTelemetry
            control: Экземпляр MSFSControl
            wasm_interface: Экземпляр MobiFlightWASM (опционально)
        """
        self.optimizer = optimizer
        self.telemetry = telemetry
        self.control = control
        self.wasm = wasm_interface

        # Метрики в реальном времени
        self.live_metrics: Dict[str, LiveMetrics] = {
            'SimConnect': LiveMetrics(method='SimConnect'),
            'WASM': LiveMetrics(method='WASM'),
            'L:Vars': LiveMetrics(method='L:Vars')
        }

        # Текущий метод
        self.current_method: Optional[str] = None

        # Профиль самолёта
        self.aircraft_profile: Optional[AircraftProfile] = None
        self.aircraft_title: Optional[str] = None

        # История переключений
        self.switch_history: List[SwitchEvent] = []

        # Настройки мониторинга
        self.monitor_enabled = True
        self.passive_monitor_interval = 1.0  # секунд (обновление метрик)
        self.active_test_interval = 120.0    # секунд (полное тестирование)
        self.last_active_test = 0.0

        # Пороги для переключения
        self.switch_threshold_score_diff = 20.0  # разница в баллах
        self.switch_threshold_degradation = True  # переключать при деградации

        # Текущая фаза полёта
        self.current_phase = FlightPhase.GROUND

        # Путь к файлу профилей
        self.profiles_file = Path("config/connection_profiles.json")

        # Загрузка профилей
        self.profiles: Dict[str, AircraftProfile] = self._load_profiles()

        logger.info("ConnectionMonitor initialized")

    def start_monitoring(self, aircraft_title: str, initial_method: str):
        """
        Запуск мониторинга для самолёта

        Args:
            aircraft_title: Название самолёта
            initial_method: Начальный метод подключения
        """
        self.aircraft_title = aircraft_title
        self.current_method = initial_method

        # Загрузка или создание профиля
        if aircraft_title in self.profiles:
            self.aircraft_profile = self.profiles[aircraft_title]
            logger.info("Loaded profile for %s", aircraft_title)
        else:
            self.aircraft_profile = AircraftProfile(
                aircraft_title=aircraft_title,
                recommended_method=initial_method
            )
            logger.info("Created new profile for %s", aircraft_title)

        # Сброс метрик
        for metrics in self.live_metrics.values():
            metrics.reset()

        # Установка доступности методов
        self.live_metrics['SimConnect'].available = True
        self.live_metrics['WASM'].available = (self.wasm is not None and
                                               hasattr(self.wasm, 'connected') and
                                               self.wasm.connected)
        self.live_metrics['L:Vars'].available = self.live_metrics['WASM'].available

        logger.info("Monitoring started for %s using %s", aircraft_title, initial_method)

    def update_metrics(self, method: str, operation: str, time_ms: float, success: bool):
        """
        Обновление метрик после операции

        Args:
            method: Метод подключения
            operation: Тип операции ('read' или 'write')
            time_ms: Время выполнения в миллисекундах
            success: Успешность операции
        """
        if not self.monitor_enabled or method not in self.live_metrics:
            return

        self.live_metrics[method].add_operation(operation, time_ms, success)

    def update_flight_phase(self, altitude_agl: float, ground_speed: float,
                           vertical_speed: float, on_ground: bool):
        """
        Обновление текущей фазы полёта

        Args:
            altitude_agl: Высота над землёй (футы)
            ground_speed: Путевая скорость (узлы)
            vertical_speed: Вертикальная скорость (фут/мин)
            on_ground: На земле
        """
        old_phase = self.current_phase

        if on_ground:
            self.current_phase = FlightPhase.GROUND
        else:
            # Validate inputs: must be finite real numbers (not None, NaN, inf, bool, str, object)
            alt_valid = isinstance(altitude_agl, (int, float)) and not isinstance(altitude_agl, bool) and math.isfinite(altitude_agl)
            vs_valid = isinstance(vertical_speed, (int, float)) and not isinstance(vertical_speed, bool) and math.isfinite(vertical_speed)

            if not alt_valid or not vs_valid:
                logger.warning(
                    "update_flight_phase: non-finite inputs altitude_agl=%r vertical_speed=%r — "
                    "preserving previous phase %s",
                    altitude_agl, vertical_speed, old_phase.value,
                )
                return

            if altitude_agl < 1500 and vertical_speed > 500:
                self.current_phase = FlightPhase.TAKEOFF
            elif altitude_agl < 10000 and vertical_speed > 500:
                self.current_phase = FlightPhase.CLIMB
            elif altitude_agl > 10000 and abs(vertical_speed) < 500:
                self.current_phase = FlightPhase.CRUISE
            elif altitude_agl > 10000 and vertical_speed < -500:
                self.current_phase = FlightPhase.DESCENT
            elif altitude_agl < 500:
                # FIX-P1-3: LANDING must be checked before the broader APPROACH
                # window (altitude_agl < 3000 and vertical_speed < 0), which
                # previously shadowed LANDING for nearly all normal descending
                # approaches below 500ft.
                self.current_phase = FlightPhase.LANDING
            elif altitude_agl < 3000 and vertical_speed < 0:
                self.current_phase = FlightPhase.APPROACH

        if old_phase != self.current_phase:
            logger.info("Flight phase changed: %s -> %s", old_phase.value, self.current_phase.value)

    def should_switch_method(self) -> Optional[str]:
        """
        Проверка необходимости переключения метода

        Returns:
            Название нового метода или None
        """
        if not self.monitor_enabled or not self.current_method:
            return None

        current_metrics = self.live_metrics.get(self.current_method)
        if not current_metrics or current_metrics.total_operations < 10:
            return None  # Недостаточно данных

        # Проверка деградации текущего метода
        if self.switch_threshold_degradation and current_metrics.is_degraded():
            logger.warning("Current method %s is degraded", self.current_method)

            # Поиск лучшей альтернативы
            best_method = None
            best_score = 0.0

            for method, metrics in self.live_metrics.items():
                if method == self.current_method:
                    continue
                if not metrics.available:
                    continue
                if metrics.total_operations < 5:
                    continue

                score = metrics.get_score()
                if score > best_score:
                    best_score = score
                    best_method = method

            if best_method and best_score > current_metrics.get_score():
                return best_method

        # Проверка значительно лучшего метода
        current_score = current_metrics.get_score()

        for method, metrics in self.live_metrics.items():
            if method == self.current_method:
                continue
            if not metrics.available:
                continue
            if metrics.total_operations < 20:
                continue

            score = metrics.get_score()
            score_diff = score - current_score

            if score_diff > self.switch_threshold_score_diff:
                logger.info("Found better method: %s (score: %s vs %s)", method, score, current_score)
                return method

        return None

    def switch_to_method(self, new_method: str, reason: str) -> bool:
        """
        Переключение на новый метод

        Args:
            new_method: Новый метод
            reason: Причина переключения

        Returns:
            True если переключение успешно
        """
        if not self.current_method or new_method == self.current_method:
            return False

        old_method = self.current_method
        old_score = self.live_metrics[old_method].get_score()
        new_score = self.live_metrics[new_method].get_score()

        # Запись события переключения
        event = SwitchEvent(
            timestamp=time.time(),
            from_method=old_method,
            to_method=new_method,
            reason=reason,
            from_score=old_score,
            to_score=new_score,
            flight_phase=self.current_phase.value
        )
        self.switch_history.append(event)

        # Обновление профиля
        if self.aircraft_profile:
            self.aircraft_profile.total_switches += 1
            self.aircraft_profile.phase_recommendations[self.current_phase.value] = new_method

        self.current_method = new_method

        logger.info("Switched connection method: %s -> %s (%s)", old_method, new_method, reason)
        logger.info("Scores: %s -> %s", old_score, new_score)

        return True

    def perform_active_test(self) -> Dict[str, float]:
        """
        Выполнение активного тестирования всех методов

        Returns:
            Словарь с баллами методов
        """
        logger.info("Performing active connection test...")

        # Используем optimizer для полного теста
        test_results = self.optimizer.test_all_methods()

        scores = {}
        for method, performance in test_results.items():
            scores[method] = performance.get_score()

            # Обновление live_metrics
            if method in self.live_metrics:
                self.live_metrics[method].avg_read_ms = performance.read_time_ms
                self.live_metrics[method].avg_write_ms = performance.write_time_ms
                self.live_metrics[method].reliability = performance.reliability
                self.live_metrics[method].available = performance.available

        self.last_active_test = time.time()

        logger.info("Active test completed. Scores: %s", scores)
        return scores

    def should_perform_active_test(self) -> bool:
        """
        Проверка необходимости активного тестирования

        Returns:
            True если пора тестировать
        """
        if not self.monitor_enabled:
            return False

        time_since_last = time.time() - self.last_active_test
        return time_since_last >= self.active_test_interval

    def get_current_metrics(self) -> Dict[str, Dict]:
        """
        Получение текущих метрик всех методов

        Returns:
            Словарь с метриками
        """
        result = {}
        for method, metrics in self.live_metrics.items():
            result[method] = {
                'available': metrics.available,
                'total_operations': metrics.total_operations,
                'successful_operations': metrics.successful_operations,
                'failed_operations': metrics.failed_operations,
                'avg_read_ms': metrics.avg_read_ms,
                'avg_write_ms': metrics.avg_write_ms,
                'reliability': metrics.reliability,
                'score': metrics.get_score(),
                'is_degraded': metrics.is_degraded(),
                'consecutive_errors': metrics.consecutive_errors
            }
        return result

    def get_switch_history(self, limit: int = 10) -> List[Dict]:
        """
        Получение истории переключений

        Args:
            limit: Максимальное количество записей

        Returns:
            Список событий переключения
        """
        recent = self.switch_history[-limit:] if limit else self.switch_history
        return [asdict(event) for event in recent]

    def save_profile(self):
        """Сохранение профиля самолёта"""
        if not self.aircraft_profile or not self.aircraft_title:
            return

        # Обновление профиля из текущих метрик
        for method, metrics in self.live_metrics.items():
            if metrics.total_operations > 0:
                self.aircraft_profile.update_from_metrics(method, metrics)

        # Определение рекомендуемого метода
        best_method = None
        best_score = 0.0
        for method, metrics in self.live_metrics.items():
            score = metrics.get_score()
            if score > best_score:
                best_score = score
                best_method = method

        if best_method:
            self.aircraft_profile.recommended_method = best_method

        # Сохранение в словарь
        self.profiles[self.aircraft_title] = self.aircraft_profile

        # Запись в файл
        self._save_profiles()

        logger.info("Profile saved for %s", self.aircraft_title)

    def _load_profiles(self) -> Dict[str, AircraftProfile]:
        """Загрузка профилей из файла"""
        if not self.profiles_file.exists():
            logger.info("No profiles file found, starting fresh")
            return {}

        try:
            with open(self.profiles_file, encoding='utf-8') as f:
                data = json.load(f)

            profiles = {}
            for aircraft_title, profile_data in data.items():
                profiles[aircraft_title] = AircraftProfile(**profile_data)

            logger.info("Loaded %s aircraft profiles", len(profiles))
            return profiles

        except Exception as e:
            logger.error("Failed to load profiles: %s", e)
            return {}

    def _save_profiles(self):
        """Сохранение профилей в файл"""
        try:
            # Создание директории если нужно
            self.profiles_file.parent.mkdir(parents=True, exist_ok=True)

            # Конвертация в словарь
            data = {}
            for aircraft_title, profile in self.profiles.items():
                data[aircraft_title] = asdict(profile)

            # Запись в файл
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug("Profiles saved to %s", self.profiles_file)

        except Exception as e:
            logger.error("Failed to save profiles: %s", e)

    def export_metrics_csv(self, filepath: str):
        """
        Экспорт метрик в CSV

        Args:
            filepath: Путь к файлу
        """
        import csv

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Заголовок
                writer.writerow([
                    'Method', 'Available', 'Total Operations', 'Successful', 'Failed',
                    'Avg Read (ms)', 'Avg Write (ms)', 'Reliability', 'Score',
                    'Consecutive Errors', 'Is Degraded'
                ])

                # Данные
                for method, metrics in self.live_metrics.items():
                    writer.writerow([
                        method,
                        metrics.available,
                        metrics.total_operations,
                        metrics.successful_operations,
                        metrics.failed_operations,
                        f"{metrics.avg_read_ms:.2f}",
                        f"{metrics.avg_write_ms:.2f}",
                        f"{metrics.reliability:.3f}",
                        f"{metrics.get_score():.2f}",
                        metrics.consecutive_errors,
                        metrics.is_degraded()
                    ])

            logger.info("Metrics exported to %s", filepath)

        except Exception as e:
            logger.error("Failed to export metrics: %s", e)

    def export_metrics_json(self, filepath: str):
        """
        Экспорт метрик в JSON

        Args:
            filepath: Путь к файлу
        """
        try:
            data = {
                'timestamp': time.time(),
                'aircraft': self.aircraft_title,
                'current_method': self.current_method,
                'flight_phase': self.current_phase.value,
                'metrics': self.get_current_metrics(),
                'switch_history': self.get_switch_history(),
                'profile': asdict(self.aircraft_profile) if self.aircraft_profile else None
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("Metrics exported to %s", filepath)

        except Exception as e:
            logger.error("Failed to export metrics: %s", e)

    def get_performance_report(self) -> str:
        """
        Получение текстового отчёта о производительности

        Returns:
            Форматированный отчёт
        """
        report = []
        report.append("=" * 70)
        report.append("CONNECTION MONITOR REPORT")
        report.append("=" * 70)

        if self.aircraft_title:
            report.append(f"\nAircraft: {self.aircraft_title}")
        report.append(f"Current Method: {self.current_method}")
        report.append(f"Flight Phase: {self.current_phase.value}")
        report.append(f"Total Switches: {len(self.switch_history)}")

        report.append("\n" + "-" * 70)
        report.append("LIVE METRICS")
        report.append("-" * 70)

        for method, metrics in self.live_metrics.items():
            is_current = "✓" if method == self.current_method else " "
            status = "✅" if metrics.available else "❌"
            degraded = "⚠️ DEGRADED" if metrics.is_degraded() else ""

            report.append(f"\n[{is_current}] {method} {status} {degraded}")
            report.append(f"    Operations: {metrics.total_operations} "
                         f"(✓{metrics.successful_operations} ✗{metrics.failed_operations})")
            report.append(f"    Read:  {metrics.avg_read_ms:6.2f}ms")
            report.append(f"    Write: {metrics.avg_write_ms:6.2f}ms")
            report.append(f"    Reliability: {metrics.reliability*100:5.1f}%")
            report.append(f"    Score: {metrics.get_score():5.1f}/100")

            if metrics.consecutive_errors > 0:
                report.append(f"    ⚠️ Consecutive Errors: {metrics.consecutive_errors}")

        if self.switch_history:
            report.append("\n" + "-" * 70)
            report.append("RECENT SWITCHES")
            report.append("-" * 70)

            for event in self.switch_history[-5:]:
                report.append(f"\n{time.strftime('%H:%M:%S', time.localtime(event.timestamp))}: "
                             f"{event.from_method} -> {event.to_method}")
                report.append(f"    Reason: {event.reason}")
                report.append(f"    Scores: {event.from_score:.1f} -> {event.to_score:.1f}")
                report.append(f"    Phase: {event.flight_phase}")

        report.append("\n" + "=" * 70)

        return "\n".join(report)
