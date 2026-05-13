from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from openai import OpenAI
from dotenv import load_dotenv
import os
import psycopg2
import asyncio
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from fpdf import FPDF
from aiogram.types import FSInputFile


load_dotenv(dotenv_path=".env")
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
BOT_TOKEN = os.getenv("BOT_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

ADMIN_ID = 1128720977

cursor = conn.cursor()

dp = Dispatcher()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📝 Create Resume")
        ],
        [
            KeyboardButton(text="💌 Cover Letter")
        ],
        [
            KeyboardButton(text="⭐ Premium"),
            KeyboardButton(text="👤 Profile")
        ]
    ],
    resize_keyboard=True
)

@dp.message(lambda message: message.text == "/admin")
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages")
    messages_count = cursor.fetchone()[0]

    await message.answer(
        f"""
📊 Admin Panel

👤 Users: {users_count}
💬 Messages: {messages_count}
"""
    )


@dp.message(CommandStart())
async def start(message: Message):

    telegram_id = message.from_user.id
    username = message.from_user.username

    cursor.execute(
        """
        INSERT INTO users (telegram_id, username)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO NOTHING
        """,
        (telegram_id, username)
    )

    conn.commit()

    await message.answer(
        "Welcome to ResumeForge AI 🚀",
        reply_markup=main_keyboard
    )

async def main():
    await dp.start_polling(bot)

@dp.message(lambda message: message.text == "📝 Create Resume")
async def create_resume(message: Message):

    await message.answer(
        "Tell me what resume you want to create 👇"
    )

@dp.message(lambda message: message.text == "💌 Cover Letter")
async def cover_letter(message: Message):

    await message.answer(
        "Describe the job and I will create a cover letter ✨"
    )

@dp.message(lambda message: message.text == "⭐ Premium")
async def premium(message: Message):

    await message.answer(
        """
⭐ Premium Plan

• Unlimited resumes
• Better AI quality
• PDF export
• Cover letters
• Resume memory

Price: $5/month
"""
    )


@dp.message(lambda message: message.text == "👤 Profile")
async def profile_info(message: Message):

    await message.answer(
        """
Send your profile like this:

Profession: Python Developer
Skills: FastAPI, PostgreSQL, Docker
Experience: 2 years
Education: Computer Science
"""
    )

@dp.message(lambda message: "Profession:" in message.text)
async def save_profile(message: Message):

    text = message.text

    lines = text.split("\n")

    profession = lines[0].replace("Profession:", "").strip()
    skills = lines[1].replace("Skills:", "").strip()
    experience = lines[2].replace("Experience:", "").strip()
    education = lines[3].replace("Education:", "").strip()

    cursor.execute(
        """
        INSERT INTO profiles (
            telegram_id,
            profession,
            skills,
            experience,
            education
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (telegram_id)
        DO UPDATE SET
            profession = EXCLUDED.profession,
            skills = EXCLUDED.skills,
            experience = EXCLUDED.experience,
            education = EXCLUDED.education
        """,
        (
            message.from_user.id,
            profession,
            skills,
            experience,
            education
        )
    )

    conn.commit()

    await message.answer(
        "✅ Profile saved!"
    )






@dp.message()
async def ai_resume(message: Message):
    await message.answer("⏳ Creating your resume...")

    conn.commit()

    user_text = message.text

    cursor.execute(
        """
        SELECT profession, skills,
        experience, education
        FROM profiles
        WHERE telegram_id = %s
        """,
        (message.from_user.id,)
    )

    profile = cursor.fetchone()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": f"""
    You are a professional resume writer.

    User profile:

    Profession: {profile[0] if profile else "Unknown"}
    Skills: {profile[1] if profile else "Unknown"}
    Experience: {profile[2] if profile else "Unknown"}
    Education: {profile[3] if profile else "Unknown"}

    Create professional resumes and career responses.
    """
            },
            {
                "role": "user",
                "content": user_text
            }
        ]
    )

    ai_answer = response.choices[0].message.content

    cursor.execute(
        """
        INSERT INTO messages (
            telegram_id,
            user_message,
            bot_response
        )
        VALUES (%s, %s, %s)
        """,
        (
            message.from_user.id,
            user_text,
            ai_answer
        )
    )

    conn.commit()

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", size=12)

    clean_text = ai_answer.encode("latin-1", "replace").decode("latin-1")

    pdf.multi_cell(0, 10, clean_text)

    pdf_file = "resume.pdf"

    pdf.output(pdf_file)

    document = FSInputFile(pdf_file)

    await message.answer_document(
        document=document,
        caption="📄 Your resume is ready!"
    )

if __name__ == "__main__":
    asyncio.run(main())