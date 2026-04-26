"""
Диалог настройки захода на посадку
"""

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from modules.airports_database import AirportsDatabase
from modules.ils_navigation import ILSConfig
from modules.msfs_airport_reader import MSFSAirportReader
from modules.types import ApproachConfig, NavStation

logger = logging.getLogger(__name__)


class ApproachConfigDialog:
    """Диалог для настройки параметров захода"""

    def __init__(self, parent, telemetry=None):
        self.parent = parent
        self.telemetry = telemetry
        self.result: Optional[ApproachConfig] = None
        self.ils_config: Optional[ILSConfig] = None
        self.db = AirportsDatabase()
        self.msfs_reader = MSFSAirportReader(telemetry) if telemetry else None
        self.detected_approach_data = None  # Для хранения автоматически определённых данных

        # Создание окна
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Approach Configuration")
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Создание виджетов диалога"""

        # Notebook для вкладок
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладка 1: Auto-Detect из MSFS
        if self.msfs_reader:
            self.auto_frame = ttk.Frame(notebook)
            notebook.add(self.auto_frame, text="Auto-Detect")
            self.create_auto_detect_tab()

        # Вкладка 2: Выбор из базы данных
        self.db_frame = ttk.Frame(notebook)
        notebook.add(self.db_frame, text="From Database")
        self.create_database_tab()

        # Вкладка 3: Ручной ввод
        self.manual_frame = ttk.Frame(notebook)
        notebook.add(self.manual_frame, text="Manual Entry")
        self.create_manual_tab()

        # Кнопки
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.RIGHT)

    def create_database_tab(self):
        """Вкладка выбора из базы данных"""
        row = 0

        # Поиск аэропорта
        ttk.Label(self.db_frame, text="Search Airport:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(self.db_frame, textvariable=self.search_var, width=30)
        search_entry.grid(row=row, column=1, padx=5, pady=5)
        ttk.Button(self.db_frame, text="Search", command=self.search_airports).grid(row=row, column=2, padx=5)
        row += 1

        # Список аэропортов
        ttk.Label(self.db_frame, text="Airport:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.airport_listbox = tk.Listbox(self.db_frame, height=6, width=50)
        self.airport_listbox.grid(row=row, column=1, columnspan=2, padx=5, pady=5)
        self.airport_listbox.bind('<<ListboxSelect>>', self.on_airport_select)
        row += 1

        # Загрузка списка аэропортов
        self.load_airports()

        # ВПП
        ttk.Label(self.db_frame, text="Runway:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.runway_combo = ttk.Combobox(self.db_frame, state='readonly', width=28)
        self.runway_combo.grid(row=row, column=1, padx=5, pady=5)
        self.runway_combo.bind('<<ComboboxSelected>>', self.on_runway_select)
        row += 1

    def create_auto_detect_tab(self):
        """Вкладка автоматического определения из MSFS"""
        row = 0

        # Заголовок
        ttk.Label(self.auto_frame, text="Automatically detect approach from MSFS",
                 font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, pady=10)
        row += 1

        # Инструкция
        instruction = ("This will read approach parameters from your current MSFS session:\n"
                      "- ILS frequency and course (if tuned in NAV1)\n"
                      "- GPS destination (if set in flight plan)\n"
                      "- Current position and heading\n\n"
                      "Make sure you have:\n"
                      "1. Tuned ILS frequency in NAV1, OR\n"
                      "2. Set destination airport in GPS/FMC")

        instruction_label = ttk.Label(self.auto_frame, text=instruction, justify=tk.LEFT)
        instruction_label.grid(row=row, column=0, columnspan=2, padx=10, pady=10, sticky=tk.W)
        row += 1

        # Кнопки детектирования и обновления Navigraph
        button_frame = ttk.Frame(self.auto_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Detect Approach",
                  command=self.detect_approach).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh Navigraph Data",
                  command=self.refresh_navigraph).pack(side=tk.LEFT, padx=5)
        row += 1

        # Результаты
        ttk.Label(self.auto_frame, text="Detected Parameters:").grid(row=row, column=0,
                                                                     sticky=tk.NW, padx=5, pady=5)
        self.auto_result_text = tk.Text(self.auto_frame, height=15, width=60, state='disabled')
        self.auto_result_text.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Поле для ручного override угла глиссады (скрыто по умолчанию)
        self.auto_glideslope_frame = ttk.Frame(self.auto_frame)
        self.auto_glideslope_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        self.auto_glideslope_frame.grid_remove()  # Скрываем по умолчанию

        ttk.Label(self.auto_glideslope_frame, text="⚠️ Glideslope angle not found!",
                 foreground='orange', font=('Arial', 9, 'bold')).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)

        ttk.Label(self.auto_glideslope_frame, text="Manual Glideslope (°):",
                 font=('Arial', 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.auto_glideslope_override_var = tk.StringVar(value="3.0")
        glideslope_entry = ttk.Entry(self.auto_glideslope_frame, textvariable=self.auto_glideslope_override_var, width=10)
        glideslope_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Подсказка
        hint_label = ttk.Label(self.auto_glideslope_frame,
                              text="(Standard: 3.0° for most approaches)",
                              font=('Arial', 8), foreground='gray')
        hint_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)
        row += 1

        # Статус
        self.auto_status_var = tk.StringVar(value="Click 'Detect Approach' to start")
        status_label = ttk.Label(self.auto_frame, textvariable=self.auto_status_var,
                                foreground='blue')
        status_label.grid(row=row, column=0, columnspan=2, pady=5)

    def detect_approach(self):
        """Автоматическое определение захода из MSFS"""
        if not self.msfs_reader:
            messagebox.showerror("Error", "MSFS reader not available")
            return

        self.auto_status_var.set("Detecting approach from MSFS...")
        self.dialog.update()

        try:
            # Получаем данные из MSFS
            approach_data = self.msfs_reader.auto_configure_approach()

            if not approach_data:
                self.auto_status_var.set("No approach data detected")
                messagebox.showwarning("Warning",
                    "Could not detect approach parameters.\n\n"
                    "Make sure:\n"
                    "1. ILS frequency is tuned in NAV1, OR\n"
                    "2. Destination is set in GPS/FMC")
                return

            # Отображаем результаты
            result_text = f"Type: {approach_data['type']}\n"

            if approach_data['type'] == 'ILS':
                freq_mhz = approach_data['frequency'] / 1000000.0
                result_text += f"Frequency: {freq_mhz:.2f} MHz\n"
                result_text += f"Course: {approach_data['course']}°\n"

            # Угол глиссады с индикатором источника
            glideslope_source = approach_data.get('glideslope_source', 'unknown')

            # Проверка: если угол глиссады не найден (только стандарт 3.0°), показываем поле ручного ввода
            if glideslope_source == 'standard' and approach_data['type'] in ['VOR', 'NDB', 'GPS']:
                # Показываем поле для ручного ввода
                self.auto_glideslope_frame.grid()
                logger.warning(f"Glideslope angle not found for {approach_data['type']} approach, manual input required")
            else:
                # Скрываем поле (данные найдены в Navigraph или MSFS)
                self.auto_glideslope_frame.grid_remove()

            source_icon = {
                'navigraph': '🗺️',
                'msfs': '✈️',
                'standard': '📏',
                'manual': '✍️'
            }.get(glideslope_source, '❓')

            result_text += f"Glideslope: {approach_data['glideslope']}° {source_icon}\n"
            result_text += f"Decision Height: {approach_data['decision_height']} ft\n"
            result_text += f"Approach Speed: {approach_data['approach_speed']} kt\n"

            # Данные ВПП с индикатором источника
            data_source = approach_data.get('data_source', 'unknown')
            runway_length = approach_data.get('runway_length')
            runway_width = approach_data.get('runway_width')

            if runway_length and runway_width:
                source_icon = '🗺️' if data_source == 'navigraph' else '✈️'
                result_text += f"\nRunway: {runway_length:.0f} x {runway_width:.0f} ft {source_icon}\n"

            result_text += "\nRunway Threshold:\n"
            result_text += f"  Latitude: {approach_data['runway_threshold_lat']:.6f}\n"
            result_text += f"  Longitude: {approach_data['runway_threshold_lon']:.6f}\n"
            result_text += f"  Elevation: {approach_data['runway_elevation']:.0f} ft\n"

            # Легенда источников данных
            result_text += "\n--- Data Sources ---\n"
            result_text += "🗺️ Navigraph  ✈️ MSFS  📏 Standard  ✍️ Manual\n"

            self.auto_result_text.configure(state='normal')
            self.auto_result_text.delete(1.0, tk.END)
            self.auto_result_text.insert(1.0, result_text)
            self.auto_result_text.configure(state='disabled')

            # Сохраняем данные для использования
            self.detected_approach_data = approach_data
            self.auto_status_var.set("Approach detected successfully! Click OK to use.")

        except Exception as e:
            self.auto_status_var.set(f"Error: {e}")
            messagebox.showerror("Error", f"Failed to detect approach: {e}")

    def refresh_navigraph(self):
        """Обновление подключения к базе данных Navigraph"""
        if not self.msfs_reader:
            messagebox.showerror("Error", "MSFS reader not available")
            return

        self.auto_status_var.set("Refreshing Navigraph database...")
        self.dialog.update()

        try:
            # Переподключение к Navigraph
            from modules.navigraph_parser import create_navigraph_parser

            # Отключаем старое подключение если есть
            if self.msfs_reader.navigraph_parser:
                self.msfs_reader.navigraph_parser.disconnect()

            # Создаём новое подключение
            self.msfs_reader.navigraph_parser = create_navigraph_parser()

            if self.msfs_reader.navigraph_parser:
                self.auto_status_var.set("✅ Navigraph database refreshed successfully")
                messagebox.showinfo("Success",
                    "Navigraph database connection refreshed.\n\n"
                    "The latest runway data and glideslope angles are now available.")
                logger.info("Navigraph database refreshed successfully")
            else:
                self.auto_status_var.set("⚠️ Navigraph database not available")
                messagebox.showwarning("Warning",
                    "Could not connect to Navigraph database.\n\n"
                    "Make sure:\n"
                    "1. LittleNavMap is installed\n"
                    "2. Navigraph database is up to date\n"
                    "3. Database path is correct")
                logger.warning("Failed to refresh Navigraph database")

        except Exception as e:
            self.auto_status_var.set(f"Error: {e}")
            messagebox.showerror("Error", f"Failed to refresh Navigraph: {e}")
            logger.error(f"Error refreshing Navigraph database: {e}")

    def create_manual_tab(self):
        """Вкладка ручного ввода"""
        row = 0

        # Тип захода
        ttk.Label(self.manual_frame, text="Approach Type:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.manual_type_var = tk.StringVar(value="ILS")
        type_combo = ttk.Combobox(self.manual_frame, textvariable=self.manual_type_var,
                                  values=["ILS", "VOR", "NDB"], state='readonly', width=28)
        type_combo.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Частота
        ttk.Label(self.manual_frame, text="Frequency (MHz):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.freq_var = tk.StringVar(value="110.30")
        ttk.Entry(self.manual_frame, textvariable=self.freq_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Курс посадки
        ttk.Label(self.manual_frame, text="Final Course (°):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.course_var = tk.StringVar(value="270")
        ttk.Entry(self.manual_frame, textvariable=self.course_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Угол глиссады
        ttk.Label(self.manual_frame, text="Glideslope (°):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.glideslope_var = tk.StringVar(value="3.0")
        ttk.Entry(self.manual_frame, textvariable=self.glideslope_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Высота принятия решения
        ttk.Label(self.manual_frame, text="Decision Height (ft):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.dh_var = tk.StringVar(value="200")
        ttk.Entry(self.manual_frame, textvariable=self.dh_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Скорость захода
        ttk.Label(self.manual_frame, text="Approach Speed (kt):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.speed_var = tk.StringVar(value="120")
        speed_entry = ttk.Entry(self.manual_frame, textvariable=self.speed_var, width=30)
        speed_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Вес самолёта
        ttk.Label(self.manual_frame, text="Aircraft Weight (lbs):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.weight_var = tk.StringVar(value="5000")
        weight_entry = ttk.Entry(self.manual_frame, textvariable=self.weight_var, width=30)
        weight_entry.grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Кнопка чтения из самолёта
        if self.telemetry:
            ttk.Button(self.manual_frame, text="Read from Aircraft",
                      command=self.read_from_aircraft).grid(row=row, column=1, pady=5, sticky=tk.W)
        row += 1

        # Превышение ВПП
        ttk.Label(self.manual_frame, text="Runway Elevation (ft):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.elev_var = tk.StringVar(value="500")
        ttk.Entry(self.manual_frame, textvariable=self.elev_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Длина ВПП
        ttk.Label(self.manual_frame, text="Runway Length (ft):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.length_var = tk.StringVar(value="8000")
        ttk.Entry(self.manual_frame, textvariable=self.length_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Ширина ВПП
        ttk.Label(self.manual_frame, text="Runway Width (ft):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.width_var = tk.StringVar(value="150")
        ttk.Entry(self.manual_frame, textvariable=self.width_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Координаты порога ВПП
        ttk.Label(self.manual_frame, text="Threshold Latitude:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.lat_var = tk.StringVar(value="55.48")
        ttk.Entry(self.manual_frame, textvariable=self.lat_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        ttk.Label(self.manual_frame, text="Threshold Longitude:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.lon_var = tk.StringVar(value="37.52")
        ttk.Entry(self.manual_frame, textvariable=self.lon_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

    def load_airports(self):
        """Загрузить список аэропортов"""
        airports = self.db.get_airport_list()
        for icao in airports:
            info = self.db.get_airport_info(icao)
            if info:
                self.airport_listbox.insert(tk.END, f"{icao} - {info.name} ({info.city})")

    def search_airports(self):
        """Поиск аэропортов"""
        query = self.search_var.get()
        if not query:
            return

        results = self.db.search_airports(query)
        self.airport_listbox.delete(0, tk.END)

        for result in results:
            self.airport_listbox.insert(tk.END,
                f"{result['icao']} - {result['name']} ({result['city']})")

    def on_airport_select(self, event):
        """Обработка выбора аэропорта"""
        selection = self.airport_listbox.curselection()
        if not selection:
            return

        text = self.airport_listbox.get(selection[0])
        icao = text.split(' - ')[0]

        # Загрузка ВПП
        runways = self.db.get_runway_list(icao)
        self.runway_combo['values'] = runways
        if runways:
            self.runway_combo.current(0)
            self.on_runway_select(None)

    def on_runway_select(self, event):
        """Обработка выбора ВПП"""
        selection = self.airport_listbox.curselection()
        if not selection:
            return

        text = self.airport_listbox.get(selection[0])
        icao = text.split(' - ')[0]
        runway = self.runway_combo.get()

        if not runway:
            return

        # Загрузка заходов
        approaches = self.db.get_approach_list(icao, runway)
        self.approach_combo['values'] = approaches
        if approaches:
            self.approach_combo.current(0)
            self.on_approach_select(None)

    def on_approach_select(self, event):
        """Обработка выбора захода"""
        selection = self.airport_listbox.curselection()
        if not selection:
            return

        text = self.airport_listbox.get(selection[0])
        icao = text.split(' - ')[0]
        runway = self.runway_combo.get()
        approach = self.approach_combo.get()

        if not runway or not approach:
            return

        # Загрузка информации о заходе
        config = self.db.get_approach_config(icao, runway, approach)
        if config:
            info = f"Type: {config.station.type}\n"
            info += f"Frequency: {config.station.frequency/1000000:.2f} MHz\n"
            info += f"Course: {config.final_approach_course}°\n"
            info += f"Glideslope: {config.glideslope_angle}°\n"
            info += f"Decision Height: {config.decision_height} ft\n"
            info += f"Approach Speed: {config.approach_speed} kt\n"
            info += f"Runway: {config.runway_length} x {config.runway_width} ft\n"
            info += f"Elevation: {config.runway_elevation} ft\n"

            self.info_text.configure(state='normal')
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info)
            self.info_text.configure(state='disabled')

    def on_ok(self):
        """Обработка нажатия OK"""
        try:
            # Проверка: Auto-Detect
            if hasattr(self, 'detected_approach_data') and self.detected_approach_data:
                data = self.detected_approach_data

                # Проверка ручного override угла глиссады (только если поле видимо)
                manual_glideslope = None
                if self.auto_glideslope_frame.winfo_ismapped():
                    # Поле видимо - значит угол не был найден автоматически
                    try:
                        manual_glideslope = float(self.auto_glideslope_override_var.get())
                        logger.info(f"Using manual glideslope override: {manual_glideslope:.2f}° (auto-detection failed)")
                    except ValueError:
                        messagebox.showerror("Error", "Invalid glideslope angle. Please enter a number.")
                        return

                # Используем ручной override если указан, иначе данные из auto_configure_approach
                glideslope_angle = manual_glideslope if manual_glideslope else data['glideslope']

                # Создание конфигурации из автоматически определённых данных
                station = NavStation(
                    name=f"MSFS {data['type']}",
                    frequency=data.get('frequency', 0),
                    latitude=data['runway_threshold_lat'],
                    longitude=data['runway_threshold_lon'],
                    type=data['type']
                )

                # Используем данные из Navigraph если доступны
                runway_length = data.get('runway_length', 8000)  # Fallback на 8000 ft
                runway_width = data.get('runway_width', 150)     # Fallback на 150 ft

                self.result = ApproachConfig(
                    station=station,
                    final_approach_course=data.get('course', 0),
                    glideslope_angle=glideslope_angle,
                    decision_height=data['decision_height'],
                    approach_speed=data['approach_speed'],
                    runway_elevation=int(data['runway_elevation']),
                    runway_length=int(runway_length),
                    runway_width=int(runway_width),
                    runway_threshold_lat=data['runway_threshold_lat'],
                    runway_threshold_lon=data['runway_threshold_lon']
                )

                if data['type'] == 'ILS':
                    self.ils_config = ILSConfig(
                        frequency=data['frequency'],
                        localizer_course=data['course'],
                        glideslope_angle=glideslope_angle,
                        decision_height=data['decision_height'],
                        approach_speed=data['approach_speed'],
                        runway_elevation=int(data['runway_elevation']),
                        runway_length=int(runway_length),
                        runway_width=int(runway_width),
                        runway_threshold_lat=data['runway_threshold_lat'],
                        runway_threshold_lon=data['runway_threshold_lon']
                    )

                self.dialog.destroy()
                return

            # Проверка: из базы данных
            selection = self.airport_listbox.curselection()
            if selection:
                text = self.airport_listbox.get(selection[0])
                icao = text.split(' - ')[0]
                runway = self.runway_combo.get()
                approach = self.approach_combo.get()

                if not runway or not approach:
                    messagebox.showerror("Error", "Please select runway and approach type")
                    return

                self.result = self.db.get_approach_config(icao, runway, approach)
                if approach == "ILS":
                    self.ils_config = self.db.get_ils_config(icao, runway)

            else:
                # Ручной ввод
                freq_mhz = float(self.freq_var.get())
                freq_hz = int(freq_mhz * 1000000)

                station = NavStation(
                    name=f"Manual {self.manual_type_var.get()}",
                    frequency=freq_hz,
                    latitude=float(self.lat_var.get()),
                    longitude=float(self.lon_var.get()),
                    type=self.manual_type_var.get()
                )

                self.result = ApproachConfig(
                    station=station,
                    final_approach_course=int(self.course_var.get()),
                    glideslope_angle=float(self.glideslope_var.get()),
                    decision_height=int(self.dh_var.get()),
                    approach_speed=int(self.speed_var.get()),
                    runway_elevation=int(self.elev_var.get()),
                    runway_length=int(self.length_var.get()),
                    runway_width=int(self.width_var.get()),
                    runway_threshold_lat=float(self.lat_var.get()),
                    runway_threshold_lon=float(self.lon_var.get())
                )

                # Сохраняем вес самолёта как атрибут
                self.result.aircraft_weight = float(self.weight_var.get())

                if self.manual_type_var.get() == "ILS":
                    self.ils_config = ILSConfig(
                        frequency=freq_hz,
                        localizer_course=int(self.course_var.get()),
                        glideslope_angle=float(self.glideslope_var.get()),
                        decision_height=int(self.dh_var.get()),
                        approach_speed=int(self.speed_var.get()),
                        runway_elevation=int(self.elev_var.get()),
                        runway_length=int(self.length_var.get()),
                        runway_width=int(self.width_var.get()),
                        runway_threshold_lat=float(self.lat_var.get()),
                        runway_threshold_lon=float(self.lon_var.get())
                    )

            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")

    def read_from_aircraft(self):
        """Чтение веса и скорости из самолёта через SimConnect"""
        if not self.telemetry or not self.telemetry.connected:
            messagebox.showerror("Error", "Not connected to MSFS")
            return

        try:
            # Читаем вес самолёта
            weight_data = self.telemetry.get_aircraft_weight()
            if weight_data and 'total_weight' in weight_data:
                total_weight = weight_data['total_weight']
                self.weight_var.set(f"{total_weight:.0f}")

            # Читаем текущую скорость (для рекомендации)
            speed_data = self.telemetry.get_speed()
            if speed_data and 'airspeed_indicated' in speed_data:
                current_speed = speed_data['airspeed_indicated']
                # Рекомендуемая скорость захода обычно на 20-30% выше скорости сваливания
                # Используем текущую скорость как базу
                if current_speed > 60:  # Разумная скорость полёта
                    self.speed_var.set(f"{current_speed:.0f}")

            messagebox.showinfo("Success",
                f"Aircraft data read:\n"
                f"Weight: {weight_data.get('total_weight', 0):.0f} lbs\n"
                f"Current IAS: {speed_data.get('airspeed_indicated', 0):.0f} kt")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read aircraft data: {e}")

    def on_cancel(self):
        """Обработка нажатия Cancel"""
        self.result = None
        self.ils_config = None
        self.dialog.destroy()

    def show(self):
        """Показать диалог и дождаться закрытия"""
        self.dialog.wait_window()
        return self.result, self.ils_config
