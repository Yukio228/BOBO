import telebot
from telebot import types
from datetime import datetime
import psycopg2
import pandas as pd


bot = telebot.TeleBot('7772607659:AAE3GUqlW_KZLwZi4TAfYJVf3aqiXYwiSKM')

conn = psycopg2.connect(
    host="localhost",
    dbname="AITUCollegeDataBaseBot",
    user="postgres",
    password="123",
    port="5432"
)
cursor = conn.cursor()
student_data = {}
current_step = {}

login_state = {}

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

        if user_type == 'admin' or user_type == 'advisor':
            cursor.execute(f"SELECT * FROM {user_type} WHERE telegram_id = %s", (user_id,))
            if not cursor.fetchone():
                bot.send_message(user_id, "У вас нет прав на выполнение этой команды.")
                return

            query = """
                SELECT lname, fname, mname, citizenship, nationality, address_constant, 
                    address_home, date_of_birth, gender, phone_number, IIN, year_of_college 
                FROM student
                ORDER BY student_id ASC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            columns = [
                'Фамилия', 'Имя', 'Отчество', 'Гражданство',
                'Национальность', 'Адрес постоянного проживания',
                'Адрес прописки', 'Дата Рождения', 'Пол', 'Номер телефона', 'ИИН', 'Курс'
            ]
            
            df = pd.DataFrame(rows, columns=columns)
            
            file_path = "students_data.xlsx"
            df.to_excel(file_path, index=False, engine='openpyxl')

            with open(file_path, "rb") as file:
                bot.send_document(user_id, file)

        elif user_type == 'student':
            cursor.execute("SELECT profile_complete FROM student WHERE login = %s", (login,))
            profile_complete = cursor.fetchone()[0]

            if not profile_complete:
                bot.send_message(user_id, "Вы успешно вошли! Ваш профиль неполный. Пожалуйста, заполните данные.")
                login_state[user_id]['step'] = 'ask_data'
                ask_for_data(message)
            else:
                cursor.execute("""
                    SELECT  lname, fname, mname, citizenship, nationality, address_constant, 
                            address_home, date_of_birth, gender, phone_number, IIN, year_of_college 
                    FROM student WHERE login = %s
                """, (login,))
                user_data = cursor.fetchone()
                
                profile_info = "\n".join([
                    f"Фамилия: {user_data[0]}",
                    f"Имя: {user_data[1]}",
                    f"Отчество: {user_data[2]}",
                    f"Гражданство: {user_data[3]}",
                    f"Национальность: {user_data[4]}",
                    f"Адрес постоянного проживания: {user_data[5]}",
                    f"Адрес прописки: {user_data[6]}",
                    f"Дата рождения: {user_data[7]}",
                    f"Пол: {user_data[8]}",
                    f"Номер телефона: {user_data[9]}",
                    f"ИИН: {user_data[10]}",
                    f"Курс: {user_data[11]}"
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
        bot.send_message(user_id, "Произошла ошибка при обработке данных.")

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
        bot.send_message(user_id, "Введите ваше Гражданство:")

    elif step == 'citizenship':
        student_data[user_id]['citizenship'] = message.text
        current_step[user_id] = 'address_constant'
        bot.send_message(user_id, "Введите ваш адрес постоянного проживания:")

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
            bot.send_message(user_id, "Введите ваш Пол (м/ж):")
        except ValueError:
            bot.send_message(user_id, "Неверный формат даты. Пожалуйста, введите дату в формате YYYY-MM-DD.")

    elif step == 'gender':
        if message.text.lower() in ['м', 'ж']:
            student_data[user_id]['gender'] = message.text.lower()
            current_step[user_id] = 'phone_number'
            bot.send_message(user_id, "Введите ваш Номер телефона:")
        else:
            bot.send_message(user_id, "Введите корректный пол (м/ж):")

    elif step == 'phone_number':
        student_data[user_id]['phone_number'] = message.text
        current_step[user_id] = 'IIN'
        bot.send_message(user_id, "Введите ваш ИИН:")

    elif step == 'IIN':
        student_data[user_id]['IIN'] = message.text
        current_step[user_id] = 'year_of_college'
        bot.send_message(user_id, "Введите курс (1, 2 или 3):")

    elif step == 'year_of_college':
        try:
            student_data[user_id]['year_of_college'] = int(message.text)
            save_student_data(user_id)
        except ValueError:
            bot.send_message(user_id, "Введите корректный Год обучения.")

def save_student_data(user_id):
    try:
        query = """
        UPDATE student SET
        lname = %s,
        fname = %s,
        mname = %s,
        citizenship = %s,
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
        """
        cursor.execute(query, (
            student_data[user_id]['lname'],
            student_data[user_id]['fname'],
            student_data[user_id]['mname'],
            student_data[user_id]['citizenship'],
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
        conn.commit()

        profile_info = (
            f"Фамилия: {student_data[user_id]['lname']}\n"
            f"Имя: {student_data[user_id]['fname']}\n"
            f"Отчество: {student_data[user_id]['mname']}\n"
            f"Гражданство: {student_data[user_id]['citizenship']}\n"
            f"Национальность: {student_data[user_id]['nationality']}\n"
            f"Адрес постоянного проживания: {student_data[user_id]['address_constant']}\n"
            f"Адрес прописки: {student_data[user_id]['address_home']}\n"
            f"Дата рождения: {student_data[user_id]['date_of_birth']}\n"
            f"Пол: {student_data[user_id]['gender']}\n"
            f"Номер телефона: {student_data[user_id]['phone_number']}\n"
            f"ИИН: {student_data[user_id]['IIN']}\n"
            f"Курс: {student_data[user_id]['year_of_college']}"
        )
        bot.send_message(user_id, f"Ваши данные:\n{profile_info}")

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Да", callback_data="edit_yes"),
            types.InlineKeyboardButton("Нет", callback_data="edit_no")
        )
        bot.send_message(user_id, "Хотите изменить данные?", reply_markup=markup)

    except Exception as e:
        conn.rollback()
        bot.send_message(user_id, f"Ошибка сохранения данных: {e}")
    finally:
        current_step.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data in ["edit_yes", "edit_no"])
def handle_edit_callback(call):
    user_id = call.message.chat.id
    if call.data == "edit_yes":
        bot.edit_message_text("Введите новые данные. Начнем с Фамилии:", chat_id=user_id, message_id=call.message.message_id)
        current_step[user_id] = 'last_name'
        student_data[user_id] = {}
    elif call.data == "edit_no":
        bot.edit_message_text("Обновление данных завершено.", chat_id=user_id, message_id=call.message.message_id)


bot.polling(none_stop=True)