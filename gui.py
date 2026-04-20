"""
Графический интерфейс для MSFS AutoLand System
"""

import logging
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Optional

from main import AutoLandSystem
from modules.approach_dialog import ApproachConfigDialog
from modules.wasm_version_checker import MobiFlightVersionChecker


class TextHandler(logging.Handler):
    """Обработчик логов для вывода в текстовое поле"""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)

        def append():
            self.text_widget.configure(state="normal")
            self.text_widget.insert(tk.END, msg + "\n")
            self.text_widget.configure(state="disabled")
            self.text_widget.see(tk.END)

        self.text_widget.after(0, append)


class AutoLandGUI:
    """Главное окно GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("MSFS AutoLand System")
        self.root.geometry("1200x800")

        # Система автопосадки
        self.system: Optional[AutoLandSystem] = None
        self.update_thread: Optional[threading.Thread] = None
        self.running = False

        # Создание интерфейса
        self.create_widgets()
        self.setup_logging()

        # Обновление интерфейса
        self.update_gui()

    def create_widgets(self):
        """Создание виджетов интерфейса"""

        # Верхняя панель - статус и управление
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(side=tk.TOP, fill=tk.X)

        # Статус подключения
        ttk.Label(top_frame, text="Status:").grid(row=0, column=0, padx=5)
        self.status_label = ttk.Label(top_frame, text="Disconnected", foreground="red")
        self.status_label.grid(row=0, column=1, padx=5)

        # Фаза захода
        ttk.Label(top_frame, text="Phase:").grid(row=0, column=2, padx=5)
        self.phase_label = ttk.Label(top_frame, text="IDLE", font=("Arial", 12, "bold"))
        self.phase_label.grid(row=0, column=3, padx=5)

        # Кнопки управления
        self.connect_btn = ttk.Button(
            top_frame, text="Connect", command=self.connect_msfs
        )
        self.connect_btn.grid(row=0, column=4, padx=5)

        self.disconnect_btn = ttk.Button(
            top_frame, text="Disconnect", command=self.disconnect_msfs, state="disabled"
        )
        self.disconnect_btn.grid(row=0, column=5, padx=5)

        self.start_btn = ttk.Button(
            top_frame,
            text="Start Approach",
            command=self.start_approach,
            state="disabled",
        )
        self.start_btn.grid(row=0, column=6, padx=5)

        self.stop_btn = ttk.Button(
            top_frame, text="Stop", command=self.stop_approach, state="disabled"
        )
        self.stop_btn.grid(row=0, column=7, padx=5)

        self.ga_btn = ttk.Button(
            top_frame, text="GO AROUND", command=self.go_around, state="disabled"
        )
        self.ga_btn.grid(row=0, column=8, padx=5)
        self.ga_btn.configure(style="Danger.TButton")

        # Чекбокс звуковых предупреждений
        self.audio_alerts_var = tk.BooleanVar(value=True)
        self.audio_check = ttk.Checkbutton(
            top_frame,
            text="Audio Alerts",
            variable=self.audio_alerts_var,
            command=self.toggle_audio_alerts,
        )
        self.audio_check.grid(row=0, column=8, padx=5)

        # Создание системы вкладок (Notebook)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Привязка клавиш для переключения вкладок
        self.root.bind("<Control-1>", lambda e: self.notebook.select(0))
        self.root.bind("<Control-2>", lambda e: self.notebook.select(1))
        self.root.bind("<Control-3>", lambda e: self.notebook.select(2))
        self.root.bind("<Control-4>", lambda e: self.notebook.select(3))
        self.root.bind("<Control-5>", lambda e: self.notebook.select(4))
        self.root.bind("<Control-6>", lambda e: self.notebook.select(5))
        self.root.bind("<Control-7>", lambda e: self.notebook.select(6))
        self.root.bind("<Control-Tab>", lambda e: self.next_tab())
        self.root.bind("<Control-Shift-Tab>", lambda e: self.prev_tab())

        # Вкладка 1: Информация о самолёте
        self.create_aircraft_tab()

        # Вкладка 2: Телеметрия
        self.create_telemetry_tab()

        # Вкладка 3: Навигация
        self.create_navigation_tab()

        # Вкладка 4: Настройки захода
        self.create_approach_config_tab()

        # Вкладка 5: Мониторинг подключения
        self.create_connection_monitor_tab()

        # Вкладка 6: Мониторинг vJoy
        self.create_vjoy_monitor_tab()

        # Вкладка 7: Логи
        self.create_logs_tab()

    def create_telemetry_panel(self, parent):
        """Панель телеметрии"""
        row = 0

        # Высота
        ttk.Label(parent, text="Altitude MSL:").grid(row=row, column=0, sticky=tk.W)
        self.alt_msl_var = tk.StringVar(value="0 ft")
        ttk.Label(parent, textvariable=self.alt_msl_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Altitude AGL:").grid(row=row, column=0, sticky=tk.W)
        self.alt_agl_var = tk.StringVar(value="0 ft")
        ttk.Label(parent, textvariable=self.alt_agl_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Radio Height:").grid(row=row, column=0, sticky=tk.W)
        self.radio_height_var = tk.StringVar(value="0 ft")
        ttk.Label(
            parent,
            textvariable=self.radio_height_var,
            font=("Arial", 10, "bold"),
            foreground="blue",
        ).grid(row=row, column=1, sticky=tk.E)
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # Скорость
        ttk.Label(parent, text="IAS:").grid(row=row, column=0, sticky=tk.W)
        self.ias_var = tk.StringVar(value="0 kt")
        ttk.Label(parent, textvariable=self.ias_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Ground Speed:").grid(row=row, column=0, sticky=tk.W)
        self.gs_var = tk.StringVar(value="0 kt")
        ttk.Label(parent, textvariable=self.gs_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Vertical Speed:").grid(row=row, column=0, sticky=tk.W)
        self.vs_var = tk.StringVar(value="0 fpm")
        ttk.Label(parent, textvariable=self.vs_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # Ориентация
        ttk.Label(parent, text="Heading:").grid(row=row, column=0, sticky=tk.W)
        self.heading_var = tk.StringVar(value="0°")
        ttk.Label(parent, textvariable=self.heading_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Pitch:").grid(row=row, column=0, sticky=tk.W)
        self.pitch_var = tk.StringVar(value="0°")
        ttk.Label(parent, textvariable=self.pitch_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Bank:").grid(row=row, column=0, sticky=tk.W)
        self.bank_var = tk.StringVar(value="0°")
        ttk.Label(parent, textvariable=self.bank_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # GPS Destination
        ttk.Label(parent, text="Destination:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W
        )
        row += 1

        ttk.Label(parent, text="Airport:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.dest_airport_var = tk.StringVar(value="N/A")
        self.dest_airport_label = ttk.Label(
            parent, textvariable=self.dest_airport_var, font=("Arial", 10, "bold")
        )
        self.dest_airport_label.grid(row=row, column=1, sticky=tk.E)
        row += 1

        ttk.Label(parent, text="Runway:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.dest_runway_var = tk.StringVar(value="N/A")
        self.dest_runway_label = ttk.Label(
            parent, textvariable=self.dest_runway_var, font=("Arial", 10, "bold")
        )
        self.dest_runway_label.grid(row=row, column=1, sticky=tk.E)
        row += 1

        ttk.Label(parent, text="Distance:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.dest_distance_var = tk.StringVar(value="0.0 nm")
        ttk.Label(parent, textvariable=self.dest_distance_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # Approach Info
        ttk.Label(parent, text="Approach:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W
        )
        row += 1

        ttk.Label(parent, text="Type:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.approach_type_var = tk.StringVar(value="N/A")
        self.approach_type_label = ttk.Label(
            parent, textvariable=self.approach_type_var, font=("Arial", 10, "bold")
        )
        self.approach_type_label.grid(row=row, column=1, sticky=tk.E)
        row += 1

        ttk.Label(parent, text="Decision Height:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.approach_dh_var = tk.StringVar(value="N/A")
        self.approach_dh_label = ttk.Label(
            parent, textvariable=self.approach_dh_var, font=("Arial", 10, "bold")
        )
        self.approach_dh_label.grid(row=row, column=1, sticky=tk.E)
        row += 1

    def next_tab(self):
        """Переключиться на следующую вкладку"""
        current = self.notebook.index(self.notebook.select())
        total = self.notebook.index("end")
        next_tab = (current + 1) % total
        self.notebook.select(next_tab)

    def prev_tab(self):
        """Переключиться на предыдущую вкладку"""
        current = self.notebook.index(self.notebook.select())
        total = self.notebook.index("end")
        prev_tab = (current - 1) % total
        self.notebook.select(prev_tab)

    def create_aircraft_tab(self):
        """Вкладка: Информация о самолёте"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Aircraft Info (Ctrl+1)")

        # Основной контейнер с прокруткой (оптимизированный)
        canvas = tk.Canvas(tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        # Оптимизация: обновление scrollregion только после idle
        def update_scrollregion(event=None):
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.after_idle(update_scrollregion)
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Привязка скроллинга мышью
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Информация о самолёте
        aircraft_frame = ttk.LabelFrame(
            scrollable_frame, text="Aircraft Information", padding="15"
        )
        aircraft_frame.pack(fill=tk.X, padx=10, pady=10)

        self.create_aircraft_panel(aircraft_frame)

        # Детальная информация о совместимости
        compat_frame = ttk.LabelFrame(
            scrollable_frame, text="Compatibility Details", padding="15"
        )
        compat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.compat_details_text = scrolledtext.ScrolledText(
            compat_frame, height=15, width=70, font=("Courier", 9), wrap=tk.WORD
        )
        self.compat_details_text.pack(fill=tk.BOTH, expand=True)
        self.compat_details_text.insert(
            "1.0", "Connect to MSFS to see aircraft information..."
        )
        self.compat_details_text.configure(state="disabled")

    def create_telemetry_tab(self):
        """Вкладка: Телеметрия"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Telemetry (Ctrl+2)")

        # Левая колонка - основная телеметрия
        left_frame = ttk.LabelFrame(tab, text="Flight Data", padding="15")
        left_frame.grid(
            row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E), padx=10, pady=10
        )

        self.create_telemetry_panel(left_frame)

        # Правая колонка - двигатели и системы
        right_frame = ttk.LabelFrame(tab, text="Engine & Systems", padding="15")
        right_frame.grid(
            row=0, column=1, sticky=(tk.N, tk.S, tk.W, tk.E), padx=10, pady=10
        )

        self.create_engine_panel(right_frame)

        # Нижняя панель - стабилизация и выравнивание
        bottom_frame = ttk.Frame(tab)
        bottom_frame.grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=10, pady=10
        )

        stab_frame = ttk.LabelFrame(bottom_frame, text="Stabilization", padding="10")
        stab_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)
        self.create_stabilization_panel(stab_frame)

        flare_frame = ttk.LabelFrame(bottom_frame, text="Flare", padding="10")
        flare_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.create_flare_panel(flare_frame)

        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

    def create_navigation_tab(self):
        """Вкладка: Навигация"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Navigation (Ctrl+3)")

        # Навигационная информация
        nav_frame = ttk.LabelFrame(tab, text="Navigation Data", padding="15")
        nav_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.create_navigation_panel(nav_frame)

    def create_approach_config_tab(self):
        """Вкладка: Настройки захода"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Approach Config (Ctrl+4)")

        # Информационная панель
        info_frame = ttk.LabelFrame(tab, text="Approach Configuration", padding="15")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        info_text = tk.Text(
            info_frame, height=20, width=80, font=("Arial", 10), wrap=tk.WORD
        )
        info_text.pack(fill=tk.BOTH, expand=True)

        info_content = """
Настройка параметров захода на посадку

Для настройки захода используйте кнопку "Start Approach" в верхней панели.

Откроется диалоговое окно с полями:

1. RUNWAY HEADING - Курс ВПП (магнитный)
2. APPROACH ALTITUDE - Высота начала захода (футы MSL)
3. FINAL ALTITUDE - Высота финального этапа (футы MSL)
4. TARGET SPEED - Целевая скорость (узлы)
5. DESCENT RATE - Скорость снижения (футы/мин)

Дополнительные опции:

• Auto-Detect - автоматическое определение параметров из MSFS
• Load from Database - загрузка из базы данных аэропортов
• ILS Configuration - настройка ILS захода (частота, курс)

Горячие клавиши:

• Ctrl+1-5 - переключение между вкладками
• Ctrl+Tab - следующая вкладка
• Ctrl+Shift+Tab - предыдущая вкладка
        """

        info_text.insert("1.0", info_content)
        info_text.configure(state="disabled")

    def create_connection_monitor_tab(self):
        """Вкладка: Мониторинг подключения"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Connection Monitor (Ctrl+5)")

        # Основной контейнер с прокруткой
        canvas = tk.Canvas(tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        def update_scrollregion(event=None):
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.after_idle(update_scrollregion)
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Панель текущего статуса
        status_frame = ttk.LabelFrame(
            scrollable_frame, text="Current Status", padding="15"
        )
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        # Текущий метод
        ttk.Label(status_frame, text="Active Method:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.monitor_method_var = tk.StringVar(value="N/A")
        self.monitor_method_label = ttk.Label(
            status_frame,
            textvariable=self.monitor_method_var,
            font=("Arial", 12, "bold"),
            foreground="blue",
        )
        self.monitor_method_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Фаза полёта
        ttk.Label(status_frame, text="Flight Phase:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.monitor_phase_var = tk.StringVar(value="N/A")
        ttk.Label(
            status_frame, textvariable=self.monitor_phase_var, font=("Arial", 10)
        ).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # Самолёт
        ttk.Label(status_frame, text="Aircraft:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.monitor_aircraft_var = tk.StringVar(value="N/A")
        ttk.Label(
            status_frame, textvariable=self.monitor_aircraft_var, font=("Arial", 10)
        ).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Количество переключений
        ttk.Label(status_frame, text="Total Switches:").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.monitor_switches_var = tk.StringVar(value="0")
        ttk.Label(
            status_frame, textvariable=self.monitor_switches_var, font=("Arial", 10)
        ).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        # Панель метрик производительности
        metrics_frame = ttk.LabelFrame(
            scrollable_frame, text="Performance Metrics", padding="15"
        )
        metrics_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Заголовки таблицы
        headers = [
            "Method",
            "Status",
            "Operations",
            "Read (ms)",
            "Write (ms)",
            "Reliability",
            "Score",
        ]
        for col, header in enumerate(headers):
            ttk.Label(metrics_frame, text=header, font=("Arial", 9, "bold")).grid(
                row=0, column=col, padx=5, pady=5
            )

        # Строки для каждого метода
        self.monitor_metrics_vars = {}
        methods = ["SimConnect", "WASM", "L:Vars"]

        for row, method in enumerate(methods, start=1):
            self.monitor_metrics_vars[method] = {
                "status": tk.StringVar(value="❌"),
                "operations": tk.StringVar(value="0"),
                "read_ms": tk.StringVar(value="0.00"),
                "write_ms": tk.StringVar(value="0.00"),
                "reliability": tk.StringVar(value="0.0%"),
                "score": tk.StringVar(value="0.0"),
            }

            # Название метода
            ttk.Label(metrics_frame, text=method, font=("Arial", 9, "bold")).grid(
                row=row, column=0, sticky=tk.W, padx=5, pady=2
            )

            # Статус
            ttk.Label(
                metrics_frame,
                textvariable=self.monitor_metrics_vars[method]["status"],
                font=("Arial", 10),
            ).grid(row=row, column=1, padx=5, pady=2)

            # Операции
            ttk.Label(
                metrics_frame,
                textvariable=self.monitor_metrics_vars[method]["operations"],
                font=("Arial", 9),
            ).grid(row=row, column=2, padx=5, pady=2)

            # Read time
            ttk.Label(
                metrics_frame,
                textvariable=self.monitor_metrics_vars[method]["read_ms"],
                font=("Arial", 9),
            ).grid(row=row, column=3, padx=5, pady=2)

            # Write time
            ttk.Label(
                metrics_frame,
                textvariable=self.monitor_metrics_vars[method]["write_ms"],
                font=("Arial", 9),
            ).grid(row=row, column=4, padx=5, pady=2)

            # Reliability
            ttk.Label(
                metrics_frame,
                textvariable=self.monitor_metrics_vars[method]["reliability"],
                font=("Arial", 9),
            ).grid(row=row, column=5, padx=5, pady=2)

            # Score
            ttk.Label(
                metrics_frame,
                textvariable=self.monitor_metrics_vars[method]["score"],
                font=("Arial", 9, "bold"),
            ).grid(row=row, column=6, padx=5, pady=2)

        # Панель истории переключений
        history_frame = ttk.LabelFrame(
            scrollable_frame, text="Switch History (Last 5)", padding="15"
        )
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.monitor_history_text = scrolledtext.ScrolledText(
            history_frame, height=10, width=80, font=("Courier", 9), wrap=tk.WORD
        )
        self.monitor_history_text.pack(fill=tk.BOTH, expand=True)
        self.monitor_history_text.insert("1.0", "No switches yet...")
        self.monitor_history_text.configure(state="disabled")

        # Кнопки управления
        buttons_frame = ttk.Frame(scrollable_frame, padding="10")
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(
            buttons_frame,
            text="Export Metrics (JSON)",
            command=self.export_monitor_json,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            buttons_frame, text="Export Metrics (CSV)", command=self.export_monitor_csv
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            buttons_frame,
            text="Force Test All Methods",
            command=self.force_connection_test,
        ).pack(side=tk.LEFT, padx=5)

    def create_vjoy_monitor_tab(self):
        """Вкладка: Мониторинг vJoy"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="vJoy Monitor (Ctrl+6)")

        # Основной контейнер
        main_frame = ttk.Frame(tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Панель статуса vJoy
        status_frame = ttk.LabelFrame(main_frame, text="vJoy Status", padding="15")
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        # Статус подключения
        ttk.Label(status_frame, text="Status:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.vjoy_status_var = tk.StringVar(value="Disconnected")
        self.vjoy_status_label = ttk.Label(
            status_frame,
            textvariable=self.vjoy_status_var,
            font=("Arial", 10, "bold"),
            foreground="red",
        )
        self.vjoy_status_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Device ID
        ttk.Label(status_frame, text="Device ID:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.vjoy_device_var = tk.StringVar(value="N/A")
        ttk.Label(
            status_frame, textvariable=self.vjoy_device_var, font=("Arial", 10)
        ).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # Total Commands
        ttk.Label(status_frame, text="Total Commands:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.vjoy_total_commands_var = tk.StringVar(value="0")
        ttk.Label(
            status_frame, textvariable=self.vjoy_total_commands_var, font=("Arial", 10)
        ).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Панель текущих значений осей
        axes_frame = ttk.LabelFrame(
            main_frame, text="Current Axis Values", padding="15"
        )
        axes_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Создание визуальных индикаторов для каждой оси
        axes = [
            ("Aileron (Roll)", "aileron", "Left", "Right"),
            ("Elevator (Pitch)", "elevator", "Down", "Up"),
            ("Rudder (Yaw)", "rudder", "Left", "Right"),
            ("Throttle", "throttle", "Idle", "Full"),
        ]

        self.vjoy_axis_vars = {}
        self.vjoy_axis_bars = {}
        self.vjoy_command_count_vars = {}

        for idx, (label, axis_name, left_label, right_label) in enumerate(axes):
            # Фрейм для оси
            axis_frame = ttk.Frame(axes_frame)
            axis_frame.pack(fill=tk.X, padx=5, pady=10)

            # Название оси и значение
            header_frame = ttk.Frame(axis_frame)
            header_frame.pack(fill=tk.X)

            ttk.Label(header_frame, text=label, font=("Arial", 10, "bold")).pack(
                side=tk.LEFT
            )

            self.vjoy_axis_vars[axis_name] = tk.StringVar(value="0.00")
            ttk.Label(
                header_frame,
                textvariable=self.vjoy_axis_vars[axis_name],
                font=("Arial", 10),
                foreground="blue",
            ).pack(side=tk.LEFT, padx=10)

            self.vjoy_command_count_vars[axis_name] = tk.StringVar(value="(0 commands)")
            ttk.Label(
                header_frame,
                textvariable=self.vjoy_command_count_vars[axis_name],
                font=("Arial", 9),
                foreground="gray",
            ).pack(side=tk.LEFT)

            # Прогресс-бар для визуализации
            bar_frame = ttk.Frame(axis_frame)
            bar_frame.pack(fill=tk.X, pady=5)

            ttk.Label(bar_frame, text=left_label, font=("Arial", 8)).pack(
                side=tk.LEFT, padx=5
            )

            # Canvas для рисования бара
            canvas = tk.Canvas(
                bar_frame,
                height=30,
                bg="white",
                highlightthickness=1,
                highlightbackground="gray",
            )
            canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            self.vjoy_axis_bars[axis_name] = canvas

            ttk.Label(bar_frame, text=right_label, font=("Arial", 8)).pack(
                side=tk.LEFT, padx=5
            )

        # Кнопки управления
        buttons_frame = ttk.Frame(main_frame, padding="10")
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(
            buttons_frame, text="Center All Axes", command=self.vjoy_center_axes
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            buttons_frame, text="Test Aileron", command=self.vjoy_test_aileron
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            buttons_frame, text="Test Elevator", command=self.vjoy_test_elevator
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            buttons_frame, text="Test Rudder", command=self.vjoy_test_rudder
        ).pack(side=tk.LEFT, padx=5)

    def create_logs_tab(self):
        """Вкладка: Логи"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Logs (Ctrl+7)")

        log_frame = ttk.Frame(tab, padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=25, state="disabled", font=("Courier", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def create_engine_panel(self, parent):
        """Панель информации о двигателях"""
        row = 0

        ttk.Label(parent, text="Throttle Position:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        ttk.Label(parent, text="Engine 1:").grid(row=row, column=0, sticky=tk.W)
        self.throttle1_var = tk.StringVar(value="0%")
        ttk.Label(parent, textvariable=self.throttle1_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Engine 2:").grid(row=row, column=0, sticky=tk.W)
        self.throttle2_var = tk.StringVar(value="0%")
        ttk.Label(parent, textvariable=self.throttle2_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        ttk.Label(parent, text="N1 (RPM):", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        ttk.Label(parent, text="Engine 1:").grid(row=row, column=0, sticky=tk.W)
        self.n1_1_var = tk.StringVar(value="0%")
        ttk.Label(parent, textvariable=self.n1_1_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Engine 2:").grid(row=row, column=0, sticky=tk.W)
        self.n1_2_var = tk.StringVar(value="0%")
        ttk.Label(parent, textvariable=self.n1_2_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        ttk.Label(parent, text="Flaps:").grid(row=row, column=0, sticky=tk.W)
        self.flaps_var = tk.StringVar(value="0°")
        ttk.Label(parent, textvariable=self.flaps_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Gear:").grid(row=row, column=0, sticky=tk.W)
        self.gear_var = tk.StringVar(value="UP")
        ttk.Label(parent, textvariable=self.gear_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

    def create_aircraft_panel(self, parent):
        """Панель информации о самолёте и автопилоте"""
        row = 0

        # Название самолёта
        ttk.Label(parent, text="Aircraft:").grid(row=row, column=0, sticky=tk.W)
        self.aircraft_name_var = tk.StringVar(value="Unknown")
        ttk.Label(
            parent, textvariable=self.aircraft_name_var, font=("Arial", 9, "bold")
        ).grid(row=row, column=1, sticky=tk.W)
        row += 1

        # Профиль автопилота
        ttk.Label(parent, text="AP Profile:").grid(row=row, column=0, sticky=tk.W)
        self.ap_profile_var = tk.StringVar(value="Standard")
        ttk.Label(parent, textvariable=self.ap_profile_var, font=("Arial", 9)).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1

        # Статус совместимости
        ttk.Label(parent, text="Status:").grid(row=row, column=0, sticky=tk.W)
        self.compat_status_var = tk.StringVar(value="Unknown")
        self.compat_status_label = ttk.Label(
            parent, textvariable=self.compat_status_var, font=("Arial", 9)
        )
        self.compat_status_label.grid(row=row, column=1, sticky=tk.W)
        row += 1

        # Статус vJoy
        ttk.Label(parent, text="vJoy:").grid(row=row, column=0, sticky=tk.W)
        self.vjoy_status_var = tk.StringVar(value="Unknown")
        self.vjoy_status_label = ttk.Label(
            parent, textvariable=self.vjoy_status_var, font=("Arial", 9)
        )
        self.vjoy_status_label.grid(row=row, column=1, sticky=tk.W)
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # MobiFlight WASM версия
        ttk.Label(parent, text="MobiFlight WASM:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, sticky=tk.W
        )
        row += 1

        ttk.Label(parent, text="Version:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.wasm_version_var = tk.StringVar(value="Checking...")
        self.wasm_version_label = ttk.Label(
            parent, textvariable=self.wasm_version_var, font=("Arial", 9)
        )
        self.wasm_version_label.grid(row=row, column=1, sticky=tk.W)
        row += 1

        # Кнопка проверки обновлений
        self.wasm_check_btn = ttk.Button(
            parent,
            text="Check for Updates",
            command=self.check_wasm_updates,
            state="normal",
        )
        self.wasm_check_btn.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # Режимы автопилота (будут обновляться если доступны)
        ttk.Label(parent, text="AP Modes:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        self.ap_modes_var = tk.StringVar(value="N/A")
        ttk.Label(parent, textvariable=self.ap_modes_var, font=("Arial", 8)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        # Доступные режимы автопилота
        ttk.Label(
            parent,
            text="Available AP modes:",
            font=("Arial", 8, "italic"),
            foreground="gray",
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W)
        row += 1

        self.ap_available_modes_var = tk.StringVar(
            value="Connect to see available modes"
        )
        ttk.Label(
            parent,
            textvariable=self.ap_available_modes_var,
            font=("Arial", 7),
            foreground="gray",
            wraplength=200,
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W)

    def create_navigation_panel(self, parent):
        """Панель навигации"""
        row = 0

        ttk.Label(parent, text="DME Distance:").grid(row=row, column=0, sticky=tk.W)
        self.dme_var = tk.StringVar(value="-- nm")
        ttk.Label(parent, textvariable=self.dme_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Cross Track Error:").grid(
            row=row, column=0, sticky=tk.W
        )
        self.xte_var = tk.StringVar(value="--°")
        ttk.Label(parent, textvariable=self.xte_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Wind:").grid(row=row, column=0, sticky=tk.W)
        self.wind_var = tk.StringVar(value="-- kt from --°")
        ttk.Label(parent, textvariable=self.wind_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # Компоненты ветра
        ttk.Label(parent, text="Headwind:").grid(row=row, column=0, sticky=tk.W)
        self.headwind_var = tk.StringVar(value="-- kt")
        ttk.Label(parent, textvariable=self.headwind_var, font=("Arial", 9)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Crosswind:").grid(row=row, column=0, sticky=tk.W)
        self.crosswind_var = tk.StringVar(value="-- kt")
        ttk.Label(parent, textvariable=self.crosswind_var, font=("Arial", 9)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # Поправки на ветер
        ttk.Label(parent, text="Wind Corrections:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        ttk.Label(parent, text="Throttle:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.wind_throttle_corr_var = tk.StringVar(value="--")
        ttk.Label(
            parent, textvariable=self.wind_throttle_corr_var, font=("Arial", 9)
        ).grid(row=row, column=1, sticky=tk.E)
        row += 1

        ttk.Label(parent, text="Crab Angle:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.crab_angle_var = tk.StringVar(value="--°")
        ttk.Label(parent, textvariable=self.crab_angle_var, font=("Arial", 9)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Drift Angle:").grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.drift_angle_var = tk.StringVar(value="--°")
        ttk.Label(parent, textvariable=self.drift_angle_var, font=("Arial", 9)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # Предупреждение о сдвиге ветра
        ttk.Label(parent, text="Wind Shear:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        self.wind_shear_var = tk.StringVar(value="Not detected")
        self.wind_shear_label = ttk.Label(
            parent, textvariable=self.wind_shear_var, font=("Arial", 9)
        )
        self.wind_shear_label.grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=(10, 0)
        )
        row += 1

        # Предупреждение о турбулентности
        ttk.Label(parent, text="Turbulence:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        self.turbulence_var = tk.StringVar(value="SMOOTH")
        self.turbulence_label = ttk.Label(
            parent, textvariable=self.turbulence_var, font=("Arial", 9)
        )
        self.turbulence_label.grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=(10, 0)
        )
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=5
        )
        row += 1

        # Approach Speeds
        ttk.Label(parent, text="Approach Speeds:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        ttk.Label(parent, text="VREF:", font=("Arial", 8)).grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.vref_var = tk.StringVar(value="---")
        ttk.Label(parent, textvariable=self.vref_var, font=("Arial", 8)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="VAPP:", font=("Arial", 8, "bold")).grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.vapp_var = tk.StringVar(value="---")
        self.vapp_label = ttk.Label(
            parent,
            textvariable=self.vapp_var,
            font=("Arial", 9, "bold"),
            foreground="blue",
        )
        self.vapp_label.grid(row=row, column=1, sticky=tk.E)
        row += 1

        ttk.Label(parent, text="Flaps:", font=("Arial", 8)).grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.flaps_config_var = tk.StringVar(value="--")
        ttk.Label(parent, textvariable=self.flaps_config_var, font=("Arial", 8)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Weight:", font=("Arial", 8)).grid(
            row=row, column=0, sticky=tk.W, padx=(10, 0)
        )
        self.weight_var = tk.StringVar(value="--")
        self.weight_label = ttk.Label(
            parent, textvariable=self.weight_var, font=("Arial", 8)
        )
        self.weight_label.grid(row=row, column=1, sticky=tk.E)
        row += 1

    def create_stabilization_panel(self, parent):
        """Панель стабилизации"""
        ttk.Label(parent, text="Status:").grid(row=0, column=0, sticky=tk.W)
        self.stab_status_var = tk.StringVar(value="Not checked")
        self.stab_status_label = ttk.Label(
            parent, textvariable=self.stab_status_var, font=("Arial", 10)
        )
        self.stab_status_label.grid(row=0, column=1, sticky=tk.E)

        self.stab_violations_text = tk.Text(
            parent, height=3, width=40, state="disabled"
        )
        self.stab_violations_text.grid(row=1, column=0, columnspan=2, pady=5)

    def create_flare_panel(self, parent):
        """Панель выравнивания"""
        row = 0

        ttk.Label(parent, text="Status:").grid(row=row, column=0, sticky=tk.W)
        self.flare_status_var = tk.StringVar(value="Inactive")
        ttk.Label(parent, textvariable=self.flare_status_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

        ttk.Label(parent, text="Progress:").grid(row=row, column=0, sticky=tk.W)
        self.flare_progress_var = tk.StringVar(value="0%")
        ttk.Label(
            parent, textvariable=self.flare_progress_var, font=("Arial", 10)
        ).grid(row=row, column=1, sticky=tk.E)
        row += 1

        ttk.Label(parent, text="Target Pitch:").grid(row=row, column=0, sticky=tk.W)
        self.flare_pitch_var = tk.StringVar(value="--°")
        ttk.Label(parent, textvariable=self.flare_pitch_var, font=("Arial", 10)).grid(
            row=row, column=1, sticky=tk.E
        )
        row += 1

    def setup_logging(self):
        """Настройка логирования в GUI"""
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(text_handler)
        logging.getLogger().setLevel(logging.INFO)

    def check_wasm_version_on_connect(self):
        """Проверка версии MobiFlight WASM при подключении"""

        def do_check():
            try:
                checker = MobiFlightVersionChecker()
                result = checker.check_for_updates()

                # Обновление GUI
                if result.get("installed_version"):
                    version_text = f"v{result['installed_version']}"

                    if result.get("update_available"):
                        version_text += " (Update available!)"
                        self.root.after(
                            0,
                            lambda: self.wasm_version_label.config(foreground="orange"),
                        )

                        # Показать уведомление об обновлении
                        message = checker.get_update_message()
                        if message:
                            self.root.after(
                                0,
                                lambda: messagebox.showwarning(
                                    "MobiFlight WASM Update Available", message
                                ),
                            )
                    else:
                        self.root.after(
                            0,
                            lambda: self.wasm_version_label.config(foreground="green"),
                        )

                    self.root.after(0, lambda: self.wasm_version_var.set(version_text))
                else:
                    self.root.after(
                        0, lambda: self.wasm_version_var.set("Not installed")
                    )
                    self.root.after(
                        0, lambda: self.wasm_version_label.config(foreground="red")
                    )

            except Exception as e:
                logging.error(f"Error checking WASM version: {e}")
                self.root.after(0, lambda: self.wasm_version_var.set("Check failed"))
                self.root.after(
                    0, lambda: self.wasm_version_label.config(foreground="gray")
                )

        # Запуск проверки в отдельном потоке
        threading.Thread(target=do_check, daemon=True).start()

    def check_wasm_updates(self):
        """Ручная проверка обновлений MobiFlight WASM"""
        self.wasm_version_var.set("Checking...")
        self.wasm_check_btn.config(state="disabled")

        def do_check():
            try:
                checker = MobiFlightVersionChecker()
                result = checker.check_for_updates()

                if result.get("error"):
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Check Failed",
                            f"Failed to check for updates:\n{result['error']}",
                        ),
                    )
                    self.root.after(
                        0, lambda: self.wasm_version_var.set("Check failed")
                    )
                    self.root.after(
                        0, lambda: self.wasm_version_label.config(foreground="gray")
                    )
                elif result.get("installed_version"):
                    version_text = f"v{result['installed_version']}"

                    if result.get("update_available"):
                        version_text += " (Update available!)"
                        self.root.after(
                            0,
                            lambda: self.wasm_version_label.config(foreground="orange"),
                        )

                        # Показать информацию об обновлении
                        message = (
                            f"Update available!\n\n"
                            f"Installed: v{result['installed_version']}\n"
                            f"Latest: v{result['latest_version']}\n\n"
                            f"Download from:\n{result['download_url']}\n\n"
                            f"See MOBIFLIGHT_SETUP.md for installation instructions."
                        )
                        self.root.after(
                            0,
                            lambda: messagebox.showinfo(
                                "MobiFlight WASM Update", message
                            ),
                        )
                    else:
                        version_text += " (Up to date)"
                        self.root.after(
                            0,
                            lambda: self.wasm_version_label.config(foreground="green"),
                        )
                        self.root.after(
                            0,
                            lambda: messagebox.showinfo(
                                "MobiFlight WASM",
                                f"You have the latest version: v{result['installed_version']}",
                            ),
                        )

                    self.root.after(0, lambda: self.wasm_version_var.set(version_text))
                else:
                    self.root.after(
                        0, lambda: self.wasm_version_var.set("Not installed")
                    )
                    self.root.after(
                        0, lambda: self.wasm_version_label.config(foreground="red")
                    )
                    self.root.after(
                        0,
                        lambda: messagebox.showwarning(
                            "MobiFlight WASM",
                            "MobiFlight WASM is not installed.\n\nSee MOBIFLIGHT_SETUP.md for installation instructions.",
                        ),
                    )

            except Exception as e:
                logging.error(f"Error checking WASM updates: {e}")
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", f"Error checking for updates:\n{error_msg}"
                    ),
                )
                self.root.after(0, lambda: self.wasm_version_var.set("Check failed"))
                self.root.after(
                    0, lambda: self.wasm_version_label.config(foreground="gray")
                )
            finally:
                self.root.after(0, lambda: self.wasm_check_btn.config(state="normal"))

        # Запуск проверки в отдельном потоке
        threading.Thread(target=do_check, daemon=True).start()

    def connect_msfs(self):
        """Подключение к MSFS"""
        # Отключить кнопку сразу
        self.connect_btn.config(state="disabled")
        self.status_label.config(text="Connecting...", foreground="orange")

        def do_connect():
            try:
                self.system = AutoLandSystem()
                if self.system.connect():
                    # Обновление GUI из потока - используем after()
                    self.root.after(
                        0,
                        lambda: self.status_label.config(
                            text="Connected", foreground="green"
                        ),
                    )
                    self.root.after(
                        0, lambda: self.disconnect_btn.config(state="normal")
                    )
                    self.root.after(0, lambda: self.start_btn.config(state="normal"))
                    self.root.after(
                        0, lambda: messagebox.showinfo("Success", "Connected to MSFS!")
                    )

                    # Получить и отобразить информацию о самолёте
                    self.display_aircraft_report()

                    # Проверить версию MobiFlight WASM
                    self.check_wasm_version_on_connect()
                else:
                    self.root.after(
                        0,
                        lambda: self.status_label.config(
                            text="Disconnected", foreground="red"
                        ),
                    )
                    self.root.after(0, lambda: self.connect_btn.config(state="normal"))
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Error", "Failed to connect to MSFS"
                        ),
                    )
            except Exception as e:
                error_msg = str(e)
                self.root.after(
                    0, lambda: self.status_label.config(text="Error", foreground="red")
                )
                self.root.after(0, lambda: self.connect_btn.config(state="normal"))
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", f"Connection error: {error_msg}"
                    ),
                )

        # Запуск подключения в отдельном потоке
        threading.Thread(target=do_connect, daemon=True).start()

    def disconnect_msfs(self):
        """Отключение от MSFS"""
        try:
            if self.system:
                self.system.disconnect()
                self.system = None

            self.status_label.config(text="Disconnected", foreground="red")
            self.connect_btn.config(state="normal")
            self.disconnect_btn.config(state="disabled")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
            self.ga_btn.config(state="disabled")

            # Сброс отображаемых данных
            self.aircraft_name_var.set("N/A")
            self.ap_profile_var.set("N/A")
            self.compat_status_var.set("N/A")
            self.ap_modes_var.set("N/A")
            self.ap_available_modes_var.set("Connect to see available modes")
            self.wasm_version_var.set("Checking...")
            self.wasm_version_label.config(foreground="gray")

            messagebox.showinfo("Disconnected", "Disconnected from MSFS")
        except Exception as e:
            messagebox.showerror("Error", f"Disconnect error: {e}")

    def start_approach(self):
        """Начать заход"""
        # Открыть диалог настройки захода (передаём телеметрию для Auto-Detect)
        dialog = ApproachConfigDialog(
            self.root, self.system.telemetry if self.system else None
        )
        approach_config, ils_config = dialog.show()

        if not approach_config:
            # Пользователь отменил
            return

        # Настройка захода
        self.system.configure_approach(approach_config)

        # Если это ILS заход, настроить ILS навигацию
        if ils_config and hasattr(self.system, "ils_navigation"):
            self.system.ils_navigation.configure(ils_config)
            logging.info("ILS navigation configured")

        self.system.start_approach()

        # Запуск потока выполнения захода
        self.running = True
        self.update_thread = threading.Thread(target=self.run_approach, daemon=True)
        self.update_thread.start()

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.ga_btn.config(state="normal")

    def run_approach(self):
        """Выполнение захода в отдельном потоке"""
        self.system.execute_approach()

    def stop_approach(self):
        """Остановить заход"""
        if self.system:
            self.system.stop_approach()
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.ga_btn.config(state="disabled")

    def toggle_audio_alerts(self):
        """Переключить звуковые предупреждения"""
        if self.system:
            self.system.audio_alerts_enabled = self.audio_alerts_var.get()
            status = "enabled" if self.audio_alerts_var.get() else "disabled"
            logging.info(f"Audio alerts {status}")

    def go_around(self):
        """Уход на второй круг"""
        if self.system:
            self.system.execute_go_around()

    def display_aircraft_report(self):
        """Отобразить отчёт о самолёте после подключения"""
        if not self.system or not self.system.telemetry.connected:
            return

        try:
            # Получить информацию о самолёте
            aircraft_info = self.system.telemetry.get_aircraft_info()

            if not aircraft_info:
                logging.warning("Failed to get aircraft info")
                return

            # Базовая информация
            title = aircraft_info.get("title", "Unknown")
            manufacturer = aircraft_info.get("aircraft_manufacturer", "Unknown")
            autopilot_type = aircraft_info.get("autopilot_type", "Unknown")
            is_custom = aircraft_info.get("is_custom_aircraft", False)

            # Определить тип (дефолт или кастом)
            aircraft_type = "Custom Aircraft" if is_custom else "Default MSFS Aircraft"

            # Получить информацию о профиле и совместимости
            profile_name = "Standard MSFS"
            profile_manufacturer = "Microsoft/Asobo"
            compatibility_status = "Compatible"
            compatibility_color = "green"
            compatibility_details = []
            version_info = "N/A"

            # Если есть aircraft_adapter, получить детальную информацию
            if (
                hasattr(self.system, "aircraft_adapter")
                and self.system.aircraft_adapter
            ):
                adapter = self.system.aircraft_adapter

                # Информация о профиле
                profile_info = adapter.get_profile_info()
                if profile_info:
                    profile_name = profile_info.get("name", "Standard MSFS")
                    profile_manufacturer = profile_info.get("manufacturer", "Unknown")

                # Проверка совместимости
                compat = adapter.check_compatibility()

                if compat.get("compatible"):
                    if compat.get("limited"):
                        compatibility_status = "Limited Compatibility"
                        compatibility_color = "orange"
                        compatibility_details.append(compat.get("reason", ""))
                        compatibility_details.append(compat.get("recommendation", ""))
                        compatibility_details.append(
                            f"Fallback: {compat.get('fallback', 'SimConnect')}"
                        )
                    else:
                        compatibility_status = "Full Compatibility"
                        compatibility_color = "green"
                        if compat.get("full_functionality"):
                            compatibility_details.append("✓ WASM support available")
                            compatibility_details.append("✓ Custom autopilot commands")
                        if compat.get("autothrottle"):
                            compatibility_details.append("✓ Autothrottle supported")
                else:
                    compatibility_status = "Not Compatible"
                    compatibility_color = "red"
                    compatibility_details.append(compat.get("reason", "Unknown reason"))

                # Попытка получить версию из конфигурационных файлов
                if adapter.config_reader:
                    try:
                        details = adapter.config_reader.get_aircraft_details(title)
                        if details.get("found"):
                            manifest = details.get("manifest")
                            if manifest:
                                version_info = manifest.get("package_version", "N/A")
                                if version_info == "N/A":
                                    version_info = manifest.get("version", "N/A")
                    except Exception as e:
                        logging.debug(f"Could not get version info: {e}")

            # Формирование отчёта
            report_lines = [
                "=" * 60,
                "AIRCRAFT DETECTION REPORT",
                "=" * 60,
                "",
                f"Aircraft Title: {title}",
                f"Type: {aircraft_type}",
                f"Manufacturer: {manufacturer}",
                f"Version: {version_info}",
                "",
                "--- Autopilot Profile ---",
                f"Profile: {profile_name}",
                f"Developer: {profile_manufacturer}",
                f"SimConnect Type: {autopilot_type}",
                "",
                "--- Compatibility Status ---",
                f"Status: {compatibility_status}",
            ]

            if compatibility_details:
                report_lines.append("")
                for detail in compatibility_details:
                    if detail:
                        report_lines.append(f"  {detail}")

            # Добавить информацию о возможностях автопилота
            ap_caps = self.system.telemetry.get_autopilot_capabilities()
            if ap_caps:
                report_lines.append("")
                report_lines.append("--- Autopilot Capabilities ---")
                if ap_caps.get("available"):
                    report_lines.append("✓ Autopilot Available")

                    # Проверка текущего состояния для определения доступных режимов
                    ap_state = self.system.telemetry.get_autopilot_state()
                    available_modes = []

                    # Все стандартные самолёты MSFS имеют базовые режимы
                    available_modes.append("Master (AP)")
                    available_modes.append("Heading Hold (HDG)")
                    available_modes.append("Altitude Hold (ALT)")

                    # Проверяем наличие дополнительных режимов
                    if ap_state is not None:
                        available_modes.append("Navigation (NAV)")
                        available_modes.append("Approach (APP)")

                    # Проверяем наличие autothrottle
                    if ap_caps.get("has_autothrottle"):
                        available_modes.append("Autothrottle (AT)")

                    max_bank = ap_caps.get("max_bank")
                    if max_bank:
                        report_lines.append(f"  Max Bank Angle: {max_bank:.1f}°")

                    report_lines.append("  Available Modes:")
                    for mode in available_modes:
                        report_lines.append(f"    • {mode}")
                else:
                    report_lines.append("✗ No Autopilot Available")

            report_lines.extend(["", "=" * 60, ""])

            # Вывод в лог
            report_text = "\n".join(report_lines)
            logging.info(report_text)

            # Обновление GUI панели Aircraft & Autopilot
            self.aircraft_name_var.set(title[:40] + "..." if len(title) > 40 else title)
            self.ap_profile_var.set(profile_name)
            self.compat_status_var.set(compatibility_status)
            self.compat_status_label.config(foreground=compatibility_color)

            # Обновление доступных режимов автопилота в GUI
            if ap_caps and ap_caps.get("available"):
                ap_state = self.system.telemetry.get_autopilot_state()
                available_modes_short = ["AP", "HDG", "ALT"]
                if ap_state is not None:
                    available_modes_short.extend(["NAV", "APP"])
                if ap_caps.get("has_autothrottle"):
                    available_modes_short.append("AT")
                self.ap_available_modes_var.set(" | ".join(available_modes_short))
            else:
                self.ap_available_modes_var.set("No autopilot")

            # Обновление текстового поля во вкладке Aircraft Info
            if hasattr(self, "compat_details_text"):
                self.compat_details_text.configure(state="normal")
                self.compat_details_text.delete("1.0", tk.END)

                detailed_report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AIRCRAFT DETECTION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Aircraft Title:
  {title}

Type: {aircraft_type}
Manufacturer: {manufacturer}
Version: {version_info}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTOPILOT PROFILE

Profile: {profile_name}
Developer: {profile_manufacturer}
SimConnect Type: {autopilot_type}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMPATIBILITY STATUS

Status: {compatibility_status}
"""

                if compatibility_details:
                    detailed_report += "\nDetails:\n"
                    for detail in compatibility_details:
                        if detail:
                            detailed_report += f"  • {detail}\n"

                detailed_report += "\n" + "━" * 60 + "\n"
                detailed_report += "\nDetection Methods Used:\n"
                detailed_report += "  1. SimConnect autopilot_type\n"
                detailed_report += "  2. TITLE pattern matching\n"
                detailed_report += (
                    "  3. Configuration files (manifest.json, aircraft.cfg)\n"
                )

                self.compat_details_text.insert("1.0", detailed_report)
                self.compat_details_text.configure(state="disabled")

            # Показать диалоговое окно с отчётом (опционально)
            # self.show_aircraft_report_dialog(...)

        except Exception as e:
            logging.error(f"Error displaying aircraft report: {e}")

    def show_aircraft_report_dialog(
        self,
        title,
        aircraft_type,
        manufacturer,
        version,
        profile_name,
        profile_dev,
        autopilot_type,
        compat_status,
        compat_color,
        compat_details,
    ):
        """Показать диалоговое окно с отчётом о самолёте"""

        dialog = tk.Toplevel(self.root)
        dialog.title("Aircraft Detection Report")
        dialog.geometry("600x500")
        dialog.resizable(False, False)

        # Заголовок
        header_frame = ttk.Frame(dialog, padding="10")
        header_frame.pack(fill=tk.X)

        ttk.Label(
            header_frame, text="Aircraft Detection Report", font=("Arial", 14, "bold")
        ).pack()

        # Основная информация
        main_frame = ttk.LabelFrame(dialog, text="Aircraft Information", padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        info_text = scrolledtext.ScrolledText(
            main_frame, height=15, width=70, font=("Courier", 9), wrap=tk.WORD
        )
        info_text.pack(fill=tk.BOTH, expand=True)

        # Формирование текста
        report = f"""
Aircraft Title:
  {title}

Type: {aircraft_type}
Manufacturer: {manufacturer}
Version: {version}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTOPILOT PROFILE

Profile: {profile_name}
Developer: {profile_dev}
SimConnect Type: {autopilot_type}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMPATIBILITY STATUS

Status: {compat_status}
"""

        if compat_details:
            report += "\nDetails:\n"
            for detail in compat_details:
                if detail:
                    report += f"  • {detail}\n"

        report += "\n" + "━" * 60 + "\n"

        info_text.insert("1.0", report)
        info_text.configure(state="disabled")

        # Цветовая индикация статуса
        status_frame = ttk.Frame(dialog, padding="10")
        status_frame.pack(fill=tk.X)

        ttk.Label(status_frame, text="Compatibility:").pack(side=tk.LEFT, padx=5)
        status_label = ttk.Label(
            status_frame,
            text=compat_status,
            font=("Arial", 11, "bold"),
            foreground=compat_color,
        )
        status_label.pack(side=tk.LEFT, padx=5)

        # Кнопка закрытия
        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="OK", command=dialog.destroy).pack()

        # Центрирование окна
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

    def _update_telemetry_panel(self, data):
        """Обновление панели телеметрии"""
        # Позиция
        self.alt_msl_var.set(f"{data['position'].get('altitude', 0):.0f} ft")
        self.alt_agl_var.set(f"{data['position'].get('altitude_agl', 0):.0f} ft")
        self.radio_height_var.set(f"{data['position'].get('radio_height', 0):.0f} ft")

        # Скорость
        self.ias_var.set(f"{data['speed'].get('airspeed_indicated', 0):.0f} kt")
        self.gs_var.set(f"{data['speed'].get('ground_speed', 0):.0f} kt")
        self.vs_var.set(f"{data['speed'].get('vertical_speed', 0):.0f} fpm")

        # Ориентация
        self.heading_var.set(f"{data['attitude'].get('heading_magnetic', 0):.0f}°")
        self.pitch_var.set(f"{data['attitude'].get('pitch', 0):.1f}°")
        self.bank_var.set(f"{data['attitude'].get('bank', 0):.1f}°")

    def _update_gps_destination_panel(self, data):
        """Обновление панели GPS Destination"""
        gps_dest = data.get("gps_destination", {})

        # Airport
        if gps_dest.get("airport_icao"):
            self.dest_airport_var.set(gps_dest["airport_icao"])
            self.dest_airport_label.config(foreground="green")
        else:
            self.dest_airport_var.set("N/A")
            self.dest_airport_label.config(foreground="gray")

        # Runway
        if gps_dest.get("runway_id"):
            self.dest_runway_var.set(gps_dest["runway_id"])
            self.dest_runway_label.config(foreground="green")
        else:
            self.dest_runway_var.set("N/A")
            self.dest_runway_label.config(foreground="gray")

        # Distance
        distance_nm = gps_dest.get("distance_nm", 0)
        self.dest_distance_var.set(f"{distance_nm:.1f} nm")

    def _update_approach_info_panel(self, data):
        """Обновление панели Approach Info"""
        approach_info = data.get("approach_info", {})
        approach_type = approach_info.get("approach_type", "UNKNOWN")

        # Approach Type
        if approach_type != "UNKNOWN":
            self.approach_type_var.set(approach_type)
            if approach_type == "ILS":
                self.approach_type_label.config(foreground="green")
            elif approach_type == "GPS":
                self.approach_type_label.config(foreground="blue")
            else:
                self.approach_type_label.config(foreground="orange")
        else:
            self.approach_type_var.set("N/A")
            self.approach_type_label.config(foreground="gray")

        # Decision Height
        decision_height = approach_info.get("decision_height")
        if decision_height and decision_height > 0:
            self.approach_dh_var.set(f"{decision_height:.0f} ft")
            if decision_height <= 100:
                self.approach_dh_label.config(foreground="red")  # CAT II
            elif decision_height <= 200:
                self.approach_dh_label.config(foreground="orange")  # CAT I
            else:
                self.approach_dh_label.config(foreground="blue")  # Non-precision
        else:
            self.approach_dh_var.set("N/A")
            self.approach_dh_label.config(foreground="gray")

    def _update_engine_panel(self, data):
        """Обновление панели двигателей"""
        if not hasattr(self, "throttle1_var"):
            return

        engine_data = data.get("engine", {})
        self.throttle1_var.set(f"{engine_data.get('throttle_1', 0):.0f}%")
        self.throttle2_var.set(f"{engine_data.get('throttle_2', 0):.0f}%")
        self.n1_1_var.set(f"{engine_data.get('n1_1', 0):.1f}%")
        self.n1_2_var.set(f"{engine_data.get('n1_2', 0):.1f}%")

        flaps = engine_data.get("flaps_position", 0)
        self.flaps_var.set(f"{flaps:.0f}°")

        gear = engine_data.get("gear_position", 0)
        self.gear_var.set("DOWN" if gear > 0.5 else "UP")

    def _update_aircraft_panel(self, data):
        """Обновление панели информации о самолёте"""
        if not hasattr(self.system, "aircraft_adapter") or not self.system.aircraft_adapter:
            return

        aircraft_info = self.system.get_aircraft_info()

        # Aircraft name
        if aircraft_info and "aircraft" in aircraft_info:
            title = aircraft_info["aircraft"].get("title", "Unknown")
            self.aircraft_name_var.set(title[:30])

        # Profile
        if aircraft_info and "profile" in aircraft_info:
            profile_name = aircraft_info["profile"].get("name", "Standard")
            self.ap_profile_var.set(profile_name)

        # Compatibility
        if aircraft_info and "compatibility" in aircraft_info:
            compat = aircraft_info["compatibility"]
            if compat.get("compatible"):
                if compat.get("limited"):
                    self.compat_status_var.set("Limited (Fallback)")
                    self.compat_status_label.config(foreground="orange")
                else:
                    self.compat_status_var.set("Full Support")
                    self.compat_status_label.config(foreground="green")
            else:
                self.compat_status_var.set("Not Compatible")
                self.compat_status_label.config(foreground="red")

    def _update_autopilot_modes_panel(self, data):
        """Обновление панели режимов автопилота"""
        modes = []

        # Попытка через aircraft_adapter (если WASM доступен)
        if self.system.aircraft_adapter and self.system.aircraft_adapter.wasm:
            ap_status = self.system.aircraft_adapter.get_autopilot_status()
            if ap_status:
                if ap_status.get("autopilot_engaged") or ap_status.get("autopilot_1_engaged"):
                    modes.append("AP")
                if ap_status.get("approach_armed"):
                    modes.append("APP")
                if ap_status.get("nav_armed"):
                    modes.append("NAV")
                if ap_status.get("loc_armed"):
                    modes.append("LOC")
        else:
            # Fallback: чтение через SimConnect напрямую
            try:
                ap_data = data.get("autopilot", {})
                if ap_data.get("master"):
                    modes.append("AP")
                if ap_data.get("approach_hold"):
                    modes.append("APP")
                if ap_data.get("nav_hold"):
                    modes.append("NAV")
                if ap_data.get("heading_hold"):
                    modes.append("HDG")
                if ap_data.get("altitude_hold"):
                    modes.append("ALT")
                if ap_data.get("airspeed_hold"):
                    modes.append("SPD")
            except (KeyError, AttributeError):
                pass

        if modes:
            self.ap_modes_var.set(" | ".join(modes))
        else:
            self.ap_modes_var.set("No modes active")

    def _update_navigation_panel(self, data):
        """Обновление панели навигации"""
        self.dme_var.set(f"{data['nav'].get('nav1_dme_distance', 0):.1f} nm")

        wind_speed = data["weather"].get("ambient_wind_velocity", 0)
        wind_dir = data["weather"].get("ambient_wind_direction", 0)
        self.wind_var.set(f"{wind_speed:.0f} kt from {wind_dir:.0f}°")

    def _update_wind_shear_panel(self):
        """Обновление панели сдвига ветра"""
        wind_shear_alert = self.system.wind_shear_detector.get_current_alert()
        if wind_shear_alert:
            alert_text = f"{wind_shear_alert.severity}: {wind_shear_alert.type} ({wind_shear_alert.magnitude:.1f})"
            self.wind_shear_var.set(alert_text)

            if wind_shear_alert.severity == "CRITICAL":
                self.wind_shear_label.config(foreground="red", font=("Arial", 9, "bold"))
            elif wind_shear_alert.severity == "WARNING":
                self.wind_shear_label.config(foreground="orange", font=("Arial", 9, "bold"))
            else:
                self.wind_shear_label.config(foreground="yellow", font=("Arial", 9))
        else:
            self.wind_shear_var.set("Not detected")
            self.wind_shear_label.config(foreground="green", font=("Arial", 9))

    def _update_turbulence_panel(self):
        """Обновление панели турбулентности"""
        turbulence_alert = self.system.turbulence_detector.get_current_alert()
        if turbulence_alert and turbulence_alert.intensity != "SMOOTH":
            turb_text = f"{turbulence_alert.intensity} {turbulence_alert.type} (G-std: {turbulence_alert.g_force_std:.3f})"
            self.turbulence_var.set(turb_text)

            if turbulence_alert.intensity == "SEVERE":
                self.turbulence_label.config(foreground="red", font=("Arial", 9, "bold"))
            elif turbulence_alert.intensity == "MODERATE":
                self.turbulence_label.config(foreground="orange", font=("Arial", 9, "bold"))
            else:  # LIGHT
                self.turbulence_label.config(foreground="yellow", font=("Arial", 9))
        else:
            self.turbulence_var.set("SMOOTH")
            self.turbulence_label.config(foreground="green", font=("Arial", 9))

    def _update_approach_params_panel(self):
        """Обновление панели параметров скорости захода"""
        if not hasattr(self.system, "approach_params") or not self.system.approach_params:
            self.vref_var.set("---")
            self.vapp_var.set("---")
            self.flaps_config_var.set("--")
            self.weight_var.set("--")
            self.weight_label.config(foreground="gray")
            return

        params = self.system.approach_params

        # Скорости
        self.vref_var.set(f"{params['vref']:.1f} kt")
        self.vapp_var.set(f"{params['vapp']:.1f} kt")

        # Конфигурация закрылков
        flaps_config = (
            params["flaps_configuration"]
            .replace("_", " ")
            .replace("flaps", "F")
            .replace("conf", "C")
        )
        self.flaps_config_var.set(flaps_config.upper())

        # Вес с цветовой индикацией
        weight_kg = params["aircraft_weight_kg"]
        max_weight = params["max_landing_weight_kg"]
        self.weight_var.set(f"{weight_kg:.0f}/{max_weight:.0f} kg")

        if params["weight_ok"]:
            self.weight_label.config(foreground="green")
        else:
            self.weight_label.config(foreground="red")

    def update_gui(self):
        """Обновление GUI - главный цикл обновления"""
        if self.system and self.system.telemetry.connected:
            try:
                # Получить все данные телеметрии один раз
                data = self.system.telemetry.get_all_data()

                # Обновить каждую панель через вспомогательные методы
                self._update_telemetry_panel(data)
                self._update_gps_destination_panel(data)
                self._update_approach_info_panel(data)
                self._update_engine_panel(data)
                self._update_aircraft_panel(data)
                self._update_autopilot_modes_panel(data)
                self._update_navigation_panel(data)
                self._update_wind_shear_panel()
                self._update_turbulence_panel()
                self._update_approach_params_panel()

                # Обновление фазы
                if self.system.phase:
                    self.phase_label.config(text=self.system.phase.value)

                # Обновление специальных панелей
                if hasattr(self.system, "connection_monitor") and self.system.connection_monitor:
                    self.update_connection_monitor_panel()

                if hasattr(self.system, "virtual_joystick") and self.system.virtual_joystick:
                    self.update_vjoy_monitor_panel()

            except Exception as e:
                logging.error("GUI update error: %s", e)

        # Повторное обновление через 500мс
        self.root.after(500, self.update_gui)

    def update_connection_monitor_panel(self):
        """Обновление панели мониторинга подключения"""
        try:
            monitor_status = self.system.get_connection_monitor_status()

            if "error" in monitor_status:
                return

            # Обновление текущего статуса
            self.monitor_method_var.set(monitor_status.get("current_method", "N/A"))
            self.monitor_phase_var.set(monitor_status.get("flight_phase", "N/A"))
            self.monitor_aircraft_var.set(monitor_status.get("aircraft", "N/A"))
            self.monitor_switches_var.set(str(monitor_status.get("total_switches", 0)))

            # Обновление метрик
            metrics = monitor_status.get("metrics", {})
            for method, method_metrics in metrics.items():
                if method in self.monitor_metrics_vars:
                    vars_dict = self.monitor_metrics_vars[method]

                    # Статус
                    if method_metrics.get("available"):
                        if method_metrics.get("is_degraded"):
                            vars_dict["status"].set("⚠️")
                        else:
                            vars_dict["status"].set("✅")
                    else:
                        vars_dict["status"].set("❌")

                    # Операции
                    vars_dict["operations"].set(
                        str(method_metrics.get("total_operations", 0))
                    )

                    # Времена
                    vars_dict["read_ms"].set(
                        f"{method_metrics.get('avg_read_ms', 0):.2f}"
                    )
                    vars_dict["write_ms"].set(
                        f"{method_metrics.get('avg_write_ms', 0):.2f}"
                    )

                    # Надёжность
                    reliability = method_metrics.get("reliability", 0) * 100
                    vars_dict["reliability"].set(f"{reliability:.1f}%")

                    # Балл
                    score = method_metrics.get("score", 0)
                    vars_dict["score"].set(f"{score:.1f}")

            # Обновление истории переключений
            history = monitor_status.get("switch_history", [])
            if history:
                self.monitor_history_text.configure(state="normal")
                self.monitor_history_text.delete("1.0", tk.END)

                for event in reversed(history):  # Новые сверху
                    timestamp = time.strftime(
                        "%H:%M:%S", time.localtime(event["timestamp"])
                    )
                    line = (
                        f"{timestamp}: {event['from_method']} -> {event['to_method']}\n"
                        f"  Reason: {event['reason']}\n"
                        f"  Scores: {event['from_score']:.1f} -> {event['to_score']:.1f}\n"
                        f"  Phase: {event['flight_phase']}\n\n"
                    )
                    self.monitor_history_text.insert(tk.END, line)

                self.monitor_history_text.configure(state="disabled")

        except Exception as e:
            logging.error(f"Connection monitor panel update error: {e}")

    def export_monitor_json(self):
        """Экспорт метрик мониторинга в JSON"""
        if not self.system or not self.system.connection_monitor:
            messagebox.showwarning("Warning", "Connection monitor not available")
            return

        try:
            from tkinter import filedialog

            filepath = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile="connection_metrics.json",
            )

            if filepath:
                self.system.connection_monitor.export_metrics_json(filepath)
                messagebox.showinfo("Success", f"Metrics exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export metrics:\n{e}")

    def export_monitor_csv(self):
        """Экспорт метрик мониторинга в CSV"""
        if not self.system or not self.system.connection_monitor:
            messagebox.showwarning("Warning", "Connection monitor not available")
            return

        try:
            from tkinter import filedialog

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="connection_metrics.csv",
            )

            if filepath:
                self.system.connection_monitor.export_metrics_csv(filepath)
                messagebox.showinfo("Success", f"Metrics exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export metrics:\n{e}")

    def force_connection_test(self):
        """Принудительное тестирование всех методов"""
        if not self.system or not self.system.connection_monitor:
            messagebox.showwarning("Warning", "Connection monitor not available")
            return

        try:
            # Запуск теста в отдельном потоке чтобы не блокировать GUI
            def run_test():
                scores = self.system.connection_monitor.perform_active_test()
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Test Complete",
                        "Connection test completed:\n\n"
                        + "\n".join(
                            [
                                f"{method}: {score:.1f}"
                                for method, score in scores.items()
                            ]
                        ),
                    ),
                )

            threading.Thread(target=run_test, daemon=True).start()
            messagebox.showinfo(
                "Testing", "Running connection test...\nThis may take a few seconds."
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to run test:\n{e}")

    def update_vjoy_monitor_panel(self):
        """Обновление панели мониторинга vJoy"""
        try:
            vjoy_status = self.system.virtual_joystick.get_status()

            # Обновление статуса
            if vjoy_status["enabled"]:
                self.vjoy_status_var.set("Connected")
                self.vjoy_status_label.config(foreground="green")
            else:
                self.vjoy_status_var.set("Disconnected")
                self.vjoy_status_label.config(foreground="red")

            self.vjoy_device_var.set(str(vjoy_status["device_id"]))
            self.vjoy_total_commands_var.set(str(vjoy_status["total_commands"]))

            # Обновление значений осей
            current_values = vjoy_status["current_values"]
            command_count = vjoy_status["command_count"]

            for axis_name, value in current_values.items():
                if axis_name in self.vjoy_axis_vars:
                    # Обновление текстового значения
                    self.vjoy_axis_vars[axis_name].set(f"{value:+.2f}")

                    # Обновление счётчика команд
                    count = command_count.get(axis_name, 0)
                    self.vjoy_command_count_vars[axis_name].set(f"({count} commands)")

                    # Обновление визуального бара
                    canvas = self.vjoy_axis_bars[axis_name]
                    self._draw_axis_bar(canvas, value)

        except Exception as e:
            logging.error(f"vJoy monitor panel update error: {e}")

    def _draw_axis_bar(self, canvas, value):
        """
        Рисование визуального индикатора оси

        Args:
            canvas: Canvas для рисования
            value: Значение от -1.0 до +1.0
        """
        try:
            canvas.delete("all")
            width = canvas.winfo_width()
            height = canvas.winfo_height()

            if width <= 1:  # Canvas ещё не отрисован
                return

            # Центр
            center_x = width / 2

            # Рисуем центральную линию
            canvas.create_line(center_x, 0, center_x, height, fill="gray", width=2)

            # Рисуем бар от центра
            bar_width = abs(value) * (width / 2)

            if value >= 0:
                # Вправо/вверх (зелёный)
                x1 = center_x
                x2 = center_x + bar_width
                color = "green"
            else:
                # Влево/вниз (красный)
                x1 = center_x - bar_width
                x2 = center_x
                color = "red"

            # Рисуем прямоугольник
            canvas.create_rectangle(x1, 5, x2, height - 5, fill=color, outline="")

            # Рисуем индикатор текущей позиции
            indicator_x = center_x + (value * (width / 2))
            canvas.create_line(
                indicator_x, 0, indicator_x, height, fill="blue", width=3
            )

        except Exception as e:
            logging.error(f"Error drawing axis bar: {e}")

    def vjoy_center_axes(self):
        """Центрировать все оси vJoy"""
        if not self.system or not self.system.virtual_joystick:
            messagebox.showwarning("Warning", "vJoy not available")
            return

        try:
            self.system.virtual_joystick.center_all_axes()
            messagebox.showinfo("Success", "All axes centered")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to center axes:\n{e}")

    def vjoy_test_aileron(self):
        """Тест оси элеронов"""
        if not self.system or not self.system.virtual_joystick:
            messagebox.showwarning("Warning", "vJoy not available")
            return

        try:

            def test():
                vjoy = self.system.virtual_joystick
                # Влево
                vjoy.set_aileron(-0.5)
                time.sleep(0.5)
                # Центр
                vjoy.set_aileron(0.0)
                time.sleep(0.5)
                # Вправо
                vjoy.set_aileron(0.5)
                time.sleep(0.5)
                # Центр
                vjoy.set_aileron(0.0)

            threading.Thread(target=test, daemon=True).start()
            messagebox.showinfo(
                "Testing", "Testing aileron: Left → Center → Right → Center"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to test aileron:\n{e}")

    def vjoy_test_elevator(self):
        """Тест оси руля высоты"""
        if not self.system or not self.system.virtual_joystick:
            messagebox.showwarning("Warning", "vJoy not available")
            return

        try:

            def test():
                vjoy = self.system.virtual_joystick
                # Вниз
                vjoy.set_elevator(-0.5)
                time.sleep(0.5)
                # Центр
                vjoy.set_elevator(0.0)
                time.sleep(0.5)
                # Вверх
                vjoy.set_elevator(0.5)
                time.sleep(0.5)
                # Центр
                vjoy.set_elevator(0.0)

            threading.Thread(target=test, daemon=True).start()
            messagebox.showinfo(
                "Testing", "Testing elevator: Down → Center → Up → Center"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to test elevator:\n{e}")

    def vjoy_test_rudder(self):
        """Тест оси руля направления"""
        if not self.system or not self.system.virtual_joystick:
            messagebox.showwarning("Warning", "vJoy not available")
            return

        try:

            def test():
                vjoy = self.system.virtual_joystick
                # Влево
                vjoy.set_rudder(-0.5)
                time.sleep(0.5)
                # Центр
                vjoy.set_rudder(0.0)
                time.sleep(0.5)
                # Вправо
                vjoy.set_rudder(0.5)
                time.sleep(0.5)
                # Центр
                vjoy.set_rudder(0.0)

            threading.Thread(target=test, daemon=True).start()
            messagebox.showinfo(
                "Testing", "Testing rudder: Left → Center → Right → Center"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to test rudder:\n{e}")


def main():
    """Запуск GUI"""
    root = tk.Tk()

    # Стиль для кнопки Go-Around
    style = ttk.Style()
    style.configure("Danger.TButton", foreground="red")

    AutoLandGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
