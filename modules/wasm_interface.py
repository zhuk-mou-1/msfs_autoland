"""
MobiFlight WASM интерфейс для работы с локальными переменными (LVARs)
Использует SimConnect CLIENT_DATA для коммуникации с WASM модулем
"""

import logging
import struct
import time
from typing import Dict, Optional

from SimConnect import SimConnect

from modules.simconnect_client_data import extend_simconnect_with_client_data

logger = logging.getLogger(__name__)


class MobiFlightWASM:
    """Интерфейс для работы с MobiFlight WASM модулем"""

    # CLIENT_DATA IDs для MobiFlight
    CLIENT_DATA_NAME_COMMAND = "MobiFlight.Command"
    CLIENT_DATA_NAME_RESPONSE = "MobiFlight.Response"
    CLIENT_DATA_NAME_LVARS = "MobiFlight.LVars"

    # Request IDs
    REQUEST_ID_COMMAND = 1000
    REQUEST_ID_RESPONSE = 1001
    REQUEST_ID_LVARS = 1002

    # Client Data IDs
    CLIENT_DATA_ID_COMMAND = 100
    CLIENT_DATA_ID_RESPONSE = 101
    CLIENT_DATA_ID_LVARS = 102

    # Команды
    CMD_GET_LVAR = 1
    CMD_SET_LVAR = 2
    CMD_TRIGGER_EVENT = 3
    CMD_LIST_LVARS = 4

    # Кэш проверки совместимости SimConnect (класс-уровень) - УДАЛЕНО
    # Теперь используем extend_simconnect_with_client_data

    def __init__(self, simconnect: SimConnect):
        """
        Args:
            simconnect: Экземпляр SimConnect
        """
        self.sm = simconnect
        self.connected = False
        self.lvars_cache: Dict[str, float] = {}
        self.last_response = None
        self.response_timeout = 2.0  # секунды
        self.client_data_api = None  # Будет инициализирован при подключении

    def connect(self) -> bool:
        """
        Подключение к MobiFlight WASM модулю

        Returns:
            True если подключение успешно
        """
        try:
            logger.info("Connecting to MobiFlight WASM...")

            # Расширяем SimConnect методами CLIENT_DATA API
            self.client_data_api = extend_simconnect_with_client_data(self.sm)
            if not self.client_data_api:
                logger.error("Failed to extend SimConnect with CLIENT_DATA API")
                return False

            # Регистрация CLIENT_DATA областей
            self._register_client_data()

            # Проверка доступности WASM модуля
            if self._check_wasm_available():
                self.connected = True
                logger.info("MobiFlight WASM connected successfully")
                return True
            else:
                logger.warning("MobiFlight WASM module not found")
                return False

        except Exception as e:
            logger.warning("Failed to connect to MobiFlight WASM: %s", e)
            return False

    def _register_client_data(self):
        """Регистрация CLIENT_DATA областей для коммуникации с WASM"""
        try:
            # Команды (отправка в WASM)
            self.client_data_api.map_client_data_name_to_id(
                self.CLIENT_DATA_NAME_COMMAND,
                self.CLIENT_DATA_ID_COMMAND
            )

            # Ответы (получение из WASM)
            self.client_data_api.map_client_data_name_to_id(
                self.CLIENT_DATA_NAME_RESPONSE,
                self.CLIENT_DATA_ID_RESPONSE
            )

            # LVars список
            self.client_data_api.map_client_data_name_to_id(
                self.CLIENT_DATA_NAME_LVARS,
                self.CLIENT_DATA_ID_LVARS
            )

            logger.debug("CLIENT_DATA areas registered")

        except Exception as e:
            logger.warning("Failed to register CLIENT_DATA: %s", e)
            raise

    def _check_wasm_available(self) -> bool:
        """
        Проверка доступности MobiFlight WASM модуля

        Returns:
            True если WASM модуль доступен
        """
        try:
            # Попытка отправить тестовую команду
            # Если WASM модуль установлен, он ответит
            test_result = self.read_lvar("MOBIFLIGHT_TEST")

            # Если получили ответ (даже 0), значит WASM работает
            return test_result is not None

        except Exception as e:
            logger.debug("WASM availability check failed: %s", e)
            return False

    def read_lvar(self, lvar_name: str) -> Optional[float]:
        """
        Чтение локальной переменной

        Args:
            lvar_name: Имя переменной (например "PMDG_737_MCP_Course")

        Returns:
            Значение переменной или None если ошибка
        """
        if not self.connected:
            logger.error("WASM not connected")
            return None

        try:
            # Проверка кэша
            if lvar_name in self.lvars_cache:
                cache_time = time.time()
                # Кэш действителен 0.5 секунды
                if hasattr(self, '_cache_time') and (cache_time - self._cache_time) < 0.5:
                    return self.lvars_cache[lvar_name]

            # Формирование команды
            command = self._pack_command(self.CMD_GET_LVAR, lvar_name)

            # Отправка команды через CLIENT_DATA
            self.client_data_api.set_client_data(
                self.CLIENT_DATA_ID_COMMAND,
                0,  # offset
                0,  # flags
                0,  # reserved
                len(command),
                command
            )

            # Ожидание ответа
            response = self._wait_for_response()

            if response is not None:
                value = self._unpack_response(response)

                # Обновление кэша
                self.lvars_cache[lvar_name] = value
                self._cache_time = time.time()

                logger.debug("Read LVAR %s = %s", lvar_name, value)
                return value
            else:
                logger.warning("No response for LVAR %s", lvar_name)
                return None

        except Exception as e:
            logger.error("Error reading LVAR %s: %s", lvar_name, e)
            return None

    def write_lvar(self, lvar_name: str, value: float) -> bool:
        """
        Запись локальной переменной

        Args:
            lvar_name: Имя переменной
            value: Значение для записи

        Returns:
            True если запись успешна
        """
        if not self.connected:
            logger.error("WASM not connected")
            return False

        try:
            # Формирование команды
            command = self._pack_command(self.CMD_SET_LVAR, lvar_name, value)

            # Отправка команды
            self.client_data_api.set_client_data(
                self.CLIENT_DATA_ID_COMMAND,
                0,
                0,
                0,
                len(command),
                command
            )

            # Обновление кэша
            self.lvars_cache[lvar_name] = value
            self._cache_time = time.time()

            logger.debug("Write LVAR %s = %s", lvar_name, value)
            return True

        except Exception as e:
            logger.error("Error writing LVAR %s: %s", lvar_name, e)
            return False

    def trigger_event(self, event_name: str, param: int = 0) -> bool:
        """
        Отправка кастомного события

        Args:
            event_name: Имя события (например "PMDG_737_MCP_COURSE_SELECTOR")
            param: Параметр события

        Returns:
            True если событие отправлено
        """
        if not self.connected:
            logger.error("WASM not connected")
            return False

        try:
            # Формирование команды
            command = self._pack_command(self.CMD_TRIGGER_EVENT, event_name, param)

            # Отправка команды
            self.client_data_api.set_client_data(
                self.CLIENT_DATA_ID_COMMAND,
                0,
                0,
                0,
                len(command),
                command
            )

            logger.debug("Trigger event %s(%s)", event_name, param)
            return True

        except Exception as e:
            logger.error("Error triggering event %s: %s", event_name, e)
            return False

    def _pack_command(self, cmd_type: int, name: str, value: float = 0.0) -> bytes:
        """
        Упаковка команды в байты для отправки в WASM

        Args:
            cmd_type: Тип команды
            name: Имя переменной/события
            value: Значение (для SET команд)

        Returns:
            Упакованные байты
        """
        # Формат: [cmd_type:4][name_len:4][name:256][value:8]
        name_bytes = name.encode('utf-8')[:256]
        name_len = len(name_bytes)

        command = struct.pack(
            '<II256sd',
            cmd_type,
            name_len,
            name_bytes.ljust(256, b'\x00'),
            value
        )

        return command

    def _wait_for_response(self) -> Optional[bytes]:
        """
        Ожидание ответа от WASM модуля

        Returns:
            Байты ответа или None если таймаут
        """
        start_time = time.time()

        while (time.time() - start_time) < self.response_timeout:
            try:
                # Запрос данных из CLIENT_DATA
                self.client_data_api.request_client_data(
                    self.CLIENT_DATA_ID_RESPONSE,
                    self.REQUEST_ID_RESPONSE,
                    0,  # offset
                    0,  # period (once)
                    0,  # flags
                    0,  # origin
                    0,  # interval
                    272  # size (4 + 8 + 260)
                )

                # Небольшая задержка для получения ответа
                time.sleep(0.05)

                # Проверка наличия ответа
                if self.last_response:
                    response = self.last_response
                    self.last_response = None
                    return response

            except Exception as e:
                logger.debug("Response wait error: %s", e)

            time.sleep(0.01)

        return None

    def _unpack_response(self, response: bytes) -> float:
        """
        Распаковка ответа от WASM

        Args:
            response: Байты ответа

        Returns:
            Значение из ответа
        """
        # Формат: [status:4][value:8][message:260]
        status, value, message_bytes = struct.unpack('<Id260s', response)

        if status != 0:
            message = message_bytes.decode('utf-8').rstrip('\x00')
            logger.warning("WASM response status %s: %s", status, message)

        return value

    def get_available_lvars(self) -> list:
        """
        Получить список доступных LVARs

        Returns:
            Список имён переменных
        """
        if not self.connected:
            return []

        try:
            # Отправка команды LIST_LVARS
            command = self._pack_command(self.CMD_LIST_LVARS, "")

            self.client_data_api.set_client_data(
                self.CLIENT_DATA_ID_COMMAND,
                0,
                0,
                0,
                len(command),
                command
            )

            # Получение списка
            # TODO: Реализовать парсинг списка LVARs
            logger.info("LVAR list requested")
            return []

        except Exception as e:
            logger.error("Error getting LVAR list: %s", e)
            return []

    def disconnect(self):
        """Отключение от WASM"""
        self.connected = False
        self.lvars_cache.clear()
        logger.info("MobiFlight WASM disconnected")
