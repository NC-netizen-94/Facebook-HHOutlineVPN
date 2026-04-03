import os
import json
import requests
import psycopg2
import uuid
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request
from outline_vpn.outline_vpn import OutlineVPN

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURATIONS
# ==========================================
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("FB_VERIFY_TOKEN", "happyhive_secret_99")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8633829411:AAEdkGteDuDt4fjJABAIR7jIMLVIPQ1PPhA")
ADMIN_IDS = [1656832105] 
DATABASE_URL = os.environ.get("DATABASE_URL")

user_plan_selections = {}

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

# 🌟 FB User ၏ အမည်ရင်းကို ဆွဲယူမည့် Function 🌟
def get_fb_user_name(psid):
    url = f"https://graph.facebook.com/{psid}?fields=first_name,last_name&access_token={FB_PAGE_ACCESS_TOKEN}"
    try:
        res = requests.get(url).json()
        if "first_name" in res:
            return f"{res.get('first_name', '')} {res.get('last_name', '')}".strip()
    except:
        pass
    return "Unknown User"

def send_to_telegram_admin_photo(fb_sender_id, image_url, selected_plan, plan_code):
    fb_name = get_fb_user_name(fb_sender_id) # နာမည်ဆွဲယူခြင်း
    
    caption_text = (
        f"🚨 **Facebook မှ ငွေလွှဲပြေစာ ရောက်လာပါပြီ!**\n\n"
        f"👤 FB User: **{fb_name}** (`{fb_sender_id}`)\n"
        f"📦 Plan: **{selected_plan}**\n\n"
        f"👇 အောက်ပါ Approve ကိုနှိပ်ပါက FB User ထံသို့ Key အလိုအလျောက် ပေးပို့မည်ဖြစ်ပါသည်။"
    )
    
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

def send_fb_local_image(recipient_id, file_path):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    if os.path.exists(file_path):
        payload = {
            'recipient': json.dumps({'id': recipient_id}),
            'message': json.dumps({'attachment': {'type': 'image', 'payload': {'is_reusable': True}}})
        }
        with open(file_path, 'rb') as f:
            files = {'filedata': (os.path.basename(file_path), f, 'image/jpeg')}
            requests.post(url, data=payload, files=files)
    else:
        send_fb_message(recipient_id, "(⚠️ Admin မှ Screenshot ပုံ ထည့်သွင်းထားခြင်း မရှိသေးပါ)")

# --- 🎁 Free Trial Auto Generator ---
def handle_free_trial(sender_id):
    send_fb_message(sender_id, "⏳ Free Trial Key ကို ဖန်တီးနေပါသည်... ခဏစောင့်ပါ ခင်ဗျာ။")
    try:
        conn = get_db()
        c = conn.cursor()
        
        c.execute("SELECT unique_id, is_trial_used FROM users WHERE telegram_id=%s", (int(sender_id),))
        user = c.fetchone()
        if not user:
            unique_id = str(uuid.uuid4())[:8].upper()
            c.execute("INSERT INTO users (telegram_id, unique_id, is_trial_used, username, referral_reward_claimed) VALUES (%s, %s, 0, %s, 0)", (int(sender_id), unique_id, f"FB_{sender_id}"))
            is_used = 0
        else:
            is_used = user[1]
            
        if is_used == 1:
            conn.close()
            quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
            send_fb_quick_replies(sender_id, "⚠️ Free Trial ကို အသုံးပြုပြီးဖြစ်ပါသည်။ Plan ဝယ်ယူရန်အတွက် Menu သို့ပြန်သွားပါ။", quick_replies)
            return
            
        c.execute("SELECT value FROM settings WHERE key='outline_api_url'")
        api_url = c.fetchone()[0]
        c.execute("SELECT value FROM settings WHERE key='outline_cert_sha256'")
        cert_sha = c.fetchone()[0]
        
        client = OutlineVPN(api_url=api_url, cert_sha256=cert_sha)
        
        new_key = client.create_key()
        start_date = datetime.now()
        end_date = start_date + timedelta(days=5)
        db_start_date = start_date.strftime("%Y-%m-%d %H:%M:%S")
        db_end_date = end_date.strftime("%Y-%m-%d %H:%M:%S")
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        suffix = f"FreeTrial_{start_str}_{end_str}_{sender_id}_Key{new_key.key_id}"
        
        client.rename_key(new_key.key_id, suffix)
        client.add_data_limit(new_key.key_id, int(3 * 1e9))
        
        c.execute('''INSERT INTO plans (telegram_id, key_id, plan_type, data_limit, start_date, end_date, is_active, username) VALUES (%s, %s, %s, %s, %s, %s, 1, %s)''', (int(sender_id), new_key.key_id, "FreeTrial", int(3 * 1e9), db_start_date, db_end_date, f"FB_{sender_id}"))
        c.execute("UPDATE users SET is_trial_used=1 WHERE telegram_id=%s", (int(sender_id),))
        conn.close()
        
        final_url = f"{new_key.access_url.split('#')[0]}#{urllib.parse.quote(suffix)}"
        
        msg = f"✅ **Free Trial 3GB ရရှိပါပြီ။**\n⏱ **(၅) ရက်တိတိ အသုံးပြုနိုင်ပါသည်။**\n\n👤 **Name:** {suffix}\n\n👇 **အောက်ပါ Key ကို Copy ကူးပြီး Outline VPN တွင် ထည့်သွင်းအသုံးပြုနိုင်ပါပြီ။**"
        send_fb_message(sender_id, msg)
        
        quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
        send_fb_quick_replies(sender_id, final_url, quick_replies)
        
        # 🌟 Admin သို့ အကြောင်းကြားရာတွင် နာမည်ထည့်သွင်းခြင်း
        fb_name = get_fb_user_name(sender_id)
        for admin in ADMIN_IDS:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": admin, "text": f"🎁 **FB Free Trial Alert**\nFB User: **{fb_name}** (`{sender_id}`) မှ 3GB Free Trial ရယူသွားပါသည်။", "parse_mode": "Markdown"}
            )
            
    except Exception as e:
        quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
        send_fb_quick_replies(sender_id, f"❌ စနစ်ချို့ယွင်းမှုဖြစ်ပေါ်နေပါသည်။ Admin သို့ အကြောင်းကြားထားပါသည်။", quick_replies)
        for admin in ADMIN_IDS:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": admin, "text": f"❌ FB Free Trial Error: {str(e)}"})

# --- 🔍 Plan/Data စစ်ရန် Auto Logic ---
def handle_check_data(sender_id):
    send_fb_message(sender_id, "⏳ အချက်အလက်များ ရှာဖွေနေပါသည်...")
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT key_id, plan_type, data_limit, start_date, end_date FROM plans WHERE telegram_id=%s AND is_active=1", (int(sender_id),))
        active_plans = c.fetchall()

        if not active_plans:
            conn.close()
            quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
            send_fb_quick_replies(sender_id, "❌ လက်ရှိ Plan မရှိသေးပါ။ Plan ဝယ်ယူရန် Menu သို့ ပြန်သွားပါ။", quick_replies)
            return

        c.execute("SELECT value FROM settings WHERE key='outline_api_url'")
        api_url = c.fetchone()[0]
        c.execute("SELECT value FROM settings WHERE key='outline_cert_sha256'")
        cert_sha = c.fetchone()[0]
        conn.close()

        client = OutlineVPN(api_url=api_url, cert_sha256=cert_sha)
        all_keys = client.get_keys()

        msg = "👤 **လက်ရှိ Plan အချက်အလက်များ**\n\n"
        for db_kid, ptype, dlimit, sdate, edate in active_plans:
            used_gb = next((((getattr(k, 'used_bytes', 0) or 0) / 1e9) for k in all_keys if str(k.key_id) == str(db_kid)), 0)
            msg += f"🔹 Plan: {ptype}\n"
            msg += f"📅 စဝယ်သည့်ရက်: {sdate[:10]}\n"
            if edate: msg += f"⏳ ကုန်ဆုံးရက်: {edate[:10]}\n"
            if dlimit: msg += f"📊 သတ်မှတ် Data: {dlimit/1e9:.2f} GB\n"
            msg += f"📈 အသုံးပြုပီး Data: {used_gb:.2f} GB\n---\n"

        quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
        send_fb_quick_replies(sender_id, msg, quick_replies)

    except Exception as e:
        quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
        send_fb_quick_replies(sender_id, f"❌ Server Error ဖြစ်နေပါသည်။ နောက်မှ ပြန်စမ်းကြည့်ပါ ခင်ဗျာ。", quick_replies)

# ==========================================
# 🌐 WEBHOOK ROUTES
# ==========================================
@app.route("/", methods=["GET"])
def home():
    return "Facebook Bot is running perfectly!", 200

@app.route("/setup", methods=["GET"])
def setup_messenger_profile():
    url = f"https://graph.facebook.com/v18.0/me/messenger_profile?access_token={FB_PAGE_ACCESS_TOKEN}"
    payload = {
        "get_started": {"payload": "GET_STARTED"},
        "greeting": [{"locale": "default", "text": "HappyHive VPN မှ ကြိုဆိုပါတယ်။ စတင်ရန် အောက်ပါ 'Get Started' (သို့မဟုတ်) 'စတင်မည်' ကို နှိပ်ပါ ခင်ဗျာ。"}]
    }
    res = requests.post(url, json=payload)
    return f"Setup Result: {res.text}", 200

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

                if "postback" in messaging_event:
                    payload = messaging_event["postback"]["payload"]
                    if payload == "GET_STARTED":
                        show_main_menu(sender_id)

                elif "message" in messaging_event and "quick_reply" in messaging_event["message"]:
                    payload = messaging_event["message"]["quick_reply"]["payload"]
                    handle_payload(sender_id, payload)
                
                elif "message" in messaging_event and "attachments" in messaging_event["message"]:
                    for attachment in messaging_event["message"]["attachments"]:
                        if attachment["type"] == "image":
                            image_url = attachment["payload"]["url"]
                            selection = user_plan_selections.get(sender_id, {"name": "Unknown Plan", "code": "unknown"})
                            
                            quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
                            send_fb_quick_replies(sender_id, "✅ ပြေစာလက်ခံရရှိပါပြီ။ Admin မှ စစ်ဆေးပြီးပါက VPN Key ကို ဤနေရာမှတဆင့် ပြန်လည်ပေးပို့ပေးပါမည်။", quick_replies)
                            
                            send_to_telegram_admin_photo(sender_id, image_url, selection["name"], selection["code"])
                            if sender_id in user_plan_selections: del user_plan_selections[sender_id]
                
                elif "message" in messaging_event and "text" in messaging_event["message"]:
                    text = messaging_event["message"]["text"].strip().lower()
                    if text in ["hi", "hello", "start", "menu"]: show_main_menu(sender_id)
                    elif text == "🏠 ပင်မ မီနူးသို့": show_main_menu(sender_id)
                    elif text == "🔙 နောက်သို့": show_main_menu(sender_id)
                    else: 
                        quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
                        send_fb_quick_replies(sender_id, "ရွေးချယ်ရန် Menu ကို ပြန်ခေါ်လိုပါက 'Menu' ဟု ရိုက်ထည့်ပါ ခင်ဗျာ။", quick_replies)
    return "EVENT_RECEIVED", 200

# ==========================================
# 🤖 BOT PAYLOAD LOGIC
# ==========================================
def show_main_menu(sender_id):
    quick_replies = [
        {"content_type": "text", "title": "🛒 Plan ဝယ်ရန်", "payload": "BUY_PLAN"},
        {"content_type": "text", "title": "🎁 3GB Free Trial", "payload": "FREE_TRIAL"},
        {"content_type": "text", "title": "🔍 Plan/Data စစ်ရန်", "payload": "CHECK_DATA"},
        {"content_type": "text", "title": "👨‍💻 Admin သို့", "payload": "CONTACT_ADMIN"}, # 🌟 အသစ်ထပ်တိုးထားသော Admin သို့ ခလုတ် 🌟
        {"content_type": "text", "title": "❓ အသုံးပြုပုံ", "payload": "HOW_TO_USE"}
    ]
    send_fb_quick_replies(sender_id, "🌟 Welcome to HappyHive VPN! 🌟\n\n👇 အောက်ပါ Menu များမှတဆင့် မိမိအသုံးပြုလိုသော ဝန်ဆောင်မှုကို ရွေးချယ်ပါ ခင်ဗျာ။", quick_replies)

def handle_payload(sender_id, payload):
    
    if payload == "MAIN_MENU":
        show_main_menu(sender_id)
        
    elif payload == "BUY_PLAN":
        # 🌟 Plan အမည်များတွင် (၁လ) ထည့်သွင်းထားသည် 🌟
        quick_replies = [
            {"content_type": "text", "title": "30GB (၁လ) - ၂၀၀၀ကျပ်", "payload": "PLAN_30GB"},
            {"content_type": "text", "title": "50GB (၁လ) - ၃၀၀၀ကျပ်", "payload": "PLAN_50GB"},
            {"content_type": "text", "title": "100GB (၁လ) - ၄၀၀၀ကျပ်", "payload": "PLAN_100GB"},
            {"content_type": "text", "title": "🔙 နောက်သို့", "payload": "MAIN_MENU"}
        ]
        send_fb_quick_replies(sender_id, "🛒 ဝယ်ယူလိုသော Plan ကို ရွေးချယ်ပါ-", quick_replies)
        
    elif payload in ["PLAN_30GB", "PLAN_50GB", "PLAN_100GB"]:
        plan_map = {
            "PLAN_30GB": ("30GB (၁လ) - ၂၀၀၀ကျပ်", "plan_30gb"),
            "PLAN_50GB": ("50GB (၁လ) - ၃၀၀၀ကျပ်", "plan_50gb"),
            "PLAN_100GB": ("100GB (၁လ) - ၄၀၀၀ကျပ်", "plan_100gb")
        }
        selected_plan, plan_code = plan_map[payload]
        user_plan_selections[sender_id] = {"name": selected_plan, "code": plan_code}
        msg = f"သင်ရွေးချယ်ထားသော Plan: {selected_plan}\n\nကျေးဇူးပြု၍ အောက်ပါ KPay သို့ ငွေလွှဲပြီး Screenshot ပြေစာ ဓာတ်ပုံကို ဤနေရာသို့ ပို့ပေးပါ။\n\n💰 KPay: 09799844344\n👤 Name: Nyein Chan\n📝 Note: shopping ဟုရေးပေးပါ။"
        
        quick_replies = [{"content_type": "text", "title": "🔙 နောက်သို့", "payload": "BUY_PLAN"}, {"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
        send_fb_quick_replies(sender_id, msg, quick_replies)
        
    elif payload == "FREE_TRIAL":
        handle_free_trial(sender_id)
        
    elif payload == "CHECK_DATA":
        handle_check_data(sender_id)
        
    # 🌟 Admin သို့ ဆက်သွယ်ရန် လမ်းကြောင်းသစ် 🌟
    elif payload == "CONTACT_ADMIN":
        msg = "👨‍💻 Admin နှင့် တိုက်ရိုက်ပြောဆိုရန် အောက်ပါ Telegram လင့်ခ်မှတဆင့် ဆက်သွယ်နိုင်ပါသည်-\n\n👉 https://t.me/HappyHive9496\n\n(သို့မဟုတ်) ဤ Messenger Chat Box တွင်လည်း စာရိုက်၍ မေးမြန်းထားနိုင်ပါသည် ခင်ဗျာ။"
        quick_replies = [{"content_type": "text", "title": "🏠 ပင်မ မီနူးသို့", "payload": "MAIN_MENU"}]
        send_fb_quick_replies(sender_id, msg, quick_replies)
        
    elif payload == "HOW_TO_USE":
        quick_replies = [
            {"content_type": "text", "title": "🤖 Android", "payload": "HTU_ANDROID"},
            {"content_type": "text", "title": "🍎 Apple (iOS)", "payload": "HTU_APPLE"},
            {"content_type": "text", "title": "🔙 နောက်သို့", "payload": "MAIN_MENU"}
        ]
        send_fb_quick_replies(sender_id, "📱 မိမိအသုံးပြုမည့် ဖုန်းအမျိုးအစားကို ရွေးချယ်ပါ-", quick_replies)

    elif payload == "HTU_ANDROID":
        send_fb_message(sender_id, "🤖 **Android ဖုန်းများအတွက် အသုံးပြုပုံ**\n\n📥 Outline App Download ဆွဲရန်:\nhttps://play.google.com/store/apps/details?id=org.outline.android.client&hl=en_SG")
        send_fb_local_image(sender_id, "android_ss.jpg")
        quick_replies = [{"content_type": "text", "title": "🔙 နောက်သို့", "payload": "HOW_TO_USE"}, {"content_type": "text", "title": "🏠 ပင်မ မီနူး", "payload": "MAIN_MENU"}]
        send_fb_quick_replies(sender_id, "Menu သို့ ပြန်သွားရန် အောက်ပါခလုတ်ကို နှိပ်ပါ", quick_replies)

    elif payload == "HTU_APPLE":
        send_fb_message(sender_id, "🍎 **Apple (iOS) ဖုန်းများအတွက် အသုံးပြုပုံ**\n\n📥 Outline App Download ဆွဲရန်:\nhttps://apps.apple.com/us/app/outline-app/id1356177741")
        send_fb_local_image(sender_id, "apple_ss.jpg")
        quick_replies = [{"content_type": "text", "title": "🔙 နောက်သို့", "payload": "HOW_TO_USE"}, {"content_type": "text", "title": "🏠 ပင်မ မီနူး", "payload": "MAIN_MENU"}]
        send_fb_quick_replies(sender_id, "Menu သို့ ပြန်သွားရန် အောက်ပါခလုတ်ကို နှိပ်ပါ", quick_replies)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
