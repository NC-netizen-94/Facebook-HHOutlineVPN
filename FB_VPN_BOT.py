import os
import json
import requests
import psycopg2
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURATIONS (အချက်အလက်များ)
# ==========================================
# Render ရဲ့ Environment Variables ကနေ လှမ်းယူမယ့် အရာများ
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN", "happyhive_secret_99")
DATABASE_URL = os.environ.get("DATABASE_URL")

# Telegram Bot အတွက် Token နှင့် Admin ID များ
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8633829411:AAEdkGteDuDt4fjJABAIR7jIMLVIPQ1PPhA")
ADMIN_IDS = [1656832105]

# မိမိအသုံးပြုမည့် ငွေလွှဲနံပါတ် (ဒီနေရာမှာ ပြင်ပါ)
KPAY_NUMBER = "09799844344 (Name: YourName)"

# ==========================================
# 🛠️ HELPER FUNCTIONS (အကူအညီပေးသော လုပ်ဆောင်ချက်များ)
# ==========================================

def send_to_telegram_admin_photo(fb_sender_id, image_url):
    """Facebook မှ ပို့သော ပြေစာကို Telegram Admin ထံ ပို့ရန်"""
    caption_text = f"🚨 Facebook မှ ငွေလွှဲပြေစာ ရောက်လာပါပြီ!\n\nFB User ID: {fb_sender_id}\nကျေးဇူးပြု၍ စစ်ဆေးပေးပါ။"
    
    # Telegram တွင် ပေါ်မည့် Approve/Reject ခလုတ်များ
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve (1 Month)", "callback_data": f"fb_approve_1m_{fb_sender_id}"},
                {"text": "❌ Reject", "callback_data": f"fb_reject_{fb_sender_id}"}
            ]
        ]
    }
    
    for admin_id in ADMIN_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": admin_id,
            "photo": image_url,
            "caption": caption_text,
            "reply_markup": reply_markup
        }
        requests.post(url, json=payload)

def send_fb_message(recipient_id, message_text):
    """Facebook User ထံ ရိုးရိုး စာသားပို့ရန်"""
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    requests.post(url, json=payload)

def send_fb_quick_replies(recipient_id, text, quick_replies):
    """Facebook User ထံ ခလုတ် (Menu) များပါသော စာပို့ရန်"""
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text,
            "quick_replies": quick_replies
        }
    }
    requests.post(url, json=payload)

# ==========================================
# 🌐 WEBHOOK ROUTES (ချိတ်ဆက်မှု လမ်းကြောင်းများ)
# ==========================================

@app.route("/", methods=["GET"])
def home():
    return "Facebook Bot is running perfectly!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Facebook မှ Webhook ချိတ်ဆက်မှုကို စစ်ဆေးရန်"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == FB_VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Forbidden", 403
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def handle_messages():
    """Facebook မှ ဝင်လာသော စာများကို လက်ခံတုံ့ပြန်ရန်"""
    data = request.json
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                # ၁။ User က Menu ခလုတ်များကို နှိပ်လာလျှင် (Quick Reply Postbacks)
                if "message" in messaging_event and "quick_reply" in messaging_event["message"]:
                    payload = messaging_event["message"]["quick_reply"]["payload"]
                    handle_payload(sender_id, payload)
                
                # ၂။ User က ဓာတ်ပုံ (Screenshot) ပို့လာလျှင်
                elif "message" in messaging_event and "attachments" in messaging_event["message"]:
                    for attachment in messaging_event["message"]["attachments"]:
                        if attachment["type"] == "image":
                            image_url = attachment["payload"]["url"]
                            # User ကို ပြန်ပြောမယ်
                            send_fb_message(sender_id, "✅ ပြေစာလက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးပေးနေပါသည်။ ခဏစောင့်ပေးပါ ခင်ဗျာ။")
                            # Telegram Admin ကို လှမ်းပို့မယ်
                            send_to_telegram_admin_photo(sender_id, image_url)
                
                # ၃။ User က ရိုးရိုး စာသား ပို့လာလျှင်
                elif "message" in messaging_event and "text" in messaging_event["message"]:
                    text = messaging_event["message"]["text"].strip()
                    
                    if text.lower() in ["hi", "hello", "start", "menu"]:
                        show_main_menu(sender_id)
                    else:
                        send_fb_message(sender_id, "ရွေးချယ်ရန် Menu ကို ပြန်ခေါ်လိုပါက 'Menu' ဟု ရိုက်ထည့်ပါ ခင်ဗျာ။")

    return "EVENT_RECEIVED", 200

# ==========================================
# 🤖 BOT LOGIC (Bot ၏ တုံ့ပြန်မှုများ)
# ==========================================

def show_main_menu(sender_id):
    """Main Menu ခလုတ်များ ပြသရန်"""
    quick_replies = [
        {"content_type": "text", "title": "🛒 Plan ဝယ်ရန်", "payload": "BUY_PLAN"},
        {"content_type": "text", "title": "🎁 3GB Free Trial", "payload": "FREE_TRIAL"},
        {"content_type": "text", "title": "🔍 Plan/Data စစ်ရန်", "payload": "CHECK_DATA"}
    ]
    send_fb_quick_replies(sender_id, "HappyHive VPN မှ ကြိုဆိုပါတယ်။ အောက်ပါ Menu များကို ရွေးချယ်နိုင်ပါသည်-", quick_replies)

def handle_payload(sender_id, payload):
    """User နှိပ်လိုက်သော ခလုတ်ပေါ်မူတည်၍ အလုပ်လုပ်ရန်"""
    
    if payload == "BUY_PLAN":
        quick_replies = [
            {"content_type": "text", "title": "1 Month (3000 Ks)", "payload": "PLAN_1M"},
            {"content_type": "text", "title": "3 Months (8000 Ks)", "payload": "PLAN_3M"}
        ]
        send_fb_quick_replies(sender_id, "🛒 ဝယ်ယူလိုသော Plan ကို ရွေးချယ်ပါ-", quick_replies)
        
    elif payload in ["PLAN_1M", "PLAN_3M"]:
        plan_name = "1 Month (3000 Ks)" if payload == "PLAN_1M" else "3 Months (8000 Ks)"
        msg = f"သင်ရွေးချယ်ထားသော Plan: {plan_name}\n\nကျေးဇူးပြု၍ အောက်ပါ KPay/Wave သို့ ငွေလွှဲပြီး Screenshot ပြေစာ ဓာတ်ပုံကို ဤနေရာသို့ ပို့ပေးပါ။\n\n💰 {KPAY_NUMBER}"
        send_fb_message(sender_id, msg)
        
    elif payload == "FREE_TRIAL":
        # ယာယီစာသား (နောက်ပိုင်း Outline API နဲ့ ချိတ်ရပါမယ်)
        send_fb_message(sender_id, "🎁 သင်၏ 3GB Free Trial Key ကို ဖန်တီးနေပါသည်။ ခဏစောင့်ပါ...\n(မှတ်ချက်: Server နှင့် ချိတ်ဆက်နေဆဲဖြစ်ပါသည်)")
        
    elif payload == "CHECK_DATA":
        # ယာယီစာသား (နောက်ပိုင်း Database ကနေ သွားစစ်ရပါမယ်)
        send_fb_message(sender_id, "🔍 သင်၏ လက်ကျန် Data မှာ 3.0 GB ဖြစ်ပါသည်။\n(မှတ်ချက်: စမ်းသပ်မှု အဆင့်သာ ဖြစ်ပါသည်)")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
