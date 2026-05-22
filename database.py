from dotenv import load_dotenv
import os
import psycopg2

load_dotenv(dotenv_path=".env")

DATABASE_URL = os.getenv("DATABASE_URL")

print(DATABASE_URL)


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    return conn, cursor


def init_db():
    conn, cursor = get_db()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_languages (
        user_id BIGINT PRIMARY KEY,
        language TEXT DEFAULT 'ua'
    )
    """)

    conn.commit()
    conn.close()


def set_language_db(user_id, language):
    conn, cursor = get_db()
    cursor.execute(
        "INSERT INTO user_languages (user_id, language) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET language = EXCLUDED.language",
        (user_id, language)
    )
    conn.commit()
    conn.close()


def get_language_db(user_id):
    conn, cursor = get_db()
    cursor.execute("SELECT language FROM user_languages WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "ua"