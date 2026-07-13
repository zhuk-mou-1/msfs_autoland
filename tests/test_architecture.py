"""
Архитектурные тесты для MSFS AutoLand

Проверяют структурные правила проекта:
- Слоистость архитектуры
- Отсутствие циклических зависимостей
- Контракты интерфейсов
- Правильность импортов
"""

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple
import pytest


class ArchitectureAnalyzer:
    """Анализатор архитектуры проекта"""

    def __init__(self, project_root: str = None):
        if project_root is None:
            # Resolve relative to this test file's directory
            project_root = str(Path(__file__).resolve().parent.parent)
        self.project_root = Path(project_root)
        self.modules_dir = self.project_root / "modules"

    def get_imports(self, file_path: Path) -> Set[str]:
        """Извлекает все импорты из Python файла"""
        try:
            with open(file_path, encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")
            return set()

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])

        return imports

    def get_module_imports(self, module_name: str) -> Set[str]:
        """Получает импорты конкретного модуля"""
        module_path = self.modules_dir / f"{module_name}.py"
        if not module_path.exists():
            return set()
        return self.get_imports(module_path)

    def find_circular_dependencies(self) -> List[Tuple[str, str]]:
        """Находит циклические зависимости между модулями"""
        circular = []
        module_files = list(self.modules_dir.glob("*.py"))

        # Строим граф зависимостей
        dependencies: Dict[str, Set[str]] = {}
        for module_file in module_files:
            if module_file.name == "__init__.py":
                continue
            module_name = module_file.stem
            imports = self.get_imports(module_file)
            # Фильтруем только локальные модули
            local_imports = {imp for imp in imports if imp in [f.stem for f in module_files]}
            dependencies[module_name] = local_imports

        # Проверяем циклы
        for module_a, imports_a in dependencies.items():
            for module_b in imports_a:
                if module_b in dependencies:
                    if module_a in dependencies[module_b]:
                        circular.append((module_a, module_b))

        return circular

    def check_layer_violation(self, layer_rules: Dict[str, List[str]]) -> List[str]:
        """
        Проверяет нарушения слоёв архитектуры

        layer_rules: {layer_name: [allowed_dependencies]}
        """
        violations = []

        for layer, allowed_deps in layer_rules.items():
            layer_files = list(self.modules_dir.glob(f"{layer}*.py"))
            for layer_file in layer_files:
                imports = self.get_imports(layer_file)
                for imp in imports:
                    # Проверяем только локальные модули
                    if any(imp.startswith(prefix) for prefix in ["modules", "gui", "main"]):
                        if not any(imp.startswith(allowed) for allowed in allowed_deps):
                            violations.append(
                                f"{layer_file.name} импортирует {imp}, что нарушает правила слоя"
                            )

        return violations


# ============================================================================
# ТЕСТ 1: Циклические зависимости
# ============================================================================

def test_no_circular_dependencies():
    """
    Проверяет отсутствие циклических зависимостей между модулями

    Циклические зависимости (A импортит B, B импортит A) приводят к:
    - Проблемам с инициализацией
    - Сложности понимания кода
    - Невозможности изолированного тестирования
    """
    analyzer = ArchitectureAnalyzer()
    circular = analyzer.find_circular_dependencies()

    if circular:
        msg = "Обнаружены циклические зависимости:\n"
        for module_a, module_b in circular:
            msg += f"  - {module_a} ↔ {module_b}\n"
        pytest.fail(msg)


# ============================================================================
# ТЕСТ 2: Слоистость архитектуры
# ============================================================================

def test_layer_separation():
    """
    Проверяет правильность слоёв архитектуры

    Архитектура MSFS AutoLand:

    Layer 1 (Core): telemetry, control
      ↓
    Layer 2 (Navigation): navigation, ils_navigation, dme_navigation
      ↓
    Layer 3 (Controllers): autothrottle, flare_controller, autopilot_takeover
      ↓
    Layer 4 (Integration): main.py, gui.py

    Правило: Нижние слои НЕ должны импортировать верхние
    """
    analyzer = ArchitectureAnalyzer()

    # Core модули не должны импортировать GUI
    core_modules = ["telemetry", "control", "simconnect_client_data"]
    for module in core_modules:
        imports = analyzer.get_module_imports(module)
        gui_imports = [imp for imp in imports if "tkinter" in imp or "gui" in imp]
        assert not gui_imports, f"{module} не должен импортировать GUI: {gui_imports}"

    # Navigation модули не должны импортировать Controllers
    nav_modules = ["navigation", "ils_navigation", "dme_navigation"]
    controller_modules = ["autothrottle", "flare_controller", "autopilot_takeover"]

    for nav_module in nav_modules:
        imports = analyzer.get_module_imports(nav_module)
        controller_imports = [imp for imp in imports if imp in controller_modules]
        assert not controller_imports, \
            f"{nav_module} не должен импортировать контроллеры: {controller_imports}"


# ============================================================================
# ТЕСТ 3: Контракты интерфейсов
# ============================================================================

def test_controller_interface_contract():
    """
    Проверяет что все контроллеры имеют обязательные методы

    Контроллеры должны иметь:
    - update() - обновление состояния
    - reset() - сброс состояния
    """
    analyzer = ArchitectureAnalyzer()

    controllers = {
        "autothrottle": ["update", "reset"],
        "flare_controller": ["update", "reset"],
        "wind_correction": ["apply_wind_corrections"],
    }

    for controller, required_methods in controllers.items():
        module_path = analyzer.modules_dir / f"{controller}.py"
        if not module_path.exists():
            continue

        with open(module_path, encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content)

        # Находим все методы в классах
        found_methods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        found_methods.add(item.name)

        for method in required_methods:
            assert method in found_methods, \
                f"{controller} должен иметь метод {method}()"


# ============================================================================
# ТЕСТ 4: Запрещённые импорты
# ============================================================================

def test_no_forbidden_imports():
    """
    Проверяет отсутствие запрещённых импортов

    Запрещено:
    - Audio модули не должны импортировать control/autopilot
    - Logger модули не должны импортировать бизнес-логику
    - Config модули не должны импортировать runtime компоненты
    """
    analyzer = ArchitectureAnalyzer()

    # Audio модуль должен только читать состояние, не управлять
    audio_imports = analyzer.get_module_imports("audio_alerts")
    forbidden_for_audio = ["control", "autopilot_takeover", "autothrottle"]
    violations = [imp for imp in audio_imports if imp in forbidden_for_audio]
    assert not violations, \
        f"audio_alerts не должен импортировать управляющие модули: {violations}"

    # Logger не должен импортировать бизнес-логику
    logger_imports = analyzer.get_module_imports("structured_logger")
    forbidden_for_logger = ["navigation", "control", "autothrottle"]
    violations = [imp for imp in logger_imports if imp in forbidden_for_logger]
    assert not violations, \
        f"structured_logger не должен импортировать бизнес-логику: {violations}"


# ============================================================================
# ТЕСТ 5: Dependency Injection
# ============================================================================

def test_main_uses_dependency_injection():
    """
    Проверяет что main.py использует dependency injection

    main.py должен создавать все зависимости и передавать их,
    а не позволять модулям создавать зависимости самостоятельно
    """
    analyzer = ArchitectureAnalyzer()
    main_path = analyzer.project_root / "main.py"

    with open(main_path, encoding='utf-8') as f:
        content = f.read()
        tree = ast.parse(content)

    # Проверяем что в __init__ создаются все основные компоненты
    required_components = [
        "MSFSTelemetry",
        "Navigation",
        "AutothrottleController",
        "FlareController",
    ]

    found_components = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                found_components.append(node.func.id)

    for component in required_components:
        assert component in found_components, \
            f"main.py должен создавать {component} в __init__"


# ============================================================================
# ТЕСТ 6: Модульная независимость
# ============================================================================

def test_modules_are_importable_independently():
    """
    Проверяет что модули можно импортировать независимо

    Каждый модуль должен быть самодостаточным и не требовать
    инициализации других модулей для импорта
    """
    analyzer = ArchitectureAnalyzer()

    # Список модулей которые должны импортироваться независимо
    independent_modules = [
        "navigation",
        "wind_correction",
        "approach_speed_calculator",
        "turbulence_detector",
        "wind_shear_detector",
    ]

    for module_name in independent_modules:
        try:
            # Пытаемся импортировать модуль
            exec(f"from modules.{module_name} import *")
        except ImportError as e:
            pytest.fail(f"Модуль {module_name} не может быть импортирован независимо: {e}")


# ============================================================================
# ТЕСТ 7: Конфигурация отделена от логики
# ============================================================================

def test_config_separation():
    """
    Проверяет что конфигурация отделена от бизнес-логики

    Config модули не должны содержать бизнес-логику
    """
    analyzer = ArchitectureAnalyzer()

    config_modules = [
        "aircraft_config_reader",
        "airports_database",
        "settings",
        "thresholds_config",
    ]

    for config_module in config_modules:
        module_path = analyzer.modules_dir / f"{config_module}.py"
        if not module_path.exists():
            continue

        with open(module_path, encoding='utf-8') as f:
            content = f.read()

        # Config модули не должны импортировать control/navigation
        forbidden = ["from modules.control", "from modules.navigation",
                     "from modules.autothrottle"]
        for forbidden_import in forbidden:
            assert forbidden_import not in content, \
                f"{config_module} не должен импортировать бизнес-логику"


# ============================================================================
# ТЕСТ 8: UI не влияет на Core логику
# ============================================================================

def test_ui_does_not_affect_core():
    """
    Проверяет что UI (gui.py, dialogs) не влияет на core логику

    Core модули не должны знать о существовании GUI
    """
    analyzer = ArchitectureAnalyzer()

    core_modules = [
        "telemetry",
        "control",
        "navigation",
        "ils_navigation",
        "autothrottle",
        "flare_controller",
    ]

    for core_module in core_modules:
        imports = analyzer.get_module_imports(core_module)
        ui_imports = [imp for imp in imports if "tkinter" in imp or "dialog" in imp]
        assert not ui_imports, \
            f"Core модуль {core_module} не должен импортировать UI: {ui_imports}"


# ============================================================================
# ТЕСТ 9: Адаптеры изолированы
# ============================================================================

def test_adapter_isolation():
    """
    Проверяет что адаптеры (aircraft_adapter, wasm_interface) изолированы

    Адаптеры должны быть заменяемыми без изменения core логики
    """
    analyzer = ArchitectureAnalyzer()

    # Проверяем что core модули не импортируют адаптеры напрямую
    core_modules = ["navigation", "autothrottle", "flare_controller"]
    adapters = ["aircraft_adapter", "wasm_interface"]

    for core_module in core_modules:
        imports = analyzer.get_module_imports(core_module)
        adapter_imports = [imp for imp in imports if imp in adapters]
        assert not adapter_imports, \
            f"{core_module} не должен напрямую импортировать адаптеры: {adapter_imports}"


# ============================================================================
# ТЕСТ 10: Детекторы независимы
# ============================================================================

def test_detector_independence():
    """
    Проверяет что детекторы (turbulence, wind_shear, engine_failure) независимы

    Детекторы должны только анализировать данные, не управлять системой
    """
    analyzer = ArchitectureAnalyzer()

    detectors = [
        "turbulence_detector",
        "wind_shear_detector",
        "engine_failure_detector",
    ]

    forbidden_imports = ["control", "autopilot_takeover", "autothrottle"]

    for detector in detectors:
        imports = analyzer.get_module_imports(detector)
        violations = [imp for imp in imports if imp in forbidden_imports]
        assert not violations, \
            f"{detector} не должен импортировать управляющие модули: {violations}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
