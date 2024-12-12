import telebot
from telebot import types
from datetime import datetime
import psycopg2
import pandas as pd
import os
import threading
import time  

bot = telebot.TeleBot('7670360536:AAHj5HjLbGUrzUZUyez9RLNm2joAUOCR2Yw')

conn = psycopg2.connect(
    host="localhost",
    dbname="AITUCollegeDataBaseBot",
    user="postgres",
    password="1234",
    port="5432"
)
cursor = conn.cursor()
student_data = {}
current_step = {}
login_state = {}
family_members = {}

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(
        message.chat.id,
        'Добро пожаловать в Базу данных колледжа AITU! Нажмите /login, чтобы авторизоваться.'
    )

@bot.message_handler(commands=['login'])
def start_login(message):
    user_id = message.chat.id
    bot.send_message(user_id, 'Введите ваш логин:')
    login_state[user_id] = {'step': 'login'}

@bot.message_handler(func=lambda msg: login_state.get(msg.chat.id, {}).get('step') == 'login')
def get_login(message):
    user_id = message.chat.id
    login = message.text.strip()
    login_state[user_id]['login'] = login
    bot.send_message(user_id, 'Введите ваш пароль:')
    login_state[user_id]['step'] = 'password'

@bot.message_handler(func=lambda msg: login_state.get(msg.chat.id, {}).get('step') == 'password')
def get_password(message):
    user_id = message.chat.id
    password = message.text.strip()
    login = login_state[user_id].get('login')
    
    user_types = [
        ('admin', "SELECT * FROM admin WHERE login = %s AND password = %s"),
        ('advisor', "SELECT * FROM advisor WHERE login = %s AND password = %s"),
        ('student', "SELECT * FROM student WHERE login = %s AND password = %s")
    ]

    user = None
    user_type = None
    for type_name, query in user_types:
        cursor.execute(query, (login, password))
        user = cursor.fetchone()
        if user:
            user_type = type_name
            break

    if not user:
        bot.send_message(user_id, 'Неверный логин или пароль. Попробуйте снова.')
        del login_state[user_id]
        return

    try:
        update_queries = {
            'admin': "UPDATE admin SET telegram_id = %s WHERE login = %s",
            'advisor': "UPDATE advisor SET telegram_id = %s WHERE login = %s",
            'student': "UPDATE student SET telegram_id = %s WHERE login = %s"
        }
        
        cursor.execute(update_queries[user_type], (user_id, login))
        conn.commit()

        if user_type == 'advisor':
            markup = types.InlineKeyboardMarkup()
            export_button = types.InlineKeyboardButton("Экспорт данных", callback_data="export_data")
            markup.add(export_button)
            bot.send_message(user_id, f"Вы успешно вошли как Куратор. Хотите экспортировать данные?", reply_markup=markup)

        if user_type == 'admin':
            markup = types.InlineKeyboardMarkup()
            export_button = types.InlineKeyboardButton("Экспорт данных", callback_data="admin_export")
            markup.add(export_button)
            bot.send_message(user_id, "Вы успешно вошли как Администратор. Какие данные хотите увидеть?", reply_markup=create_admin_main_keyboard())
       
        elif user_type == 'student':
            cursor.execute("SELECT profile_complete FROM student WHERE login = %s", (login,))
            profile_complete = cursor.fetchone()[0]

            if not profile_complete:
                bot.send_message(user_id, "Вы успешно вошли! Ваш профиль неполный. Пожалуйста, заполните данные.")
                login_state[user_id]['step'] = 'ask_data'
                ask_for_data(message)
            else:
                cursor.execute("""
                    SELECT  s.lname, s.fname, s.mname, s.citizenship, s.reason_for_stay, s.nationality, s.address_constant, 
                            s.address_home, s.date_of_birth, s.gender, s.phone_number, s.IIN, s.year_of_college, f.family_type,
                            f.member_type, f.name, f.job,  f.phone_number
                    FROM student s
                    LEFT JOIN family_member f ON s.student_id = f.student_id
                    WHERE login = %s
                """, (login,))
                user_data = cursor.fetchone()
                
                profile_info = "\n".join([
                    f"Фамилия: {user_data[0]}",
                    f"Имя: {user_data[1]}",
                    f"Отчество: {user_data[2]}",
                    f"Гражданство: {user_data[3]}",
                    f"Основание пребывания: {user_data[4]}",
                    f"Национальность: {user_data[5]}",
                    f"Адрес постоянного проживания: {user_data[6]}",
                    f"Адрес прописки: {user_data[7]}",
                    f"Дата рождения: {user_data[8]}",
                    f"Пол: {user_data[9]}",
                    f"Номер телефона: {user_data[10]}",
                    f"ИИН: {user_data[11]}",
                    f"Курс: {user_data[12]}",
                    f"Семейный статус: {user_data[13]}",
                    f"Тип родителя/опекуна: {user_data[14]}",
                    f"Имя родителя/опекуна: {user_data[15]}",
                    f"Место работы родителя/опекуна: {user_data[16]}",
                    f"Контакт родителя/опекуна: {user_data[17]}"
                ])
                
                bot.send_message(user_id, f"Вы успешно вошли! Вот ваши данные:\n{profile_info}")

                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("Обновить данные", callback_data="edit_yes"),
                    types.InlineKeyboardButton("Оставить как есть", callback_data="edit_no")
                )
                bot.send_message(user_id, "Хотите обновить свои данные?", reply_markup=markup)

        del login_state[user_id]

    except Exception as e:
        conn.rollback()
        print(f"Error processing login: {e}")
        import traceback
        traceback.print_exc()
        bot.send_message(user_id, f"Произошла ошибка при обработке данных: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "export_data")
def export_data_callback(call):
    user_id = call.message.chat.id
    try:
        cursor.execute("SELECT login FROM admin WHERE telegram_id = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            export_student_data(user_id, 'admin', user[0])
            return
        
        cursor.execute("SELECT login FROM advisor WHERE telegram_id = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            export_student_data(user_id, 'advisor', user[0])
            return
        
        bot.send_message(user_id, "Не удалось определить тип пользователя.")
    
    except Exception as e:
        bot.send_message(user_id, f"Произошла ошибка при экспорте: {str(e)}")

def export_student_data(user_id, user_type, login, filter_group=None, filter_all_groups=None, 
                        filter_year=None, filter_citizenship=None, filter_family_status=None, 
                        filter_age_range=None, filter_gender=None):
    try:
        base_query = """
            SELECT  s.lname, s.fname, s.mname, g.group_name, s.citizenship, s.reason_for_stay, 
                    s.nationality, s.address_constant, s.address_home, s.date_of_birth, 
                    s.gender, s.phone_number, s.IIN, s.year_of_college, f.family_type,
                    f.member_type, f.name, f.job, f.phone_number
            FROM student s
            LEFT JOIN groups g ON s.group_id = g.group_id
            LEFT JOIN family_member f ON s.student_id = f.student_id
            WHERE 1=1
        """
        
        params = []
        
        if user_type == 'advisor':
            base_query += " AND g.advisor_id = (SELECT advisor_id FROM advisor WHERE login = %s)"
            params.append(login)
        
        if filter_group:
            base_query += " AND g.group_name = %s"
            params.append(filter_group)

        if filter_all_groups:
            base_query += ", GROUP BY group_id, ORDER BY s.lname ASC"
        
        if filter_year:
            base_query += " AND s.year_of_college = %s"
            params.append(filter_year)
        
        if filter_citizenship == 'РК':
            base_query += " AND s.citizenship = 'РК'"
        elif filter_citizenship == 'international':
            base_query += " AND s.citizenship != 'РК'"
        
        if filter_family_status:
            base_query += " AND f.family_type = %s"
            params.append(filter_family_status)
        
        if filter_age_range:
            current_year = datetime.now().year
            if filter_age_range == 'under_15':
                base_query += " AND (EXTRACT(YEAR FROM AGE(s.date_of_birth)) < 15)"
            elif filter_age_range == '15':
                base_query += " AND (EXTRACT(YEAR FROM AGE(s.date_of_birth)) = 15)"
            elif filter_age_range == '16':
                base_query += " AND (EXTRACT(YEAR FROM AGE(s.date_of_birth)) = 16)"
            elif filter_age_range == '17':
                base_query += " AND (EXTRACT(YEAR FROM AGE(s.date_of_birth)) = 17)"
            elif filter_age_range == '18':
                base_query += " AND (EXTRACT(YEAR FROM AGE(s.date_of_birth)) = 18)"
            elif filter_age_range == 'over_18':
                base_query += " AND (EXTRACT(YEAR FROM AGE(s.date_of_birth)) > 18)"
        
        if filter_gender:
            base_query += " AND s.gender = %s"
            params.append('м' if filter_gender == 'male' else 'ж')
        
        base_query += " ORDER BY g.group_name, s.lname"
        
        if params:
            cursor.execute(base_query, tuple(params))
        else:
            cursor.execute(base_query)
        
        rows = cursor.fetchall()

        columns = [
            'Фамилия', 'Имя', 'Отчество', 'Группа', 'Гражданство', 'Основание пребывания',
            'Национальность', 'Адрес постоянного проживания', 'Адрес прописки', 
            'Дата Рождения', 'Пол', 'Номер телефона', 'ИИН', 'Курс',
            'Семейный статус', 'Тип родителя/опекуна', 'Имя родителя/опекуна',
            'Рабочее место родителя/опекуна', 'Контакт родителя/опекуна'
        ]
        
        df = pd.DataFrame(rows, columns=columns)
        
        filename_parts = ["колледж"]
        if filter_group:
            filename_parts.append(f"группа_{filter_group}")
        if filter_all_groups:
            filename_parts.append("все_группы")
        if filter_year:
            filename_parts.append(f"{filter_year}_курс")
        if filter_citizenship:
            filename_parts.append(f"гражданство_{filter_citizenship}")
        if filter_family_status:
            filename_parts.append(f"семья_{filter_family_status}")
        if filter_age_range:
            filename_parts.append(f"возраст_{filter_age_range}")
        if filter_gender:
            filename_parts.append(f"пол_{filter_gender}")
        
        filename = "_".join(filename_parts) + ".xlsx"
        
        os.makedirs('exports', exist_ok=True)
        file_path = os.path.join('exports', filename)
        df.to_excel(file_path, index=False, engine='openpyxl')

        with open(file_path, "rb") as file:
            bot.send_document(user_id, file)

        os.remove(file_path)

    except Exception as e:
        print(f"Error exporting data: {e}")
        bot.send_message(user_id, f"Произошла ошибка при экспорте данных: {str(e)}")

def create_admin_main_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Весь колледж", callback_data="export_all_groups"),
        types.InlineKeyboardButton("Определенная группа", callback_data="export_specific_group")
    )
    keyboard.row(
        types.InlineKeyboardButton("1 курс", callback_data="export_year_1"),
        types.InlineKeyboardButton("2 курс", callback_data="export_year_2"),
        types.InlineKeyboardButton("3 курс", callback_data="export_year_3")
    )
    keyboard.row(
        types.InlineKeyboardButton("По гражданству/нации", callback_data="export_citizenship"),
        types.InlineKeyboardButton("Семейное положение", callback_data="export_family_status")
    )
    keyboard.row(
        types.InlineKeyboardButton("По возрасту", callback_data="export_age"),
        types.InlineKeyboardButton("Мужской пол", callback_data="export_gender_male"),
        types.InlineKeyboardButton("Женский пол", callback_data="export_gender_female")
    )
    return keyboard

def create_group_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    # Fetch groups from database
    cursor.execute("SELECT group_name FROM groups ORDER BY group_name")
    groups = cursor.fetchall()
    
    # Create keyboard rows of 3 buttons each
    for i in range(0, len(groups), 3):
        row_groups = groups[i:i+3]
        row_buttons = [
            types.InlineKeyboardButton(group[0], callback_data=f"group_{group[0]}") 
            for group in row_groups
        ]
        keyboard.row(*row_buttons)
    
    return keyboard

def create_family_status_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Полная семья", callback_data="family_full"),
        types.InlineKeyboardButton("Неполная семья", callback_data="family_incomplete"),
        types.InlineKeyboardButton("Сирота", callback_data="family_orphan")
    )
    return keyboard

def create_age_range_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    keyboard.row(
        types.InlineKeyboardButton("До 15 лет", callback_data="age_under_15"),
        types.InlineKeyboardButton("15 лет", callback_data="age_15"),
        types.InlineKeyboardButton("16 лет", callback_data="age_16")
    )
    keyboard.row(
        types.InlineKeyboardButton("17 лет", callback_data="age_17"),
        types.InlineKeyboardButton("18 лет", callback_data="age_18"),
        types.InlineKeyboardButton("Старше 18 лет", callback_data="age_over_18")
    )
    return keyboard

def create_citizenship_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("РК", callback_data="citizenship_rk"),
        types.InlineKeyboardButton("Иное", callback_data="citizenship_international")
    )
    return keyboard

def create_citizenship_keyboard_admin():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("РК", callback_data="citizenship_rk_admin"),
        types.InlineKeyboardButton("Иное", callback_data="citizenship_international_admin")
    )
    return keyboard

def create_reason_stay_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("ВНЖ", callback_data="reason_vnj"),
        types.InlineKeyboardButton("РВП", callback_data="reason_rvp")
    )
    return keyboard

def create_gender_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Мужской", callback_data="gender_male"),
        types.InlineKeyboardButton("Женский", callback_data="gender_female")
    )
    return keyboard

def create_year_of_college_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("1 курс", callback_data="year_1"),
        types.InlineKeyboardButton("2 курс", callback_data="year_2"),
        types.InlineKeyboardButton("3 курс", callback_data="year_3")
    )
    return keyboard

def create_family_type_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Полная", callback_data="family_full"),
        types.InlineKeyboardButton("Неполная", callback_data="family_incomplete"),
        types.InlineKeyboardButton("Сирота", callback_data="family_orphan")
    )
    return keyboard

def create_family_member_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Мать", callback_data="member_mother"),
        types.InlineKeyboardButton("Отец", callback_data="member_father"),
        types.InlineKeyboardButton("Опекун", callback_data="member_guardian")
    )
    return keyboard

@bot.message_handler(func=lambda msg: login_state.get(msg.chat.id, {}).get('step') == 'ask_data')
def ask_for_data(message):
    user_id = message.chat.id
    current_step[user_id] = 'last_name'
    bot.send_message(user_id, "Введите вашу Фамилию:")
    student_data[user_id] = {}

@bot.message_handler(func=lambda msg: msg.chat.id in current_step)
def handle_data_input(message):
    user_id = message.chat.id
    step = current_step[user_id]
    
    if step == 'last_name':
        student_data[user_id]['lname'] = message.text
        current_step[user_id] = 'first_name'
        bot.send_message(user_id, "Введите ваше Имя:")

    elif step == 'first_name':
        student_data[user_id]['fname'] = message.text
        current_step[user_id] = 'middle_name'
        bot.send_message(user_id, "Введите ваше Отчество:")

    elif step == 'middle_name':
        student_data[user_id]['mname'] = message.text
        current_step[user_id] = 'citizenship'
        bot.send_message(user_id, "Выберите ваше Гражданство:", reply_markup=create_citizenship_keyboard())

    elif step == 'citizenship_international':
        student_data[user_id]['citizenship'] = message.text.lower()
        current_step[user_id] = 'reason_for_stay'
        bot.send_message(user_id, "Выберите основание пребывания:", reply_markup=create_reason_stay_keyboard())

    elif step == 'address_constant':
        student_data[user_id]['address_constant'] = message.text
        current_step[user_id] = 'address_home'
        bot.send_message(user_id, "Введите вашу адрес прописки:")

    elif step == 'address_home':
        student_data[user_id]['address_home'] = message.text
        current_step[user_id] = 'nationality'
        bot.send_message(user_id, "Введите вашу Национальность:")

    elif step == 'nationality':
        student_data[user_id]['nationality'] = message.text
        current_step[user_id] = 'date_of_birth'
        bot.send_message(user_id, "Введите вашу дату рождения (YYYY-MM-DD):")

    elif step == 'date_of_birth':
        try:
            student_data[user_id]['date_of_birth'] = datetime.strptime(message.text, "%Y-%m-%d").date()
            current_step[user_id] = 'gender'
            bot.send_message(user_id, "Выберите ваш Пол:", reply_markup=create_gender_keyboard())
        except ValueError:
            bot.send_message(user_id, "Неверный формат даты. Пожалуйста, введите дату в формате YYYY-MM-DD.")

    elif step == 'phone_number':
        student_data[user_id]['phone_number'] = message.text
        current_step[user_id] = 'IIN'
        bot.send_message(user_id, "Введите ваш ИИН:")

    elif step == 'IIN':
        student_data[user_id]['IIN'] = message.text
        current_step[user_id] = 'year_of_college'
        bot.send_message(user_id, "Выберите курс:", reply_markup=create_year_of_college_keyboard())

    elif step == 'family_type':
        current_step[user_id] = 'family_type'
        bot.send_message(user_id, "Выберите семейный статус:", reply_markup=create_family_type_keyboard())

    elif step == 'member_type':
        bot.send_message(user_id, "Выберите родителя/опекуна:", reply_markup=create_family_member_keyboard())

    elif step == 'parent_name_first':
        family_members[user_id].append({
            'name': message.text,
            'type': 'мать'
        })
        current_step[user_id] = 'job_first'
        bot.send_message(user_id, "Введите место работы матери:")

    elif step == 'job_first':
        family_members[user_id][-1]['job'] = message.text
        current_step[user_id] = 'parent_phone_number_first'
        bot.send_message(user_id, "Введите номер телефона матери:")

    elif step == 'parent_phone_number_first':
        family_members[user_id][-1]['phone_number'] = message.text
        current_step[user_id] = 'parent_name_second'
        bot.send_message(user_id, "Теперь добавим отца:\nВведите полное ФИО отца:")

    elif step == 'parent_name_second':
        family_members[user_id].append({
            'name': message.text,
            'type': 'отец'
        })
        current_step[user_id] = 'job_second'
        bot.send_message(user_id, "Введите место работы отца:")

    elif step == 'job_second':
        family_members[user_id][-1]['job'] = message.text
        current_step[user_id] = 'parent_phone_number_second'
        bot.send_message(user_id, "Введите номер телефона отца:")

    elif step == 'parent_phone_number_second':
        family_members[user_id][-1]['phone_number'] = message.text
        save_student_data(user_id)

    elif step == 'parent_name':
        if 'member_type' in student_data[user_id]:
            student_data[user_id]['parent_name'] = message.text
            current_step[user_id] = 'job'
            bot.send_message(user_id, "Введите место работы родителя/опекуна:")
        else:
            bot.send_message(user_id, "Произошла ошибка. Пожалуйста, начните процесс регистрации заново.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id

    if call.data == "edit_yes":
        bot.edit_message_text("Введите новые данные. Начнем с Фамилии:", chat_id=user_id, message_id=call.message.message_id)
        current_step[user_id] = 'last_name'
        student_data[user_id] = {}
    elif call.data == "edit_no":
        bot.edit_message_text("Обновление данных завершено.", chat_id=user_id, message_id=call.message.message_id)

    elif call.data == "admin_export":
        bot.edit_message_text(
            "Какие данные хотите увидеть?", 
            chat_id=user_id, 
            message_id=call.message.message_id, 
            reply_markup=create_admin_main_keyboard()
        )

    elif call.data == "export_all_groups":
        export_student_data(user_id, 'admin', None, filter_all_groups='all')
    
    elif call.data == "export_specific_group":
        bot.edit_message_text(
            "Выберите группу:", 
            chat_id=user_id, 
            message_id=call.message.message_id, 
            reply_markup=create_group_keyboard()
        )
    
    elif call.data == "export_family_status":
        bot.edit_message_text(
            "Выберите тип семейного статуса:", 
            chat_id=user_id, 
            message_id=call.message.message_id, 
            reply_markup=create_family_status_keyboard()
        )
    
    elif call.data == "export_age":
        bot.edit_message_text(
            "Выберите возрастной диапазон:", 
            chat_id=user_id, 
            message_id=call.message.message_id, 
            reply_markup=create_age_range_keyboard()
        )
    
    elif call.data == "export_year_1":
        export_student_data(user_id, 'admin', None, filter_year=1)
    elif call.data == "export_year_2":
        export_student_data(user_id, 'admin', None, filter_year=2)
    elif call.data == "export_year_3":
        export_student_data(user_id, 'admin', None, filter_year=3)

    # Export by specific group (groups from the previous code)
    elif call.data.startswith("group_"):
        group_name = call.data.split("_", 1)[1]
        export_student_data(user_id, 'admin', None, filter_group=group_name)

    # Export by citizenship
    elif call.data == "export_citizenship":
        bot.edit_message_text(
            "Выберите гражданство:", 
            chat_id=user_id, 
            message_id=call.message.message_id, 
            reply_markup=create_citizenship_keyboard_admin()
        )

    # Export different citizenship types
    elif call.data == "citizenship_rk_admin":
        export_student_data(user_id, 'admin', None, filter_citizenship='РК')
    elif call.data == "citizenship_international_admin":
        export_student_data(user_id, 'admin', None, filter_citizenship='international')

    # Export by gender
    elif call.data == "export_gender_male":
        export_student_data(user_id, 'admin', None, filter_gender='male')
    elif call.data == "export_gender_female":
        export_student_data(user_id, 'admin', None, filter_gender='female')

    # Export by family status (from previous callback code)
    elif call.data == "family_full":
        export_student_data(user_id, 'admin', None, filter_family_status='полная')
    elif call.data == "family_incomplete":
        export_student_data(user_id, 'admin', None, filter_family_status='неполная')
    elif call.data == "family_orphan":
        export_student_data(user_id, 'admin', None, filter_family_status='сирота')

    # Export by age range
    elif call.data == "age_under_15":
        export_student_data(user_id, 'admin', None, filter_age_range='under_15')
    elif call.data == "age_15":
        export_student_data(user_id, 'admin', None, filter_age_range='15')
    elif call.data == "age_16":
        export_student_data(user_id, 'admin', None, filter_age_range='16')
    elif call.data == "age_17":
        export_student_data(user_id, 'admin', None, filter_age_range='17')
    elif call.data == "age_18":
        export_student_data(user_id, 'admin', None, filter_age_range='18')
    elif call.data == "age_over_18":
        export_student_data(user_id, 'admin', None, filter_age_range='over_18') 

    elif call.data == "citizenship_rk":
        student_data[user_id]['citizenship'] = 'РК'
        student_data[user_id]['reason_for_stay'] = 'Местный'
        current_step[user_id] = 'address_constant'
        bot.edit_message_text("Введите ваш адрес постоянного проживания:", chat_id=user_id, message_id=call.message.message_id)
    elif call.data == "citizenship_international":
        current_step[user_id] = 'citizenship_international'
        bot.edit_message_text("Введите ваше Гражданство:", chat_id=user_id, message_id=call.message.message_id)

    # Reason for stay callbacks
    elif call.data == "reason_vnj":
        student_data[user_id]['reason_for_stay'] = 'ВНЖ'
        current_step[user_id] = 'address_constant'
        bot.edit_message_text("Введите ваш адрес постоянного проживания:", chat_id=user_id, message_id=call.message.message_id)
    elif call.data == "reason_rvp":
        student_data[user_id]['reason_for_stay'] = 'РВП'
        current_step[user_id] = 'address_constant'
        bot.edit_message_text("Введите ваш адрес постоянного проживания:", chat_id=user_id, message_id=call.message.message_id)

    # Gender callbacks
    elif call.data == "gender_male":
        student_data[user_id]['gender'] = 'м'
        current_step[user_id] = 'phone_number'
        bot.edit_message_text("Введите ваш Номер телефона:", chat_id=user_id, message_id=call.message.message_id)
    elif call.data == "gender_female":
        student_data[user_id]['gender'] = 'ж'
        current_step[user_id] = 'phone_number'
        bot.edit_message_text("Введите ваш Номер телефона:", chat_id=user_id, message_id=call.message.message_id)

    # Year of college callbacks
    elif call.data == "year_1":
        student_data[user_id]['year_of_college'] = 1
        current_step[user_id] = 'family_type'
        bot.edit_message_text("Выберите семейный статус:", chat_id=user_id, message_id=call.message.message_id, reply_markup=create_family_type_keyboard())
    elif call.data == "year_2":
        student_data[user_id]['year_of_college'] = 2
        current_step[user_id] = 'family_type'
        bot.edit_message_text("Выберите семейный статус:", chat_id=user_id, message_id=call.message.message_id, reply_markup=create_family_type_keyboard())
    elif call.data == "year_3":
        student_data[user_id]['year_of_college'] = 3
        current_step[user_id] = 'family_type'
        bot.edit_message_text("Выберите семейный статус:", chat_id=user_id, message_id=call.message.message_id, reply_markup=create_family_type_keyboard())

    # Family type callbacks
    elif call.data == "family_full":
        student_data[user_id]['family_type'] = 'полная'
        family_members[user_id] = []
        current_step[user_id] = 'parent_name_first'
        bot.edit_message_text("Введите полное ФИО матери:", chat_id=user_id, message_id=call.message.message_id)
    elif call.data == "family_incomplete":
        student_data[user_id]['family_type'] = 'неполная'
        current_step[user_id] = 'member_type'
        bot.edit_message_text("Выберите родителя/опекуна:", chat_id=user_id, message_id=call.message.message_id, reply_markup=create_family_member_keyboard())
    elif call.data == "family_orphan":
        student_data[user_id]['family_type'] = 'сирота'
        current_step[user_id] = 'member_type'
        bot.edit_message_text("Выберите родителя/опекуна:", chat_id=user_id, message_id=call.message.message_id, reply_markup=create_family_member_keyboard())

    # Family member callbacks
    elif call.data == "member_mother":
        student_data[user_id]['member_type'] = 'мать'
        current_step[user_id] = 'parent_name'
        bot.edit_message_text("Введите ФИО матери:", chat_id=user_id, message_id=call.message.message_id)
    elif call.data == "member_father":
        student_data[user_id]['member_type'] = 'отец'
        current_step[user_id] = 'parent_name'
        bot.edit_message_text("Введите ФИО отца:", chat_id=user_id, message_id=call.message.message_id)
    elif call.data == "member_guardian":
        student_data[user_id]['member_type'] = 'опекун'
        current_step[user_id] = 'parent_name'
        bot.edit_message_text("Введите ФИО опекуна:", chat_id=user_id, message_id=call.message.message_id)

def save_student_data(user_id):
    try:
        query = """
        UPDATE student SET
        lname = %s,
        fname = %s,
        mname = %s,
        citizenship = %s,
        reason_for_stay = %s,
        nationality = %s,
        address_constant = %s,
        address_home = %s,
        date_of_birth = %s,
        gender = %s,
        phone_number = %s,
        IIN = %s,
        year_of_college = %s,
        profile_complete = TRUE
        WHERE telegram_id = %s
        RETURNING student_id
        """
        
        cursor.execute(query, (
            student_data[user_id]['lname'],
            student_data[user_id]['fname'],
            student_data[user_id]['mname'],
            student_data[user_id]['citizenship'],
            student_data[user_id]['reason_for_stay'],
            student_data[user_id]['nationality'],
            student_data[user_id]['address_constant'],
            student_data[user_id]['address_home'],
            student_data[user_id]['date_of_birth'],
            student_data[user_id]['gender'],
            student_data[user_id]['phone_number'],
            student_data[user_id]['IIN'],
            student_data[user_id]['year_of_college'],
            user_id
        ))
        
        result = cursor.fetchone()
        if not result:
            cursor.execute("SELECT student_id FROM student WHERE telegram_id = %s", (user_id,))
            result = cursor.fetchone()
        
        if result:
            student_id = result[0]
        
            if family_members.get(user_id):
                for member in family_members[user_id]:
                    query_family = """
                        INSERT INTO family_member(
                            student_id, 
                            family_type, 
                            member_type, 
                            name, 
                            job, 
                            phone_number
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query_family, (
                        student_id,
                        student_data[user_id]['family_type'],
                        member['type'],
                        member['name'],
                        member['job'],
                        member['phone_number']
                    ))
    
                conn.commit()
                
                del family_members[user_id]

            profile_info = (
                "Личные данные: \n"
                f"Фамилия: {student_data[user_id]['lname']}\n"
                f"Имя: {student_data[user_id]['fname']}\n"
                f"Отчество: {student_data[user_id]['mname']}\n"
                f"Гражданство: {student_data[user_id]['citizenship']}\n"
                f"Основание пребывания: {student_data[user_id]['reason_for_stay']}\n"
                f"Национальность: {student_data[user_id]['nationality']}\n"
                f"Адрес постоянного проживания: {student_data[user_id]['address_constant']}\n"
                f"Адрес прописки: {student_data[user_id]['address_home']}\n"
                f"Дата рождения: {student_data[user_id]['date_of_birth']}\n"
                f"Пол: {student_data[user_id]['gender']}\n"
                f"Номер телефона: {student_data[user_id]['phone_number']}\n"
                f"ИИН: {student_data[user_id]['IIN']}\n"
                f"Курс: {student_data[user_id]['year_of_college']}\n"
                "Данные о семье: \n"
                f"Семейный статус: {student_data[user_id]['family_type']}\n"
            )
            
            if family_members.get(user_id):
                for i, member in enumerate(family_members[user_id], 1):
                    profile_info += (
                        f"Родитель {i}:\n"
                        f"Тип: {member['type']}\n"
                        f"Имя: {member['name']}\n"
                        f"Рабочее место: {member['job']}\n"
                        f"Контакт: {member['phone_number']}\n"
                    )

            bot.send_message(user_id, f"Ваши данные:\n{profile_info}")

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("Да", callback_data="edit_yes"),
                types.InlineKeyboardButton("Нет", callback_data="edit_no")
            )
            bot.send_message(user_id, "Хотите изменить данные?", reply_markup=markup)
        else:
            bot.send_message(user_id, "Ошибка: Не удалось найти студента.")

    except Exception as e:
        conn.rollback()
        bot.send_message(user_id, f"Ошибка сохранения данных: {e}")
    finally:
        current_step.pop(user_id, None)


def get_notifications():
    """
    Функция для получения и отправки уведомлений из базы данных
    """
    try:
        cursor.execute("""
            SELECT notification_id, table_name, record_id, 
                   action_type, notification_text 
            FROM notifications 
            WHERE sent_to_telegram IS NOT TRUE 
            ORDER BY created_at
        """)
        notifications = cursor.fetchall()

        for notification in notifications:
            notification_id, table_name, record_id, action_type, notification_text = notification

            # Отправка уведомления в Telegram
            # Замените на конкретный chat_id администратора
            ADMIN_CHAT_ID = '1555234543'  # Замените на реальный ID
            
            bot.send_message(
                ADMIN_CHAT_ID, 
                f"📋 Уведомление:\n"
                f"Таблица: {table_name}\n"
                f"Действие: {action_type}\n"
                f"Детали: {notification_text}"
            )

            # Помечаем уведомление как отправленное
            cursor.execute("""
                UPDATE notifications 
                SET sent_to_telegram = TRUE 
                WHERE notification_id = %s
            """, (notification_id,))

        # Подтверждаем изменения
        conn.commit()

    except Exception as e:
        print(f"Ошибка при отправке уведомлений: {e}")
    finally:
        # Закрываем соединение
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()

def notification_thread():
    """
    Поток для периодической проверки уведомлений
    """
    while True:
        get_notifications()
        # Проверяем каждые 10 секунд
        time.sleep(10)


notification_monitor = threading.Thread(target=notification_thread)
notification_monitor.daemon = True
notification_monitor.start()














bot.polling(none_stop=True)