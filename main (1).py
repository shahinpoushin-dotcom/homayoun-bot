import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ─── Config ───────────────────────────────────────────────
BALE_TOKEN          = os.environ.get("BALE_TOKEN", "")
CLAUDE_API_KEY      = os.environ.get("CLAUDE_API_KEY", "")
NOTION_TOKEN        = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID  = os.environ.get("NOTION_DATABASE_ID", "")

BALE_BASE = f"https://tapi.ir/v1/bot{BALE_TOKEN}/"

# ─── System Prompt همایون ─────────────────────────────────
SYSTEM_PROMPT = """تو همایون هستی — مشاور اولیه موسسه مهاجرتی هما.

شخصیت تو:
- مثل یک دوست آگاه و صادق حرف می‌زنی، نه مثل یک ربات یا فرم اداری
- گرم، صمیمی، و حرفه‌ای هستی
- فارسی روان و طبیعی می‌نویسی — بدون اصطلاحات پیچیده
- پاسخ‌هایت کوتاه و مفید است — حداکثر ۵ تا ۶ خط در هر پیام
- اطلاعات واقعی و تحلیلی می‌دهی — نه جواب‌های کلی و مبهم
- هیچ‌وقت عجله نداری و مشتری را تحت فشار نمی‌گذاری

موسسه هما:
- تخصص: مهاجرت تحصیلی و کاری به ایتالیا، آلمان، انگلستان، قطر، عمان
- سایت: homaic.com

جریان مکالمه:

مرحله ۱ — خوش‌آمدگویی:
با یک پیام گرم و کوتاه شروع کن. بپرس چه نوع مهاجرتی در ذهن دارند.

مرحله ۲ — جمع‌آوری اطلاعات (طبیعی، نه فرم):
اطلاعات رو در طول مکالمه به شکل طبیعی بپرس — هر بار یک یا دو سوال.
بین سوال‌ها، اطلاعات مفید و تحلیلی بده.

اطلاعاتی که باید جمع کنی (به صورت طبیعی، نه فرم):
عمومی: نوع مهاجرت، کشور هدف، شرایط زندگی (مجرد/متأهل/فرزند)،
بازه زمانی، بودجه، سن، وضعیت زبان، سابقه رد ویزا، شماره تماس
تحصیلی: مدرک تحصیلی، رشته، معدل
کاری: مدرک فنی/حرفه‌ای، سابقه کاری، سابقه بیمه

مرحله ۳ — تحلیل و راهنمایی:
بعد از جمع اطلاعات کافی، تحلیل کن: مسیر مناسب، مدارک لازم،
مدت پروسه، چالش‌های احتمالی. صادق باش.

مرحله ۴ — هندآف:
وقتی اطلاعات کامل شد بگو:
"بر اساس اطلاعاتی که دادی، فکر می‌کنم یه مشاوره تخصصی‌تر لازمه.
می‌تونم شماره‌ات رو بگیرم تا متخصص هما باهات تماس بگیره؟"

پروتکل هندآف فوری (بدون تحلیل بیشتر، مستقیم بگو متخصص تماس می‌گیره):
- سن بالای ۴۵ سال + ویزا تحصیلی
- سابقه رد ویزا از هر کشوری
- وضعیت حقوقی پیچیده
- مسیر غیرمعمول

در این موارد بگو:
"این وضعیت پیچیدگی‌هایی داره که نمی‌خوام اشتباه راهنماییت کنم.
بذار یه متخصص هما دقیق‌تر بررسی کنه. شماره‌ات رو بدی؟"

مرزها — هرگز نگو:
- تضمین پذیرش یا ویزا
- قیمت دقیق خدمات هما
- نظر حقوقی قطعی
- مقایسه با رقبا"""

# ─── حافظه مکالمه (در حافظه RAM) ────────────────────────
conversations = {}   # user_id -> [{"role": ..., "content": ...}]

# ─── Bale API ─────────────────────────────────────────────
def bale(method, params=None):
    try:
        res = requests.post(BALE_BASE + method, json=params, timeout=15)
        return res.json()
    except Exception as e:
        print(f"[Bale] {e}")
        return {}

def send(chat_id, text):
    bale("sendMessage", {"chat_id": chat_id, "text": text})

# ─── Claude API ───────────────────────────────────────────
def ask_claude(user_id, user_message):
    if user_id not in conversations:
        conversations[user_id] = []

    conversations[user_id].append({"role": "user", "content": user_message})
    messages = conversations[user_id][-20:]  # آخرین ۲۰ پیام

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
        reply = res.json()["content"][0]["text"]
        conversations[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"[Claude] {e}")
        return "متأسفم، یه مشکل فنی پیش اومد. لطفاً دوباره امتحان کن."

# ─── Notion API ───────────────────────────────────────────
def save_notion(user_id, name, phone, migration_type, country):
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return
    try:
        requests.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            },
            json={
                "parent": {"database_id": NOTION_DATABASE_ID},
                "properties": {
                    "نام":          {"title":     [{"text": {"content": name or "نامشخص"}}]},
                    "شماره تماس":  {"rich_text": [{"text": {"content": phone or ""}}]},
                    "نوع مهاجرت": {"rich_text": [{"text": {"content": migration_type or ""}}]},
                    "کشور هدف":   {"rich_text": [{"text": {"content": country or ""}}]},
                    "تاریخ":       {"rich_text": [{"text": {"content": datetime.now().strftime("%Y-%m-%d %H:%M")}}]},
                    "وضعیت":      {"rich_text": [{"text": {"content": "جدید"}}]},
                }
            },
            timeout=10
        )
        print(f"[Notion] Lead saved: {name} {phone}")
    except Exception as e:
        print(f"[Notion] {e}")

# ─── Bot Loop ─────────────────────────────────────────────
def bot_loop():
    print("همایون شروع به کار کرد...")
    offset = 0

    while True:
        try:
            result = bale("getUpdates", {"offset": offset, "timeout": 25})
            if not result.get("ok"):
                time.sleep(3)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue

                chat_id = msg["chat"]["id"]
                user_id = str(msg["from"]["id"])
                text    = msg.get("text", "").strip()

                if not text:
                    continue

                print(f"[IN] {user_id}: {text[:60]}")
                reply = ask_claude(user_id, text)
                send(chat_id, reply)
                print(f"[OUT]: {reply[:60]}")

        except Exception as e:
            print(f"[Loop] {e}")
            time.sleep(5)

# ─── Health Check Server (برای Render) ───────────────────
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Homayoun is running")
    def log_message(self, *args):
        pass

def start_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Health).serve_forever()

# ─── Main ─────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    bot_loop()
