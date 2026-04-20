"""
Модуль для парсинга данных из Navigraph SQLite базы (LittleNavMap)
Получает недостающие данные для заходов: длину ВПП, ширину ВПП, угол глиссады
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class NavigraphRunwayData:
    """Данные ВПП из Navigraph"""
    length: float  # футы
    width: float  # футы
    airport_elevation: float  # футы
    glideslope_angle: Optional[float] = None  # градусы (только для ILS)
    source: str = "navigraph"  # источник данных


class QueryCache:
    """Простой кэш для запросов с TTL"""

    def __init__(self, ttl_seconds: int = 3600):
        """
        Args:
            ttl_seconds: Время жизни кэша в секундах
        """
        self.ttl_seconds = ttl_seconds
        self.cache = {}  # {key: (value, timestamp)}

    def get(self, key: str) -> Optional[any]:
        """Получить значение из кэша"""
        if key not in self.cache:
            return None

        value, timestamp = self.cache[key]

        # Проверка TTL
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[key]
            return None

        return value

    def set(self, key: str, value: any):
        """Сохранить значение в кэш"""
        self.cache[key] = (value, time.time())

    def clear(self):
        """Очистить весь кэш"""
        self.cache.clear()

    def size(self) -> int:
        """Получить размер кэша"""
        return len(self.cache)


class NavigraphParser:
    """Парсер данных Navigraph из SQLite базы LittleNavMap"""

    # Путь к базе данных Navigraph по умолчанию
    DEFAULT_DB_PATH = Path.home() / "AppData/Roaming/ABarthel/little_navmap_db/little_navmap_navigraph.sqlite"

    def __init__(self, db_path: Optional[Path] = None, cache_ttl: int = 3600):
        """
        Args:
            db_path: Путь к SQLite базе Navigraph (опционально)
            cache_ttl: Время жизни кэша в секундах (по умолчанию 1 час)
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self.conn: Optional[sqlite3.Connection] = None
        self.connected = False
        self.cache = QueryCache(ttl_seconds=cache_ttl)

    def connect(self) -> bool:
        """
        Подключение к базе данных Navigraph

        Returns:
            True если подключение успешно
        """
        try:
            if not self.db_path.exists():
                logger.error(f"Navigraph database not found: {self.db_path}")
                return False

            self.conn = sqlite3.connect(str(self.db_path))
            self.connected = True
            logger.info(f"Connected to Navigraph database: {self.db_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Navigraph database: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Отключение от базы данных"""
        if self.conn:
            self.conn.close()
            self.connected = False
            logger.info("Disconnected from Navigraph database")

    def clear_cache(self):
        """Очистить кэш запросов"""
        self.cache.clear()
        logger.info("Navigraph query cache cleared")

    def get_cache_stats(self) -> dict:
        """
        Получить статистику кэша

        Returns:
            Словарь со статистикой: size, ttl
        """
        return {
            'size': self.cache.size(),
            'ttl_seconds': self.cache.ttl_seconds
        }

    def get_runway_data(self,
                       icao: str,
                       runway_name: str,
                       approach_type: str = 'ILS') -> Optional[NavigraphRunwayData]:
        """
        Получить данные ВПП из Navigraph

        Args:
            icao: ICAO код аэропорта (например, "UUEE")
            runway_name: Название ВПП (например, "07C", "24L")
            approach_type: Тип захода ('ILS', 'VOR', 'NDB', 'GPS')

        Returns:
            NavigraphRunwayData или None если не найдено
        """
        if not self.connected:
            logger.error("Not connected to Navigraph database")
            return None

        # Проверка кэша
        cache_key = f"{icao.upper()}_{runway_name.upper()}_{approach_type.upper()}"
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_data

        try:
            cursor = self.conn.cursor()

            if approach_type.upper() == 'ILS':
                # Для ILS: получаем угол глиссады из таблицы ils
                query = '''
                SELECT
                    r.length,
                    r.width,
                    a.altitude as airport_elevation,
                    ils.gs_pitch as glideslope_angle
                FROM runway r
                JOIN airport a ON r.airport_id = a.airport_id
                JOIN runway_end re ON (re.runway_end_id = r.primary_end_id
                                    OR re.runway_end_id = r.secondary_end_id)
                LEFT JOIN ils ON ils.loc_runway_end_id = re.runway_end_id
                WHERE a.ident = ? AND re.name = ?
                LIMIT 1
                '''
            else:
                # Для VOR/NDB/GPS: только длина/ширина ВПП
                # Угол глиссады будет None (используется стандарт 3.0° или ручной ввод)
                query = '''
                SELECT
                    r.length,
                    r.width,
                    a.altitude as airport_elevation,
                    NULL as glideslope_angle
                FROM runway r
                JOIN airport a ON r.airport_id = a.airport_id
                JOIN runway_end re ON (re.runway_end_id = r.primary_end_id
                                    OR re.runway_end_id = r.secondary_end_id)
                WHERE a.ident = ? AND re.name = ?
                LIMIT 1
                '''

            cursor.execute(query, (icao.upper(), runway_name.upper()))
            result = cursor.fetchone()

            if result:
                length, width, elevation, glideslope = result

                # Проверка валидности данных
                if length is None or width is None or elevation is None:
                    logger.warning(f"Incomplete data for {icao} RWY {runway_name}")
                    return None

                data = NavigraphRunwayData(
                    length=float(length),
                    width=float(width),
                    airport_elevation=float(elevation),
                    glideslope_angle=float(glideslope) if glideslope else None,
                    source="navigraph"
                )

                logger.info(f"Navigraph data for {icao} RWY {runway_name}: "
                           f"Length={data.length:.0f}ft, Width={data.width:.0f}ft, "
                           f"Elevation={data.airport_elevation:.0f}ft, "
                           f"Glideslope={data.glideslope_angle:.2f}° " if data.glideslope_angle
                           else "Glideslope=N/A")

                # Сохранение в кэш
                self.cache.set(cache_key, data)
                return data
            else:
                logger.warning(f"No data found in Navigraph for {icao} RWY {runway_name}")
                return None

        except Exception as e:
            logger.error(f"Error querying Navigraph database: {e}")
            return None

    def get_glideslope_angle(self,
                            icao: str,
                            runway_name: str,
                            approach_type: str,
                            manual_override: Optional[float] = None) -> float:
        """
        Получить угол глиссады с fallback логикой

        Приоритет:
        1. Ручной ввод (manual_override)
        2. Navigraph база данных (для ILS)
        3. Стандартное значение 3.0° (для VOR/NDB/GPS)

        Args:
            icao: ICAO код аэропорта
            runway_name: Название ВПП
            approach_type: Тип захода
            manual_override: Ручной ввод угла глиссады (опционально)

        Returns:
            Угол глиссады в градусах
        """
        # Приоритет 1: Ручной ввод
        if manual_override is not None:
            logger.info(f"Using manual glideslope angle: {manual_override:.2f}° "
                       f"(user override for {icao} RWY {runway_name})")
            return manual_override

        # Приоритет 2: Navigraph база данных (только для ILS)
        if approach_type.upper() == 'ILS' and self.connected:
            data = self.get_runway_data(icao, runway_name, approach_type)
            if data and data.glideslope_angle is not None:
                logger.info(f"Using Navigraph glideslope angle: {data.glideslope_angle:.2f}° "
                           f"for {icao} RWY {runway_name}")
                return data.glideslope_angle

        # Приоритет 3: Стандартное значение 3.0°
        logger.info(f"Using standard glideslope angle: 3.0° "
                   f"for {approach_type} approach {icao} RWY {runway_name}")
        return 3.0

    def test_connection(self) -> Tuple[bool, str]:
        """
        Тестирование подключения к базе данных

        Returns:
            (success, message)
        """
        if not self.db_path.exists():
            return False, f"Database file not found: {self.db_path}"

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Проверка наличия необходимых таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = ['airport', 'runway', 'runway_end', 'ils']
            missing_tables = [t for t in required_tables if t not in tables]

            if missing_tables:
                conn.close()
                return False, f"Missing required tables: {', '.join(missing_tables)}"

            # Проверка количества аэропортов
            cursor.execute("SELECT COUNT(*) FROM airport")
            airport_count = cursor.fetchone()[0]

            conn.close()

            return True, f"Database OK: {airport_count} airports available"

        except Exception as e:
            return False, f"Database error: {e}"


def create_navigraph_parser(db_path: Optional[str] = None) -> Optional[NavigraphParser]:
    """
    Удобная функция для создания и подключения парсера Navigraph

    Args:
        db_path: Путь к базе данных (опционально, если не указан - читается из settings.json)

    Returns:
        NavigraphParser или None если подключение не удалось
    """
    # Если путь не указан явно, пытаемся прочитать из настроек
    if db_path is None:
        try:
            from modules.settings import get_settings
            settings = get_settings()
            settings_db_path = settings.get_navigraph_db_path()
            if settings_db_path:
                db_path = str(settings_db_path)
                logger.info(f"Using Navigraph database path from settings: {db_path}")
        except Exception as e:
            logger.warning(f"Failed to read Navigraph path from settings: {e}, using default")

    parser = NavigraphParser(Path(db_path) if db_path else None)

    if parser.connect():
        return parser
    else:
        logger.warning("Failed to connect to Navigraph database, parser not available")
        return None


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Создание парсера
    parser = create_navigraph_parser()

    if parser:
        # Тест подключения
        success, message = parser.test_connection()
        print(f"Connection test: {message}")

        # Тест получения данных для ILS
        print("\n--- ILS Approach (UUEE RWY 06C) ---")
        data = parser.get_runway_data("UUEE", "06C", "ILS")
        if data:
            print(f"Length: {data.length:.0f} ft")
            print(f"Width: {data.width:.0f} ft")
            print(f"Elevation: {data.airport_elevation:.0f} ft")
            print(f"Glideslope: {data.glideslope_angle:.2f}°" if data.glideslope_angle else "Glideslope: N/A")

        # Тест получения данных для VOR
        print("\n--- VOR Approach (UUEE RWY 06L) ---")
        data = parser.get_runway_data("UUEE", "06L", "VOR")
        if data:
            print(f"Length: {data.length:.0f} ft")
            print(f"Width: {data.width:.0f} ft")
            print(f"Elevation: {data.airport_elevation:.0f} ft")
            print(f"Glideslope: {data.glideslope_angle:.2f}°" if data.glideslope_angle else "Glideslope: N/A (will use 3.0° standard)")

        # Тест fallback логики угла глиссады
        print("\n--- Glideslope Angle Fallback Logic ---")

        # ILS с данными из Navigraph
        angle = parser.get_glideslope_angle("UUEE", "06C", "ILS")
        print(f"ILS (from Navigraph): {angle:.2f}°")

        # VOR без данных (стандарт 3.0°)
        angle = parser.get_glideslope_angle("UUEE", "06L", "VOR")
        print(f"VOR (standard): {angle:.2f}°")

        # Ручной ввод (приоритет)
        angle = parser.get_glideslope_angle("UUEE", "06C", "ILS", manual_override=3.5)
        print(f"ILS (manual override): {angle:.2f}°")

        parser.disconnect()
