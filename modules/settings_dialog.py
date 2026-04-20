"""
Диалог настроек приложения
"""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from modules.settings import get_settings

logger = logging.getLogger(__name__)


class SettingsDialog:
    """Диалог настроек приложения"""

    def __init__(self, parent):
        self.parent = parent
        self.settings = get_settings()

        # Создание окна
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Создание виджетов диалога"""

        # Notebook для вкладок
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладка Navigraph
        self.navigraph_frame = ttk.Frame(notebook)
        notebook.add(self.navigraph_frame, text="Navigraph")
        self.create_navigraph_tab()

        # Вкладка GUI
        self.gui_frame = ttk.Frame(notebook)
        notebook.add(self.gui_frame, text="GUI")
        self.create_gui_tab()

        # Кнопки
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Save", command=self.on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.RIGHT)

    def create_navigraph_tab(self):
        """Вкладка настроек Navigraph"""
        row = 0

        # Заголовок
        ttk.Label(self.navigraph_frame, text="Navigraph Database Settings",
                 font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=3, pady=10)
        row += 1

        # Путь к базе данных
        ttk.Label(self.navigraph_frame, text="Database Path:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)

        self.db_path_var = tk.StringVar()
        current_path = self.settings.get_navigraph_db_path()
        if current_path:
            self.db_path_var.set(str(current_path))
        else:
            # Показываем путь по умолчанию
            from modules.navigraph_parser import NavigraphParser
            self.db_path_var.set(str(NavigraphParser.DEFAULT_DB_PATH))

        path_entry = ttk.Entry(self.navigraph_frame, textvariable=self.db_path_var, width=50)
        path_entry.grid(row=row, column=1, padx=5, pady=5)

        ttk.Button(self.navigraph_frame, text="Browse...",
                  command=self.browse_db_path).grid(row=row, column=2, padx=5)
        row += 1

        # Подсказка
        hint_text = ("Leave empty to use default path:\n"
                    "%APPDATA%\\ABarthel\\little_navmap_db\\little_navmap_navigraph.sqlite")
        ttk.Label(self.navigraph_frame, text=hint_text, font=('Arial', 8),
                 foreground='gray', justify=tk.LEFT).grid(row=row, column=0, columnspan=3,
                                                          sticky=tk.W, padx=5, pady=5)
        row += 1

        # Разделитель
        ttk.Separator(self.navigraph_frame, orient='horizontal').grid(row=row, column=0,
                                                                       columnspan=3, sticky='ew', pady=10)
        row += 1

        # Кэширование
        ttk.Label(self.navigraph_frame, text="Cache Settings",
                 font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=3, pady=10)
        row += 1

        self.cache_enabled_var = tk.BooleanVar(value=self.settings.get('navigraph.cache_enabled', False))
        ttk.Checkbutton(self.navigraph_frame, text="Enable query caching",
                       variable=self.cache_enabled_var).grid(row=row, column=0, columnspan=2,
                                                             sticky=tk.W, padx=5, pady=5)
        row += 1

        ttk.Label(self.navigraph_frame, text="Cache TTL (seconds):").grid(row=row, column=0,
                                                                          sticky=tk.W, padx=5, pady=5)
        self.cache_ttl_var = tk.StringVar(value=str(self.settings.get('navigraph.cache_ttl_seconds', 3600)))
        ttk.Entry(self.navigraph_frame, textvariable=self.cache_ttl_var, width=10).grid(row=row, column=1,
                                                                                         sticky=tk.W, padx=5, pady=5)
        row += 1

        # Кнопка тестирования подключения
        ttk.Button(self.navigraph_frame, text="Test Connection",
                  command=self.test_connection).grid(row=row, column=0, columnspan=3, pady=20)

    def create_gui_tab(self):
        """Вкладка настроек GUI"""
        row = 0

        ttk.Label(self.gui_frame, text="GUI Settings",
                 font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, pady=10)
        row += 1

        # Размеры окна
        ttk.Label(self.gui_frame, text="Window Width:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.window_width_var = tk.StringVar(value=str(self.settings.get('gui.window_width', 1200)))
        ttk.Entry(self.gui_frame, textvariable=self.window_width_var, width=10).grid(row=row, column=1,
                                                                                      sticky=tk.W, padx=5, pady=5)
        row += 1

        ttk.Label(self.gui_frame, text="Window Height:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.window_height_var = tk.StringVar(value=str(self.settings.get('gui.window_height', 800)))
        ttk.Entry(self.gui_frame, textvariable=self.window_height_var, width=10).grid(row=row, column=1,
                                                                                       sticky=tk.W, padx=5, pady=5)

    def browse_db_path(self):
        """Выбор файла базы данных"""
        filename = filedialog.askopenfilename(
            title="Select Navigraph Database",
            filetypes=[("SQLite Database", "*.sqlite"), ("All Files", "*.*")]
        )
        if filename:
            self.db_path_var.set(filename)

    def test_connection(self):
        """Тестирование подключения к базе данных"""
        db_path = self.db_path_var.get().strip()

        try:
            from modules.navigraph_parser import NavigraphParser

            # Если путь пустой, используем путь по умолчанию
            parser = NavigraphParser(Path(db_path) if db_path else None)

            success, message = parser.test_connection()

            if success:
                messagebox.showinfo("Connection Test", f"✅ {message}")
            else:
                messagebox.showerror("Connection Test", f"❌ {message}")

        except Exception as e:
            messagebox.showerror("Connection Test", f"Error: {e}")

    def on_save(self):
        """Сохранение настроек"""
        try:
            # Navigraph settings
            db_path = self.db_path_var.get().strip()

            # Если путь совпадает с путём по умолчанию, сохраняем None
            from modules.navigraph_parser import NavigraphParser
            if db_path == str(NavigraphParser.DEFAULT_DB_PATH):
                db_path = None

            self.settings.set('navigraph.database_path', db_path if db_path else None)
            self.settings.set('navigraph.cache_enabled', self.cache_enabled_var.get())

            try:
                cache_ttl = int(self.cache_ttl_var.get())
                self.settings.set('navigraph.cache_ttl_seconds', cache_ttl)
            except ValueError:
                messagebox.showerror("Error", "Cache TTL must be a number")
                return

            # GUI settings
            try:
                window_width = int(self.window_width_var.get())
                window_height = int(self.window_height_var.get())
                self.settings.set('gui.window_width', window_width)
                self.settings.set('gui.window_height', window_height)
            except ValueError:
                messagebox.showerror("Error", "Window dimensions must be numbers")
                return

            # Сохранение в файл
            self.settings.save()

            messagebox.showinfo("Success", "Settings saved successfully")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            logger.error(f"Error saving settings: {e}")

    def on_cancel(self):
        """Отмена"""
        self.dialog.destroy()
