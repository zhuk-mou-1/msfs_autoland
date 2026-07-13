"""
Модуль автоматической генерации исправлений кода
Анализирует код и генерирует патчи, НЕ модифицируя файлы
"""

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeFix:
    """Предложение по исправлению кода"""
    file_path: str
    line_number: int
    function_name: str
    error_type: str
    severity: str
    description: str
    current_code: str
    suggested_code: str
    explanation: str


class AutoFixer:
    """Генератор исправлений кода (только анализ, без модификации)"""

    def __init__(self, project_root: str = "."):
        """
        Args:
            project_root: Корневая директория проекта
        """
        self.project_root = Path(project_root)
        self.fixes: List[CodeFix] = []

    def generate_fixes(self, analysis_report) -> List[CodeFix]:
        """
        Генерация исправлений на основе отчёта анализа

        Args:
            analysis_report: Отчёт от LogAnalyzer

        Returns:
            Список предложений по исправлению
        """
        self.fixes = []

        for code_fix in analysis_report.code_fixes:
            for file_path in code_fix['affected_files']:
                for function_name in code_fix['affected_functions']:
                    fix = self._analyze_and_generate_fix(
                        file_path=file_path,
                        function_name=function_name,
                        error_type=code_fix['error_type'],
                        severity=code_fix['severity'],
                        description=code_fix['description'],
                        suggested_fix=code_fix['suggested_fix']
                    )
                    if fix:
                        self.fixes.append(fix)

        logger.info(f"Generated {len(self.fixes)} code fixes")
        return self.fixes

    def _analyze_and_generate_fix(self, file_path: str, function_name: str,
                                   error_type: str, severity: str,
                                   description: str, suggested_fix: str) -> Optional[CodeFix]:
        """
        Анализ кода и генерация конкретного исправления

        Args:
            file_path: Путь к файлу
            function_name: Имя функции
            error_type: Тип ошибки
            severity: Критичность
            description: Описание проблемы
            suggested_fix: Предложенное исправление

        Returns:
            CodeFix или None
        """
        full_path = self.project_root / file_path
        if not full_path.exists():
            logger.warning(f"File not found: {full_path}")
            return None

        try:
            with open(full_path, encoding='utf-8') as f:
                source_code = f.read()

            tree = ast.parse(source_code)

            # Поиск функции в AST
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    line_number = node.lineno

                    # Извлечение текущего кода функции
                    lines = source_code.split('\n')
                    current_code = self._extract_function_code(lines, line_number)

                    # Генерация исправленного кода
                    suggested_code = self._generate_suggested_code(
                        current_code, error_type, suggested_fix
                    )

                    return CodeFix(
                        file_path=file_path,
                        line_number=line_number,
                        function_name=function_name,
                        error_type=error_type,
                        severity=severity,
                        description=description,
                        current_code=current_code,
                        suggested_code=suggested_code,
                        explanation=suggested_fix
                    )

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return None

        return None

    def _extract_function_code(self, lines: List[str], start_line: int,
                               context_lines: int = 5) -> str:
        """
        Извлечение кода функции с контекстом

        Args:
            lines: Строки файла
            start_line: Начальная строка функции (1-indexed)
            context_lines: Количество строк контекста

        Returns:
            Код функции
        """
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), start_line + context_lines)
        return '\n'.join(lines[start_idx:end_idx])

    def _generate_suggested_code(self, current_code: str, error_type: str,
                                 suggested_fix: str) -> str:
        """
        Генерация предложенного кода (шаблон)

        Args:
            current_code: Текущий код
            error_type: Тип ошибки
            suggested_fix: Текстовое описание исправления

        Returns:
            Предложенный код (с комментариями)
        """
        # Простая генерация с комментариями
        # В будущем можно добавить реальную модификацию AST

        suggestion = f"# {suggested_fix}\n"

        if error_type == 'AttributeError':
            suggestion += "# Добавить проверку:\n"
            suggestion += "# if obj is not None:\n"
            suggestion += "#     obj.attribute\n\n"
        elif error_type == 'KeyError':
            suggestion += "# Заменить dict[key] на:\n"
            suggestion += "# value = dict.get(key, default_value)\n\n"
        elif error_type == 'IndexError':
            suggestion += "# Добавить проверку:\n"
            suggestion += "# if len(list) > index:\n"
            suggestion += "#     list[index]\n\n"

        suggestion += current_code
        return suggestion

    def generate_fix_report(self, fixes: List[CodeFix], output_file: Path):
        """
        Генерация отчёта с исправлениями

        Args:
            fixes: Список исправлений
            output_file: Путь к выходному файлу
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Отчёт автоматических исправлений\n\n")
            f.write(f"**Дата:** {Path(__file__).stat().st_mtime}\n")
            f.write(f"**Всего исправлений:** {len(fixes)}\n\n")
            f.write("---\n\n")

            for i, fix in enumerate(fixes, 1):
                f.write(f"## {i}. {fix.file_path}:{fix.line_number} - {fix.function_name}\n\n")
                f.write(f"**Тип ошибки:** {fix.error_type}\n")
                f.write(f"**Критичность:** {fix.severity}\n")
                f.write(f"**Описание:** {fix.description}\n\n")

                f.write("### Текущий код:\n\n")
                f.write("```python\n")
                f.write(fix.current_code)
                f.write("\n```\n\n")

                f.write("### Предложенное исправление:\n\n")
                f.write("```python\n")
                f.write(fix.suggested_code)
                f.write("\n```\n\n")

                f.write(f"**Объяснение:** {fix.explanation}\n\n")
                f.write("---\n\n")

        logger.info(f"Fix report generated: {output_file}")

    def generate_diff(self, fix: CodeFix) -> str:
        """
        Генерация diff для исправления

        Args:
            fix: Исправление

        Returns:
            Unified diff
        """
        import difflib

        current_lines = fix.current_code.split('\n')
        suggested_lines = fix.suggested_code.split('\n')

        diff = difflib.unified_diff(
            current_lines,
            suggested_lines,
            fromfile=f"{fix.file_path} (current)",
            tofile=f"{fix.file_path} (suggested)",
            lineterm=''
        )

        return '\n'.join(diff)
