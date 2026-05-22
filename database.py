from dotenv import load_dotenv
import os
import psycopg2

load_dotenv(dotenv_path=".env")

DATABASE_URL = os.getenv("DATABASE_URL")

print(DATABASE_URL)

conn = psycopg2.connect(DATABASE_URL)

cursor = conn.cursor()

print("Database connected!")

def set_language_db(user_id, language):
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_languages (user_id, language) VALUES (?, ?)",
        (user_id, language)
    )
    conn.commit()
    conn.close()

def get_language_db(user_id):
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM user_languages WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "ua"