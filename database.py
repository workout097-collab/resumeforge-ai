from dotenv import load_dotenv
import os
import psycopg2

load_dotenv(dotenv_path=".env")

DATABASE_URL = os.getenv("DATABASE_URL")

print(DATABASE_URL)

conn = psycopg2.connect(DATABASE_URL)

cursor = conn.cursor()

print("Database connected!")