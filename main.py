from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.command import CommandObject
from translations import translations
from database import set_language_db, get_language_db, get_db
from openai import OpenAI
from dotenv import load_dotenv
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import stripe
import os
import psycopg2
import asyncio
from fpdf import FPDF
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "DejaVuSans.ttf")
load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    return conn, cursor

ADMIN_ID = 1128720977

# ---------------------- СТАРТ І ВИБІР МОВИ ----------------------
@dp.message(CommandStart())
async def start_cmd(message: Message, command: CommandObject):
    conn, cursor = get_db()
    telegram_id = message.from_user.id

    args = command.args
    referrer_id = int(args) if args and args.isdigit() else None
    if referrer_id and referrer_id != telegram_id:
        cursor.execute("UPDATE subscriptions SET referrals = referrals + 1 WHERE telegram_id = %s", (referrer_id,))
        conn.commit()

    username = message.from_user.username
    cursor.execute("INSERT INTO users (telegram_id, username) VALUES (%s, %s) ON CONFLICT (telegram_id) DO NOTHING", (telegram_id, username))
    cursor.execute("INSERT INTO subscriptions (telegram_id) VALUES (%s) ON CONFLICT (telegram_id) DO NOTHING", (telegram_id,))
    conn.commit()

    language_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🇬🇧 English"), KeyboardButton(text="🇺🇦 Українська")]], resize_keyboard=True)
    await message.answer("🌍 Choose your language / Оберіть мову:", reply_markup=language_keyboard)

@dp.message(lambda message: message.text == "🇬🇧 English")
async def set_english(message: Message):
    user_id = message.from_user.id
    set_language_db(user_id, "en")
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Create Resume")],
        [KeyboardButton(text="🚀 Create Resume (step by step)")],
        [KeyboardButton(text="💌 Cover Letter")],
        [KeyboardButton(text="💎 Premium"), KeyboardButton(text="👤 Profile")],
        [KeyboardButton(text="🎁 Invite Friends"), KeyboardButton(text="❓ Help")],
        [KeyboardButton(text="🌍 Change Language")]
    ], resize_keyboard=True)
    await message.answer("🇬🇧 English enabled!\n\n🚀 Welcome to ResumeForge AI\n\nCreate professional resumes and cover letters with AI.\n\n💎 Free Plan: 3 resumes per day\n\n👇 Press a button to start", reply_markup=keyboard)

@dp.message(lambda message: message.text in ["🌍 Змінити мову", "🌍 Change Language"])
async def change_language(message: Message):
    language_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🇬🇧 English"), KeyboardButton(text="🇺🇦 Українська")]], resize_keyboard=True)
    await message.answer("🌍 Choose your language / Оберіть мову:", reply_markup=language_keyboard)

@dp.message(lambda message: message.text == "🇺🇦 Українська")
async def set_ukrainian(message: Message):
    user_id = message.from_user.id
    set_language_db(user_id, "ua")
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Створити резюме")],
        [KeyboardButton(text="🚀 Створити резюме (покроково)")],
        [KeyboardButton(text="💌 Супровідний лист")],
        [KeyboardButton(text="💎 Преміум"), KeyboardButton(text="👤 Профіль")],
        [KeyboardButton(text="🎁 Запросити друзів"), KeyboardButton(text="❓ Допомога")],
        [KeyboardButton(text="🌍 Змінити мову")]
    ], resize_keyboard=True)
    await message.answer("🇺🇦 Українська увімкнена!\n\n🚀 Ласкаво просимо до ResumeForge AI\n\nСтворюй професійні резюме та супровідні листи з AI.\n\n💎 Безкоштовний план: 3 резюме на день\n\n👇 Натисни кнопку щоб почати", reply_markup=keyboard)

# ---------------------- ОСНОВНІ КНОПКИ (ОКРЕМІ ХЕНДЛЕРИ) ----------------------
@dp.message(lambda message: message.text == "📝 Створити резюме")
async def create_resume_ua(message: Message):
    await message.answer("Розкажи про роботу, яку хочеш (наприклад: 'Python розробник з досвідом 2 роки'):")

@dp.message(lambda message: message.text == "📝 Create Resume")
async def create_resume_en(message: Message):
    await message.answer("Tell me about the job you want (e.g., 'Python Developer with 2 years experience'):")

# ПОКРОКОВИЙ МАЙСТЕР – ОКРЕМІ ХЕНДЛЕРИ ДЛЯ УКР/АНГЛ
@dp.message(lambda message: message.text == "🚀 Створити резюме (покроково)")
async def start_wizard_ua(message: Message, state: FSMContext):
    await state.set_state(ResumeForm.profession)
    await message.answer("🚀 Почнемо створювати резюме крок за кроком!\n\n1️⃣ Напиши свою **професію** або **назву посади** (наприклад: 'Python Backend Developer'):")

@dp.message(lambda message: message.text == "🚀 Create Resume (step by step)")
async def start_wizard_en(message: Message, state: FSMContext):
    await state.set_state(ResumeForm.profession)
    await message.answer("🚀 Let's create your resume step by step!\n\n1️⃣ Write your **profession** or **job title** (e.g., 'Python Backend Developer'):")

# FSM – з урахуванням мови (для подальших кроків)
class ResumeForm(StatesGroup):
    profession = State()
    skills = State()
    experience = State()
    last_job = State()
    education = State()

@dp.message(ResumeForm.profession)
async def process_profession(message: Message, state: FSMContext):
    await state.update_data(profession=message.text)
    await state.set_state(ResumeForm.skills)
    user_lang = get_language_db(message.from_user.id)
    if user_lang == "en":
        await message.answer("2️⃣ List your **skills** separated by commas\n(e.g., 'Python, Django, PostgreSQL, Docker'):")
    else:
        await message.answer("2️⃣ Перелічи свої **навички** через кому\n(наприклад: 'Python, Django, PostgreSQL, Docker'):")

@dp.message(ResumeForm.skills)
async def process_skills(message: Message, state: FSMContext):
    await state.update_data(skills=message.text)
    await state.set_state(ResumeForm.experience)
    user_lang = get_language_db(message.from_user.id)
    if user_lang == "en":
        await message.answer("3️⃣ How many years of **experience** in this field?\n(e.g., '3 years' or 'No experience'):")
    else:
        await message.answer("3️⃣ Скільки років **досвіду** в цій сфері?\n(наприклад: '3 роки' або 'Без досвіду'):")

@dp.message(ResumeForm.experience)
async def process_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await state.set_state(ResumeForm.last_job)
    user_lang = get_language_db(message.from_user.id)
    if user_lang == "en":
        await message.answer("4️⃣ Where did you work **most recently**?\n(e.g., 'Company XYZ, Python Developer' or 'Freelance'):")
    else:
        await message.answer("4️⃣ Де ти працював **останнім часом**?\n(наприклад: 'ТОВ Рога і Копита, Python Developer' або 'Фріланс'):")

@dp.message(ResumeForm.last_job)
async def process_last_job(message: Message, state: FSMContext):
    await state.update_data(last_job=message.text)
    await state.set_state(ResumeForm.education)
    user_lang = get_language_db(message.from_user.id)
    if user_lang == "en":
        await message.answer("5️⃣ What is your **education**?\n(e.g., 'University of Kyiv, Computer Science' or 'Self-taught'):")
    else:
        await message.answer("5️⃣ Яка в тебе **освіта**?\n(наприклад: 'КНУ ім. Шевченка, Комп'ютерні науки' або 'Самоук'):")

@dp.message(ResumeForm.education)
async def process_education(message: Message, state: FSMContext):
    await state.update_data(education=message.text)
    data = await state.get_data()
    user_text = f"""Profession: {data['profession']}\nSkills: {data['skills']}\nExperience: {data['experience']}\nLast job: {data['last_job']}\nEducation: {data['education']}"""
    conn, cursor = get_db()
    cursor.execute("""INSERT INTO profiles (telegram_id, profession, skills, experience, education) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (telegram_id) DO UPDATE SET profession = EXCLUDED.profession, skills = EXCLUDED.skills, experience = EXCLUDED.experience, education = EXCLUDED.education""", (message.from_user.id, data['profession'], data['skills'], data['experience'], data['education']))
    conn.commit()
    await state.clear()
    user_lang = get_language_db(message.from_user.id)
    await message.answer("⏳ Creating your resume based on your answers..." if user_lang == "en" else "⏳ Створюю твоє резюме на основі відповідей...")
    # Виклик GPT
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": f"You are a professional resume writer. Create an ATS-optimized resume based on the data:\n{user_text}\nLanguage: {'English' if user_lang == 'en' else 'Ukrainian'}"},
            {"role": "user", "content": "Create a professional resume."}
        ]
    )
    ai_answer = response.choices[0].message.content

    # Генерація PDF з правильним шрифтом
    pdf = FPDF()
    pdf.add_page()
    # Додаємо шрифт (звичайний і жирний)
    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.add_font("DejaVu", "B", FONT_PATH, uni=True)  # важливо для жирного
    pdf.set_font("DejaVu", "", 12)
    pdf.set_fill_color(25, 35, 60)
    pdf.rect(0, 0, 210, 35, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B", 24)
    pdf.set_xy(10, 10)
    pdf.cell(0, 10, "Professional Resume")
    pdf.set_font("DejaVu", "", 12)
    pdf.set_xy(10, 20)
    pdf.cell(0, 10, "Generated by ResumeForge AI")
    pdf.set_text_color(40, 40, 40)
    pdf.ln(30)
    pdf.set_font("DejaVu", "", 12)
    pdf.multi_cell(0, 8, ai_answer)
    pdf.output("resume.pdf")
    docx_file = generate_docx(ai_answer, "resume.docx")
    await message.answer_document(document=FSInputFile("resume.pdf"), caption="📄 Your resume (PDF) is ready!" if user_lang == "en" else "📄 Твоє резюме (PDF) готове!")
    await message.answer_document(document=FSInputFile(docx_file), caption="📝 Your resume (DOCX) — editable in Word!" if user_lang == "en" else "📝 Твоє резюме (DOCX) — можна редагувати у Word!")

@dp.message(Command("cancel"))
async def cancel_wizard(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Resume creation cancelled. Press /start to begin again." if get_language_db(message.from_user.id) == "en" else "❌ Створення резюме скасовано. Натисни /start, щоб почати заново.")

# ---------------------- ІНШІ КНОПКИ ----------------------
@dp.message(lambda message: message.text in ["👤 Профіль", "👤 Profile"])
async def profile_info(message: Message):
    user_lang = get_language_db(message.from_user.id)
    conn, cursor = get_db()
    try:
        cursor.execute("SELECT is_premium, referrals, resumes_today FROM subscriptions WHERE telegram_id = %s", (message.from_user.id,))
        subscription = cursor.fetchone()
        if subscription:
            is_premium, referrals, resumes_today = subscription
            status = "💎 PREMIUM" if is_premium else "🆓 FREE"
            if user_lang == "ua":
                text = f"""👤 Твій Профіль\n\n{status}\n\n📄 Резюме сьогодні: {resumes_today}/3\n\n👥 Запрошення: {referrals}/3\n\n━━━━━━━━━━\n\nНадішли свій профіль у такому форматі:\n\nПрофесія: Python Developer\nНавички: FastAPI, PostgreSQL, Docker\nДосвід: 2 роки\nОсвіта: Комп'ютерні науки"""
            else:
                text = f"""👤 Your Profile\n\n{status}\n\n📄 Resumes today: {resumes_today}/3\n\n👥 Referrals: {referrals}/3\n\n━━━━━━━━━━\n\nSend your profile in this format:\n\nProfession: Python Developer\nSkills: FastAPI, PostgreSQL, Docker\nExperience: 2 years\nEducation: Computer Science"""
            await message.answer(text)
        else:
            await message.answer("❌ Profile not found" if user_lang == "en" else "❌ Профіль не знайдено")
    finally:
        cursor.close()
        conn.close()

@dp.message(lambda message: message.text in ["❓ Допомога", "❓ Help"])
async def help_menu(message: Message):
    user_lang = get_language_db(message.from_user.id)
    if user_lang == "ua":
        text = """📌 Як користуватися ResumeForge AI\n\n1. Натисни 📝 Створити резюме\n2. Опиши свою бажану роботу\n3. AI створить професійне резюме\n4. Завантаж PDF миттєво\n\n💎 Преміум:\n• Безліміт резюме\n• Краща якість AI\n• Супровідні листи"""
    else:
        text = """📌 How to use ResumeForge AI\n\n1. Press 📝 Create Resume\n2. Describe your desired job\n3. AI will create a professional resume\n4. Download PDF instantly\n\n💎 Premium:\n• Unlimited resumes\n• Better AI quality\n• Cover letters"""
    await message.answer(text)

@dp.message(lambda message: message.text == "🎁 Запросити друзів")
async def invite_friends_ua(message: Message):
    telegram_id = message.from_user.id
    invite_link = f"https://t.me/resumeforge_ai_bot?start={telegram_id}"
    await message.answer(f"🎁 Запроси друзів\n\nЗапроси 3 друзів та отримай БЕЗКОШТОВНИЙ Преміум 💎\n\nТвоє персональне посилання:\n\n{invite_link}")

@dp.message(lambda message: message.text == "🎁 Invite Friends")
async def invite_friends_en(message: Message):
    telegram_id = message.from_user.id
    invite_link = f"https://t.me/resumeforge_ai_bot?start={telegram_id}"
    await message.answer(f"🎁 Invite Friends\n\nInvite 3 friends and get FREE Premium 💎\n\nYour personal link:\n\n{invite_link}")

@dp.message(lambda message: message.text == "💎 Преміум")
async def premium_ua(message: Message):
    try:
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=str(message.from_user.id),
            payment_method_types=["card"],
            line_items=[{"price": "price_1TZC5nQQBexcBmcKUUidsJZs", "quantity": 1}],
            mode="subscription",
            success_url="https://t.me/resumeforge_ai_bot",
            cancel_url="https://t.me/resumeforge_ai_bot"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Купити Преміум", url=checkout_session.url)]])
        await message.answer("💎 Преміум підписка", reply_markup=keyboard)
    except Exception as e:
        await message.answer(f"Stripe error:\n{e}")

@dp.message(lambda message: message.text == "💎 Premium")
async def premium_en(message: Message):
    try:
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=str(message.from_user.id),
            payment_method_types=["card"],
            line_items=[{"price": "price_1TZC5nQQBexcBmcKUUidsJZs", "quantity": 1}],
            mode="subscription",
            success_url="https://t.me/resumeforge_ai_bot",
            cancel_url="https://t.me/resumeforge_ai_bot"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Buy Premium", url=checkout_session.url)]])
        await message.answer("💎 Premium subscription", reply_markup=keyboard)
    except Exception as e:
        await message.answer(f"Stripe error:\n{e}")

@dp.message(lambda message: message.text == "💌 Супровідний лист")
async def cover_letter_ua(message: Message):
    await message.answer("📝 Опиши вакансію (посада, вимоги, компанія), і я створю супровідний лист.\n\nНаприклад:\n`Вакансія: Python Developer в компанії Tech Corp. Вимоги: досвід 2+ роки, знання Django, PostgreSQL. Мої навички: Python, Django, 2 роки досвіду.`")

@dp.message(lambda message: message.text == "💌 Cover Letter")
async def cover_letter_en(message: Message):
    await message.answer("📝 Describe the job (position, requirements, company), and I'll create a cover letter.\n\nExample:\n`Job: Python Developer at Tech Corp. Requirements: 2+ years experience, Django, PostgreSQL. My skills: Python, Django, 2 years experience.`")

# ---------------------- ШВИДКЕ РЕЗЮМЕ ----------------------
@dp.message(lambda message: message.text.lower().startswith(("швидке резюме", "швидко резюме", "quick resume", "quick")))
async def quick_resume(message: Message):
    user_text = message.text.replace("швидке резюме", "").replace("швидко резюме", "").replace("quick resume", "").replace("quick", "").strip()
    if not user_text:
        await message.answer("✍️ Напиши коротко про себе, наприклад:\n\n🇺🇦 `швидке резюме: Python developer, 2 роки, Django, PostgreSQL`\n\n🇬🇧 `quick resume: Python developer, 2 years, Django, PostgreSQL`\n\nАбо просто: `Junior Python developer`")
        return
    await message.answer(f"⏳ Creating your resume for: {user_text}...")
    user_lang = get_language_db(message.from_user.id)
    if user_lang == "ua":
        system_prompt = f"Ти професійний автор резюме. Створи професійне резюме на основі опису користувача.\nВикористовуй УКРАЇНСЬКУ МОВУ для всього резюме.\n\nОПИС КОРИСТУВАЧА: {user_text}\n\n**ВАЖЛИВО:**\n- Всі заголовки: 'Досвід роботи', 'Навички', 'Освіта', 'Про себе'\n- Не використовуй таблиці, колонки, графіку\n- Додай 1-2 досягнення з цифрами\n- Мова: українська"
    else:
        system_prompt = f"You are a professional resume writer. Create a complete, professional resume based on the user's description.\n\nUSER DESCRIPTION: {user_text}\n\n**IMPORTANT GUIDELINES:**\n- Use a modern, professional tone\n- Add realistic skills relevant to the description\n- Use standard ATS-friendly headings: 'Work Experience', 'Skills', 'Education', 'Summary'\n- Do NOT use tables, columns, or graphics\n- Add 1-2 quantifiable achievements\n- Language: English"
    try:
        response = client.chat.completions.create(model="gpt-4.1-mini", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "Create a professional resume."}], timeout=30.0)
        ai_answer = response.choices[0].message.content
    except Exception as e:
        await message.answer(f"❌ AI error: {str(e)}\nPlease try again later.")
        return
    docx_file = generate_docx(ai_answer, "resume.docx")
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.add_font("DejaVu", "B", FONT_PATH, uni=True)
    pdf.set_font("DejaVu", "", 12)
    pdf.set_font("DejaVu", "B", 20)
    pdf.cell(0, 10, "Professional Resume", ln=True, align='C')
    pdf.set_font("DejaVu", "I", 10)
    pdf.cell(0, 10, "Generated by ResumeForge AI", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("DejaVu", "", 12)
    for line in ai_answer.split('\n'):
        if isinstance(line, bytes):
            line = line.decode('utf-8')
        line = line.replace('\u2013', '-').replace('\u2014', '-')
        while len(line) > 80:
            pdf.cell(0, 6, line[:80], ln=True)
            line = line[80:]
        pdf.cell(0, 6, line, ln=True)
        pdf.ln(2)
    pdf.output("resume.pdf")
    await message.answer_document(document=FSInputFile("resume.pdf"), caption="📄 Your resume (PDF) is ready!")
    await message.answer_document(document=FSInputFile(docx_file), caption="📝 Your resume (DOCX) — editable in Word!")

# ---------------------- ДОПОМІЖНІ ФУНКЦІЇ ----------------------
def generate_docx(ai_answer: str, filename: str = "resume.docx"):
    document = Document()
    title = document.add_heading('Professional Resume', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = document.add_heading('Generated by ResumeForge AI', 2)
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for paragraph_text in ai_answer.split('\n\n'):
        if paragraph_text.strip():
            p = document.add_paragraph()
            p.add_run(paragraph_text.strip())
    document.save(filename)
    return filename

# ---------------------- ОБРОБНИК ЗВИЧАЙНИХ ТЕКСТОВИХ ПОВІДОМЛЕНЬ (ДЛЯ СТВОРЕННЯ РЕЗЮМЕ) ----------------------
@dp.message()
async def handle_text(message: Message, state: FSMContext):
    if await state.get_state() is not None:
        return
    user_lang = get_language_db(message.from_user.id)
    # Якщо це опис для cover letter
    if message.text.lower().startswith(("вакансія:", "job:", "cover letter for")):
        await message.answer("⏳ Creating cover letter..." if user_lang == "en" else "⏳ Створюю супровідний лист...")
        if user_lang == "ua":
            prompt = f"Напиши професійний супровідний лист на основі опису:\n{message.text}\nМова: українська"
        else:
            prompt = f"Write a professional cover letter based on:\n{message.text}\nLanguage: English"
        try:
            response = client.chat.completions.create(model="gpt-4.1-mini", messages=[{"role": "user", "content": prompt}], timeout=30.0)
            letter = response.choices[0].message.content
            await message.answer(f"📄 *Cover Letter*\n\n{letter}" if user_lang == "en" else f"📄 *Супровідний лист*\n\n{letter}", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")
        return

    # Інакше – створюємо резюме
    if message.text and not message.text.startswith('/'):
        conn, cursor = get_db()
        cursor.execute("SELECT resumes_today, is_premium FROM subscriptions WHERE telegram_id = %s", (message.from_user.id,))
        subscription = cursor.fetchone()
        if not subscription:
            cursor.execute("INSERT INTO subscriptions (telegram_id) VALUES (%s)", (message.from_user.id,))
            conn.commit()
            cursor.execute("SELECT resumes_today, is_premium FROM subscriptions WHERE telegram_id = %s", (message.from_user.id,))
            subscription = cursor.fetchone()
        resumes_today, is_premium = subscription
        if not is_premium and resumes_today >= 3:
            await message.answer("❌ Free limit reached. Buy Premium for unlimited." if user_lang == "en" else "❌ Безкоштовний ліміт вичерпано. Купи Premium.")
            return
        await message.answer("⏳ Creating your resume..." if user_lang == "en" else "⏳ Створюю твоє резюме...")
        cursor.execute("SELECT profession, skills, experience, education FROM profiles WHERE telegram_id = %s", (message.from_user.id,))
        profile = cursor.fetchone()
        if user_lang == "ua":
            prompt = f"Створи професійне резюме на основі: {message.text}"
            if profile and any(profile):
                prompt += f"\n\nДодаткова інформація з профілю:\nПрофесія: {profile[0]}\nНавички: {profile[1]}\nДосвід: {profile[2]}\nОсвіта: {profile[3]}"
        else:
            prompt = f"Create a professional resume based on: {message.text}"
            if profile and any(profile):
                prompt += f"\n\nAdditional profile info:\nProfession: {profile[0]}\nSkills: {profile[1]}\nExperience: {profile[2]}\nEducation: {profile[3]}"
        try:
            response = client.chat.completions.create(model="gpt-4.1-mini", messages=[{"role": "user", "content": prompt}], timeout=30.0)
            ai_answer = response.choices[0].message.content
            cursor.execute("UPDATE subscriptions SET resumes_today = resumes_today + 1 WHERE telegram_id = %s", (message.from_user.id,))
            conn.commit()
            docx_file = generate_docx(ai_answer, "resume.docx")
            pdf = FPDF()
            pdf.add_page()
            pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
            pdf.add_font("DejaVu", "B", FONT_PATH, uni=True)
            pdf.set_font("DejaVu", "", 12)
            pdf.set_font("DejaVu", "B", 20)
            pdf.cell(0, 10, "Professional Resume", ln=True, align='C')
            pdf.set_font("DejaVu", "I", 10)
            pdf.cell(0, 10, "Generated by ResumeForge AI", ln=True, align='C')
            pdf.ln(10)
            pdf.set_font("DejaVu", "", 12)
            for line in ai_answer.split('\n'):
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                while len(line) > 80:
                    pdf.cell(0, 6, line[:80], ln=True)
                    line = line[80:]
                pdf.cell(0, 6, line, ln=True)
                pdf.ln(2)
            pdf.output("resume.pdf")
            await message.answer_document(document=FSInputFile("resume.pdf"), caption="📄 Your resume (PDF) is ready!" if user_lang == "en" else "📄 Твоє резюме (PDF) готове!")
            await message.answer_document(document=FSInputFile(docx_file), caption="📝 Your resume (DOCX) — editable in Word!" if user_lang == "en" else "📝 Твоє резюме (DOCX) — можна редагувати у Word!")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

# ---------------------- АДМІН І ЗАПУСК ----------------------
@dp.message(Command("activate"))
async def activate_premium(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        conn, cursor = get_db()
        cursor.execute("UPDATE subscriptions SET is_premium = true WHERE telegram_id = %s", (user_id,))
        conn.commit()
        await message.answer(f"✅ Premium активовано для {user_id}")
    except:
        await message.answer("❌ Формат: /activate user_id")

@dp.message(lambda message: message.text == "/admin")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn, cursor = get_db()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages")
    messages_count = cursor.fetchone()[0]
    await message.answer(f"📊 Admin Panel\n\n👤 Users: {users_count}\n💬 Messages: {messages_count}")

def reset_daily_limits():
    conn, cursor = get_db()
    cursor.execute("UPDATE subscriptions SET resumes_today = 0")
    conn.commit()
    print("✅ Daily limits reset")

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(reset_daily_limits, "cron", hour=0, minute=0)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())