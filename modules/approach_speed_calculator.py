"""
Модуль расчёта параметров захода на посадку (VREF/VAPP)
Улучшенный метод с учётом веса, ветра, высоты и температуры
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ApproachSpeedCalculator:
    """Калькулятор параметров захода на посадку"""

    def __init__(self, config_path: str = "config/aircraft_performance.json"):
        """
        Args:
            config_path: Путь к файлу с коэффициентами самолётов
        """
        self.config_path = config_path
        self.aircraft_db = {}
        self.matching_rules = {}
        self.category_defaults = {}
        self.load_database()

    def load_database(self):
        """Загрузить базу данных коэффициентов"""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                logger.error("Aircraft performance database not found: %s", self.config_path)
                return

            with open(config_file, encoding='utf-8') as f:
                data = json.load(f)

            self.aircraft_db = data.get('aircraft_performance', {})
            self.matching_rules = data.get('matching_rules', {})
            self.category_defaults = data.get('category_defaults', {})

            logger.info("Loaded %s aircraft profiles", len(self.aircraft_db))

        except Exception as e:
            logger.error("Failed to load aircraft performance database: %s", e)

    def identify_aircraft(self, aircraft_title: str) -> Optional[str]:
        """
        Определить ID самолёта по названию

        Args:
            aircraft_title: Название самолёта из SimConnect

        Returns:
            ID самолёта в базе данных или None
        """
        # Прямое совпадение
        for pattern, aircraft_id in self.matching_rules.items():
            if pattern.lower() in aircraft_title.lower():
                logger.info("Aircraft identified: %s -> %s", aircraft_title, aircraft_id)
                return aircraft_id

        # Fallback по категории (определяем по весу или названию)
        if any(word in aircraft_title.lower() for word in ['737', '747', '777', '787', 'a320', 'a330', 'a350']):
            return self.category_defaults.get('narrow_body_jet', 'DEFAULT_JET')
        elif any(word in aircraft_title.lower() for word in ['tbm', 'king air', 'caravan']):
            return self.category_defaults.get('turboprop', 'DEFAULT_TURBOPROP')
        elif any(word in aircraft_title.lower() for word in ['cessna', 'piper', 'diamond', 'cirrus']):
            return self.category_defaults.get('general_aviation', 'DEFAULT_GA')
        else:
            logger.warning("Unknown aircraft: %s, using DEFAULT_JET", aircraft_title)
            return 'DEFAULT_JET'

    def select_flaps_configuration(self, aircraft_data: Dict, runway_length_m: int) -> Tuple[str, Dict]:
        """
        Выбрать конфигурацию закрылков

        Args:
            aircraft_data: Данные самолёта из БД
            runway_length_m: Длина ВПП (метры)

        Returns:
            (название конфигурации, данные конфигурации)
        """
        min_runway = aircraft_data.get('min_runway_length_m', 1500)
        preferred = aircraft_data.get('preferred_flaps', 'flaps_full')

        # Если ВПП короткая - полные закрылки
        if runway_length_m < min_runway * 1.2:
            # Ищем конфигурацию с максимальными закрылками
            for config_name in ['flaps_40', 'conf_full', 'flaps_full']:
                if config_name in aircraft_data:
                    logger.info("Short runway (%sm), using %s", runway_length_m, config_name)
                    return config_name, aircraft_data[config_name]

        # Иначе - предпочтительная конфигурация
        if preferred in aircraft_data:
            return preferred, aircraft_data[preferred]

        # Fallback - первая доступная конфигурация
        for key, value in aircraft_data.items():
            if isinstance(value, dict) and 'base_vref' in value:
                return key, value

        raise ValueError("No flaps configuration found for aircraft")

    def calculate_vref(self,
                      aircraft_weight_kg: float,
                      flaps_config: Dict,
                      base_weight_kg: float) -> float:
        """
        Расчёт VREF (референсная скорость)

        Args:
            aircraft_weight_kg: Текущий вес самолёта (кг)
            flaps_config: Конфигурация закрылков из БД
            base_weight_kg: Базовый вес из БД

        Returns:
            VREF в узлах
        """
        base_vref = flaps_config['base_vref']
        weight_coefficient = flaps_config['weight_coefficient']
        min_vref = flaps_config['min_vref']
        max_vref = flaps_config['max_vref']

        # Формула: VREF = base + (weight - base_weight) / 1000 * coefficient
        weight_diff_kg = aircraft_weight_kg - base_weight_kg
        vref = base_vref + (weight_diff_kg / 1000) * weight_coefficient

        # Ограничения
        vref = max(min_vref, min(vref, max_vref))

        return vref

    def calculate_wind_correction(self, headwind_kt: float, gust_kt: float = 0) -> Tuple[float, float]:
        """
        Расчёт поправки на ветер

        Args:
            headwind_kt: Встречный ветер (узлы, положительный = встречный)
            gust_kt: Порывы ветра (узлы)

        Returns:
            (wind_correction, gust_correction) в узлах
        """
        # Встречный ветер: добавляем половину (но не более 20 kt)
        wind_correction = 0
        if headwind_kt > 0:
            wind_correction = min(headwind_kt / 2, 20)

        # Порывы: добавляем половину разницы
        gust_correction = 0
        if gust_kt > abs(headwind_kt):
            gust_correction = (gust_kt - abs(headwind_kt)) / 2

        return wind_correction, gust_correction

    def calculate_altitude_correction(self, runway_elevation_ft: float) -> float:
        """
        Расчёт поправки на высоту аэропорта

        Args:
            runway_elevation_ft: Высота ВПП (футы MSL)

        Returns:
            Поправка в узлах
        """
        # На каждые 1000 футов высоты +1 узел IAS
        return runway_elevation_ft / 1000

    def calculate_temperature_correction(self,
                                        temperature_c: float,
                                        runway_elevation_ft: float) -> float:
        """
        Расчёт поправки на температуру

        Args:
            temperature_c: Температура (°C)
            runway_elevation_ft: Высота ВПП (футы MSL)

        Returns:
            Поправка в узлах
        """
        # ISA температура на уровне моря = 15°C, -2°C на 1000 футов
        isa_temp = 15 - (runway_elevation_ft / 1000) * 2
        temp_deviation = temperature_c - isa_temp

        # На каждые 10°C выше ISA +1 узел (только если выше ISA)
        if temp_deviation > 0:
            return temp_deviation / 10
        else:
            return 0

    def calculate_approach_parameters(self,
                                     aircraft_title: str,
                                     aircraft_weight_kg: float,
                                     runway_length_m: int,
                                     runway_elevation_ft: float,
                                     temperature_c: float,
                                     headwind_kt: float = 0,
                                     gust_kt: float = 0) -> Dict:
        """
        Полный расчёт параметров захода

        Args:
            aircraft_title: Название самолёта
            aircraft_weight_kg: Вес самолёта (кг)
            runway_length_m: Длина ВПП (метры)
            runway_elevation_ft: Высота ВПП (футы MSL)
            temperature_c: Температура (°C)
            headwind_kt: Встречный ветер (узлы, + = встречный, - = попутный)
            gust_kt: Порывы ветра (узлы)

        Returns:
            Dict с параметрами захода
        """
        # 1. Определение самолёта
        aircraft_id = self.identify_aircraft(aircraft_title)
        if not aircraft_id or aircraft_id not in self.aircraft_db:
            logger.error("Aircraft not found in database: %s", aircraft_title)
            return self._get_fallback_parameters()

        aircraft_data = self.aircraft_db[aircraft_id]

        # 2. Выбор конфигурации закрылков
        flaps_name, flaps_config = self.select_flaps_configuration(aircraft_data, runway_length_m)

        # 3. Расчёт VREF
        base_weight = aircraft_data['base_weight_kg']
        vref = self.calculate_vref(aircraft_weight_kg, flaps_config, base_weight)

        # 4. Поправки
        wind_corr, gust_corr = self.calculate_wind_correction(headwind_kt, gust_kt)
        alt_corr = self.calculate_altitude_correction(runway_elevation_ft)
        temp_corr = self.calculate_temperature_correction(temperature_c, runway_elevation_ft)

        # 5. Итоговая VAPP
        vapp = vref + wind_corr + gust_corr + alt_corr + temp_corr

        # Ограничения
        vapp = max(vapp, vref + 5)  # Минимум VREF + 5
        vapp = min(vapp, vref + 30)  # Максимум VREF + 30

        # Decision Height (стандарт CAT I)
        decision_height = 200

        return {
            'aircraft_id': aircraft_id,
            'aircraft_name': aircraft_data['name'],
            'aircraft_category': aircraft_data['category'],
            'flaps_configuration': flaps_name,
            'vref': round(vref, 1),
            'vapp': round(vapp, 1),
            'wind_correction': round(wind_corr, 1),
            'gust_correction': round(gust_corr, 1),
            'altitude_correction': round(alt_corr, 1),
            'temperature_correction': round(temp_corr, 1),
            'decision_height': decision_height,
            'aircraft_weight_kg': aircraft_weight_kg,
            'base_weight_kg': base_weight,
            'max_landing_weight_kg': aircraft_data['max_landing_weight_kg'],
            'weight_ok': aircraft_weight_kg <= aircraft_data['max_landing_weight_kg']
        }

    def _get_fallback_parameters(self) -> Dict:
        """Параметры по умолчанию при ошибке"""
        return {
            'aircraft_id': 'UNKNOWN',
            'aircraft_name': 'Unknown Aircraft',
            'aircraft_category': 'unknown',
            'flaps_configuration': 'unknown',
            'vref': 130,
            'vapp': 140,
            'wind_correction': 0,
            'gust_correction': 0,
            'altitude_correction': 0,
            'temperature_correction': 0,
            'decision_height': 200,
            'aircraft_weight_kg': 60000,
            'base_weight_kg': 60000,
            'max_landing_weight_kg': 70000,
            'weight_ok': True
        }

    def get_aircraft_info(self, aircraft_title: str) -> Optional[Dict]:
        """
        Получить информацию о самолёте из БД

        Args:
            aircraft_title: Название самолёта

        Returns:
            Данные самолёта или None
        """
        aircraft_id = self.identify_aircraft(aircraft_title)
        if aircraft_id and aircraft_id in self.aircraft_db:
            return self.aircraft_db[aircraft_id]
        return None
