import os
import sys
import threading
import customtkinter as ctk
import pystray
import pkg_resources
import winreg
import psutil
import requests
from PIL import Image
from .site import BlockManagerServer

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class ServerManager(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.server = None
        self.tray_icon = None
        self.tray_thread = None
        self.server_process = None
        self.server_running = False  # Добавлено для контроля состояния сервера
        
        # Static
        self.static_folder = pkg_resources.resource_filename(__name__, 'static')
        self.APP_NAME = "BMServer"
        
        # Основные настройки окна
        self.title("BMServer")
        self.geometry("400x250")
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.resizable(False, False)
        self.iconbitmap(f'{self.static_folder}/icon/favicon.ico')
        
        self.create_widgets()
        
        # Проверка автозагрузки
        self.check_autostart_status()
        
        # Инициализация трея
        self.init_tray_icon()
        
        # Запуск сервера при старте
        self.start_server()
        
        # Сворачиваем в трей
        self.minimize_to_tray()
        
    def start_server(self):
        def run():
            try:
                # Создаем полный путь к файлу настроек
                settings_path = os.path.join(os.path.dirname(__file__), 'static', 'setting.json')
                if not os.path.exists(settings_path):
                    # Создаем директорию, если ее нет
                    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
                    # Создаем пустой файл настроек
                    with open(settings_path, 'w') as f:
                        f.write('{}')
                
                self.server = BlockManagerServer()
                self.server_thread = threading.Thread(
                    target=self.server.start,
                    kwargs={'debug': False, 'use_reloader': False}
                )
                self.server_thread.daemon = True
                self.server_thread.start()
                self.server_process = psutil.Process()
                self.server_running = True
                self.update_status()
            except Exception as e:
                print(f"Server start error: {e}")
                self.server_running = False
                self.update_status()

        threading.Thread(target=run, daemon=True).start()

    def stop_server(self):
        try:
            if self.server_process:
                # Убиваем весь процесс и дочерние элементы
                parent = psutil.Process(self.server_process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                
                # Дополнительная проверка через requests
                try:
                    requests.get("http://localhost:8083", timeout=1)
                except:
                    pass
                
                self.server_running = False
                self.update_status()
        except Exception as e:
            print(f"Stop server error: {e}")
        finally:
            self.server_running = False
            self.update_status()

    def create_widgets(self):
        # Основная рамка
        frame = ctk.CTkFrame(self, corner_radius=10)
        frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        # Статус сервера
        self.status_label = ctk.CTkLabel(frame, text="Статус сервера: Проверка...", font=("Arial", 14))
        self.status_label.pack(pady=10)
        
        # Автозагрузка
        self.autostart_var = ctk.BooleanVar(value=False)
        self.autostart_check = ctk.CTkCheckBox(
            frame, 
            text="Запускать при старте системы", 
            variable=self.autostart_var,
            command=self.toggle_autostart
        )
        self.autostart_check.pack(pady=10)

    def toggle_autostart(self):
        key = winreg.HKEY_LOCAL_MACHINE  # Изменено на CURRENT_USER для работы без админских прав
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        try:
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_ALL_ACCESS) as registry_key:
                if self.autostart_var.get():
                    winreg.SetValueEx(
                        registry_key,
                        self.APP_NAME,
                        0,
                        winreg.REG_SZ,
                        f'"{sys.executable}"'  # Добавлены кавычки для путей с пробелами
                    )
                else:
                    try:
                        winreg.DeleteValue(registry_key, self.APP_NAME)
                    except FileNotFoundError:
                        pass
        except Exception as e:
            print(f"Autostart error: {e}")
            ctk.CTkMessageBox(title="Ошибка", message=f"Не удалось изменить настройки автозагрузки: {e}")
            self.autostart_var.set(not self.autostart_var.get())

    def check_autostart_status(self):
        try:
            key = winreg.HKEY_LOCAL_MACHINE  # Изменено на CURRENT_USER
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, key_path) as registry_key:
                try:
                    winreg.QueryValueEx(registry_key, self.APP_NAME)
                    self.autostart_var.set(True)
                except FileNotFoundError:
                    self.autostart_var.set(False)
        except Exception as e:
            print(f"Check autostart error: {e}")
            self.autostart_var.set(False)
            
    def init_tray_icon(self):
        # Иконка для трея
        menu = (
            pystray.MenuItem("Открыть", self.restore_from_tray),
            pystray.MenuItem("Выход", self.quit_app)
        )
        
        try:
            image = Image.open(f"{self.static_folder}/icon/favicon.ico")
            self.tray_icon = pystray.Icon("server_manager", image, "Server Manager", menu)
        except Exception as e:
            print(f"Tray icon error: {e}")
            # Создаем простую иконку, если файл не найден
            image = Image.new('RGB', (16, 16), color='red')
            self.tray_icon = pystray.Icon("server_manager", image, "Server Manager", menu)

    def run_tray_icon(self):
        """Запускает иконку в трее в отдельном потоке"""
        try:
            if self.tray_icon:
                self.tray_icon.run()
        except Exception as e:
            print(f"Tray run error: {e}")

    def minimize_to_tray(self):
        """Сворачивает окно в трей"""
        self.withdraw()
        if not hasattr(self, 'tray_thread') or self.tray_thread is None or not self.tray_thread.is_alive():
            self.tray_thread = threading.Thread(target=self.run_tray_icon, daemon=True)
            self.tray_thread.start()

    def restore_from_tray(self, icon=None, item=None):
        """Восстанавливает окно из трея"""
        self.deiconify()
        self.lift()
        self.focus_force()

    def update_status(self):
        """Обновляет статус сервера в интерфейсе"""
        if self.server_running:
            self.status_label.configure(text="Статус сервера: Активен", text_color="green")
        else:
            self.status_label.configure(text="Статус сервера: Остановлен", text_color="red")

    def quit_app(self, icon=None, item=None):
        """Полностью закрывает приложение"""
        self.stop_server()
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()
        os._exit(0)