from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import os, json, sys, re
from datetime import datetime


class BlockManagerServer:
    def __init__(self):
        # self.static_folder = os.path.abspath("static")
        # self.template_dir = os.path.abspath(f'templates')
        self.static_folder = os.path.abspath(f"{os.path.dirname(sys.executable)}/static")
        self.template_dir = os.path.abspath(f'{os.path.dirname(sys.executable)}/templates')
        
        # Загружаем настройки до инициализации Flask
        self.setting = self._load_setting()
        
        # Генерируем секретный ключ при первом запуске
        if 'secret_key' not in self.setting:
            self.setting['secret_key'] = os.urandom(24).hex()
            self._save_settings()
        
        # Инициализируем Flask с секретным ключом
        self.app = Flask(__name__, 
                       template_folder=self.template_dir,
                       static_folder=self.static_folder)
        self.app.secret_key = self.setting['secret_key']
        
        # Остальная инициализация...
        self.users = self._load_users()
        self.access = {
            '0': 'Создатель',
            '1': 'Администратор',
            '2': 'Пользователь',
            '3': 'Менеджер'
        }

        if not os.path.exists(f'{self.static_folder}/guide.json'):
            # Создаем директорию если не существует
            os.makedirs(self.static_folder, exist_ok=True)
            
            data = {
                "app_list": []
            }
            
            # Правильный порядок аргументов: (data, file)
            with open(f'{self.static_folder}/guide.json', 'w', encoding='UTF-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        self._register_routes()

    def _load_setting(self):
        setting_file = os.path.join(self.static_folder, 'setting.json')
        settings = {}
        if os.path.exists(setting_file):
            try:
                with open(setting_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            except:
                pass
        return settings

    def _save_settings(self):
        setting_file = os.path.join(self.static_folder, 'setting.json')
        with open(setting_file, 'w', encoding='utf-8') as f:
            json.dump(self.setting, f, indent=4, ensure_ascii=False)
    
    def _load_users(self):
        user_file = f'{self.static_folder}/user.json'
        if os.path.exists(user_file) and os.path.getsize(user_file) > 0:
            with open(user_file, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _register_routes(self):
        # Основные переходы
        self.app.add_url_rule('/', 'index', self.index)
        self.app.add_url_rule('/login', 'login', self.login, methods=['GET', 'POST'])
        self.app.add_url_rule('/logout', 'logout', self.logout)
        self.app.add_url_rule('/dashboard', 'dashboard', self.dashboard)
        
        # Найстройки
        self.app.add_url_rule('/change_theme', 'change_theme', self.change_theme, methods=['POST'])
        
        # Клиентские
        self.app.add_url_rule('/get_json_list', 'get_json_list', self.get_json_list)
        self.app.add_url_rule('/get_json_file', 'get_json_file', self.get_json_file)
        
        # Выполнение действий
        self.app.add_url_rule('/add_program', 'add_program', self.add_program, methods=['POST'])
        self.app.add_url_rule('/add_json', 'add_json', self.add_json, methods=['POST'])
        self.app.add_url_rule('/add_user', 'add_user', self.add_user, methods=['POST'])
        self.app.add_url_rule('/delete_program', 'delete_program', self.delete_program, methods=['POST'])
        self.app.add_url_rule('/delete_json', 'delete_json', self.delete_json, methods=['POST'])
        self.app.add_url_rule('/delete_user', 'delete_user', self.delete_user, methods=['POST'])

    def _check_auth(self):
        return ('username' in session) and (session['username'] in self.users)
    
    def _check_access(self, required_level):
        """Проверяет, имеет ли текущий пользователь достаточный уровень доступа"""
        if not self._check_auth():
            return False
        user_access = self.users.get(session['username'], {}).get('access', '3')
        return int(user_access) <= int(required_level)
    
    def index(self):
        if self._check_auth():
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    
    def _save_users(self):
        with open(f'{self.static_folder}/user.json', 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=4)

    def login(self):
        self.setting = self._load_setting()
        username = session.get('username')
        # Получаем тему в порядке приоритета: куки → настройки пользователя → настройки сервера → темная
        theme = request.cookies.get('theme') or \
                self.users.get(username, {}).get('theme') or \
                self.setting.get('theme', 'dark')
        self.users = self._load_users()
        if self._check_auth():
            return redirect(url_for('dashboard'))
        
        # Если нет пользователей, создаем первый аккаунт
        if not self.users:
            if request.method == 'POST':
                username = request.form.get('login')
                password = request.form.get('pass')
                
                if not username or not password:
                    return render_template('login.html', 
                                        title='Создание первого аккаунта', 
                                        error='Логин и пароль обязательны',
                                        first_account=True, 
                                        current_theme=theme)
                
                # Создаем первого пользователя (администратора)
                self.users[username] = {'password': password, 'access': '0'}
                self._save_users()
                
                session['username'] = username
                return redirect(url_for('dashboard'))

            return render_template('login.html', 
                                title='Создание первого аккаунта', 
                                message='Создайте первый аккаунт администратора',
                                first_account=True, 
                                current_theme=theme)
        
        # Обычный вход для существующих пользователей
        if request.method == 'POST':
            username = request.form.get('login')
            password = request.form.get('pass')
            
            if username in self.users and self.users[username]['password'] == password:
                session['username'] = username
                return redirect(url_for('dashboard'))
            return render_template('login.html', 
                                title='Вход', 
                                error='Неверный логин или пароль',
                                first_account=False,
                                current_theme=theme)
        
        return render_template('login.html', title='Вход', current_theme=theme)
        
    def get_files_with_content(self, directory):
        result = {"files": []}
        
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith('.json'):
                    filepath = os.path.join(root, filename)
                    file_info = {
                        "filename": filename,
                        "path": os.path.relpath(filepath, directory),  # относительный путь
                        "content": None,
                        "error": None
                    }
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            file_info["content"] = json.load(f)
                    except json.JSONDecodeError as e:
                        file_info["error"] = f"Invalid JSON: {str(e)}"
                    except Exception as e:
                        file_info["error"] = f"Error reading file: {str(e)}"
                    
                    result["files"].append(file_info)
        
        return result

    def dashboard(self):
        username = session.get('username')
        # Получаем тему в порядке приоритета: куки → настройки пользователя → настройки сервера → темная
        theme = request.cookies.get('theme') or \
                self.users.get(username, {}).get('theme') or \
                self.setting.get('theme', 'dark')
        self.setting = self._load_setting()
        self.users = self._load_users()
        if not self._check_auth():
            return redirect(url_for('login'))
        
        files = self.get_files_with_content(f"{self.static_folder}\\json_dir")
        menu_data = {}
        guid_data = {}
        page = request.args.get('p', 'list')
        json_file = request.args.get('json', '')

        if os.path.exists(f"{self.static_folder}\\menu_data.json"):
            with open(f"{self.static_folder}\\menu_data.json", 'r', encoding='UTF-8') as file:
                menu_data = json.load(file)
        else:
            menu_data = [
                {
                    "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' class='lucide lucide-list '><line x1='8' x2='21' y1='6' y2='6'></line><line x1='8' x2='21' y1='12' y2='12'></line><line x1='8' x2='21' y1='18' y2='18'></line><line x1='3' x2='3.01' y1='6' y2='6'></line><line x1='3' x2='3.01' y1='12' y2='12'></line><line x1='3' x2='3.01' y1='18' y2='18'></line></svg>",
                    "name": "Списки",
                    "page": "list",
                    "url": "/dashboard?p=list"
                },
                {
                    "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' class='lucide lucide-list '><path d='M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2'></path><circle cx='12' cy='7' r='4'></circle></svg>",
                    "name": "Пользователи",
                    "page": "users",
                    "url": "/dashboard?p=users"
                },
                {
                    "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' class='lucide lucide-file-text '><path d='M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z'></path><path d='M14 2v4a2 2 0 0 0 2 2h4'></path><path d='M10 9H8'></path><path d='M16 13H8'></path><path d='M16 17H8'></path></svg>",
                    "name": "Справочник",
                    "page": "guide",
                    "url": "/dashboard?p=guide"
                },
                {
                    "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' class='lucide lucide-settings '><path d='M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z'></path><circle cx='12' cy='12' r='3'></circle></svg>",
                    "name": "Найстройки",
                    "page": "setting",
                    "url": "/dashboard?p=setting"
                }
            ]

        if os.path.exists(f"{self.static_folder}/guide.json"):
            try:
                with open(f"{self.static_folder}/guide.json", 'r', encoding='UTF-8') as file:
                    if os.path.getsize(f"{self.static_folder}/guide.json") > 0:
                        guid_data = json.load(file)
                    else:
                        guid_data = {}
            except (json.JSONDecodeError, IOError):
                guid_data = {}
        else:
            guid_data = {}

        if page in ['users'] and not self._check_access(1):
            page = 'list'

        # Получаем уровень доступа пользователя
        user_access = self.users.get(session['username'], {}).get('access', '3')
        
        return render_template('dashboard.html', 
                            title='Панель управления',
                            menu_data=menu_data,
                            files=files,
                            page=page,
                            json_file=json_file,
                            guid_data=guid_data,
                            users=self.users,
                            access_list=self.access,
                            setting=self.setting,
                            current_theme=theme,
                            username=session.get('username'),
                            user_access=self.access.get(user_access, 'Менеджер'))
    
    def change_theme(self):
        if not self._check_auth():
            return jsonify({"success": False, "error": "Доступ запрещен"}), 403
            
        try:
            data = request.get_json()
            theme = data.get('theme')
            username = session.get('username')
            
            if theme not in ['light', 'dark']:
                return jsonify({"success": False, "error": "Некорректная тема"}), 400
                
            # Обновляем тему в файле пользователя
            users_path = os.path.join(self.static_folder, 'user.json')
            if os.path.exists(users_path):
                with open(users_path, 'r+', encoding='utf-8') as f:
                    users = json.load(f)
                    if username in users:
                        users[username]['theme'] = theme
                        f.seek(0)
                        json.dump(users, f, ensure_ascii=False, indent=4)
                        f.truncate()
            
            response = jsonify({"success": True, "theme": theme})
            response.set_cookie('theme', theme, max_age=31536000)

            users_path = os.path.abspath(os.path.join(self.static_folder, 'user.json'))
            return response
            
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
        
    def add_json(self):
        if not self._check_access(2):
            return jsonify({"success": False, "error": "У вас недостаточно прав для выполнения этой операции"}), 403
        
        try:
            # Получаем данные из запроса
            data = request.get_json()
            json_filename = data.get('json')
            
            if not json_filename:
                return jsonify({"success": False, "error": "Не указано имя файла"}), 400
            
            # Проверяем расширение .json
            if not json_filename.endswith('.json'):
                json_filename += '.json'
            
            # Проверяем валидность имени файла
            if not re.match(r'^[a-zA-Z0-9_\-]+\.json$', json_filename):
                return jsonify({"success": False, "error": "Некорректное имя файла"}), 400
            
            # Путь к директории с JSON-файлами
            json_dir = os.path.join(self.static_folder, "json_dir")
            os.makedirs(json_dir, exist_ok=True)  # Создаем директорию если ее нет
            
            filepath = os.path.join(json_dir, json_filename)
            
            # Проверяем, не существует ли уже файл
            if os.path.exists(filepath):
                return jsonify({"success": False, "error": "Файл уже существует"}), 400
            
            # Создаем начальную структуру JSON
            initial_data = {
                "app_list": [],
                "metadata": {
                    "created_by": session.get('username', 'unknown'),
                    "created_at": datetime.now().isoformat()
                }
            }
            
            # Записываем файл
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                "success": True,
                "message": "Файл успешно создан",
                "filename": json_filename
            })
            
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка сервера: {str(e)}"}), 500
        
    def add_user(self):
        if not self._check_access(1):  # Только администратор
            return jsonify({"success": False, "error": "У вас недостаточно прав для выполнения этой операции"}), 403
        
        try:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            access = data.get('access', '3')  # По умолчанию уровень 3
            
            # Проверка обязательных полей
            if not username or not password:
                return jsonify({"success": False, "error": "Логин и пароль обязательны"}), 400
            
            # Проверка валидности уровня доступа
            if access not in {'1', '2', '3'}:
                return jsonify({"success": False, "error": "Некорректный уровень доступа"}), 400
            
            if access in {'0', '1'} and not self._check_access(0):
                return jsonify({"success": False, "error": "У вас недостаточно прав для выполнения этой операции"}), 403

            # Загрузка существующих пользователей
            user_file = os.path.join(self.static_folder, 'user.json')
            users = {}
            
            if os.path.exists(user_file):
                with open(user_file, 'r', encoding='utf-8') as f:
                    users = json.load(f)
            
            # Проверка существующего пользователя
            if username in users:
                return jsonify({"success": False, "error": "Пользователь уже существует"}), 400
            
            # Добавление нового пользователя
            users[username] = {
                "password": password,  # В реальном приложении нужно хешировать!
                "access": access
            }
            
            # Сохранение в файл
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                "success": True,
                "message": "Пользователь успешно добавлен",
                "username": username
            })
            
        except json.JSONDecodeError:
            return jsonify({"success": False, "error": "Ошибка чтения файла пользователей"}), 500
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка сервера: {str(e)}"}), 500
        
    def add_program(self):
        if not self._check_access(2):
            return jsonify({"success": False, "error": "У вас недостаточно прав для выполнения этой операции"}), 403
            
        try:
            try:
                data2 = request.get_json()
            except:
                data2 = ''
            if data2:
                json_filename = data2['json']
                program_name = data2['program_name']
            else:
                json_filename = request.form.get('json')
                program_name = request.form.get('program_name')

            if not json_filename:
                return jsonify({"success": False, "error": "Не указан файл JSON"}), 400
                
            # Безопасная проверка имени файла
            if not json_filename.endswith('.json') or '/' in json_filename or '\\' in json_filename:
                return jsonify({"success": False, "error": "Некорректное имя файла"}), 400
            
            # Путь к директории с JSON-файлами
            json_dir = os.path.join(self.static_folder)

            # Проверяем существование файла (рекурсивно во всех подпапках)
            filepath = None
            for root, dirs, files in os.walk(json_dir):
                if json_filename in files:
                    filepath = os.path.join(root, json_filename)
                    break
            
            if not os.path.exists(filepath):
                return jsonify({"success": False, "error": "Файл не найден"}), 404
            
            with open(filepath, 'r+', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    
                    # Проверяем наличие app_list
                    if 'app_list' not in data:
                        data['app_list'] = []

                    # Разделяем имена программ по запятым
                    if isinstance(program_name, str):
                        program_names = [name.strip() for name in program_name.split(',') if name.strip()]
                    else:
                        program_names = [program_name] if program_name else []

                    if not program_names:
                        return jsonify({"success": False, "error": "Нет программ для добавления"}), 400

                    # Получаем список существующих программ (в нижнем регистре для сравнения)
                    existing_programs = {p['name'].lower() for p in data['app_list']}
                    
                    # Добавляем только новые программы
                    added_programs = []
                    duplicates = []
                    
                    for name in program_names:
                        if name.lower() not in existing_programs:
                            data['app_list'].append({"name": name})
                            existing_programs.add(name.lower())
                            added_programs.append(name)
                        else:
                            duplicates.append(name)

                    if not added_programs:
                        return jsonify({
                            "success": False, 
                            "error": "Все программы уже существуют",
                            "duplicates": duplicates
                        }), 400
                    
                    # Перезаписываем файл
                    f.seek(0)
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.truncate()
                    
                    response = {
                        "success": True,
                        "added": len(added_programs),
                        "programs": added_programs
                    }
                    
                    if duplicates:
                        response["warning"] = f"Некоторые программы уже существуют ({len(duplicates)})"
                        response["duplicates"] = duplicates
                    
                    return jsonify(response)
                    
                except json.JSONDecodeError:
                    return jsonify({"success": False, "error": "Ошибка чтения JSON файла"}), 400
                    
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка сервера: {str(e)}"}), 500

    def delete_json(self):
        if not self._check_access(2):
            return jsonify({"success": False, "error": "У вас недостаточно прав для выполнения этой операции"}), 403
        try:
            # Получаем данные из запроса
            data = request.get_json()
            json_filename = data.get('filename')
            
            if not json_filename:
                return jsonify({"success": False, "error": "Не указано имя файла"}), 400
            
            # Проверяем расширение .json
            if not json_filename.endswith('.json'):
                return jsonify({"success": False, "error": "Некорректный формат файла (требуется .json)"}), 400
            
            # Проверяем безопасность имени файла
            if not re.match(r'^[a-zA-Z0-9_\-\.\s]+\.json$', json_filename):
                return jsonify({"success": False, "error": "Недопустимые символы в имени файла"}), 400
            
            # Путь к директории с JSON-файлами
            json_dir = os.path.join(self.static_folder, "json_dir")
            
            # Полный путь к файлу с защитой от directory traversal
            filepath = os.path.abspath(os.path.normpath(os.path.join(json_dir, json_filename)))

            if not filepath.startswith(os.path.abspath(json_dir)):
                return jsonify({"success": False, "error": "Недопустимый путь к файлу"}), 400
            
            # Проверяем существование файла
            print(filepath)
            if not os.path.isfile(filepath):
                return jsonify({"success": False, "error": "Файл не существует"}), 404

            os.remove(filepath)

            return jsonify({"success": True, "message": "Файл удалён"})
            
        except PermissionError:
            return jsonify({"success": False, "error": "Нет прав для удаления файла"}), 403
        except Exception as e:
            self.app.logger.error(f"Ошибка при удалении файла {json_filename}: {str(e)}")
            return jsonify({"success": False, "error": "Внутренняя ошибка сервера"}), 500
            

    def delete_program(self):
        if not self._check_access(2):
            return jsonify({"success": False, "error": "У вас недостаточно прав для выполнения этой операции"}), 403
            
        try:
            # Получаем данные из JSON запроса
            data = request.get_json()
            json_filename = data.get('filename')
            program_name = data.get('program_name')

            if not json_filename:
                return jsonify({"success": False, "error": "Не указан файл JSON"}), 400
                
            if not program_name or not program_name.strip():
                return jsonify({"success": False, "error": "Название программы не найдено"}), 400
                
            program_name = program_name.strip()
            
            # Безопасная проверка имени файла
            if not json_filename.endswith('.json') or '/' in json_filename or '\\' in json_filename:
                return jsonify({"success": False, "error": "Некорректное имя файла"}), 400
            
            # Путь к директории с JSON-файлами
            json_dir = os.path.join(self.static_folder)

            # Проверяем существование файла (рекурсивно во всех подпапках)
            filepath = None
            for root, dirs, files in os.walk(json_dir):
                if json_filename in files:
                    filepath = os.path.join(root, json_filename)
                    break
            
            if not os.path.exists(filepath):
                return jsonify({"success": False, "error": "Файл не найден"}), 404
            
            # Читаем и обновляем JSON
            with open(filepath, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                
                # Проверяем наличие app_list
                if 'app_list' not in data:
                    return jsonify({"success": False, "error": "Некорректный формат файла"}), 400
                
                # Ищем программу для удаления
                program_index = -1
                for i, program in enumerate(data['app_list']):
                    if program['name'].lower() == program_name.lower():
                        program_index = i
                        break
                
                if program_index == -1:
                    return jsonify({"success": False, "error": "Программа не найдена в списке"}), 404
                
                # Удаляем программу
                data['app_list'].pop(program_index)
                
                # Перезаписываем файл
                f.seek(0)
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.truncate()
                
                return jsonify({"success": True})
                
        except json.JSONDecodeError:
            return jsonify({"success": False, "error": "Ошибка чтения JSON файла"}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка сервера: {str(e)}"}), 500

    def delete_user(self):
        if not self._check_access(1):  # Только администратор
            return jsonify({"success": False, "error": "У вас недостаточно прав для выполнения этой операции"}), 403
        
        try:
            data = request.get_json()
            username = data.get('username')

            # Проверка обязательных полей
            if not username:
                return jsonify({"success": False, "error": "Логин пользователя обязателен"}), 400
            
            # Загрузка существующих пользователей
            user_file = os.path.join(self.static_folder, 'user.json')
            users = {}
            
            if os.path.exists(user_file):
                with open(user_file, 'r', encoding='utf-8') as f:
                    try:
                        users = json.load(f)
                    except json.JSONDecodeError:
                        users = {}

            # Проверка существования пользователя
            if username not in users:
                return jsonify({"success": False, "error": "Пользователь не найден"}), 404
            
            if session.get('username', 'unknown') == username:
                return jsonify({"success": False, "error": "Вы не можете удалить сами себя"}), 404

            # Удаление пользователя
            if int(users[username]['access']) == 0:
                return jsonify({"success": False, "error": "Данного пользователя нельзя удалить"}), 404
            elif int(users[username]['access']) == 1 and not self._check_access(0):
                return jsonify({"success": False, "error": "У вас недостаточно прав для данного действия"}), 404
            else:
                del users[username]

            # Сохранение обновленных данных
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                "success": True,
                "message": "Пользователь успешно удален",
                "username": username
            })
            
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка сервера: {str(e)}"}), 500

    def get_json_file(self):
        json_filename = request.args.get('json', '')
        if not json_filename:
            return jsonify({"error": "No filename provided"}), 400
        
        # Безопасная проверка имени файла
        if not json_filename.endswith('.json') or '/' in json_filename or '\\' in json_filename:
            return jsonify({"error": "Invalid filename"}), 400
        
        # Путь к директории с JSON-файлами
        json_dir = os.path.join(self.static_folder, "json_dir")
        
        # Проверяем существование файла (рекурсивно во всех подпапках)
        filepath = None
        for root, dirs, files in os.walk(json_dir):
            if json_filename in files:
                filepath = os.path.join(root, json_filename)
                break
        
        if not filepath:
            return jsonify({"error": "File not found"}), 404
        
        try:
            # Отправляем файл из найденной директории
            directory = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            return send_from_directory(directory, filename, mimetype='application/json')
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    def get_json_list(self):       
        # Путь к директории с JSON-файлами
        json_dir = os.path.join(self.static_folder, "json_dir")
        json_list = []
        
        # Проверяем существование директории
        if not os.path.exists(json_dir):
            return jsonify({"error": "Directory not found"}), 404
        
        # Рекурсивно ищем все JSON-файлы
        for root, dirs, files in os.walk(json_dir):
            for file in files:
                if file.endswith('.json'):
                    # Добавляем относительный путь от json_dir
                    rel_path = os.path.relpath(os.path.join(root, file), json_dir)
                    json_list.append(rel_path)
        
        if not json_list:
            return jsonify({"error": "No JSON files found"}), 404
    
        try:
            # Возвращаем список файлов в формате JSON
            return jsonify({
                "status": "success",
                "files": json_list,
                "count": len(json_list)
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    def logout(self):
        session.pop('username', None)
        return redirect(url_for('login'))

    def start(self, host='0.0.0.0', port=8083, debug=False, use_reloader=False):
        try:
            host = self.setting['host']
        except:
            host = '0.0.0.0'
        port = 8083
        self.app.run(host=host, port=port, debug=True, use_reloader=use_reloader)