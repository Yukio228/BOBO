import telebot
import psycopg2
from datetime import datetime
from telebot import types

bot = telebot.TeleBot('7931264121:AAG0v-S7xwK88gixDU_v7qBRzHdW-8Lt3OE')

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

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, '''Добро пожаловать в Базу данных колледжа AITU! 
    Пожалуйста, следуйте инструкциям, чтобы ввести данные студента.''')
    current_step[message.chat.id] = 'last_name' 
    bot.send_message(message.chat.id, "Введите вашу Фамилию:")

@bot.message_handler(func=lambda message: message.chat.id in current_step)
def handle_message(message):
    user_id = message.chat.id
    step = current_step[user_id]
 
    if step == 'last_name':
        student_data['last_name'] = message.text
        current_step[user_id] = 'first_name'
        bot.send_message(user_id, "Введите ваше Имя:")

    elif step == 'first_name':
        student_data['first_name'] = message.text
        current_step[user_id] = 'middle_name'
        bot.send_message(user_id, 'Введите ваше Отчество')

    elif step == 'middle_name':
        student_data['middle_name'] = message.text
        current_step[user_id] = 'citizenship'
        bot.send_message(user_id, "Теперь, пожалуйста, введите гражданство:")

    elif step == 'citizenship':
        student_data['citizenship'] = message.text
        current_step[user_id] = 'nationality'
        bot.send_message(user_id, "Теперь, пожалуйста, введите национальность:")

    elif step == 'nationality':
        student_data['nationality'] = message.text
        current_step[user_id] = 'date_of_birth'
        bot.send_message(user_id, "Теперь, пожалуйста, введите дату рождения (в формате YYYY-MM-DD):")

    elif step == 'date_of_birth':
        try:
            student_data['date_of_birth'] = datetime.strptime(message.text, "%Y-%m-%d").date()
            current_step[user_id] = 'gender'
            bot.send_message(user_id, "Теперь, пожалуйста, введите пол (м/ж):")
        except ValueError:
            bot.send_message(user_id, "Неверный формат даты. Пожалуйста, введите дату в формате YYYY-MM-DD.")

    elif step == 'gender':
        if message.text in ['м', 'ж']:
            student_data['gender'] = message.text
            current_step[user_id] = 'phone_number'
            bot.send_message(user_id, "Теперь, пожалуйста, введите номер телефона:")

        else:
            bot.send_message(user_id, "Пожалуйста, введите пол как 'м' или 'ж'.")

    elif step == 'phone_number':
        student_data['phone_number'] = message.text
        current_step[user_id] = 'year_of_college'
        bot.send_message(user_id, "Теперь, пожалуйста, введите год обучения в колледже:")

    elif step == 'year_of_college':
        try:
            student_data['year_of_college'] = int(message.text)
            current_step[user_id] = 'IIN' 
            bot.send_message(user_id, "Теперь, пожалуйста, введите ИИН:")
        except ValueError:
            bot.send_message(user_id, "Неверный формат года. Пожалуйста, введите целое число.")
    
    elif step == 'IIN':  
        student_data['IIN'] = message.text
        current_step[user_id] = 'done' 
        save_to_db(message)  

@bot.message_handler(commands=['read'])
def read_data(message):
    user_id = message.chat.id

    try:
        if user_id in current_step:
            del current_step[user_id]

        query = '''
        SELECT lname, fname, mname, citizenship, nationality, 
               date_of_birth, gender, phone_number, 
               year_of_college, IIN 
        FROM COLLEGE 
        WHERE user_id = %s
        '''
        cursor.execute(query, (user_id,))
        record = cursor.fetchone()

        if record:
            student_info = (
                f"ФИО: {record[0]}, {record[1]}, {record[2]}\n"
                f"Гражданство: {record[3]}\n"
                f"Национальность: {record[4]}\n"
                f"Дата рождения: {record[5]}\n"
                f"Пол: {record[6]}\n"
                f"Номер телефона: {record[7]}\n"
                f"Год обучения: {record[8]}\n"
                f"ИИН: {record[9]}"
            )
            bot.send_message(message.chat.id, f"Ваши данные:\n{student_info}")
        else:
            bot.send_message(message.chat.id, "Данные для этого пользователя не найдены.")

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при чтении данных: {e}")

def save_to_db(message):
    global student_data
    try:
        # Сначала удаляем существующую запись для данного user_id
        delete_query = "DELETE FROM COLLEGE WHERE user_id = %s"
        cursor.execute(delete_query, (message.chat.id,))
        
        # Затем вставляем новую запись
        query = """
        INSERT INTO COLLEGE 
        (user_id, lname, fname, mname, citizenship, nationality, date_of_birth, gender, phone_number, year_of_college, IIN)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            message.chat.id,
            student_data.get('last_name', ''), 
            student_data.get('first_name', ''),  
            student_data.get('middle_name', ''), 
            student_data.get('citizenship', ''),  
            student_data.get('nationality', ''), 
            student_data.get('date_of_birth', None),  
            student_data.get('gender', ''), 
            student_data.get('phone_number', ''),  
            student_data.get('year_of_college', None), 
            student_data.get('IIN', '') 
        ))
        conn.commit()
        
        if message.chat.id in current_step:
            del current_step[message.chat.id]
        
        student_data = {}
        
        bot.send_message(message.chat.id, "Данные успешно сохранены!")

    except Exception as e:
        conn.rollback()
        bot.send_message(message.chat.id, f"Ошибка при сохранении данных: {e}")

@bot.message_handler(func=lambda message: True)
def handle_unexpected_message(message):
    if message.chat.id not in current_step:
        bot.send_message(message.chat.id, "Пожалуйста, начните с команды /start или используйте доступные команды")

@bot.message_handler(commands=['update'])
def update_data(message):

    try:
        query = '''
        SELECT * FROM COLLEGE WHERE user_id = %s
        '''
        cursor.execute(query, (message.chat.id,))
        record = cursor.fetchone()

        if record:
            markup = types.InlineKeyboardMarkup()

            yes_btn = types.InlineKeyboardButton(text='Да', callback_data='update_yes')
            no_btn = types.InlineKeyboardButton(text='Нет', callback_data='update_no')
            markup.add(yes_btn, no_btn)

            bot.send_message(message.chat.id, 'Хотите изменить данные?', reply_markup=markup)
        else:
            bot.send_message(message.chat.id, 'Ваши данные отсутствуют в бд, пожалуйста сначало введите их с помощью команды /start')

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при проверке данных: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ["update_yes", "update_no"])
def handle_update_callback(call):
    user_id = call.message.chat.id
    if call.data == "update_yes":
        bot.edit_message_text("Пожалуйста, введите новые данные. Начнем с Фамилии:", chat_id=user_id, message_id=call.message.message_id)
        current_step[user_id] = 'last_name'
        student_data[user_id] = {}

    elif call.data == "update_no":
        bot.edit_message_text("Обновление данных отменено.", chat_id=user_id, message_id=call.message.message_id)

bot.polling()
