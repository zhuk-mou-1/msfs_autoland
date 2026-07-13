"""
Модуль для чтения конфигурационных файлов кастомных самолётов
Читает manifest.json и aircraft.cfg для определения типа самолёта
"""

import configparser
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AircraftConfigReader:
    """Класс для чтения конфигурации самолётов из файлов"""

    def __init__(self):
        self.msfs_packages_paths = self._get_msfs_packages_paths()

    def _get_msfs_packages_paths(self) -> List[Path]:
        """
        Получить возможные пути к папкам с самолётами MSFS

        Returns:
            Список путей к папкам Community и Official
        """
        possible_paths = []

        # Стандартные пути MSFS 2020
        msfs_2020_paths = [
            Path.home() / "AppData/Local/Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalCache/Packages",
            Path.home() / "AppData/Roaming/Microsoft Flight Simulator/Packages",
            Path("C:/Program Files/WindowsApps/Microsoft.FlightSimulator_*/Packages"),
        ]

        # Стандартные пути MSFS 2024
        msfs_2024_paths = [
            Path.home() / "AppData/Local/Packages/Microsoft.Limitless_8wekyb3d8bbwe/LocalCache/Packages",
        ]

        # Steam версия
        steam_paths = [
            Path("C:/Program Files (x86)/Steam/steamapps/common/MicrosoftFlightSimulator/Packages"),
        ]

        all_paths = msfs_2020_paths + msfs_2024_paths + steam_paths

        for path in all_paths:
            if path.exists():
                # Добавляем Community и Official папки
                community = path / "Community"
                official = path / "Official"

                if community.exists():
                    possible_paths.append(community)
                if official.exists():
                    possible_paths.append(official)

        logger.info("Found %s MSFS package directories", len(possible_paths))
        return possible_paths

    def find_aircraft_folder(self, aircraft_title: str) -> Optional[Path]:
        """
        Найти папку самолёта по его названию

        Args:
            aircraft_title: Название самолёта из SimConnect (TITLE)

        Returns:
            Path к папке самолёта или None
        """
        if not aircraft_title:
            return None

        # Очистка названия для поиска
        search_terms = aircraft_title.lower().split()

        for packages_path in self.msfs_packages_paths:
            try:
                # Перебираем все папки в Community/Official
                for aircraft_folder in packages_path.iterdir():
                    if not aircraft_folder.is_dir():
                        continue

                    folder_name = aircraft_folder.name.lower()

                    # Проверяем совпадение ключевых слов
                    if any(term in folder_name for term in search_terms):
                        # Проверяем наличие manifest.json или aircraft.cfg
                        if (aircraft_folder / "manifest.json").exists() or \
                           any((aircraft_folder / "SimObjects/Airplanes").glob("*/aircraft.cfg")):
                            logger.info("Found aircraft folder: %s", aircraft_folder)
                            return aircraft_folder

            except Exception as e:
                logger.warning("Error scanning %s: %s", packages_path, e)

        logger.debug("Aircraft folder not found for: %s", aircraft_title)
        return None

    def read_manifest(self, aircraft_folder: Path) -> Optional[Dict]:
        """
        Прочитать manifest.json

        Args:
            aircraft_folder: Путь к папке самолёта

        Returns:
            Dict с данными из manifest.json или None
        """
        manifest_path = aircraft_folder / "manifest.json"

        if not manifest_path.exists():
            logger.debug("manifest.json not found in %s", aircraft_folder)
            return None

        try:
            with open(manifest_path, encoding='utf-8') as f:
                manifest = json.load(f)
                logger.info("Successfully read manifest.json from %s", aircraft_folder.name)
                return manifest
        except Exception as e:
            logger.error("Error reading manifest.json: %s", e)
            return None

    def read_aircraft_cfg(self, aircraft_folder: Path) -> Optional[Dict]:
        """
        Прочитать aircraft.cfg

        Args:
            aircraft_folder: Путь к папке самолёта

        Returns:
            Dict с данными из aircraft.cfg или None
        """
        # Ищем aircraft.cfg в SimObjects/Airplanes
        simobjects_path = aircraft_folder / "SimObjects/Airplanes"

        if not simobjects_path.exists():
            logger.debug("SimObjects/Airplanes not found in %s", aircraft_folder)
            return None

        try:
            # Ищем первый aircraft.cfg
            for aircraft_cfg_path in simobjects_path.rglob("aircraft.cfg"):
                config = configparser.ConfigParser()
                config.read(aircraft_cfg_path, encoding='utf-8')

                # Извлекаем важные секции
                result = {}

                # [GENERAL]
                if 'GENERAL' in config:
                    result['general'] = dict(config['GENERAL'])

                # [FLTSIM.0] - основная ливрея
                if 'FLTSIM.0' in config:
                    result['fltsim'] = dict(config['FLTSIM.0'])

                # [AUTOPILOT] - если есть
                if 'AUTOPILOT' in config:
                    result['autopilot'] = dict(config['AUTOPILOT'])

                logger.info("Successfully read aircraft.cfg from %s", aircraft_cfg_path)
                return result

        except Exception as e:
            logger.error("Error reading aircraft.cfg: %s", e)
            return None

        return None

    def detect_aircraft_profile(self, aircraft_title: str) -> Optional[str]:
        """
        Определить профиль самолёта по конфигурационным файлам

        Args:
            aircraft_title: Название самолёта из SimConnect

        Returns:
            Ключ профиля (например, "PMDG_737") или None
        """
        # Найти папку самолёта
        aircraft_folder = self.find_aircraft_folder(aircraft_title)

        if not aircraft_folder:
            return None

        # Читаем manifest.json
        manifest = self.read_manifest(aircraft_folder)

        if manifest:
            profile = self._detect_from_manifest(manifest, aircraft_folder.name)
            if profile:
                return profile

        # Читаем aircraft.cfg
        aircraft_cfg = self.read_aircraft_cfg(aircraft_folder)

        if aircraft_cfg:
            profile = self._detect_from_aircraft_cfg(aircraft_cfg, aircraft_folder.name)
            if profile:
                return profile

        return None

    def _check_pmdg(self, creator: str, manufacturer: str, title: str, folder: str) -> Optional[str]:
        """Проверка PMDG самолётов"""
        if not any(keyword in text for text in [creator, manufacturer, folder] for keyword in ['pmdg']):
            return None

        if '737' in title or '737' in folder:
            logger.info("Detected PMDG_737 from manifest")
            return 'PMDG_737'
        elif '777' in title or '777' in folder:
            logger.info("Detected PMDG_777 from manifest")
            return 'PMDG_777'
        return None

    def _check_fenix(self, creator: str, manufacturer: str, title: str, folder: str) -> Optional[str]:
        """Проверка Fenix самолётов"""
        if not any(keyword in text for text in [creator, manufacturer, folder] for keyword in ['fenix']):
            return None

        if 'a320' in title or 'a320' in folder:
            logger.info("Detected FENIX_A320 from manifest")
            return 'FENIX_A320'
        return None

    def _check_flybywire(self, creator: str, manufacturer: str, title: str, folder: str) -> Optional[str]:
        """Проверка FlyByWire самолётов"""
        if not any(keyword in text for text in [creator, manufacturer, folder] for keyword in ['flybywire', 'fbw']):
            return None

        if any(model in title or model in folder for model in ['a32nx', 'a320']):
            logger.info("Detected FBW_A32NX from manifest")
            return 'FBW_A32NX'
        return None

    def _check_fslabs(self, creator: str, manufacturer: str, folder: str, title: str) -> Optional[str]:
        """Проверка FSLabs самолётов"""
        if not any(keyword in text for text in [creator, folder] for keyword in ['fslabs', 'flight sim labs']):
            return None

        if any(model in title for model in ['a32', 'a320', 'a319', 'a321']):
            logger.info("Detected FSLABS_A32X from manifest")
            return 'FSLABS_A32X'
        return None

    def _check_inibuilds(self, creator: str, manufacturer: str, title: str, folder: str) -> Optional[str]:
        """Проверка iniBuilds самолётов"""
        if not any(keyword in text for text in [creator, folder] for keyword in ['inibuilds', 'ini builds']):
            return None

        if 'a300' in title or 'a300' in folder:
            logger.info("Detected INIBUILDS_A300 from manifest")
            return 'INIBUILDS_A300'
        elif 'a310' in title or 'a310' in folder:
            logger.info("Detected INIBUILDS_A310 from manifest")
            return 'INIBUILDS_A310'
        return None

    def _detect_from_manifest(self, manifest: Dict, folder_name: str) -> Optional[str]:
        """
        Определить профиль из manifest.json

        Args:
            manifest: Данные из manifest.json
            folder_name: Имя папки самолёта

        Returns:
            Ключ профиля или None
        """
        creator = manifest.get('creator', '').lower()
        manufacturer = manifest.get('manufacturer', '').lower()
        title = manifest.get('title', '').lower()
        folder = folder_name.lower()

        # Проверяем каждого производителя
        checkers = [
            self._check_pmdg,
            self._check_fenix,
            self._check_flybywire,
            self._check_fslabs,
            self._check_inibuilds,
        ]

        for checker in checkers:
            result = checker(creator, manufacturer, title, folder)
            if result:
                return result

        return None

    def _detect_from_aircraft_cfg(self, aircraft_cfg: Dict, folder_name: str) -> Optional[str]:
        """
        Определить профиль из aircraft.cfg

        Args:
            aircraft_cfg: Данные из aircraft.cfg
            folder_name: Имя папки самолёта

        Returns:
            Ключ профиля или None
        """
        folder_lower = folder_name.lower()

        # Извлекаем данные
        general = aircraft_cfg.get('general', {})
        fltsim = aircraft_cfg.get('fltsim', {})

        atc_type = general.get('atc_type', '').lower()
        atc_model = general.get('atc_model', '').lower()
        ui_manufacturer = fltsim.get('ui_manufacturer', '').lower()
        ui_type = fltsim.get('ui_type', '').lower()

        combined = f"{atc_type} {atc_model} {ui_manufacturer} {ui_type} {folder_lower}"

        # PMDG
        if 'pmdg' in combined:
            if '737' in combined:
                logger.info("Detected PMDG_737 from aircraft.cfg")
                return 'PMDG_737'
            elif '777' in combined:
                logger.info("Detected PMDG_777 from aircraft.cfg")
                return 'PMDG_777'

        # Fenix
        if 'fenix' in combined and 'a320' in combined:
            logger.info("Detected FENIX_A320 from aircraft.cfg")
            return 'FENIX_A320'

        # FlyByWire
        if ('flybywire' in combined or 'fbw' in combined) and ('a32nx' in combined or 'a320' in combined):
            logger.info("Detected FBW_A32NX from aircraft.cfg")
            return 'FBW_A32NX'

        # FSLabs
        if 'fslabs' in combined or 'flight sim labs' in combined:
            if 'a32' in combined or 'a320' in combined or 'a319' in combined or 'a321' in combined:
                logger.info("Detected FSLABS_A32X from aircraft.cfg")
                return 'FSLABS_A32X'

        # iniBuilds
        if 'inibuilds' in combined or 'ini builds' in combined:
            if 'a300' in combined:
                logger.info("Detected INIBUILDS_A300 from aircraft.cfg")
                return 'INIBUILDS_A300'
            elif 'a310' in combined:
                logger.info("Detected INIBUILDS_A310 from aircraft.cfg")
                return 'INIBUILDS_A310'

        return None

    def get_aircraft_details(self, aircraft_title: str) -> Dict:
        """
        Получить детальную информацию о самолёте из конфигурационных файлов

        Args:
            aircraft_title: Название самолёта из SimConnect

        Returns:
            Dict с информацией о самолёте
        """
        result = {
            'found': False,
            'profile': None,
            'manifest': None,
            'aircraft_cfg': None,
            'folder_path': None
        }

        aircraft_folder = self.find_aircraft_folder(aircraft_title)

        if not aircraft_folder:
            return result

        result['found'] = True
        result['folder_path'] = str(aircraft_folder)

        # Читаем файлы
        manifest = self.read_manifest(aircraft_folder)
        aircraft_cfg = self.read_aircraft_cfg(aircraft_folder)

        result['manifest'] = manifest
        result['aircraft_cfg'] = aircraft_cfg

        # Определяем профиль
        if manifest:
            profile = self._detect_from_manifest(manifest, aircraft_folder.name)
            if profile:
                result['profile'] = profile
                return result

        if aircraft_cfg:
            profile = self._detect_from_aircraft_cfg(aircraft_cfg, aircraft_folder.name)
            if profile:
                result['profile'] = profile

        return result
