"""
Расширение SimConnect с поддержкой CLIENT_DATA API
Реализация методов для работы с MobiFlight WASM через ctypes
"""

import logging
from ctypes import c_char_p, c_float, byref, create_string_buffer
from ctypes.wintypes import DWORD

logger = logging.getLogger(__name__)


# Константы CLIENT_DATA (из SimConnect SDK)
SIMCONNECT_CLIENTDATA_MAX_SIZE = 8192
SIMCONNECT_CLIENTDATATYPE_INT8 = -1
SIMCONNECT_CLIENTDATATYPE_INT16 = -2
SIMCONNECT_CLIENTDATATYPE_INT32 = -3
SIMCONNECT_CLIENTDATATYPE_INT64 = -4
SIMCONNECT_CLIENTDATATYPE_FLOAT32 = -5
SIMCONNECT_CLIENTDATATYPE_FLOAT64 = -6
SIMCONNECT_CLIENTDATAOFFSET_AUTO = -1

# Флаги для CLIENT_DATA
SIMCONNECT_CLIENT_DATA_REQUEST_FLAG_CHANGED = 0x00000001
SIMCONNECT_CLIENT_DATA_REQUEST_FLAG_TAGGED = 0x00000002
SIMCONNECT_CLIENT_DATA_SET_FLAG_DEFAULT = 0x00000000
SIMCONNECT_CLIENT_DATA_SET_FLAG_TAGGED = 0x00000001

# Периоды обновления
SIMCONNECT_CLIENT_DATA_PERIOD_NEVER = 0
SIMCONNECT_CLIENT_DATA_PERIOD_ONCE = 1
SIMCONNECT_CLIENT_DATA_PERIOD_VISUAL_FRAME = 2
SIMCONNECT_CLIENT_DATA_PERIOD_ON_SET = 3


class SimConnectClientDataAPI:
    """
    Расширение SimConnect с методами CLIENT_DATA API
    Позволяет работать с MobiFlight WASM модулем
    """

    def __init__(self, simconnect_instance):
        """
        Args:
            simconnect_instance: Экземпляр SimConnect из Python-SimConnect
        """
        self.sm = simconnect_instance
        self.dll = simconnect_instance.dll
        self.hSimConnect = simconnect_instance.hSimConnect

        # Проверка доступности методов в DLL
        self._check_dll_methods()

        logger.info("SimConnect CLIENT_DATA API initialized")

    def _check_dll_methods(self):
        """Проверка наличия необходимых методов в SimConnect.dll"""
        required_methods = [
            'MapClientDataNameToID',
            'CreateClientData',
            'AddToClientDataDefinition',
            'RequestClientData',
            'SetClientData',
            'ClearClientDataDefinition'
        ]

        missing_methods = []
        for method_name in required_methods:
            if not hasattr(self.dll, method_name):
                missing_methods.append(method_name)

        if missing_methods:
            logger.warning("Some CLIENT_DATA methods not found in DLL: %s", missing_methods)
        else:
            logger.info("All CLIENT_DATA methods available in SimConnect.dll")

    def map_client_data_name_to_id(self, client_data_name: str, client_data_id: int) -> bool:
        """
        Связывает имя CLIENT_DATA области с ID

        Args:
            client_data_name: Имя CLIENT_DATA области (например "MobiFlight.Command")
            client_data_id: Числовой ID для этой области

        Returns:
            True если успешно
        """
        try:
            # SimConnect_MapClientDataNameToID(
            #     HANDLE hSimConnect,
            #     const char* szClientDataName,
            #     SIMCONNECT_CLIENT_DATA_ID ClientDataID
            # )

            result = self.dll.MapClientDataNameToID(
                self.hSimConnect,
                c_char_p(client_data_name.encode('utf-8')),
                DWORD(client_data_id)
            )

            if result == 0:  # S_OK
                logger.debug("Mapped CLIENT_DATA: '%s' -> ID %s", client_data_name, client_data_id)
                return True
            else:
                logger.error("Failed to map CLIENT_DATA '%s': error %s", client_data_name, result)
                return False

        except Exception as e:
            logger.error("Exception in map_client_data_name_to_id: %s", e)
            return False

    def create_client_data(self, client_data_id: int, size: int, read_only: bool = False) -> bool:
        """
        Создаёт CLIENT_DATA область

        Args:
            client_data_id: ID CLIENT_DATA области
            size: Размер в байтах (макс 8192)
            read_only: Только для чтения

        Returns:
            True если успешно
        """
        try:
            # SimConnect_CreateClientData(
            #     HANDLE hSimConnect,
            #     SIMCONNECT_CLIENT_DATA_ID ClientDataID,
            #     DWORD dwSize,
            #     SIMCONNECT_CREATE_CLIENT_DATA_FLAG Flags
            # )

            flags = 0x00000001 if read_only else 0x00000000  # SIMCONNECT_CREATE_CLIENT_DATA_FLAG_READ_ONLY

            if size > SIMCONNECT_CLIENTDATA_MAX_SIZE:
                logger.warning("CLIENT_DATA size %s exceeds max %s, clamping", size, SIMCONNECT_CLIENTDATA_MAX_SIZE)
                size = SIMCONNECT_CLIENTDATA_MAX_SIZE

            result = self.dll.CreateClientData(
                self.hSimConnect,
                DWORD(client_data_id),
                DWORD(size),
                DWORD(flags)
            )

            if result == 0:  # S_OK
                logger.debug("Created CLIENT_DATA ID %s, size %s bytes", client_data_id, size)
                return True
            else:
                logger.error("Failed to create CLIENT_DATA %s: error %s", client_data_id, result)
                return False

        except Exception as e:
            logger.error("Exception in create_client_data: %s", e)
            return False

    def add_to_client_data_definition(self, define_id: int, offset: int,
                                      size_or_type: int, epsilon: float = 0.0,
                                      datum_id: int = 0) -> bool:
        """
        Добавляет переменную в определение CLIENT_DATA

        Args:
            define_id: ID определения
            offset: Смещение в байтах (или SIMCONNECT_CLIENTDATAOFFSET_AUTO)
            size_or_type: Размер в байтах или тип (SIMCONNECT_CLIENTDATATYPE_*)
            epsilon: Порог изменения для уведомлений
            datum_id: ID данных

        Returns:
            True если успешно
        """
        try:
            # SimConnect_AddToClientDataDefinition(
            #     HANDLE hSimConnect,
            #     SIMCONNECT_CLIENT_DATA_DEFINITION_ID DefineID,
            #     DWORD dwOffset,
            #     DWORD dwSizeOrType,
            #     float fEpsilon,
            #     DWORD DatumID
            # )

            result = self.dll.AddToClientDataDefinition(
                self.hSimConnect,
                DWORD(define_id),
                DWORD(offset),
                DWORD(size_or_type),
                c_float(epsilon),
                DWORD(datum_id)
            )

            if result == 0:  # S_OK
                logger.debug("Added to CLIENT_DATA definition %s: offset=%s, size/type=%s", define_id, offset, size_or_type)
                return True
            else:
                logger.error("Failed to add to CLIENT_DATA definition %s: error %s", define_id, result)
                return False

        except Exception as e:
            logger.error("Exception in add_to_client_data_definition: %s", e)
            return False

    def request_client_data(self, client_data_id: int, request_id: int,
                           define_id: int, period: int = SIMCONNECT_CLIENT_DATA_PERIOD_ONCE,
                           flags: int = 0, origin: int = 0, interval: int = 0,
                           limit: int = 0) -> bool:
        """
        Запрашивает данные из CLIENT_DATA области

        Args:
            client_data_id: ID CLIENT_DATA области
            request_id: ID запроса (для идентификации ответа)
            define_id: ID определения данных
            period: Период обновления
            flags: Флаги запроса
            origin: Начальная запись (для массивов)
            interval: Интервал между записями
            limit: Максимальное количество записей

        Returns:
            True если успешно
        """
        try:
            # SimConnect_RequestClientData(
            #     HANDLE hSimConnect,
            #     SIMCONNECT_CLIENT_DATA_ID ClientDataID,
            #     SIMCONNECT_DATA_REQUEST_ID RequestID,
            #     SIMCONNECT_CLIENT_DATA_DEFINITION_ID DefineID,
            #     SIMCONNECT_CLIENT_DATA_PERIOD Period,
            #     SIMCONNECT_CLIENT_DATA_REQUEST_FLAG Flags,
            #     DWORD origin,
            #     DWORD interval,
            #     DWORD limit
            # )

            result = self.dll.RequestClientData(
                self.hSimConnect,
                DWORD(client_data_id),
                DWORD(request_id),
                DWORD(define_id),
                DWORD(period),
                DWORD(flags),
                DWORD(origin),
                DWORD(interval),
                DWORD(limit)
            )

            if result == 0:  # S_OK
                logger.debug("Requested CLIENT_DATA %s, request ID %s", client_data_id, request_id)
                return True
            else:
                logger.error("Failed to request CLIENT_DATA %s: error %s", client_data_id, result)
                return False

        except Exception as e:
            logger.error("Exception in request_client_data: %s", e)
            return False

    def set_client_data(self, client_data_id: int, define_id: int,
                       flags: int, reserved: int, data_size: int,
                       data: bytes) -> bool:
        """
        Записывает данные в CLIENT_DATA область

        Args:
            client_data_id: ID CLIENT_DATA области
            define_id: ID определения данных
            flags: Флаги записи
            reserved: Зарезервировано (должно быть 0)
            data_size: Размер данных в байтах
            data: Данные для записи (bytes)

        Returns:
            True если успешно
        """
        try:
            # SimConnect_SetClientData(
            #     HANDLE hSimConnect,
            #     SIMCONNECT_CLIENT_DATA_ID ClientDataID,
            #     SIMCONNECT_CLIENT_DATA_DEFINITION_ID DefineID,
            #     SIMCONNECT_CLIENT_DATA_SET_FLAG Flags,
            #     DWORD dwReserved,
            #     DWORD cbUnitSize,
            #     void* pDataSet
            # )

            # Создаём буфер с данными
            buffer = create_string_buffer(data, data_size)

            result = self.dll.SetClientData(
                self.hSimConnect,
                DWORD(client_data_id),
                DWORD(define_id),
                DWORD(flags),
                DWORD(reserved),
                DWORD(data_size),
                byref(buffer)
            )

            if result == 0:  # S_OK
                logger.debug("Set CLIENT_DATA %s, %s bytes", client_data_id, data_size)
                return True
            else:
                logger.error("Failed to set CLIENT_DATA %s: error %s", client_data_id, result)
                return False

        except Exception as e:
            logger.error("Exception in set_client_data: %s", e)
            return False

    def clear_client_data_definition(self, define_id: int) -> bool:
        """
        Очищает определение CLIENT_DATA

        Args:
            define_id: ID определения для очистки

        Returns:
            True если успешно
        """
        try:
            # SimConnect_ClearClientDataDefinition(
            #     HANDLE hSimConnect,
            #     SIMCONNECT_CLIENT_DATA_DEFINITION_ID DefineID
            # )

            result = self.dll.ClearClientDataDefinition(
                self.hSimConnect,
                DWORD(define_id)
            )

            if result == 0:  # S_OK
                logger.debug("Cleared CLIENT_DATA definition %s", define_id)
                return True
            else:
                logger.error("Failed to clear CLIENT_DATA definition %s: error %s", define_id, result)
                return False

        except Exception as e:
            logger.error("Exception in clear_client_data_definition: %s", e)
            return False


def extend_simconnect_with_client_data(simconnect_instance):
    """
    Расширяет экземпляр SimConnect методами CLIENT_DATA API

    Args:
        simconnect_instance: Экземпляр SimConnect из Python-SimConnect

    Returns:
        Экземпляр SimConnectClientDataAPI или None при ошибке
    """
    try:
        client_data_api = SimConnectClientDataAPI(simconnect_instance)

        # Добавляем методы к экземпляру SimConnect
        simconnect_instance.map_client_data_name_to_id = client_data_api.map_client_data_name_to_id
        simconnect_instance.create_client_data = client_data_api.create_client_data
        simconnect_instance.add_to_client_data_definition = client_data_api.add_to_client_data_definition
        simconnect_instance.request_client_data = client_data_api.request_client_data
        simconnect_instance.set_client_data = client_data_api.set_client_data
        simconnect_instance.clear_client_data_definition = client_data_api.clear_client_data_definition

        logger.info("SimConnect extended with CLIENT_DATA API methods")
        return client_data_api

    except Exception as e:
        logger.error("Failed to extend SimConnect with CLIENT_DATA API: %s", e)
        return None
