import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURATIONS (အချက်အလက်များ)
# ==========================================
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN", "happyhive_secret_99")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8633829411:AAEdkGteDuDt4fjJABAIR7jIMLVIPQ1PPhA")
ADMIN_IDS = [1656832105] 

user_plan_selections = {}

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================
def send_to_telegram_admin_photo(fb_sender_id, image_url, selected_plan, plan_code):
    caption_text = (
        f"🚨 **Facebook မှ ငွေလွှဲပြေစာ ရောက်လာပါပြီ!**\n\n"
        f"👤 FB User ID: `{fb_sender_id}`\n"
        f"📦 Plan: **{selected_plan}**\n\n"
        f"👇 အောက်ပါ Approve ကိုနှိပ်ပါက FB User ထံသို့ Key အလိုအလျောက် ပေးပို့မည်ဖြစ်ပါသည်။"
    )
    
    # Approve / Reject ခလုတ်များ ထည့်သွင်းခြင်း
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve & Auto-Send Key", "callback_data": f"fbapp_{plan_code}_{fb_sender_id}"},
                {"text": "❌ Reject", "callback_data": f"fbrej_{fb_sender_id}"}
            ]
        ]
    }
    
    for admin_id in ADMIN_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": admin_id,
            "photo": image_url,
            "caption": caption_text,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup
        }
        requests.post(url, json=payload)

def send_fb_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    requests.post(url, json=payload)

def send_fb_quick_replies(recipient_id, text, quick_replies):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text, "quick_replies": quick_replies}}
    requests.post(url, json=payload)

# ==========================================
# 🌐 WEBHOOK ROUTES
# ==========================================
@app.route("/", methods=["GET"])
def home():
    return "Facebook Bot is running with Auto-Approve Buttons!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token:
        if mode == "subscribe" and token == FB_VERIFY_TOKEN: return challenge, 200
        else: return "Forbidden", 403
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def handle_messages():
    data = request.json
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                if "message" in messaging_event and "quick_reply" in messaging_event["message"]:
                    payload = messaging_event["message"]["quick_reply"]["payload"]
                    handle_payload(sender_id, payload)
                
                elif "message" in messaging_event and "attachments" in messaging_event["message"]:
                    for attachment in messaging_event["message"]["attachments"]:
                        if attachment["type"] == "image":
                            image_url = attachment["payload"]["url"]
                            selection = user_plan_selections.get(sender_id, {"name": "Unknown Plan", "code": "unknown"})
                            send_fb_message(sender_id, "✅ ပြေစာလက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးပြီးပါက VPN Key ကို ဤနေရာမှတဆင့် ပြန်လည်ပေးပို့ပေးပါမည်။")
                            send_to_telegram_admin_photo(sender_id, image_url, selection["name"], selection["code"])
                            if sender_id in user_plan_selections: del user_plan_selections[sender_id]
                
                elif "message" in messaging_event and "text" in messaging_event["message"]:
                    text = messaging_event["message"]["text"].strip().lower()
                    if text in ["hi", "hello", "start", "menu"]: show_main_menu(sender_id)
                    else: send_fb_message(sender_id, "ရွေးချယ်ရန် Menu ကို ပြန်ခေါ်လိုပါက 'Menu' ဟု ရိုက်ထည့်ပါ ခင်ဗျာ။")
    return "EVENT_RECEIVED", 200

def show_main_menu(sender_id):
    quick_replies = [
        {"content_type": "text", "title": "🛒 Plan ဝယ်ရန်", "payload": "BUY_PLAN"},
        {"content_type": "text", "title": "🎁 3GB Free Trial", "payload": "FREE_TRIAL"},
        {"content_type": "text", "title": "❓ အသုံးပြုပုံ", "payload": "HOW_TO_USE"}
    ]
    send_fb_quick_replies(sender_id, "🌟 Welcome to HappyHive VPN! 🌟\n\n👇 အောက်ပါ Menu များမှတဆင့် မိမိအသုံးပြုလိုသော ဝန်ဆောင်မှုကို ရွေးချယ်ပါ ခင်ဗျာ။", quick_replies)

def handle_payload(sender_id, payload):
    if payload == "BUY_PLAN":
        quick_replies = [
            {"content_type": "text", "title": "30GB (၂၀၀၀ကျပ်)", "payload": "PLAN_30GB"},
            {"content_type": "text", "title": "50GB (၃၀၀၀ကျပ်)", "payload": "PLAN_50GB"},
            {"content_type": "text", "title": "100GB (၄၀၀၀ကျပ်)", "payload": "PLAN_100GB"}
        ]
        send_fb_quick_replies(sender_id, "🛒 ဝယ်ယူလိုသော Plan ကို ရွေးချယ်ပါ-", quick_replies)
        
    elif payload in ["PLAN_30GB", "PLAN_50GB", "PLAN_100GB"]:
        plan_map = {
            "PLAN_30GB": ("30GB Plan (၂၀၀၀ ကျပ်)", "plan_30gb"),
            "PLAN_50GB": ("50GB Plan (၃၀၀၀ ကျပ်)", "plan_50gb"),
            "PLAN_100GB": ("100GB Plan (၄၀၀၀ ကျပ်)", "plan_100gb")
        }
        selected_plan, plan_code = plan_map[payload]
        user_plan_selections[sender_id] = {"name": selected_plan, "code": plan_code}
        msg = f"သင်ရွေးချယ်ထားသော Plan: {selected_plan}\n\nကျေးဇူးပြု၍ အောက်ပါ KPay သို့ ငွေလွှဲပြီး Screenshot ပြေစာ ဓာတ်ပုံကို ဤနေရာသို့ ပို့ပေးပါ။\n\n💰 KPay: 09799844344\n👤 Name: Nyein Chan\n📝 Note: shopping ဟုရေးပေးပါ။"
        send_fb_message(sender_id, msg)
        
    elif payload == "FREE_TRIAL":
        send_fb_message(sender_id, "🎁 Free Trial အတွက် Admin ထံသို့ စာတိုက်ရိုက် ပို့ထားပေးပါ။ Admin မှ စစ်ဆေးပြီးပါက 3GB (၅ ရက်) Key ကို ဤနေရာမှတဆင့် ချပေးပါမည်။")
        
    elif payload == "HOW_TO_USE":
        send_fb_message(sender_id, "Android တွင် အသုံးပြုလိုပါက Play Store မှ 'Outline' App ကို ဒေါင်းလုဒ်ဆွဲပါ။ iOS အတွက် App Store မှ 'Outline App' ကို ဒေါင်းလုဒ်ဆွဲပါ။ Admin မှ ပေးသော Key ကို Copy ကူး၍ App ထဲတွင် Add Server နှိပ်ပြီး အသုံးပြုနိုင်ပါသည်။")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
