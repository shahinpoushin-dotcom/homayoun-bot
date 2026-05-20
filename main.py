import os
import re
import json
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

BALE_TOKEN         = os.environ.get("BALE_TOKEN", "")
CLAUDE_API_KEY     = os.environ.get("CLAUDE_API_KEY", "")
NOTION_TOKEN       = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
RENDER_URL         = os.environ.get("RENDER_URL", "https://homayoun-bot.onrender.com")

BALE_BASE = f"https://tapi.bale.ai/bot{BALE_TOKEN}"

COUNTRY_KNOWLEDGE = {
    "ایتالیا": {
        "مسیر": ["تحصیلی"],
        "وضعیت": "فعال",
        "توضیح": "مناسب تحصیل اروپا با بودجه متوسط. زبان بسته به دانشگاه انگلیسی یا ایتالیایی. نیاز به بررسی رشته، مدرک، گپ تحصیلی و شرایط مالی."
    },
    "آلمان": {
        "مسیر": ["تحصیلی", "کاری"],
        "وضعیت": "فعال",
        "توضیح_تحصیلی": "مناسب افراد منظم با زبان قوی و برنامه بلندمدت. نیاز به بررسی زبان، مدرک، سن، گپ و شرایط مالی.",
        "توضیح_کاری": "نیاز به معادل‌سازی مدرک، زبان آلمانی و سابقه کار. برای نیروهای متخصص مناسب‌تر."
    },
    "انگلستان": {
        "مسیر": ["تحصیلی"],
        "وضعیت": "فعال",
        "توضیح": "مناسب متقاضیانی با بودجه قوی و هدف تحصیلی مشخص. نیاز به بررسی زبان، بودجه، رشته و دانشگاه."
    },
    "ترکیه": {
        "مسیر": ["تحصیلی"],
        "وضعیت": "فعال",
        "توضیح": "مناسب کسانی که نزدیکی فرهنگی، هزینه منطقی‌تر و مسیر ساده‌تر می‌خواهند. بسته به دانشگاه، زبان ترکی یا انگلیسی مهم است."
    },
    "کانادا": {
        "مسیر": ["تحصیلی"],
        "وضعیت": "قابل بررسی",
        "توضیح": "نیاز به بودجه قوی، پرونده تحصیلی منطقی و مدارک مالی قابل دفاع. ریسک ویزا باید دقیق بررسی شود."
    },
    "هلند": {
        "مسیر": ["تحصیلی"],
        "وضعیت": "قابل بررسی",
        "توضیح": "مناسب تحصیل انگلیسی‌زبان در اروپا. نیاز به بودجه مناسب، زبان انگلیسی و انتخاب رشته دقیق."
    },
    "روسیه": {
        "مسیر": ["تحصیلی"],
        "وضعیت": "قابل بررسی",
        "توضیح": "مناسب برخی رشته‌ها. باید رشته، بودجه، زبان، سن و هدف اقامت بررسی شود."
    },
    "چین": {
        "مسیر": ["تحصیلی"],
        "وضعیت": "قابل بررسی",
        "توضیح": "مناسب تحصیل در آسیا. باید زبان تحصیل، رشته، دانشگاه، بودجه و هدف بررسی شود."
    },
    "قطر": {
        "مسیر": ["تحصیلی", "کاری"],
        "وضعیت": "با احتیاط",
        "توضیح_تحصیلی": "قابل بررسی در صورت وجود برنامه مناسب. باید رشته، بودجه، زبان و هدف بررسی شود.",
        "توضیح_کاری": "به دلیل شرایط منطقه‌ای باید محتاطانه توضیح داده شود. گزینه‌های امن‌تر هم پیشنهاد شود."
    },
    "عمان": {
        "مسیر": ["تحصیلی", "کاری"],
        "وضعیت": "با احتیاط",
        "توضیح_تحصیلی": "قابل بررسی در صورت وجود برنامه مناسب.",
        "توضیح_کاری": "نیاز به بررسی کارفرما، قرارداد، شغل و شرایط. با احتیاط توضیح داده شود."
    },
    "آذربایجان": {
        "مسیر": ["کاری"],
        "وضعیت": "اولویت اول",
        "توضیح": "اولویت اول مسیر کاری هما. مناسب مشاغل ساده، نیمه‌تخصصی و تخصصی. سن تا ۴۵ سال. حقوق ۷۰۰ تا ۸۰۰۰ منات. پروسه ۶ هفته.",
        "مدارک_متقاضی": ["پاسپورت رنگی", "عکس پرسنلی", "رزومه انگلیسی", "مدرک تحصیلی یا فنی‌وحرفه‌ای", "سابقه کار", "شماره تماس", "وضعیت تأهل"]
    },
    "لهستان": {
        "مسیر": ["کاری"],
        "وضعیت": "قابل بررسی",
        "توضیح": "مناسب کسانی که مسیر کاری اروپا می‌خواهند. باید سن، سابقه کار، رزومه و نوع شغل بررسی شود."
    },
    "رومانی": {
        "مسیر": ["تحصیلی", "کاری"],
        "وضعیت": "فعال",
        "توضیح_تحصیلی": "مناسب تحصیل در اروپا با هزینه منطقی‌تر. باید رشته، دانشگاه، زبان، بودجه، سن و مدرک بررسی شود.",
        "توضیح_کاری": "مناسب ورود کاری به اروپا. باید سابقه کار، مدرک، مهارت، رزومه، زبان، سن و نوع شغل بررسی شود."
    },
    "اسپانیا": {
        "مسیر": ["نومد ویزا", "اقامت خاص"],
        "وضعیت": "قابل بررسی",
        "توضیح": "برای نومد ویزا یا مسیرهای اقامتی خاص قابل بررسی. باید درآمد، شغل ریموت، مدارک مالی و بیمه بررسی شود."
    },
    "پرتغال": {
        "مسیر": ["نومد ویزا", "اقامت خاص"],
        "وضعیت": "قابل بررسی",
        "توضیح": "برای نومد ویزا یا مسیرهای اقامتی خاص قابل بررسی. باید درآمد، شغل ریموت، مدارک مالی و بیمه بررسی شود."
    }
}

COUNTRY_KNOWLEDGE_STR = json.dumps(COUNTRY_KNOWLEDGE, ensure_ascii=False, indent=2)

SYSTEM_PROMPT = f"""تو همایون هستی — مشاور اولیه موسسه مهاجرتی هما.

⚠️ قوانین زبانی:
- هیچ‌وقت از کلمه «خیار» استفاده نکن — همیشه «گزینه»
- فارسی روان، طبیعی و بدون غلط نوشتاری بنویس
- پاسخ‌ها کوتاه و مفید — معمولاً حداکثر ۵ تا ۶ خط
- لحن صمیمی، انسانی، قابل اعتماد و حرفه‌ای باشد
- مکالمه شبیه فرم خشک نباشد
- اطلاعات را طبیعی و مرحله‌به‌مرحله بپرس
- اگر کاربر چند اطلاعات را یک‌جا داد، همان‌ها را تحلیل کن و فقط موارد ناقص را بپرس
- قیمت دقیق نده
- تضمین ویزا، تضمین کار، تضمین پذیرش یا نظر حقوقی قطعی نده

جمله شروع:
«سلام! خوش اومدی! من همایون هستم، مشاور اولیه موسسه مهاجرتی هما. چه کمکی می‌تونم بکنم؟»

اطلاعات موسسه هما:
- سایت: homaic.com
- تماس: 026-32232003 | 021-91010246 | 0936-2552218
- آدرس: کرج، میدان توحید، جنب درمانگاه نفت، پلاک 102، مجتمع هما

اطلاعاتی که باید طبیعی جمع کنی:
نام، موبایل، مسیر (تحصیلی/کاری/نومد ویزا/اقامت خاص)، کشور درخواستی، سن، مدرک تحصیلی، رشته، سطح زبان، سابقه کاری، سابقه بیمه، بودجه تقریبی، بازه زمانی اقدام، سابقه رد ویزا، کشور و شهر محل تماس، ایمیل اگر داد.

هندآف فوری به مشاور:
- سن بالای ۴۵ سال + مسیر تحصیلی
- سابقه رد ویزا
- سوال درباره هزینه خدمات
- وضعیت پیچیده
- متقاضی جدی با شماره موبایل
- پرسش‌های حقوقی یا قطعی

اگر کسی درباره هزینه‌های خدمات پرسید بگو:
«برای اطلاعات دقیق هزینه‌ها، همکارم از واحد مالی باهات تماس می‌گیره. شماره موبایلت رو بده تا هماهنگ کنیم.»

اطلاعات کشورها:
{COUNTRY_KNOWLEDGE_STR}

قوانین استفاده از اطلاعات کشورها:
- اگر کاربر کشور را گفت، بررسی کن برای چه مسیری در هما فعال است
- اگر کاربر نگفت تحصیلی یا کاری، اول بپرس
- اگر کشور در لیست نبود، بگو قابل بررسی است و اطلاعات پایه را بگیر
- درباره کشورهایی که خدمات فعال ندارند با قطعیت نظر نده"""

EXTRACTOR_PROMPT = """تو یک Extractor هستی. از مکالمه زیر فقط یک JSON معتبر برگردان. هیچ متن دیگری ننویس. بدون markdown. بدون توضیح.

قوانین:
- اگر فیلدی وجود نداشت، مقدار خالی یا نامشخص بگذار
- شماره موبایل را به فرمت 09xxxxxxxxx تبدیل کن (اعداد فارسی، عربی و انگلیسی همه قبول)
- کانال ورودی همیشه "بله"
- وضعیت لید همیشه "جدید"
- تماس اولیه همیشه "نیاز به تماس"
- لینک واتس‌اپ را از شماره موبایل بساز: https://wa.me/98XXXXXXXXXX
- تاریخ ثبت ISO-8601 باشد
- خلاصه رزومه کوتاه ولی مفید باشد: مسیر، کشور، سن، مدرک، زبان، سابقه، بودجه اگر موجود بود

ساختار JSON:
{
  "نام": "",
  "موبایل": "",
  "کانال ورودی": "بله",
  "وضعیت لید": "جدید",
  "تماس اولیه": "نیاز به تماس",
  "مسیر": "",
  "کشور درخواستی": "",
  "کشور مخاطب (از کجا تماس گرفت)": "",
  "شهر مخاطب (از کجا تماس گرفت)": "",
  "ایمیل": "",
  "آیدی بله": "",
  "لینک واتس‌اپ": "",
  "خلاصه رزومه": "",
  "تاریخ ثبت": ""
}"""

conversations = {}
user_info = {}
pending_timers = {}
pending_messages = {}
notion_saved = {}


def normalize_digits(text):
    if not text:
        return ""
    fa_digits = "۰۱۲۳۴۵۶۷۸۹"
    ar_digits = "٠١٢٣٤٥٦٧٨٩"
    for i in range(10):
        text = text.replace(fa_digits[i], str(i))
        text = text.replace(ar_digits[i], str(i))
    return text


def normalize_phone_to_iran_mobile(raw):
    if not raw:
        return None
    raw = normalize_digits(raw)
    raw = re.sub(r'[\s\-\(\)\.\u200c\u200b\u200f\u00a0]+', '', raw)
    if raw.startswith("+98"):
        raw = "0" + raw[3:]
    elif raw.startswith("0098"):
        raw = "0" + raw[4:]
    elif raw.startswith("98") and len(raw) == 12:
        raw = "0" + raw[2:]
    if re.fullmatch(r"09\d{9}", raw):
        return raw
    return None


def extract_phone(text):
    if not text:
        return None
    text_norm = normalize_digits(text)
    compact = re.sub(r'[\s\-\(\)\.\u200c\u200b\u200f\u00a0]+', '', text_norm)
    pattern = r'(?:(?:\+98|0098|98|0)9\d{9})'
    match = re.search(pattern, compact)
    if match:
        return normalize_phone_to_iran_mobile(match.group())
    return None


def build_whatsapp_link(mobile):
    if not mobile:
        return ""
    number = mobile.lstrip("0")
    return f"https://wa.me/98{number}"


def bale_send(chat_id, text):
    try:
        requests.post(
            f"{BALE_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"[Bale send error] {e}")


def ask_claude(user_id, user_message):
    if user_id not in conversations:
        conversations[user_id] = []
    conversations[user_id].append({"role": "user", "content": user_message})
    messages = conversations[user_id][-20:]

    for attempt in range(3):
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
                err_type = data["error"].get("type", "")
                if "overloaded" in err_type or "capacity" in err_type:
                    print(f"[Claude overloaded] attempt {attempt + 1}")
                    time.sleep(2 * (attempt + 1))
                    continue
                print(f"[Claude error] {data['error']}")
                return "متأسفم، الان پاسخ‌دهی کمی کند شده. لطفاً چند لحظه دیگه دوباره پیام بده 🙏"

            reply = data["content"][0]["text"]
            conversations[user_id].append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            print(f"[Claude exception] attempt {attempt + 1}: {e}")
            time.sleep(2 * (attempt + 1))

    print(f"[Claude failed] all retries exhausted for user {user_id}")
    return "متأسفم، الان پاسخ‌دهی کمی کند شده. لطفاً چند لحظه دیگه دوباره پیام بده 🙏"


def extract_info_with_claude(user_id, first_name, bale_id):
    if user_id not in conversations:
        return None
    convo_text = "\n".join([
        f"{'کاربر' if m['role'] == 'user' else 'همایون'}: {m['content']}"
        for m in conversations[user_id]
    ])
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
                "max_tokens": 600,
                "system": EXTRACTOR_PROMPT,
                "messages": [{"role": "user", "content": convo_text}]
            },
            timeout=30
        )
        data = res.json()
        raw = data["content"][0]["text"].strip()
        print(f"[Extractor raw] {raw[:200]}")
        info = json.loads(raw)

        if not info.get("آیدی بله"):
            info["آیدی بله"] = str(bale_id)
        if not info.get("نام") or info["نام"] == "نامشخص":
            info["نام"] = first_name
        if not info.get("تاریخ ثبت"):
            info["تاریخ ثبت"] = datetime.now(timezone.utc).isoformat()
        if info.get("موبایل") and not info.get("لینک واتس‌اپ"):
            info["لینک واتس‌اپ"] = build_whatsapp_link(info["موبایل"])

        return info
    except Exception as e:
        print(f"[Extractor error] {e}")
        return None


def save_to_notion(info):
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return False

    phone = info.get("موبایل", "") or ""
    email = info.get("ایمیل", "") or ""
    whatsapp = info.get("لینک واتس‌اپ", "") or ""
    country = info.get("کشور درخواستی", "نامشخص") or "نامشخص"

    properties = {
        "نام": {"title": [{"text": {"content": info.get("نام", "نامشخص")}}]},
        "کانال ورودی": {"select": {"name": "بله"}},
        "وضعیت لید": {"status": {"name": "جدید"}},
        "تماس اولیه": {"status": {"name": "نیاز به تماس"}},
        "آیدی بله": {"rich_text": [{"text": {"content": str(info.get("آیدی بله", ""))}}]},
        "آیدی تلگرام": {"rich_text": [{"text": {"content": ""}}]},
        "آیدی روبیکا": {"rich_text": [{"text": {"content": ""}}]},
        "آیدی سروش": {"rich_text": [{"text": {"content": ""}}]},
        "کشور مخاطب (از کجا تماس گرفت)": {"rich_text": [{"text": {"content": info.get("کشور مخاطب (از کجا تماس گرفت)", "")}}]},
        "شهر مخاطب (از کجا تماس گرفت)": {"rich_text": [{"text": {"content": info.get("شهر مخاطب (از کجا تماس گرفت)", "")}}]},
        "خلاصه رزومه": {"rich_text": [{"text": {"content": info.get("خلاصه رزومه", "")}}]},
        "فرصت‌های شغلی": {"rich_text": [{"text": {"content": ""}}]},
    }

    if phone:
        properties["موبایل"] = {"phone_number": phone}

    if email:
        properties["ایمیل"] = {"email": email}
    else:
        properties["ایمیل"] = {"email": None}

    if whatsapp:
        properties["لینک واتس‌اپ"] = {"url": whatsapp}
    else:
        properties["لینک واتس‌اپ"] = {"url": None}

    if info.get("تاریخ ثبت"):
        properties["تاریخ ثبت"] = {"date": {"start": info["تاریخ ثبت"]}}

    try:
        properties["کشور درخواستی"] = {"select": {"name": country}}
        notion_res = requests.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            },
            json={"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties},
            timeout=15
        )
        print(f"[Notion status] {notion_res.status_code}")
        print(f"[Notion response] {notion_res.text[:300]}")

        if notion_res.json().get("object") == "page":
            print(f"[Notion] ✅ saved — {info.get('نام')}")
            return True
        else:
            raise Exception("not a page object")

    except Exception:
        try:
            properties["کشور درخواستی"] = {"select": None}
            notion_res = requests.post(
                "https://api.notion.com/v1/pages",
                headers={
                    "Authorization": f"Bearer {NOTION_TOKEN}",
                    "Content-Type": "application/json",
                    "Notion-Version": "2022-06-28"
                },
                json={"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties},
                timeout=15
            )
            print(f"[Notion status] {notion_res.status_code}")
            print(f"[Notion response] {notion_res.text[:300]}")
            if notion_res.json().get("object") == "page":
                print(f"[Notion] ✅ saved (fallback) — {info.get('نام')}")
                return True
        except Exception as e2:
            print(f"[Notion error] {e2}")

    return False


def should_save(user_id):
    if notion_saved.get(user_id):
        return False
    if user_id not in conversations:
        return False
    convo = conversations[user_id]
    all_text = " ".join([m["content"] for m in convo])
    phone = extract_phone(all_text)
    if phone:
        return True
    if len(convo) < 4:
        return False
    keywords = [
        "سال", "مدرک", "سابقه", "زبان", "کشور", "ایتالیا", "آلمان",
        "آذربایجان", "قطر", "عمان", "لهستان", "رومانی", "ترکیه",
        "انگلستان", "کانادا", "هلند", "روسیه", "چین", "اسپانیا",
        "پرتغال", "تحصیل", "کار", "مهاجرت", "نومد"
    ]
    hits = sum(1 for k in keywords if k in all_text)
    return hits >= 3


def run_save(user_id, first_name, bale_id):
    info = extract_info_with_claude(user_id, first_name, bale_id)
    if info:
        saved = save_to_notion(info)
        if saved:
            notion_saved[user_id] = True


def process_message(chat_id, user_id, first_name, text):
    phone = extract_phone(text)
    if phone:
        print(f"[Phone detected] {user_id}")
        if user_id not in user_info:
            user_info[user_id] = {}
        user_info[user_id]["phone"] = phone

    reply = ask_claude(user_id, text)
    bale_send(chat_id, reply)
    print(f"[OUT] {reply[:100]}")

    if should_save(user_id):
        threading.Thread(
            target=run_save,
            args=(user_id, first_name, user_id),
            daemon=True
        ).start()


def handle_pending(chat_id, user_id, first_name):
    messages = pending_messages.pop(user_id, [])
    if not messages:
        return
    combined = " ".join(messages)
    print(f"[IN] {user_id} ({first_name}): {combined[:120]}")
    process_message(chat_id, user_id, first_name, combined)


def set_webhook():
    webhook_url = f"{RENDER_URL}/webhook"
    try:
        res = requests.post(
            f"{BALE_BASE}/setWebhook",
            json={"url": webhook_url},
            timeout=10
        )
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

            if user_id not in pending_messages:
                pending_messages[user_id] = []
            pending_messages[user_id].append(text)

            if user_id in pending_timers:
                pending_timers[user_id].cancel()

            timer = threading.Timer(
                3.0,
                handle_pending,
                args=(chat_id, user_id, first_name)
            )
            pending_timers[user_id] = timer
            timer.start()

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
