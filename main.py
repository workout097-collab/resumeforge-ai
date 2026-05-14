from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from openai import OpenAI
from dotenv import load_dotenv
import stripe
import os
import psycopg2
import asyncio
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from fpdf import FPDF
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.filters.command import CommandObject
scheduler = AsyncIOScheduler()
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()
print(os.getenv("STRIPE_SECRET_KEY"))

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
BOT_TOKEN = os.getenv("BOT_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    return conn, cursor

ADMIN_ID = 1128720977


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📝 Create Resume")
        ],
        [
            KeyboardButton(text="💌 Cover Letter")
        ],
        [
            KeyboardButton(text="💎 Premium"),
            KeyboardButton(text="👤 Profile")
        ],
        [
            KeyboardButton(text="🎁 Invite Friends"),
            KeyboardButton(text="❓ Help")

        ]
    ],
    resize_keyboard=True
)



@dp.message(lambda message: message.text == "🎁 Invite Friends")
async def invite_friends(message: Message):
    conn, cursor = get_db()

    telegram_id = message.from_user.id

    invite_link = f"https://t.me/resumeforge_ai_bot?start={telegram_id}"

    await message.answer(
        f"""
🎁 Invite Friends

Invite 3 friends and get FREE Premium 💎

Your personal invite link:

{invite_link}
        """
    )

@dp.message(lambda message: message.text == "💎 Premium")
async def premium(message: Message):

    try:

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],

            line_items=[
                {
                    "price": "price_1TWsnV3bJAkY3z2OPYDLUEMy",
                    "quantity": 1,
                }
            ],

            mode="subscription",

            success_url="https://google.com",
            cancel_url="https://google.com"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💳 Buy Premium",
                        url=checkout_session.url
                    )
                ]
            ]
        )

        await message.answer(
            "💎 Premium Subscription",
            reply_markup=keyboard
        )

    except Exception as e:
        await message.answer(f"Stripe error:\n{e}")



@dp.message(lambda message: message.text == "/admin")
async def admin_panel(message: Message):
    conn, cursor = get_db()

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
async def start(message: Message, command: CommandObject):

    conn, cursor = get_db()

    telegram_id = message.from_user.id

    referrer_id = None

    if referrer_id:

        if int(referrer_id) != telegram_id:
            cursor.execute(
                """
                UPDATE subscriptions
                SET referrals = referrals + 1
                WHERE telegram_id = %s
                """,
                (referrer_id,)
            )

            conn.commit()

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

    cursor.execute(
        """
        INSERT INTO subscriptions (telegram_id)
        VALUES (%s)
        ON CONFLICT (telegram_id) DO NOTHING
        """,
        (telegram_id,)
    )

    conn.commit()

    await message.answer(
        """
    🚀 Welcome to ResumeForge AI

    Create professional resumes and cover letters with AI.

    📄 Features:
    • AI Resume Generator
    • Cover Letters
    • PDF Export
    • Career Assistant
    • Smart Profile Memory

    💎 Free Plan:
    3 resumes per day

    👇 Press "Create Resume" to start
    """,
        reply_markup=main_keyboard
    )



def reset_daily_limits():
        conn, cursor = get_db()
        cursor.execute(
            """
            UPDATE subscriptions
            SET resumes_today = 0
            """
        )

        conn.commit()

        print("✅ Daily limits reset")

async def main():
    scheduler.add_job(
        reset_daily_limits,
        "cron",
        hour=0,
        minute=0
    )

    scheduler.start()

    await dp.start_polling(bot)


@dp.message(lambda message: message.text == "📝 Create Resume")
async def create_resume(message: Message):
    conn, cursor = get_db()

    await message.answer(
        "Tell me what resume you want to create 👇"
    )

@dp.message(lambda message: message.text == "💌 Cover Letter")
async def cover_letter(message: Message):
    conn, cursor = get_db()

    await message.answer(
        "Describe the job and I will create a cover letter ✨"
    )


@dp.message(lambda message: message.text == "👤 Profile")
async def profile_info(message: Message):

    conn, cursor = get_db()

    cursor.execute(
        """
        SELECT is_premium, referrals, resumes_today
        FROM subscriptions
        WHERE telegram_id = %s
        """,
        (message.from_user.id,)
    )

    subscription = cursor.fetchone()

    is_premium = subscription[0]
    referrals = subscription[1]
    resumes_today = subscription[2]

    status = "💎 PREMIUM" if is_premium else "🆓 FREE"

    await message.answer(
        f"""
👤 Your Profile

{status}

📄 Resumes today: {resumes_today}/3

👥 Referrals: {referrals}/3

━━━━━━━━━━

Send your profile like this:

Profession: Python Developer
Skills: FastAPI, PostgreSQL, Docker
Experience: 2 years
Education: Computer Science
"""
    )

@dp.message(lambda message: "Profession:" in message.text)
async def save_profile(message: Message):

    conn, cursor = get_db()

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

@dp.message(lambda message: message.text == "❓ Help")
async def help_menu(message: Message):

    await message.answer(
        """
📌 How to use ResumeForge AI

1. Press 📝 Create Resume
2. Describe your dream job
3. AI creates a professional resume
4. Download PDF instantly

💎 Premium:
• Unlimited resumes
• Better AI quality
• Cover letters
"""
    )




@dp.message()
async def ai_resume(message: Message):
    conn, cursor = get_db()
    await message.answer("⏳ Creating your resume...")

    cursor.execute(
        """
        SELECT resumes_today, is_premium
        FROM subscriptions
        WHERE telegram_id = %s
        """,
        (message.from_user.id,)
    )

    subscription = cursor.fetchone()

    if not subscription:
        cursor.execute(
            """
            INSERT INTO subscriptions (telegram_id)
            VALUES (%s)
            """,
            (message.from_user.id,)
        )

        cursor.execute(
            """
            SELECT resumes_today, is_premium
            FROM subscriptions
            WHERE telegram_id = %s
            """,
            (message.from_user.id,)
        )

        subscription = cursor.fetchone()

        resumes_today = subscription[0]
        is_premium = subscription[1]

        if not is_premium and resumes_today >= 3:
            await message.answer(
                "❌ Free limit reached."
            )

            return

    conn.commit()

    resumes_today = subscription[0]
    is_premium = subscription[1]

    if not is_premium and resumes_today >= 3:
        await message.answer(
            "❌ Free limit reached."
        )

        return

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
    Profession: {profile[0] if profile else "Unknown"}
    Skills: {profile[1] if profile else "Unknown"}
    Experience: {profile[2] if profile else "Unknown"}
    Education: {profile[3] if profile else "Unknown"}

    Create professional resumes and career responses.
    """
            },
            {
                "role": "user",
                "content": f"""
    {user_text}

    Please generate a complete professional resume.
    """
            }
        ]

    )
    ai_answer = response.choices[0].message.content

    cursor.execute(
        """
        UPDATE subscriptions
        SET resumes_today = resumes_today + 1
        WHERE telegram_id = %s
        """,
        (message.from_user.id,)
    )

    conn.commit()

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

    # Background Header
    pdf.set_fill_color(25, 35, 60)
    pdf.rect(0, 0, 210, 35, "F")

    # Title
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 24)

    pdf.set_xy(10, 10)

    pdf.cell(0, 10, "Professional Resume")

    # Subtitle
    pdf.set_font("Arial", "", 12)

    pdf.set_xy(10, 20)

    pdf.cell(0, 10, "Generated by ResumeForge AI")

    # Reset text color
    pdf.set_text_color(40, 40, 40)

    pdf.ln(30)

    pdf.ln(10)

    pdf.set_font("Arial", size=12)

    pdf.set_text_color(40, 40, 40)

    clean_text = ai_answer.encode("latin-1", "replace").decode("latin-1")



    pdf.multi_cell(
        0,
        8,
        clean_text
    )

    pdf_file = "resume.pdf"

    pdf.output(pdf_file)

    document = FSInputFile(pdf_file)

    await message.answer_document(
        document=document,
        caption="📄 Your resume is ready!"
    )


if __name__ == "__main__":
    asyncio.run(main())