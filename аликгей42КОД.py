import telebot
import psycopg2
from datetime import datetime
from telebot import types
import hashlib
import logging

bot = telebot.TeleBot('7931264121:AAG0v-S7xwK88gixDU_v7qBRzHdW-8Lt3OE')

conn = psycopg2.connect(
    host="localhost",
    dbname="AITUCollegeDataBaseBot",
    user="postgres",
    password="123",
    port="5432"
)
cursor = conn.cursor()

user_auth_state = {}
student_data = {}
current_step = {}

logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def authenticate_user(login, password):
    try:
        logger.debug(f"Attempting to authenticate user: {login}")
        
        cursor.execute("SELECT student_id, 'student' as user_type FROM student WHERE login = %s AND password = %s", (login, password))
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Student authentication successful for {login}")
            return result
        
        cursor.execute("SELECT admin_id, 'admin' as user_type FROM admin WHERE login = %s AND password = %s", (login, password))
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Admin authentication successful for {login}")
            return result
        
        cursor.execute("SELECT advisor_id, 'advisor' as user_type FROM advisor WHERE login = %s AND password = %s", (login, password))
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Advisor authentication successful for {login}")
            return result
        
        logger.warning(f"Authentication failed for {login}")
        return None

    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        return None

@bot.message_handler(commands=['login'])
def login_handler(message):
    try:
        logger.debug(f"Login command received from user {message.chat.id}")
        bot.send_message(message.chat.id, "Введите ваш логин:")
        user_auth_state[message.chat.id] = 'login_username'
    except Exception as e:
        logger.error(f"Error in login_handler: {e}")

@bot.message_handler(func=lambda message: message.chat.id in user_auth_state)
def handle_auth_input(message):
    try:
        user_id = message.chat.id
        state = user_auth_state.get(user_id)
        logger.debug(f"Processing authentication for user {user_id}, current state: {state}")

        if state == 'login_username':
            user_auth_state[user_id] = {'login': message.text, 'step': 'login_password'}
            bot.send_message(user_id, "Введите пароль:")
            logger.debug(f"Requested password for user {user_id}")

        elif state == 'login_password':
            login = user_auth_state[user_id]['login']
            password = message.text
            
            logger.debug(f"Attempting to authenticate user {login}")
            authenticated_user = authenticate_user(login, password)
            
            if authenticated_user:
                user_type_id, user_type = authenticated_user
                logger.info(f"User {login} authenticated as {user_type}")
                
                bot.send_message(user_id, f"Вы успешно авторизованы как {user_type}!")
                
                user_auth_state[user_id] = {
                    'login': login,
                    'user_type': user_type,
                    'user_type_id': user_type_id
                }
                
                if user_type == 'student':
                    try:
                        cursor.execute("SELECT profile_complete FROM student WHERE student_id = %s", (user_type_id,))
                        profile_complete = cursor.fetchone()[0]
                        
                        if not profile_complete:
                            bot.send_message(user_id, "Ваш профиль incomplete. Пожалуйста, заполните данные.")
                            current_step[user_id] = 'last_name'
                            bot.send_message(user_id, "Введите вашу Фамилию:")
                        else:
                            bot.send_message(user_id, "Ваш профиль уже заполнен. Используйте другие команды.")
                    
                    except Exception as e:
                        logger.error(f"Error checking profile completeness: {e}")
                        bot.send_message(user_id, "Произошла ошибка при проверке профиля.")
                
                del user_auth_state[user_id]
            else:
                logger.warning(f"Authentication failed for user {login}")
                bot.send_message(user_id, "Неверный логин или пароль.")
                del user_auth_state[user_id]

    except Exception as e:
        logger.error(f"Unexpected error in authentication handler: {e}")
        bot.send_message(user_id, "Произошла непредвиденная ошибка. Попробуйте снова.")

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, '''Добро пожаловать в Базу данных колледжа AITU! 
Пожалуйста, войдите в систему с помощью /login''')

@bot.message_handler(func=lambda message: message.chat.id in current_step)
def handle_message(message):
    user_id = message.chat.id
    step = current_step.get(user_id)
 
    if user_id not in user_auth_state or user_auth_state.get(user_id, {}).get('user_type') != 'student':
        bot.send_message(user_id, "Пожалуйста, сначала войдите в систему.")
        return

    student_id = user_auth_state[user_id]['user_type_id']

    if step == 'last_name':
        student_data['lname'] = message.text
        current_step[user_id] = 'first_name'
        bot.send_message(user_id, "Введите ваше Имя:")

    elif step == 'first_name':
        student_data['fname'] = message.text
        current_step[user_id] = 'middle_name'
        bot.send_message(user_id, 'Введите ваше Отчество')

    elif step == 'middle_name':
        student_data['mname'] = message.text
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
        current_step[user_id] = 'IIN'
        bot.send_message(user_id, "Теперь, пожалуйста, введите ИИН:")

    elif step == 'IIN':
        student_data['IIN'] = message.text
        save_to_db(student_id, student_data)

def save_to_db(student_id, data):
    try:
        update_query = """
        UPDATE student 
        SET 
            lname = %s, 
            fname = %s, 
            mname = %s, 
            citizenship = %s, 
            nationality = %s, 
            date_of_birth = %s, 
            gender = %s, 
            phone_number = %s, 
            IIN = %s,
            profile_complete = TRUE
        WHERE student_id = %s
        """
        
        cursor.execute(update_query, (
            data.get('lname', ''),
            data.get('fname', ''),
            data.get('mname', ''),
            data.get('citizenship', ''),
            data.get('nationality', ''),
            data.get('date_of_birth'),
            data.get('gender', ''),
            data.get('phone_number', ''),
            data.get('IIN', ''),
            student_id
        ))
        conn.commit()
        
        bot.send_message(student_id, "Данные успешно сохранены!")
        
        # Clear steps and data
        if student_id in current_step:
            del current_step[student_id]
        student_data.clear()

    except Exception as e:
        conn.rollback()
        bot.send_message(student_id, f"Ошибка при сохранении данных: {e}")

@bot.message_handler(commands=['read'])
def read_data(message):
    if message.chat.id not in user_auth_state:
        bot.send_message(message.chat.id, "Пожалуйста, сначала войдите в систему.")
        return

    user_type = user_auth_state[message.chat.id].get('user_type')
    user_type_id = user_auth_state[message.chat.id].get('user_type_id')

    try:
        if user_type == 'student':
            query = '''
            SELECT lname, fname, mname, citizenship, nationality, 
                   date_of_birth, gender, phone_number, 
                   year_of_college, IIN 
            FROM student 
            WHERE student_id = %s
            '''
            cursor.execute(query, (user_type_id,))
        else:
            bot.send_message(message.chat.id, "У вас нет доступа к чтению данных.")
            return

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
            bot.send_message(message.chat.id, "Данные не найдены.")

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при чтении данных: {e}")

# Modify bot polling to include error handling
try:
    logger.info("Starting bot polling")
    bot.polling(none_stop=True)
except Exception as e:
    logger.critical(f"Bot polling failed: {e}")