"""
Скрипт для Claude: подключение к базе данных логов и чтение информации
Позволяет Claude читать логи из SQLite базы данных
"""

import sys
from datetime import datetime
from pathlib import Path

# Добавление корневой директории в путь
sys.path.insert(0, str(Path(__file__).parent))

from modules.log_database import LogDatabase


def format_timestamp(timestamp: float) -> str:
    """Форматировать timestamp"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def claude_read_database(session_id: str = None):
    """
    Команда для Claude: прочитать логи из базы данных

    Args:
        session_id: ID сессии (если None, берётся последняя)
    """
    db = LogDatabase()

    print("\n[DATABASE] CONNECTING TO LOG DATABASE")
    print("="*80)

    # Статистика базы данных
    stats = db.get_database_stats()
    print("\n[STATS] DATABASE STATISTICS:")
    print(f"Total sessions: {stats['total_sessions']}")
    print(f"Total logs: {stats['total_logs']}")
    print(f"Total errors: {stats['total_errors']}")
    print(f"Database size: {stats['db_size_mb']:.2f} MB")

    # Определение сессии
    if session_id is None:
        latest = db.get_latest_session()
        if not latest:
            print("\n[ERROR] No sessions found. Run the program to generate logs.")
            return
        session_id = latest['session_id']

    print(f"\n[ANALYSIS] SESSION: {session_id}")
    print("="*80)

    # Информация о сессии
    session_info = db.get_session_info(session_id)
    if not session_info:
        print(f"[ERROR] Session {session_id} not found")
        return

    print("\n[INFO] SESSION INFORMATION:")
    print(f"Start: {format_timestamp(session_info['start_time'])}")
    if session_info['end_time']:
        print(f"End: {format_timestamp(session_info['end_time'])}")
        duration = session_info['end_time'] - session_info['start_time']
        print(f"Duration: {duration:.1f} seconds")
    print(f"Status: {session_info['status']}")
    print(f"Total logs: {session_info['total_logs']}")
    print(f"Errors: {session_info['error_count']}")
    print(f"Warnings: {session_info['warning_count']}")

    # Ошибки
    errors = db.get_session_errors(session_id)
    if errors:
        print(f"\n[ERRORS] FOUND ERRORS ({len(errors)}):")
        print("="*80)

        for i, error in enumerate(errors, 1):
            severity = '[!!!]' if error['count'] > 5 else '[!!]'
            print(f"\n{i}. {severity} {error['error_type']}")
            print(f"   Message: {error['message']}")
            print(f"   Count: {error['count']}")
            print(f"   Module: {error['module']}")
            print(f"   Function: {error['function']}")
            print(f"   First occurrence: {format_timestamp(error['first_occurrence'])}")
            print(f"   Last occurrence: {format_timestamp(error['last_occurrence'])}")

    # Производительность
    perf_stats = db.get_performance_stats(session_id)
    if perf_stats:
        print("\n[PERFORMANCE] PERFORMANCE STATS:")
        print("="*80)

        # Сортировка по среднему времени
        sorted_perf = sorted(perf_stats.items(), key=lambda x: x[1]['avg_ms'], reverse=True)

        for operation, stats in sorted_perf[:10]:
            print(f"  * {operation}:")
            print(f"    Avg: {stats['avg_ms']:.1f}ms, "
                  f"Min: {stats['min_ms']:.1f}ms, "
                  f"Max: {stats['max_ms']:.1f}ms "
                  f"({stats['count']} measurements)")

    # Последние критические логи
    critical_logs = db.get_session_logs(session_id, level='CRITICAL', limit=10)
    if critical_logs:
        print(f"\n[CRITICAL] CRITICAL EVENTS ({len(critical_logs)}):")
        print("="*80)

        for log in critical_logs:
            print(f"\n[{format_timestamp(log['timestamp'])}] {log['category']}")
            print(f"   {log['message']}")
            print(f"   Module: {log['module']}, Function: {log['function']}, Line: {log['line']}")

    # Последние ошибки
    error_logs = db.get_session_logs(session_id, level='ERROR', limit=10)
    if error_logs:
        print(f"\n[ERROR] RECENT ERRORS ({len(error_logs)}):")
        print("="*80)

        for log in error_logs:
            print(f"\n[{format_timestamp(log['timestamp'])}] {log['category']}")
            print(f"   {log['message']}")
            print(f"   Module: {log['module']}, Function: {log['function']}, Line: {log['line']}")
            if log['exception_type']:
                print(f"   Exception: {log['exception_type']}: {log['exception_message']}")

    print("\n" + "="*80)
    print("DONE! Claude can use this information for code fixes.")
    print("="*80)


def claude_search_logs(search_text: str, session_id: str = None):
    """
    Поиск в логах

    Args:
        search_text: Текст для поиска
        session_id: ID сессии (опционально)
    """
    db = LogDatabase()

    print(f"\n[SEARCH] SEARCHING LOGS: '{search_text}'")
    print("="*80)

    results = db.search_logs(search_text, session_id, limit=50)

    if not results:
        print("[INFO] Nothing found")
        return

    print(f"\n[FOUND] Records found: {len(results)}")
    print("="*80)

    for log in results:
        print(f"\n[{format_timestamp(log['timestamp'])}] [{log['level']}] {log['category']}")
        print(f"   {log['message']}")
        print(f"   Session: {log['session_id']}")
        print(f"   Module: {log['module']}, Function: {log['function']}")


def claude_list_sessions():
    """Показать список всех сессий"""
    db = LogDatabase()

    print("\n[LIST] SESSION LIST")
    print("="*80)

    sessions = db.get_all_sessions(limit=20)

    if not sessions:
        print("[INFO] No sessions found")
        return

    print(f"\nTotal sessions: {len(sessions)}\n")

    for i, session in enumerate(sessions, 1):
        print(f"{i}. {session['session_id']}")
        print(f"   Start: {format_timestamp(session['start_time'])}")
        if session['end_time']:
            print(f"   End: {format_timestamp(session['end_time'])}")
        print(f"   Status: {session['status']}")
        print(f"   Logs: {session['total_logs']}, "
              f"Errors: {session['error_count']}, "
              f"Warnings: {session['warning_count']}")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Claude: работа с базой данных логов')
    subparsers = parser.add_subparsers(dest='command', help='Команды')

    # Команда read
    read_parser = subparsers.add_parser('read', help='Прочитать логи сессии')
    read_parser.add_argument('--session', type=str, help='ID сессии')

    # Команда search
    search_parser = subparsers.add_parser('search', help='Поиск в логах')
    search_parser.add_argument('text', type=str, help='Текст для поиска')
    search_parser.add_argument('--session', type=str, help='ID сессии')

    # Команда list
    list_parser = subparsers.add_parser('list', help='Список сессий')

    args = parser.parse_args()

    if args.command == 'read':
        claude_read_database(args.session)
    elif args.command == 'search':
        claude_search_logs(args.text, args.session)
    elif args.command == 'list':
        claude_list_sessions()
    else:
        # По умолчанию - чтение последней сессии
        claude_read_database()
