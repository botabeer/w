import random, os, json
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

# --- جلسات لكل مصدر (فرد أو مجموعة) ---
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

# --- قراءة الأمثال من الملف ---
with open("proverbs.json", "r", encoding="utf-8") as f:
    emoji_proverbs = json.load(f)

# --- قراءة الألغاز من الملف ---
with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

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
        try:
            display_name = line_bot_api.get_profile(source_id).display_name
        except:
            display_name = "صديق"
    elif source_type == "group":
        source_id = event.source.group_id
        display_name = "المجموعة"
    elif source_type == "room":
        source_id = event.source.room_id
        display_name = "الغرفة"
    else:
        return

    # --- مساعدة ---
    if text == "مساعدة":
        reply = (
            "أوامر البوت:\n"
            "امثله → أمثال مصورة مع زر لإظهار المعنى\n"
            "لغز → ألغاز مع زر لإظهار الإجابة\n"
            "💡 في الأمثال والألغاز: اضغط على الزر لإظهار التلميح أولاً، ثم الإجابة."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # --- أمثال مصورة ---
    if text == "امثله":
        proverb = random.choice(emoji_proverbs)
        sessions[source_id] = {"type":"proverb", "text":proverb["text"]}
        emoji_text = split_text(proverb.get("emoji", ""))
        bubble = {
            "type": "bubble",
            "body": {"type":"box","layout":"vertical","contents":[
                {"type":"text","text":emoji_text,"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer": {"type":"box","layout":"vertical","contents":[
                {"type":"button","action":{"type":"postback","label":"اظهر المعنى","data":"show_proverb"}} 
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))
        return

    # --- ألغاز ---
    if text == "لغز":
        riddle = random.choice(riddles)
        sessions[source_id] = {"type":"riddle", "answer":riddle["answer"]}
        riddle_text = split_text(riddle["question"])
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":riddle_text,"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer":{"type":"box","layout":"vertical","contents":[
                {"type":"button","action":{"type":"postback","label":"اظهر الإجابة","data":"show_riddle"}} 
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="لغز", contents=bubble))
        return

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

    data = event.postback.data
    if source_id in sessions:
        session = sessions[source_id]
        if data == "show_riddle" and session.get("type")=="riddle":
            answer = session["answer"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 الإجابة: {answer}"))
        elif data == "show_proverb" and session.get("type")=="proverb":
            text = session["text"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 المعنى: {text}"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
