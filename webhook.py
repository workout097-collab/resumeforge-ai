from fastapi import FastAPI, Request
import stripe
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")  # Отримай у Stripe Dashboard

DATABASE_URL = os.getenv("DATABASE_URL")


@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        return {"error": str(e)}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        telegram_id = session.get("client_reference_id")

        if telegram_id:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE subscriptions SET is_premium = true WHERE telegram_id = %s",
                (telegram_id,)
            )
            conn.commit()
            conn.close()
            print(f"✅ Premium активовано для {telegram_id}")

    return {"status": "ok"}