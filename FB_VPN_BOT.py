import os
import psycopg2
import requests
from flask import Flask, request, jsonify
from datetime import datetime
import uuid

app = Flask(__name__)

# --- Environment Variables ---
# Facebook ပေးမည့် Token များ (Render တွင် သွားထည့်ရပါမည်)
FB_PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN', 'YOUR_PAGE_ACCESS_TOKEN')
FB_VERIFY_TOKEN = os.environ.get('FB_VERIFY_TOKEN', 'happyhive_webhook_secret_123')

# Database (Telegram Bot နှင့် အတူတူပင် ဖြစ်သည်)
DB_URL = os.environ.get('DATABASE_URL')

# Telegram Admin အချက်အလက်များ (Messenger မှ ပြေစာများကို Telegram သို့ ပို့ရန်)
TELEGRAM_BOT_TOKEN = "8633829411:AAEdkGteDuDt4fjJABAIR7jIMLVIPQ1PPhA"
ADMIN_IDS = [1656832105]

# --- Database Connection ---
def get_db():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    return conn

# --- Helper: Save User to DB ---
def get_or_create_fb_user(sender_psid, username="FB_User"):
    # Facebook ရဲ့ ID (PSID) ကလည်း ဂဏန်းရှည်ကြီးဖြစ်လို့ Telegram ID column ထဲမှာပဲ ထည့်မှတ်လို့ရပါတယ်
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT unique_id FROM users WHERE telegram_id=%s", (sender_psid,))
    user = c.fetchone()
    if not user:
        unique_id = str(uuid.uuid4())[:8].upper()
        c.execute("INSERT INTO users (telegram_id, unique_id, is_trial_used, username, referral_reward_claimed, has_rated) VALUES (%s, %s, 0, %s, 0, 0)", 
                  (sender_psid, unique_id, username))
    conn.close()

# --- Helper: Send Message via Facebook Graph API ---
def send_message(recipient_id, message_text, quick_replies=None):
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    if quick_replies:
        data["message"]["quick_replies"] = quick_replies

    response = requests.post("https://graph.facebook.com/v18.0/me/messages", params=params, headers=headers, json=data)
    return response.json()

# --- Helper: Notify Telegram Admins ---
def notify_admin_on_telegram(text):
    for admin_id in ADMIN_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": admin_id, "text": text, "parse_mode": "Markdown"})

# --- Facebook Webhook Verification ---
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == FB_VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            return "Forbidden", 403
    return "Hello from FB VPN Bot", 200

# --- Handle Incoming Messenger Messages ---
@app.route('/webhook', methods=['POST'])
def handle_messages():
    body = request.json

    if body.get("object") == "page":
        for entry in body.get("entry", []):
            for webhook_event in entry.get("messaging", []):
                sender_psid = webhook_event["sender"]["id"]
                
                # User အသစ်ဆိုရင် Database ထဲ မှတ်မယ်
                get_or_create_fb_user(sender_psid)

                if "message" in webhook_event:
                    handle_postback_or_message(sender_psid, webhook_event["message"])
                elif "postback" in webhook_event:
                    # ခလုတ်နှိပ်တဲ့ လုပ်ဆောင်ချက်များ
                    pass

        return "EVENT_RECEIVED", 200
    return "Not Found", 404

def handle_postback_or_message(sender_psid, message):
    text = message.get("text", "").lower()
    
    # 📸 Screenshot ပို့လာလျှင် (Attachment ပါလျှင်)
    if "attachments" in message:
        for attachment in message["attachments"]:
            if attachment["type"] == "image":
                img_url = attachment["payload"]["url"]
                send_message(sender_psid, "✅ ငွေလွှဲပြေစာ လက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးပေးနေပါသည်။")
                # Telegram Admin ဆီကို ပို့ပေးမယ်
                notify_admin_on_telegram(f"🔔 **FB Messenger မှ ငွေသွင်းမှုအသစ်!**\n\nUser ID: `{sender_psid}`\n\nပြေစာပုံကြည့်ရန်: [Click Here]({img_url})")
                return

    # Quick Reply (ခလုတ်) ကနေ နှိပ်လိုက်တဲ့ Data ကို ဖမ်းခြင်း
    payload = None
    if "quick_reply" in message:
        payload = message["quick_reply"]["payload"]

    # --- Main Menu ---
    if text in ["hi", "hello", "start", "menu"] or payload == "BACK_TO_MAIN":
        welcome_msg = "🌟 Welcome to HappyHive VPN! 🌟\nအောက်ပါ ဝန်ဆောင်မှုများကို ရွေးချယ်နိုင်ပါသည်။ 👇"
        quick_replies = [
            {"content_type": "text", "title": "🎁 Free Trial", "payload": "FREE_TRIAL"},
            {"content_type": "text", "title": "🛒 Plan ဝယ်ရန်", "payload": "BUY_PLAN"},
            {"content_type": "text", "title": "👤 Plan/Data စစ်ရန်", "payload": "MY_PLAN"}
        ]
        send_message(sender_psid, welcome_msg, quick_replies)
        
    elif payload == "BUY_PLAN":
        msg = "🛒 ဝယ်ယူလိုသော Plan ကို ရွေးချယ်ပါ (KPay: 09799844344 သို့ ငွေလွှဲပြီး Screenshot ပို့ပေးပါ)"
        quick_replies = [
            {"content_type": "text", "title": "30GB (၂၀၀၀ကျပ်)", "payload": "PLAN_30GB"},
            {"content_type": "text", "title": "50GB (၃၀၀၀ကျပ်)", "payload": "PLAN_50GB"},
            {"content_type": "text", "title": "100GB (၄၀၀၀ကျပ်)", "payload": "PLAN_100GB"},
            {"content_type": "text", "title": "🔙 နောက်သို့", "payload": "BACK_TO_MAIN"}
        ]
        send_message(sender_psid, msg, quick_replies)
        
    elif payload == "FREE_TRIAL":
        send_message(sender_psid, "⏳ Free Trial Key ထုတ်ပေးနေပါသည်... (မကြာမီ ရရှိပါမည်)")
        # ဤနေရာတွင် Outline API ကိုခေါ်၍ Key ထုတ်ပေးသည့် Logic ထည့်ရန်

    else:
        send_message(sender_psid, "ရွေးချယ်ရန် Menu ကို ပြန်ခေါ်လိုပါက 'Menu' ဟု ရိုက်ထည့်ပါ။")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)