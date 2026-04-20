"""
Модуль звуковых предупреждений (Audio Alerts)
Воспроизведение голосовых предупреждений о сдвиге ветра и других критических ситуациях
"""

import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Попытка импорта библиотек для воспроизведения звука
try:
    import pygame
    from gtts import gTTS
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logger.warning("Audio libraries not available. Install: pip install gtts pygame")


class AudioAlertSystem:
    """Система звуковых предупреждений"""

    def __init__(self, audio_dir: str = "audio_alerts"):
        """
        Args:
            audio_dir: Директория для хранения аудио файлов
        """
        self.audio_dir = audio_dir
        self.enabled = AUDIO_AVAILABLE
        self.is_playing = False
        self.volume = 1.0  # 0.0 - 1.0

        if self.enabled:
            # Создание директории для аудио
            os.makedirs(self.audio_dir, exist_ok=True)

            # Инициализация pygame mixer
            try:
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                logger.info("Audio alert system initialized")
            except Exception as e:
                logger.error("Failed to initialize pygame mixer: %s", e)
                self.enabled = False

        # Предопределённые сообщения
        self.alert_messages = {
            'WINDSHEAR_CRITICAL': "WINDSHEAR! WINDSHEAR! GO AROUND!",
            'WINDSHEAR_WARNING': "WINDSHEAR AHEAD! CAUTION!",
            'SINK_RATE': "SINK RATE! PULL UP!",
            'TERRAIN': "TERRAIN! TERRAIN! PULL UP!",
            'STALL': "STALL! STALL!",
            'MINIMUMS': "MINIMUMS! MINIMUMS!",
            'RETARD': "RETARD! RETARD!",
            'TOO_LOW_GEAR': "TOO LOW GEAR!",
            'TOO_LOW_FLAPS': "TOO LOW FLAPS!"
        }

        # Кэш аудио файлов
        self.audio_cache = {}

    def play_alert(self, alert_type: str, blocking: bool = False):
        """
        Воспроизвести звуковое предупреждение

        Args:
            alert_type: Тип предупреждения (ключ из alert_messages)
            blocking: Ждать завершения воспроизведения
        """
        if not self.enabled:
            logger.debug("Audio alert skipped (disabled): %s", alert_type)
            return

        if self.is_playing:
            logger.debug("Audio alert skipped (already playing): %s", alert_type)
            return

        message = self.alert_messages.get(alert_type)
        if not message:
            logger.warning("Unknown alert type: %s", alert_type)
            return

        if blocking:
            self._play_message(message, alert_type)
        else:
            # Воспроизведение в отдельном потоке
            thread = threading.Thread(target=self._play_message, args=(message, alert_type))
            thread.daemon = True
            thread.start()

    def _play_message(self, message: str, alert_type: str):
        """
        Внутренний метод воспроизведения сообщения

        Args:
            message: Текст сообщения
            alert_type: Тип предупреждения
        """
        try:
            self.is_playing = True

            # Проверка кэша
            audio_file = self.audio_cache.get(alert_type)

            if not audio_file or not os.path.exists(audio_file):
                # Генерация аудио файла
                audio_file = os.path.join(self.audio_dir, f"{alert_type}.mp3")

                logger.info("Generating audio for: %s", message)
                tts = gTTS(text=message, lang='en', slow=False)
                tts.save(audio_file)

                self.audio_cache[alert_type] = audio_file

            # Воспроизведение
            logger.info("Playing audio alert: %s", alert_type)
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play()

            # Ожидание завершения
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

        except Exception as e:
            logger.error("Failed to play audio alert: %s", e)
        finally:
            self.is_playing = False

    def play_custom_message(self, message: str, blocking: bool = False):
        """
        Воспроизвести произвольное сообщение

        Args:
            message: Текст сообщения
            blocking: Ждать завершения воспроизведения
        """
        if not self.enabled:
            return

        if blocking:
            self._play_custom(message)
        else:
            thread = threading.Thread(target=self._play_custom, args=(message,))
            thread.daemon = True
            thread.start()

    def _play_custom(self, message: str):
        """Воспроизведение произвольного сообщения"""
        try:
            self.is_playing = True

            # Временный файл
            temp_file = os.path.join(self.audio_dir, "temp_alert.mp3")

            tts = gTTS(text=message, lang='en', slow=False)
            tts.save(temp_file)

            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            # Удаление временного файла
            try:
                os.remove(temp_file)
            except OSError:
                pass

        except Exception as e:
            logger.error("Failed to play custom message: %s", e)
        finally:
            self.is_playing = False

    def set_volume(self, volume: float):
        """
        Установить громкость

        Args:
            volume: Громкость 0.0 - 1.0
        """
        self.volume = max(0.0, min(1.0, volume))
        logger.info("Audio volume set to: %s", self.volume)

    def stop(self):
        """Остановить воспроизведение"""
        if self.enabled and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            self.is_playing = False
            logger.info("Audio playback stopped")

    def is_available(self) -> bool:
        """Проверить доступность аудио системы"""
        return self.enabled

    def pregenerate_alerts(self):
        """Предварительная генерация всех аудио файлов"""
        if not self.enabled:
            logger.warning("Cannot pregenerate alerts - audio system disabled")
            return

        logger.info("Pregenerating audio alerts...")

        for alert_type, message in self.alert_messages.items():
            audio_file = os.path.join(self.audio_dir, f"{alert_type}.mp3")

            if os.path.exists(audio_file):
                logger.debug("Alert already exists: %s", alert_type)
                self.audio_cache[alert_type] = audio_file
                continue

            try:
                logger.info("Generating: %s - '%s'", alert_type, message)
                tts = gTTS(text=message, lang='en', slow=False)
                tts.save(audio_file)
                self.audio_cache[alert_type] = audio_file
            except Exception as e:
                logger.error("Failed to generate %s: %s", alert_type, e)

        logger.info("Pregeneration complete. %s alerts ready.", len(self.audio_cache))


# Глобальный экземпляр (singleton)
_audio_system: Optional[AudioAlertSystem] = None


def get_audio_system() -> AudioAlertSystem:
    """Получить глобальный экземпляр аудио системы"""
    global _audio_system
    if _audio_system is None:
        _audio_system = AudioAlertSystem()
    return _audio_system


def play_windshear_alert(severity: str = 'CRITICAL'):
    """
    Быстрый доступ к воспроизведению предупреждения о сдвиге ветра

    Args:
        severity: 'CRITICAL' или 'WARNING'
    """
    audio = get_audio_system()
    if severity == 'CRITICAL':
        audio.play_alert('WINDSHEAR_CRITICAL')
    else:
        audio.play_alert('WINDSHEAR_WARNING')
