import random, os
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, PostbackEvent
)
import json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- جلسات لكل مستخدم أو مجموعة ---
sessions = {}

# --- دالة تقسيم النص الطويل ---
def split_text(text, max_chars=50):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 > max_chars:
            lines.append(current_line)
            current_line = word
        else:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
    if current_line:
        lines.append(current_line)
    return "\n".join(lines)

# --- قراءة الملفات الخارجية ---
with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

with open("proverbs.json", "r", encoding="utf-8") as f:
    emoji_proverbs = json.load(f)

# --- إنشاء Flex Message ---
def make_flex(title, content, buttons):
    bubble = {
        "type":"bubble",
        "body":{"type":"box","layout":"vertical","contents":[
            {"type":"text","text":split_text(title),"weight":"bold","size":"lg","wrap":True},
            {"type":"text","text":split_text(content),"wrap":True,"size":"sm","margin":"md"} if content else {}
        ]},
        "footer":{"type":"box","layout":"vertical","contents":buttons}
    }
    return FlexSendMessage(alt_text=title, contents=bubble)

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
    if source_type == "user":
        source_id = event.source.user_id
    elif source_type == "group":
        source_id = event.source.group_id
    elif source_type == "room":
        source_id = event.source.room_id
    else:
        return

    # --- مساعدة ---
    if text == "مساعدة":
        reply = (
            "📌 أوامر البوت:\n"
            "امثله → أمثال مصورة مع زر لإظهار المعنى والسابق/التالي\n"
            "لغز → ألغاز مع زر لإظهار الإجابة والتلميح والسابق/التالي"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # --- أمثال ---
    if text == "امثله":
        random.shuffle(emoji_proverbs)
        sessions[source_id] = {"type":"proverb","items":emoji_proverbs,"index":0}
        send_proverb(source_id, event.reply_token)
        return

    # --- ألغاز ---
    if text == "لغز":
        random.shuffle(riddles)
        sessions[source_id] = {"type":"riddle","items":riddles,"index":0}
        send_riddle(source_id, event.reply_token)
        return

# --- إرسال أمثال ---
def send_proverb(source_id, reply_token):
    session = sessions[source_id]
    item = session["items"][session["index"]]
    buttons = [
        {"type":"button","action":{"type":"postback","label":"اظهر المعنى","data":"show_proverb"}},
        {"type":"button","action":{"type":"postback","label":"السابق","data":"prev"}},
        {"type":"button","action":{"type":"postback","label":"التالي","data":"next"}}
    ]
    flex_msg = make_flex(item["emoji"], "", buttons)
    line_bot_api.reply_message(reply_token, flex_msg)

# --- إرسال ألغاز ---
def send_riddle(source_id, reply_token):
    session = sessions[source_id]
    item = session["items"][session["index"]]
    buttons = [
        {"type":"button","action":{"type":"postback","label":"تلميح","data":"hint"}},
        {"type":"button","action":{"type":"postback","label":"اظهر الإجابة","data":"show_riddle"}},
        {"type":"button","action":{"type":"postback","label":"السابق","data":"prev"}},
        {"type":"button","action":{"type":"postback","label":"التالي","data":"next"}}
    ]
    flex_msg = make_flex(item["question"], "", buttons)
    line_bot_api.reply_message(reply_token, flex_msg)

# --- الرد على أزرار Flex ---
@handler.add(PostbackEvent)
def handle_postback(event):
    source_type = event.source.type
    if source_type == "user":
        source_id = event.source.user_id
    elif source_type == "group":
        source_id = event.source.group_id
    elif source_type == "room":
        source_id = event.source.room_id
    else:
        return

    if source_id not in sessions:
        return

    session = sessions[source_id]
    data = event.postback.data

    # --- التحكم بالتنقل بين العناصر ---
    if data == "next":
        session["index"] = (session["index"] + 1) % len(session["items"])
    elif data == "prev":
        session["index"] = (session["index"] - 1) % len(session["items"])
    
    # --- إظهار الإجابة أو المعنى ---
    if data == "show_riddle" and session["type"]=="riddle":
        answer = session["items"][session["index"]]["answer"]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 الإجابة: {answer}"))
        return
    elif data == "show_proverb" and session["type"]=="proverb":
        text = session["items"][session["index"]]["text"]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 المعنى: {text}"))
        return
    elif data == "hint" and session["type"]=="riddle":
        hint = session["items"][session["index"]].get("hint","لا يوجد تلميح.")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 تلميح: {hint}"))
        return

    # --- إعادة إرسال العنصر الحالي بعد السابق/التالي ---
    if session["type"]=="proverb":
        send_proverb(source_id, event.reply_token)
    elif session["type"]=="riddle":
        send_riddle(source_id, event.reply_token)

if __name__ == "__main__":
    port = int(os.getenv("PORT",5000))
    app.run(host="0.0.0.0", port=port)
