"""
Система автоматического анализа логов и генерации отчётов
Анализирует структурированные логи и создаёт отчёты для исправления ошибок
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ErrorPattern:
    """Паттерн ошибки"""
    error_type: str
    message_pattern: str
    count: int
    first_occurrence: str
    last_occurrence: str
    affected_modules: List[str]
    affected_functions: List[str]
    sample_data: List[Dict]
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'


@dataclass
class AnalysisReport:
    """Отчёт анализа логов"""
    session_id: str
    analysis_time: str
    total_logs: int
    error_count: int
    warning_count: int
    error_patterns: List[ErrorPattern]
    performance_issues: List[Dict]
    recommendations: List[str]
    code_fixes: List[Dict]
    summary: str


class LogAnalyzer:
    """Анализатор логов"""

    def __init__(self, log_dir: str = "logs"):
        """
        Args:
            log_dir: Директория с логами
        """
        self.log_dir = Path(log_dir)

        # Паттерны известных ошибок
        self.known_error_patterns = {
            'SimConnect': {
                'pattern': r'SimConnect.*(?:connection|failed|timeout)',
                'severity': 'CRITICAL',
                'fix': 'Проверить подключение к MSFS, убедиться что симулятор запущен'
            },
            'WASM': {
                'pattern': r'WASM.*(?:not available|failed|error)',
                'severity': 'HIGH',
                'fix': 'Установить MobiFlight WASM модуль или использовать fallback на SimConnect'
            },
            'Audio': {
                'pattern': r'Audio.*(?:not available|failed)',
                'severity': 'MEDIUM',
                'fix': 'Установить библиотеки: pip install gtts pygame'
            },
            'Telemetry': {
                'pattern': r'Telemetry.*(?:invalid|missing|null)',
                'severity': 'HIGH',
                'fix': 'Проверить SimConnect переменные, возможно самолёт не поддерживает некоторые параметры'
            },
            'Navigation': {
                'pattern': r'Navigation.*(?:invalid|out of range)',
                'severity': 'MEDIUM',
                'fix': 'Проверить настройки захода, убедиться что координаты корректны'
            }
        }

    def analyze_session(self, session_id: str) -> AnalysisReport:
        """
        Анализировать сессию

        Args:
            session_id: ID сессии

        Returns:
            Отчёт анализа
        """
        json_log_file = self.log_dir / f"session_{session_id}.jsonl"
        error_log_file = self.log_dir / f"errors_{session_id}.jsonl"

        if not json_log_file.exists():
            raise FileNotFoundError(f"Log file not found: {json_log_file}")

        # Загрузка логов
        all_logs = self._load_logs(json_log_file)
        error_logs = self._load_logs(error_log_file) if error_log_file.exists() else []

        # Анализ
        error_patterns = self._analyze_errors(error_logs)
        performance_issues = self._analyze_performance(all_logs)
        recommendations = self._generate_recommendations(error_patterns, performance_issues)
        code_fixes = self._generate_code_fixes(error_patterns)
        summary = self._generate_summary(all_logs, error_logs, error_patterns)

        return AnalysisReport(
            session_id=session_id,
            analysis_time=datetime.now().isoformat(),
            total_logs=len(all_logs),
            error_count=len(error_logs),
            warning_count=sum(1 for log in all_logs if log.get('level') == 'WARNING'),
            error_patterns=error_patterns,
            performance_issues=performance_issues,
            recommendations=recommendations,
            code_fixes=code_fixes,
            summary=summary
        )

    def _load_logs(self, log_file: Path) -> List[Dict]:
        """Загрузить логи из JSONL файла"""
        logs = []
        with open(log_file, encoding='utf-8') as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return logs

    def _analyze_errors(self, error_logs: List[Dict]) -> List[ErrorPattern]:
        """Анализ ошибок и группировка по паттернам"""
        if not error_logs:
            return []

        # Группировка по типу исключения и сообщению
        error_groups = defaultdict(list)

        for log in error_logs:
            exception = log.get('exception')
            if exception:
                error_type = exception.get('type', 'Unknown')
                message = log.get('message', '')
            else:
                error_type = 'Error'
                message = log.get('message', '')

            # Нормализация сообщения (удаление чисел, путей)
            normalized_msg = re.sub(r'\d+', 'N', message)
            normalized_msg = re.sub(r'[A-Z]:\\[^\s]+', 'PATH', normalized_msg)

            key = f"{error_type}:{normalized_msg[:100]}"
            error_groups[key].append(log)

        # Создание паттернов
        patterns = []
        for key, logs in error_groups.items():
            error_type = logs[0].get('exception', {}).get('type', 'Error')
            message_pattern = logs[0].get('message', '')

            # Определение серьезности
            severity = self._determine_severity(error_type, message_pattern, len(logs))

            pattern = ErrorPattern(
                error_type=error_type,
                message_pattern=message_pattern,
                count=len(logs),
                first_occurrence=logs[0].get('datetime_str', ''),
                last_occurrence=logs[-1].get('datetime_str', ''),
                affected_modules=list(set(log.get('module', 'unknown') for log in logs)),
                affected_functions=list(set(log.get('function', 'unknown') for log in logs)),
                sample_data=[log.get('data', {}) for log in logs[:3]],
                severity=severity
            )
            patterns.append(pattern)

        # Сортировка по серьезности и частоте
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        patterns.sort(key=lambda p: (severity_order.get(p.severity, 4), -p.count))

        return patterns

    def _determine_severity(self, error_type: str, message: str, count: int) -> str:
        """Определить серьезность ошибки"""
        # Проверка известных паттернов
        for pattern_name, pattern_info in self.known_error_patterns.items():
            if re.search(pattern_info['pattern'], message, re.IGNORECASE):
                return pattern_info['severity']

        # Критические типы ошибок
        critical_types = ['ConnectionError', 'TimeoutError', 'SystemError']
        if error_type in critical_types:
            return 'CRITICAL'

        # Частые ошибки
        if count > 10:
            return 'HIGH'
        elif count > 5:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _analyze_performance(self, all_logs: List[Dict]) -> List[Dict]:
        """Анализ производительности"""
        perf_logs = [log for log in all_logs if log.get('category') == 'PERFORMANCE']

        if not perf_logs:
            return []

        # Группировка по операциям
        operations = defaultdict(list)
        for log in perf_logs:
            data = log.get('data', {})
            operation = data.get('operation', 'unknown')
            duration_ms = data.get('duration_ms', 0)
            operations[operation].append(duration_ms)

        # Анализ
        issues = []
        for operation, durations in operations.items():
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)

            # Пороги производительности
            if avg_duration > 100:  # > 100ms среднее
                issues.append({
                    'operation': operation,
                    'avg_duration_ms': avg_duration,
                    'max_duration_ms': max_duration,
                    'count': len(durations),
                    'severity': 'HIGH' if avg_duration > 500 else 'MEDIUM',
                    'recommendation': f'Оптимизировать операцию {operation}, среднее время {avg_duration:.1f}ms'
                })

        return sorted(issues, key=lambda x: x['avg_duration_ms'], reverse=True)

    def _generate_recommendations(self, error_patterns: List[ErrorPattern],
                                   performance_issues: List[Dict]) -> List[str]:
        """Генерация рекомендаций"""
        recommendations = []

        # Рекомендации по ошибкам
        for pattern in error_patterns[:5]:  # Топ 5 ошибок
            # Проверка известных паттернов
            for pattern_name, pattern_info in self.known_error_patterns.items():
                if re.search(pattern_info['pattern'], pattern.message_pattern, re.IGNORECASE):
                    recommendations.append(
                        f"[{pattern.severity}] {pattern.error_type} ({pattern.count}x): {pattern_info['fix']}"
                    )
                    break
            else:
                recommendations.append(
                    f"[{pattern.severity}] {pattern.error_type} ({pattern.count}x) в {', '.join(pattern.affected_modules[:2])}: "
                    f"Проверить код в функциях {', '.join(pattern.affected_functions[:2])}"
                )

        # Рекомендации по производительности
        for issue in performance_issues[:3]:  # Топ 3 проблемы
            recommendations.append(
                f"[PERFORMANCE] {issue['recommendation']}"
            )

        return recommendations

    def _generate_code_fixes(self, error_patterns: List[ErrorPattern]) -> List[Dict]:
        """Генерация предложений по исправлению кода"""
        fixes = []

        for pattern in error_patterns:
            if pattern.severity in ['CRITICAL', 'HIGH']:
                fix = {
                    'error_type': pattern.error_type,
                    'severity': pattern.severity,
                    'affected_files': [f"{mod}.py" for mod in pattern.affected_modules],
                    'affected_functions': pattern.affected_functions,
                    'description': pattern.message_pattern,
                    'suggested_fix': self._suggest_fix(pattern)
                }
                fixes.append(fix)

        return fixes

    def _suggest_fix(self, pattern: ErrorPattern) -> str:
        """Предложить исправление для паттерна ошибки"""
        # Проверка известных паттернов
        for pattern_name, pattern_info in self.known_error_patterns.items():
            if re.search(pattern_info['pattern'], pattern.message_pattern, re.IGNORECASE):
                return pattern_info['fix']

        # Общие рекомендации по типу ошибки
        if pattern.error_type == 'AttributeError':
            return "Добавить проверку на None перед обращением к атрибуту"
        elif pattern.error_type == 'KeyError':
            return "Использовать .get() вместо прямого обращения к ключу словаря"
        elif pattern.error_type == 'IndexError':
            return "Добавить проверку длины списка перед обращением по индексу"
        elif pattern.error_type == 'TypeError':
            return "Добавить проверку типов данных и type hints"
        elif pattern.error_type == 'ValueError':
            return "Добавить валидацию входных данных"
        else:
            return "Добавить try-except блок и логирование ошибки"

    def _generate_summary(self, all_logs: List[Dict], error_logs: List[Dict],
                          error_patterns: List[ErrorPattern]) -> str:
        """Генерация краткой сводки"""
        if not all_logs:
            return "Нет данных для анализа"

        error_rate = (len(error_logs) / len(all_logs) * 100) if all_logs else 0

        critical_errors = sum(1 for p in error_patterns if p.severity == 'CRITICAL')
        high_errors = sum(1 for p in error_patterns if p.severity == 'HIGH')

        summary = f"Проанализировано {len(all_logs)} записей логов. "
        summary += f"Обнаружено {len(error_logs)} ошибок ({error_rate:.1f}% от всех записей). "

        if critical_errors > 0:
            summary += f"КРИТИЧНО: {critical_errors} критических ошибок требуют немедленного исправления. "
        if high_errors > 0:
            summary += f"ВАЖНО: {high_errors} серьёзных ошибок требуют внимания. "

        if error_rate < 1:
            summary += "Система работает стабильно."
        elif error_rate < 5:
            summary += "Система работает с незначительными проблемами."
        elif error_rate < 10:
            summary += "Система требует оптимизации."
        else:
            summary += "Система работает нестабильно, требуется срочное исправление."

        return summary

    def generate_report_file(self, report: AnalysisReport, output_file: Optional[Path] = None):
        """
        Сгенерировать файл отчёта в Markdown

        Args:
            report: Отчёт анализа
            output_file: Путь к выходному файлу
        """
        if output_file is None:
            output_file = self.log_dir / f"analysis_{report.session_id}.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Анализ логов сессии {report.session_id}\n\n")
            f.write(f"**Время анализа:** {report.analysis_time}\n\n")

            # Сводка
            f.write("## Сводка\n\n")
            f.write(f"{report.summary}\n\n")
            f.write(f"- Всего записей: {report.total_logs}\n")
            f.write(f"- Ошибок: {report.error_count}\n")
            f.write(f"- Предупреждений: {report.warning_count}\n\n")

            # Паттерны ошибок
            if report.error_patterns:
                f.write("## Обнаруженные ошибки\n\n")
                for i, pattern in enumerate(report.error_patterns, 1):
                    f.write(f"### {i}. {pattern.error_type} [{pattern.severity}]\n\n")
                    f.write(f"**Сообщение:** {pattern.message_pattern}\n\n")
                    f.write(f"**Количество:** {pattern.count}\n\n")
                    f.write(f"**Первое появление:** {pattern.first_occurrence}\n\n")
                    f.write(f"**Последнее появление:** {pattern.last_occurrence}\n\n")
                    f.write(f"**Затронутые модули:** {', '.join(pattern.affected_modules)}\n\n")
                    f.write(f"**Затронутые функции:** {', '.join(pattern.affected_functions)}\n\n")

            # Проблемы производительности
            if report.performance_issues:
                f.write("## Проблемы производительности\n\n")
                for issue in report.performance_issues:
                    f.write(f"- **{issue['operation']}** [{issue['severity']}]: "
                           f"среднее {issue['avg_duration_ms']:.1f}ms, "
                           f"максимум {issue['max_duration_ms']:.1f}ms "
                           f"({issue['count']} измерений)\n")
                f.write("\n")

            # Рекомендации
            if report.recommendations:
                f.write("## Рекомендации\n\n")
                for rec in report.recommendations:
                    f.write(f"- {rec}\n")
                f.write("\n")

            # Предложения по исправлению кода
            if report.code_fixes:
                f.write("## Предложения по исправлению кода\n\n")
                for fix in report.code_fixes:
                    f.write(f"### {fix['error_type']} [{fix['severity']}]\n\n")
                    f.write(f"**Файлы:** {', '.join(fix['affected_files'])}\n\n")
                    f.write(f"**Функции:** {', '.join(fix['affected_functions'])}\n\n")
                    f.write(f"**Описание:** {fix['description']}\n\n")
                    f.write(f"**Предлагаемое исправление:** {fix['suggested_fix']}\n\n")

        return output_file


def analyze_latest_session(log_dir: str = "logs") -> Optional[AnalysisReport]:
    """
    Анализировать последнюю сессию

    Args:
        log_dir: Директория с логами

    Returns:
        Отчёт анализа или None если логов нет
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return None

    # Найти последний файл логов
    log_files = list(log_path.glob("session_*.jsonl"))
    if not log_files:
        return None

    latest_file = max(log_files, key=lambda p: p.stat().st_mtime)
    session_id = latest_file.stem.replace("session_", "")

    analyzer = LogAnalyzer(log_dir)
    report = analyzer.analyze_session(session_id)
    analyzer.generate_report_file(report)

    return report
