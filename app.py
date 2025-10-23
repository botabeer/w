import os, json, random
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, PostbackEvent
)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- تحميل الملفات ---
with open("proverbs.json", "r", encoding="utf-8") as f:
    proverbs_list = json.load(f)

with open("riddles.json", "r", encoding="utf-8") as f:
    riddles_list = json.load(f)

# --- جلسات لكل مصدر ---
sessions = {}

# --- تقسيم النص الطويل ---
def split_text(text, max_chars=50):
    words = text.split()
    lines, current_line = [], ""
    for word in words:
        if len(current_line) + len(word) + 1 > max_chars:
            lines.append(current_line)
            current_line = word
        else:
            current_line = f"{current_line} {word}".strip() if current_line else word
    if current_line:
        lines.append(current_line)
    return "\n".join(lines)

# --- Webhook ---
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature")
    except Exception as e:
        print(f"Webhook exception: {e}")
    return "OK", 200

# --- التعامل مع الرسائل ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    source_type = event.source.type
    source_id = getattr(event.source, f"{source_type}_id", None)
    if not source_id:
        return

    # --- مساعدة ---
    if text.lower() == "مساعدة":
        reply = (
            "📌 أوامر البوت:\n"
            "امثله → لإظهار مثل مصور.\n"
            "لغز → لإظهار لغز.\n"
            "زر التلميح متاح لإظهار تلميح.\n"
            "زر السابق والتالي للتنقل بين الأمثال والألغاز."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # --- أمثال ---
    if text.lower() == "امثله":
        index = random.randint(0, len(proverbs_list)-1)
        sessions[source_id] = {"type":"proverb", "index": index}
        send_proverb(event, index)
        return

    # --- ألغاز ---
    if text.lower() == "لغز":
        index = random.randint(0, len(riddles_list)-1)
        sessions[source_id] = {"type":"riddle", "index": index}
        send_riddle(event, index)
        return

# --- إرسال مثل ---
def send_proverb(event, index):
    proverb = proverbs_list[index]
    bubble = {
        "type": "bubble",
        "body": {"type":"box","layout":"vertical","contents":[
            {"type":"text","text":split_text(proverb["emoji"]),"weight":"bold","size":"lg","wrap":True}
        ]},
        "footer":{"type":"box","layout":"vertical","contents":[
            {"type":"button","action":{"type":"postback","label":"اظهر المعنى","data":"show_proverb"}},
            {"type":"button","action":{"type":"postback","label":"السابق","data":"prev"}},
            {"type":"button","action":{"type":"postback","label":"التالي","data":"next"}}
        ]}
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="مثل", contents=bubble))

# --- إرسال لغز ---
def send_riddle(event, index):
    riddle = riddles_list[index]
    bubble = {
        "type":"bubble",
        "body":{"type":"box","layout":"vertical","contents":[
            {"type":"text","text":split_text(riddle["لغز"]),"weight":"bold","size":"lg","wrap":True}
        ]},
        "footer":{"type":"box","layout":"vertical","contents":[
            {"type":"button","action":{"type":"postback","label":"اظهر التلميح","data":"hint"}},
            {"type":"button","action":{"type":"postback","label":"اظهر الإجابة","data":"answer"}},
            {"type":"button","action":{"type":"postback","label":"السابق","data":"prev"}},
            {"type":"button","action":{"type":"postback","label":"التالي","data":"next"}}
        ]}
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="لغز", contents=bubble))

# --- الرد على أزرار Flex ---
@handler.add(PostbackEvent)
def handle_postback(event):
    source_type = event.source.type
    source_id = getattr(event.source, f"{source_type}_id", None)
    if not source_id or source_id not in sessions:
        return

    session = sessions[source_id]
    data = event.postback.data

    # --- أمثال ---
    if session["type"]=="proverb":
        index = session["index"]
        if data == "show_proverb":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"💡 المعنى: {proverbs_list[index]['text']}"))
        elif data == "next":
            index = (index + 1) % len(proverbs_list)
            sessions[source_id]["index"] = index
            send_proverb(event, index)
        elif data == "prev":
            index = (index - 1) % len(proverbs_list)
            sessions[source_id]["index"] = index
            send_proverb(event, index)

    # --- ألغاز ---
    elif session["type"]=="riddle":
        index = session["index"]
        if data == "hint":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"💡 التلميح: {riddles_list[index]['تلميح']}"))
        elif data == "answer":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"✅ الإجابة: {riddles_list[index]['الإجابة']}"))
        elif data == "next":
            index = (index + 1) % len(riddles_list)
            sessions[source_id]["index"] = index
            send_riddle(event, index)
        elif data == "prev":
            index = (index - 1) % len(riddles_list)
            sessions[source_id]["index"] = index
            send_riddle(event, index)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
