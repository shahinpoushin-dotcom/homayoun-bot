import os
import re
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ─── Config ───────────────────────────────────────────────
BALE_TOKEN         = os.environ.get("BALE_TOKEN", "")
CLAUDE_API_KEY     = os.environ.get("CLAUDE_API_KEY", "")
NOTION_TOKEN       = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")

BALE_BASE = f"https://tapi.ir/v1/bot{BALE_TOKEN}"

# ─── System Prompt همایون ─────────────────────────────────
SYSTEM_PROMPT = """تو همایون هستی — مشاور اولیه موسسه مهاجرتی هما.

اطلاعات موسسه هما:
- تخصص: مهاجرت تحصیلی و کاری به ایتالیا، آلمان، انگلستان، قطر، عمان
- سایت: homaic.com
- شماره‌های تماس: 026-32232003 | 021-91010246 | 0936-2552218
- آدرس: کرج، میدان توحید، جنب درمانگاه نفت، پلاک 102، مجتمع هما
- ساعت کاری: شنبه تا چهارشنبه ۹ تا ۱۸، پنجشنبه ۹ تا ۱۴

شخصیت تو:
- مثل یک دوست آگاه و صادق حرف می‌زنی، نه مثل یک ربات یا فرم اداری
- گرم، صمیمی، و حرفه‌ای هستی
- فارسی روان و طبیعی می‌نویسی
- پاسخ‌هایت کوتاه و مفید — حداکثر ۵ تا ۶ خط در هر پیام
- اطلاعات واقعی و تحلیلی می‌دهی
- هیچ‌وقت عجله نداری و مشتری را تحت فشار نمی‌گذاری

اطلاعات تخصصی مهاجرت تحصیلی:
ایتالیا: ویزای D تحصیلی، بدون محدودیت سنی، ایلتس ۵.۵ یا B2 ایتالیایی،
هزینه تحصیل 160-400 یورو در سال، پروسه ۳-۶ ماه، امکان اقامت بعد از فارغ‌التحصیلی.
آلمان: بلوکه حساب ۱۱۹۰۴ یورو الزامی، زبان B2، دانشگاه رایگان، پروسه ۶-۹ ماه.
انگلستان: هزینه بالا (10000-30000 پوند)، IELTS 6.0+، CAS از دانشگاه، پروسه ۳-۵ ماه.

اطلاعات تخصصی مهاجرت کاری:
قطر: حداقل ۲ سال سابقه کاری، بیمه پیوسته مهم، اسپانسری کارفرما، حقوق بدون مالیات.
عمان: شرایط مشابه قطر، کمی آسان‌تر، مناسب تکنسین‌ها.
آلمان کاری: معادل‌سازی مدرک (Anerkennung)، حداقل B1 آلمانی، پروسه ۸-۱۲ ماه.

جریان مکالمه:
۱. خوش‌آمدگویی گرم + بپرس نوع مهاجرت (تحصیلی/کاری)
۲. اطلاعات رو طبیعی جمع کن — هر بار یک یا دو سوال:
   عمومی: کشور هدف، شرایط زندگی، بازه زمانی، بودجه، سن، زبان، سابقه رد ویزا
   تحصیلی: مدرک، رشته، معدل
   کاری: مدرک فنی، سابقه کاری، سابقه بیمه
۳. تحلیل کن: مسیر مناسب، مدارک، مدت، چالش‌ها. صادق باش.
۴. شماره موبایل بخواه و بگو متخصص تماس می‌گیره.
   وقتی شماره داد بگو: "ممنون! یکی از متخصصان هما در اولین فرصت باهات تماس می‌گیره."

هندآف فوری (مستقیم شماره بخواه):
- سن بالای ۴۵ + تحصیلی
- سابقه رد ویزا
- وضعیت حقوقی پیچیده

مرزها — هرگز نگو:
- تضمین ویزا یا پذیرش
- قیمت دقیق خدمات هما
- نظر حقوقی قطعی"""

# ─── حافظه کاربران ────────────────────────────────────────
conversations = {}    # user_id -> messages
user_info     = {}    # user_id -> {name, phone, country, saved}

# ─── استخراج شماره موبایل ─────────────────────────────────
def extract_phone(text):
    match = re.search(r'(\+98|0098|0)9[\d\s\-]{9,11}', text)
    if match:
        return re.sub(r'[\s\-]', '', match.group())
    return None

# ─── استخراج کشور از مکالمه ───────────────────────────────
def extract_country(conversations_list):
    countries = ["ایتالیا", "آلمان", "انگلستان", "قطر", "عمان", "ترکیه"]
    for msg in reversed(conversations_list):
        for c in countries:
            if c in msg.get("content", ""):
                return c
    return ""

# ─── Bale API ─────────────────────────────────────────────
def bale(method, params=None):
    url = f"{BALE_BASE}/{method}"
    try:
        res = requests.post(url, json=params, timeout=15)
        data = res.json()
        if not data.get("ok"):
            print(f"[Bale error] {method}: {data}")
        return data
    except Exception as e:
        print(f"[Bale exception] {e}")
        return {}

def send(chat_id, text):
    bale("sendMessage", {"chat_id": chat_id, "text": text})

# ─── Claude API ───────────────────────────────────────────
def ask_claude(user_id, user_message):
    if user_id not in conversations:
        conversations[user_id] = []
    conversations[user_id].append({"role": "user", "content": user_message})
    messages = conversations[user_id][-20:]
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 800,
                "system": SYSTEM_PROMPT,
                "messages": messages
            },
            timeout=30
        )
        data = res.json()
        if "error" in data:
            print(f"[Claude error] {data['error']}")
            return "متأسفم، مشکل موقتی پیش اومد. دوباره امتحان کن."
        reply = data["content"][0]["text"]
        conversations[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"[Claude exception] {e}")
        return "متأسفم، مشکل موقتی پیش اومد. دوباره امتحان کن."

# ─── Notion — ذخیره در People ────────────────────────────
def save_to_notion(user_id, name, phone, bale_id, country):
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print("[Notion] توکن تنظیم نشده")
        return
    try:
        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            },
            json={
                "parent": {"database_id": NOTION_DATABASE_ID},
                "properties": {
                    "نام":            {"title":  [{"text": {"content": name or "نامشخص"}}]},
                    "موبایل":         {"phone_number": phone or ""},
                    "کانال ورودی":   {"select": {"name": "بله"}},
                    "وضعیت لید":     {"select": {"name": "جدید"}},
                    "آیدی بله":      {"rich_text": [{"text": {"content": str(bale_id or "")}}]},
                    "کشور درخواستی": {"select": {"name": country}} if country else {},
                    "تاریخ ثبت":     {"date": {"start": datetime.now().isoformat()}},
                }
            },
            timeout=10
        )
        data = res.json()
        if data.get("object") == "page":
            print(f"[Notion] ✅ {name} — {phone} — {country}")
        else:
            print(f"[Notion] ❌ {data}")
    except Exception as e:
        print(f"[Notion exception] {e}")

# ─── Bot Loop ─────────────────────────────────────────────
def bot_loop():
    print("همایون شروع به کار کرد...")
    me = bale("getMe")
    print(f"[getMe] {me}")
    offset = 0
    while True:
        try:
            result = bale("getUpdates", {"offset": offset, "timeout": 20})
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue

                chat_id   = msg["chat"]["id"]
                user_id   = str(msg["from"]["id"])
                first_name= msg["from"].get("first_name", "")
                text      = msg.get("text", "").strip()
                if not text:
                    continue

                print(f"[IN] {user_id}: {text[:80]}")

                # اگه کاربر جدیده، اطلاعاتش رو ذخیره کن
                if user_id not in user_info:
                    user_info[user_id] = {
                        "name": first_name,
                        "phone": None,
                        "country": "",
                        "saved": False
                    }

                # بررسی شماره موبایل
                phone = extract_phone(text)
                if phone and not user_info[user_id]["saved"]:
                    user_info[user_id]["phone"] = phone
                    country = extract_country(conversations.get(user_id, []))
                    user_info[user_id]["country"] = country
                    save_to_notion(
                        user_id,
                        user_info[user_id]["name"],
                        phone,
                        user_id,
                        country
                    )
                    user_info[user_id]["saved"] = True
                    print(f"[Lead saved] {first_name} — {phone}")

                reply = ask_claude(user_id, text)
                send(chat_id, reply)
                print(f"[OUT] {reply[:80]}")

        except Exception as e:
            print(f"[Loop error] {e}")
            time.sleep(5)

# ─── Health Check ─────────────────────────────────────────
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Homayoun is running")
    def log_message(self, *args):
        pass

def start_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"Health server on port {port}")
    HTTPServer(("0.0.0.0", port), Health).serve_forever()

# ─── Main ─────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    bot_loop()
