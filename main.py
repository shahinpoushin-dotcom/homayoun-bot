import os
import re
import json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ─── Config ───────────────────────────────────────────────
BALE_TOKEN         = os.environ.get("BALE_TOKEN", "")
CLAUDE_API_KEY     = os.environ.get("CLAUDE_API_KEY", "")
NOTION_TOKEN       = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
RENDER_URL         = os.environ.get("RENDER_URL", "https://homayoun-bot.onrender.com")

BALE_BASE = f"https://tapi.bale.ai/bot{BALE_TOKEN}"

SYSTEM_PROMPT = """تو همایون هستی — مشاور اولیه موسسه مهاجرتی هما.

اطلاعات موسسه هما:
- تخصص: مهاجرت تحصیلی و کاری به ایتالیا، آلمان، انگلستان، قطر، عمان
- سایت: homaic.com
- شماره‌های تماس: 026-32232003 | 021-91010246 | 0936-2552218
- آدرس: کرج، میدان توحید، جنب درمانگاه نفت، پلاک 102، مجتمع هما

شخصیت تو:
- مثل یک دوست آگاه و صادق حرف می‌زنی
- گرم، صمیمی، و حرفه‌ای هستی
- فارسی روان و طبیعی می‌نویسی
- پاسخ‌هایت کوتاه و مفید — حداکثر ۵ تا ۶ خط
- اطلاعات واقعی و تحلیلی می‌دهی
- هیچ‌وقت عجله نداری

اطلاعات تخصصی مهاجرت تحصیلی:
ایتالیا: ویزای D، بدون محدودیت سنی، ایلتس ۵.۵ یا B2 ایتالیایی، هزینه 160-400 یورو، پروسه ۳-۶ ماه.
آلمان: بلوکه ۱۱۹۰۴ یورو، زبان B2، دانشگاه رایگان، پروسه ۶-۹ ماه.
انگلستان: هزینه 10000-30000 پوند، IELTS 6.0+، پروسه ۳-۵ ماه.

اطلاعات تخصصی مهاجرت کاری:
قطر: حداقل ۲ سال سابقه، بیمه پیوسته مهم، اسپانسری کارفرما، حقوق بدون مالیات.
عمان: مشابه قطر، کمی آسان‌تر.
آلمان کاری: معادل‌سازی مدرک، حداقل B1 آلمانی، پروسه ۸-۱۲ ماه.

جریان مکالمه:
۱. خوش‌آمدگویی + بپرس نوع مهاجرت (تحصیلی/کاری)
۲. اطلاعات رو طبیعی جمع کن: کشور هدف، شرایط زندگی، بازه زمانی، بودجه، سن، زبان، سابقه رد ویزا
   تحصیلی: مدرک، رشته، معدل
   کاری: مدرک فنی، سابقه کاری، سابقه بیمه
۳. تحلیل کن: مسیر مناسب، مدارک، مدت، چالش‌ها
۴. شماره موبایل بخواه — بگو متخصص تماس می‌گیره

هندآف فوری: سن بالای ۴۵ + تحصیلی، سابقه رد ویزا، وضعیت پیچیده

مرزها: تضمین ویزا نده، قیمت دقیق نگو، نظر حقوقی قطعی نده"""

# حافظه مکالمه
conversations = {}
user_info = {}

def extract_phone(text):
    match = re.search(r'(\+98|0098|0)9[\d\s\-]{9,11}', text)
    if match:
        return re.sub(r'[\s\-]', '', match.group())
    return None

def bale_send(chat_id, text):
    try:
        requests.post(f"{BALE_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"[Bale send error] {e}")

def ask_claude(user_id, user_message):
    if user_id not in conversations:
        conversations[user_id] = []
    conversations[user_id].append({"role": "user", "content": user_message})
    messages = conversations[user_id][-20:]
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": CLAUDE_API_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001",
                  "max_tokens": 800,
                  "system": SYSTEM_PROMPT,
                  "messages": messages},
            timeout=30)
        data = res.json()
        if "error" in data:
            print(f"[Claude error] {data['error']}")
            return "متأسفم، مشکل موقتی. دوباره امتحان کن."
        reply = data["content"][0]["text"]
        conversations[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"[Claude exception] {e}")
        return "متأسفم، مشکل موقتی. دوباره امتحان کن."

def save_notion(name, phone, bale_id):
    print(f"[Notion] trying to save: name={name}, phone={phone}, bale_id={bale_id}")

    if not NOTION_TOKEN or not NOTION_DATABASE_ID or NOTION_TOKEN == "placeholder":
        print("[Notion] skipped: missing NOTION_TOKEN or NOTION_DATABASE_ID")
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
                    "نام": {
                        "title": [{"text": {"content": name or "نامشخص"}}]
                    },
                    "موبایل": {
                        "phone_number": phone or ""
                    },
                    "کانال ورودی": {
                        "status": {"name": "بله"}
                    },
                    "وضعیت لید": {
                        "status": {"name": "جدید"}
                    },
                    "آیدی بله": {
                        "rich_text": [{"text": {"content": str(bale_id or "")}}]
                    },
                }
            },
            timeout=10
        )

        print(f"[Notion status] {res.status_code}")
        print(f"[Notion response] {res.text}")

        if res.status_code in [200, 201]:
            print(f"[Notion] ✅ saved: {name} — {phone}")
        else:
            print("[Notion] ❌ failed")

    except Exception as e:
        print(f"[Notion error] {e}")

def set_webhook():
    webhook_url = f"{RENDER_URL}/webhook"
    try:
        res = requests.post(f"{BALE_BASE}/setWebhook",
            json={"url": webhook_url}, timeout=10)
        print(f"[Webhook] {res.json()}")
    except Exception as e:
        print(f"[Webhook error] {e}")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Homayoun is running")

    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.send_response(200)
        self.end_headers()

        try:
            update = json.loads(body)
            msg = update.get("message")
            if not msg:
                return

            chat_id    = msg["chat"]["id"]
            user_id    = str(msg["from"]["id"])
            first_name = msg["from"].get("first_name", "")
            text       = msg.get("text", "").strip()
            if not text:
                return

            print(f"[IN] {user_id} ({first_name}): {text[:80]}")

            if user_id not in user_info:
                user_info[user_id] = {"name": first_name, "phone": None, "saved": False}

            phone = extract_phone(text)
            if phone and not user_info[user_id]["saved"]:
                user_info[user_id]["phone"] = phone
                save_notion(first_name, phone, user_id)
                user_info[user_id]["saved"] = True

            reply = ask_claude(user_id, text)
            bale_send(chat_id, reply)
            print(f"[OUT] {reply[:80]}")

        except Exception as e:
            print(f"[Handler error] {e}")

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    print("همایون شروع به کار کرد — Webhook mode")
    set_webhook()
    port = int(os.environ.get("PORT", 10000))
    print(f"Server on port {port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
