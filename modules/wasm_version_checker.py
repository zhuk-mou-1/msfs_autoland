"""
Модуль для проверки версии MobiFlight WASM Module
Проверяет установленную версию и сравнивает с последней доступной на GitHub
"""

import json
import logging
import os
import re
from typing import Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class MobiFlightVersionChecker:
    """Проверка версии MobiFlight WASM Module"""

    GITHUB_API_URL = "https://api.github.com/repos/MobiFlight/MobiFlight-WASM-Module/releases/latest"
    COMMUNITY_FOLDER = os.path.expandvars(
        r"C:\Users\MYRIG\AppData\Local\Packages\Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalCache\Packages\Community"
    )
    WASM_FOLDER_NAME = "mobiflight-event-module"

    def __init__(self):
        """Инициализация"""
        self.installed_version: Optional[str] = None
        self.latest_version: Optional[str] = None
        self.latest_download_url: Optional[str] = None
        self.update_available: bool = False

    def get_installed_version(self) -> Optional[str]:
        """
        Получить установленную версию из manifest.json

        Returns:
            Версия в формате "1.0.1" или None если не найдена
        """
        manifest_path = os.path.join(
            self.COMMUNITY_FOLDER,
            self.WASM_FOLDER_NAME,
            "manifest.json"
        )

        if not os.path.exists(manifest_path):
            logger.warning("MobiFlight WASM manifest not found: %s", manifest_path)
            return None

        try:
            with open(manifest_path, encoding='utf-8') as f:
                manifest = json.load(f)

            # Версия в формате package_version
            version = manifest.get('package_version')
            if version:
                self.installed_version = version
                logger.info("Installed MobiFlight WASM version: %s", version)
                return version
            else:
                logger.warning("package_version not found in manifest.json")
                return None

        except Exception as e:
            logger.error("Error reading manifest.json: %s", e)
            return None

    def get_latest_version(self) -> Optional[Tuple[str, str]]:
        """
        Получить последнюю версию с GitHub API

        Returns:
            Tuple (version, download_url) или None если ошибка
        """
        try:
            # Валидация URL для безопасности (только HTTPS GitHub API)
            if not self.GITHUB_API_URL.startswith('https://api.github.com/'):
                logger.error("Invalid GitHub API URL: %s", self.GITHUB_API_URL)
                return None

            # GitHub API требует User-Agent
            request = Request(
                self.GITHUB_API_URL,
                headers={'User-Agent': 'MSFS-AutoLand/1.0'}
            )

            with urlopen(request, timeout=10) as response:  # nosec B310
                data = json.loads(response.read().decode('utf-8'))

            # Версия из tag_name (например "v1.0.1")
            tag_name = data.get('tag_name', '')
            version = tag_name.lstrip('v')  # Убираем 'v' если есть

            # URL для скачивания (первый asset)
            assets = data.get('assets', [])
            download_url = None

            if assets:
                # Ищем .zip файл
                for asset in assets:
                    if asset.get('name', '').endswith('.zip'):
                        download_url = asset.get('browser_download_url')
                        break

            if not download_url:
                # Fallback на zipball_url
                download_url = data.get('zipball_url')

            self.latest_version = version
            self.latest_download_url = download_url

            logger.info("Latest MobiFlight WASM version: %s", version)
            logger.info("Download URL: %s", download_url)

            return (version, download_url)

        except HTTPError as e:
            logger.error("HTTP error checking GitHub: %s %s", e.code, e.reason)
            return None
        except URLError as e:
            logger.error("URL error checking GitHub: %s", e.reason)
            return None
        except Exception as e:
            logger.error("Error checking latest version: %s", e)
            return None

    def compare_versions(self, version1: str, version2: str) -> int:
        """
        Сравнить две версии

        Args:
            version1: Первая версия (например "1.0.1")
            version2: Вторая версия (например "1.0.2")

        Returns:
            -1 если version1 < version2
             0 если version1 == version2
             1 если version1 > version2
        """
        # Разбиваем на числа
        def parse_version(v: str) -> list:
            # Убираем 'v' если есть
            v = v.lstrip('v')
            # Извлекаем числа
            parts = re.findall(r'\d+', v)
            return [int(p) for p in parts]

        v1_parts = parse_version(version1)
        v2_parts = parse_version(version2)

        # Дополняем нулями до одинаковой длины
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        # Сравниваем
        for p1, p2 in zip(v1_parts, v2_parts):
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1

        return 0

    def check_for_updates(self) -> Dict:
        """
        Проверить наличие обновлений

        Returns:
            Dict с информацией о версиях и обновлениях:
            {
                'installed_version': str,
                'latest_version': str,
                'update_available': bool,
                'download_url': str,
                'error': str (если была ошибка)
            }
        """
        result = {
            'installed_version': None,
            'latest_version': None,
            'update_available': False,
            'download_url': None,
            'error': None
        }

        # Получаем установленную версию
        installed = self.get_installed_version()
        if not installed:
            result['error'] = "MobiFlight WASM not installed or manifest.json not found"
            return result

        result['installed_version'] = installed

        # Получаем последнюю версию
        latest_info = self.get_latest_version()
        if not latest_info:
            result['error'] = "Failed to check latest version from GitHub"
            return result

        latest_version, download_url = latest_info
        result['latest_version'] = latest_version
        result['download_url'] = download_url

        # Сравниваем версии
        comparison = self.compare_versions(installed, latest_version)

        if comparison < 0:
            # Установленная версия старше
            result['update_available'] = True
            self.update_available = True
            logger.info("Update available: %s -> %s", installed, latest_version)
        elif comparison == 0:
            logger.info("MobiFlight WASM is up to date: %s", installed)
        else:
            logger.info("Installed version is newer than latest release: %s > %s", installed, latest_version)

        return result

    def get_update_message(self) -> Optional[str]:
        """
        Получить сообщение об обновлении для отображения пользователю

        Returns:
            Строка с сообщением или None если обновление не требуется
        """
        if not self.update_available:
            return None

        message = (
            f"Доступно обновление MobiFlight WASM!\n\n"
            f"Установленная версия: {self.installed_version}\n"
            f"Последняя версия: {self.latest_version}\n\n"
            f"Скачать: {self.latest_download_url}\n\n"
            f"Инструкции по установке см. в MOBIFLIGHT_SETUP.md"
        )

        return message


def check_mobiflight_version(show_message: bool = True) -> Dict:
    """
    Удобная функция для проверки версии MobiFlight WASM

    Args:
        show_message: Показывать ли сообщение в логе

    Returns:
        Dict с результатами проверки
    """
    checker = MobiFlightVersionChecker()
    result = checker.check_for_updates()

    if show_message and result.get('update_available'):
        message = checker.get_update_message()
        if message:
            logger.warning(message)

    return result


if __name__ == "__main__":
    # Настройка логирования для теста
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("MobiFlight WASM Version Checker")
    print("=" * 70)
    print()

    checker = MobiFlightVersionChecker()
    result = checker.check_for_updates()

    print("Результаты проверки:")
    print(f"  Установленная версия: {result.get('installed_version', 'Не найдена')}")
    print(f"  Последняя версия: {result.get('latest_version', 'Не найдена')}")
    print(f"  Обновление доступно: {'Да' if result.get('update_available') else 'Нет'}")

    if result.get('download_url'):
        print(f"  URL для скачивания: {result['download_url']}")

    if result.get('error'):
        print(f"  Ошибка: {result['error']}")

    print()

    if result.get('update_available'):
        print(checker.get_update_message())
