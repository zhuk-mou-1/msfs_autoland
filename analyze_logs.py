"""
Скрипт анализа логов и генерации отчётов
Запускается после завершения сессии или вручную
"""

import argparse
import sys
from pathlib import Path

# Добавление корневой директории в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.auto_fixer import AutoFixer
from modules.log_analyzer import LogAnalyzer


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Анализ логов MSFS AutoLand')
    parser.add_argument('--session', type=str, help='ID сессии для анализа')
    parser.add_argument('--latest', action='store_true', help='Анализировать последнюю сессию')
    parser.add_argument('--log-dir', type=str, default='logs', help='Директория с логами')
    parser.add_argument('--generate-fixes', action='store_true', help='Генерировать предложения по исправлению')
    parser.add_argument('--output', type=str, help='Путь к выходному файлу отчёта')

    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    if not log_dir.exists():
        print(f"Директория логов не найдена: {log_dir}")
        return 1

    analyzer = LogAnalyzer(str(log_dir))

    # Определение сессии для анализа
    if args.latest or not args.session:
        # Найти последнюю сессию
        log_files = list(log_dir.glob("session_*.jsonl"))
        if not log_files:
            print("Логи не найдены")
            return 1

        latest_file = max(log_files, key=lambda p: p.stat().st_mtime)
        session_id = latest_file.stem.replace("session_", "")
        print(f"Анализ последней сессии: {session_id}")
    else:
        session_id = args.session
        print(f"Анализ сессии: {session_id}")

    # Анализ
    try:
        report = analyzer.analyze_session(session_id)
    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
        return 1

    # Генерация отчёта
    output_file = Path(args.output) if args.output else None
    report_file = analyzer.generate_report_file(report, output_file)
    print(f"\nОтчёт сохранён: {report_file}")

    # Вывод сводки
    print("\n" + "="*80)
    print("СВОДКА АНАЛИЗА")
    print("="*80)
    print(f"\nСессия: {report.session_id}")
    print(f"Время анализа: {report.analysis_time}")
    print(f"\nВсего записей: {report.total_logs}")
    print(f"Ошибок: {report.error_count}")
    print(f"Предупреждений: {report.warning_count}")

    if report.error_patterns:
        print(f"\nОбнаружено паттернов ошибок: {len(report.error_patterns)}")
        print("\nТоп-5 ошибок:")
        for i, pattern in enumerate(report.error_patterns[:5], 1):
            print(f"  {i}. [{pattern.severity}] {pattern.error_type}: {pattern.message_pattern[:80]}...")
            print(f"     Количество: {pattern.count}, Модули: {', '.join(pattern.affected_modules[:3])}")

    if report.performance_issues:
        print(f"\nПроблемы производительности: {len(report.performance_issues)}")
        for issue in report.performance_issues[:3]:
            print(f"  - {issue['operation']}: {issue['avg_duration_ms']:.1f}ms среднее")

    print(f"\n{report.summary}")

    if report.recommendations:
        print("\nРЕКОМЕНДАЦИИ:")
        for rec in report.recommendations[:10]:
            print(f"  • {rec}")

    # Генерация исправлений
    if args.generate_fixes and report.error_patterns:
        print("\n" + "="*80)
        print("ГЕНЕРАЦИЯ ИСПРАВЛЕНИЙ")
        print("="*80)

        fixer = AutoFixer()
        fixes = fixer.generate_fixes(report)

        if fixes:
            fix_report_file = log_dir / f"fixes_{session_id}.md"
            fixer.generate_fix_report(fixes, fix_report_file)
            print(f"\nСгенерировано исправлений: {len(fixes)}")
            print(f"Отчёт с исправлениями: {fix_report_file}")

            print("\nПредлагаемые исправления:")
            for i, fix in enumerate(fixes[:5], 1):
                print(f"  {i}. {fix.file_path}:{fix.line_number} -> {fix.function_name}")
                print(f"     {fix.description}")
        else:
            print("\nИсправления не требуются")

    print("\n" + "="*80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
