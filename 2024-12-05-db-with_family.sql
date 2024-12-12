CREATE TABLE admin (
    admin_id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    login VARCHAR UNIQUE NOT NULL,
    password VARCHAR NOT NULL
);

CREATE TABLE advisor (
    advisor_id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    login VARCHAR UNIQUE NOT NULL,
    password VARCHAR NOT NULL
);

CREATE TABLE groups (
    group_id SERIAL PRIMARY KEY,
    group_name VARCHAR NOT NULL,
    advisor_id INTEGER,
    FOREIGN KEY (advisor_id) REFERENCES advisor(advisor_id)
);

CREATE TABLE student (
    student_id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    login VARCHAR UNIQUE NOT NULL,
    password VARCHAR NOT NULL,
    group_id INTEGER,
    lname VARCHAR(100),
    fname VARCHAR(100),
    mname VARCHAR(100),
    citizenship VARCHAR(100),
    nationality VARCHAR(100),
	address_constant VARCHAR(100), --адрес постояния проживания
	address_home VARCHAR(100), -- адрес прописки
    date_of_birth DATE,
    gender CHAR(1) CHECK (gender IN ('м', 'ж', 'M', 'F')),
    phone_number VARCHAR(20),
    year_of_college INTEGER,
    IIN BIGINT UNIQUE,
    profile_complete BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (group_id) REFERENCES groups(group_id)
);

CREATE TABLE family_member (
    family_member_id SERIAL PRIMARY KEY,
    student_id INTEGER,
    name VARCHAR(100) NOT NULL,
	family_type VARCHAR(20),
    member_type VARCHAR(20) NOT NULL CHECK (member_type IN ('отец', 'мать', 'сирота')),
    job VARCHAR(100),
    phone_number VARCHAR(20),
    FOREIGN KEY (student_id) REFERENCES student(student_id)
);

INSERT INTO admin(login, password) VALUES 
    ('SauleErzhanovna', '1234'),
    ('AigulManasbekovna', '1234'),
    ('AigulSerikovna', '1234');

INSERT INTO advisor(login, password) VALUES 
    ('KaldygulKambarovna', '1234'),
    ('AsselAlimzhan', '1234'),
    ('Erkeayim', '1234');

INSERT INTO groups(group_name, advisor_id) VALUES 
    ('ПО2308', 1),
    ('SomeGroup', 2);

INSERT INTO student(login, password, group_id) VALUES 
    ('AdaibekovAibolat', '1234', 1),
    ('AlenovMadi', '1234', 1),
    ('ArgynulyAliakbar', '1234', 1),
    ('BergalyAlan', '1234', 1),
    ('AshimkhanAlikhan', '1234', 1),
    ('BalkenAlizhan', '1234', 1),
    ('BatyrgaliyevaCamila', '1234', 1),
    ('BayandinAlmas', '1234', 1),
    ('GramolinaNataliya', '1234', 1),
    ('ZhuvashevAspandiyar', '1234', 1),
    ('ManayAidos', '1234', 1),
    ('MillerCarolina', '1234', 1),
    ('SeidildaulyBakdaulet', '1234', 1),
    ('SmagulovaAruzhan', '1234', 1),
    ('TazhenovAldiyar', '1234', 1),
    ('TokabayevBatyrkhan', '1234', 1),
    ('KhakimAlibek', '1234', 1),
    ('ShaihislamovRamil', '1234', 1),
    ('ShamenovDanial', '1234', 1);

SELECT * FROM student ORDER BY student_id ASC;
SELECT * FROM family_member