"""
Команда для Claude: чтение и анализ логов проекта
Позволяет Claude читать логи, анализировать ошибки и показывать информацию
Все исправления вносятся совместно с пользователем
"""

import sys
from pathlib import Path

# Добавление корневой директории в путь
sys.path.insert(0, str(Path(__file__).parent))

from modules.log_analyzer import LogAnalyzer


def format_error_details(pattern, index: int) -> str:
    """Форматировать детали ошибки"""
    severity_emoji = {
        'CRITICAL': '[!!!]',
        'HIGH': '[!!]',
        'MEDIUM': '[!]',
        'LOW': '[i]'
    }
    emoji = severity_emoji.get(pattern.severity, '[-]')

    output = f"\n{index}. {emoji} [{pattern.severity}] {pattern.error_type}\n"
    output += f"   Сообщение: {pattern.message_pattern}\n"
    output += f"   Количество: {pattern.count}\n"
    output += f"   Первое появление: {pattern.first_occurrence}\n"
    output += f"   Последнее появление: {pattern.last_occurrence}\n"
    output += f"   Модули: {', '.join(pattern.affected_modules)}\n"
    output += f"   Функции: {', '.join(pattern.affected_functions)}\n"

    # Показать примеры данных если есть
    if pattern.sample_data:
        output += "   Примеры данных:\n"
        for i, sample in enumerate(pattern.sample_data[:2], 1):
            if sample:
                output += f"      {i}. {sample}\n"

    return output


def claude_read_logs(session_id: str = None):
    """
    Команда для Claude: прочитать и проанализировать логи

    Args:
        session_id: ID сессии (если None, берётся последняя)
    """
    log_dir = Path("logs")

    if not log_dir.exists():
        print("[ERROR] Log directory not found.")
        print("   Run the program (python gui.py) to generate logs.")
        return

    analyzer = LogAnalyzer(str(log_dir))

    # Определение сессии
    if session_id is None:
        log_files = list(log_dir.glob("session_*.jsonl"))
        if not log_files:
            print("[ERROR] Logs not found.")
            print("   Run the program (python gui.py) to generate logs.")
            return

        latest_file = max(log_files, key=lambda p: p.stat().st_mtime)
        session_id = latest_file.stem.replace("session_", "")

    print(f"\n[ANALYSIS] LOG ANALYSIS FOR SESSION: {session_id}")
    print("="*80)

    try:
        report = analyzer.analyze_session(session_id)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return

    # Сводка
    print("\n[SUMMARY]")
    print(f"Total logs: {report.total_logs}")
    print(f"Errors: {report.error_count}")
    print(f"Warnings: {report.warning_count}")
    print(f"\n{report.summary}")

    # Ошибки
    if report.error_patterns:
        print(f"\n[ERRORS FOUND] ({len(report.error_patterns)}):")
        print("="*80)

        for i, pattern in enumerate(report.error_patterns, 1):
            print(format_error_details(pattern, i))

    # Производительность
    if report.performance_issues:
        print(f"\n[PERFORMANCE ISSUES] ({len(report.performance_issues)}):")
        print("="*80)

        for issue in report.performance_issues:
            print(f"  * {issue['operation']}: avg {issue['avg_duration_ms']:.1f}ms, "
                  f"max {issue['max_duration_ms']:.1f}ms ({issue['count']} measurements)")

    # Рекомендации
    if report.recommendations:
        print("\n[RECOMMENDATIONS]:")
        print("="*80)
        for rec in report.recommendations:
            print(f"  * {rec}")

    # Сохранение отчёта
    report_file = analyzer.generate_report_file(report)
    print(f"\n[SAVED] Report saved: {report_file}")

    print("\n" + "="*80)
    print("DONE! Claude can use this information for collaborative code fixes.")
    print("="*80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Claude: чтение и анализ логов')
    parser.add_argument('--session', type=str, help='ID сессии для анализа')
    args = parser.parse_args()

    claude_read_logs(args.session)
