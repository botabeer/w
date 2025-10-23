import os, random, json
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

# --- جلسات لكل مصدر ---
sessions = {}

# --- تحميل البيانات ---
with open("proverbs.json", "r", encoding="utf-8") as f:
    proverbs = json.load(f)

with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

# --- دالة تقسيم النص ---
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
        bubble = {
            "type": "bubble",
            "body": {"type": "box", "layout": "vertical","contents":[
                {"type":"text","text":"أوامر البوت:\nامثله\nلغز","wrap":True,"weight":"bold","size":"md"}
            ]},
            "footer": {"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"🔜","data":"help_next"}},
                {"type":"button","action":{"type":"postback","label":"🔙","data":"help_prev"}}
            ],
            "justifyContent":"flex-start"}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="مساعدة", contents=bubble))
        return

    # --- أمثال ---
    if text == "امثله":
        proverb = random.choice(proverbs)
        sessions[source_id] = {"type":"proverb", "text":proverb["text"]}
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":split_text(proverb["emoji"]),"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer":{"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"🔜","data":"proverb_next"}},
                {"type":"button","action":{"type":"postback","label":"☑️","data":"proverb_show"}},
                {"type":"button","action":{"type":"postback","label":"🔙","data":"proverb_prev"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))
        return

    # --- ألغاز ---
    if text == "لغز":
        riddle = random.choice(riddles)
        sessions[source_id] = {"type":"riddle", "question":riddle["question"], "answer":riddle["answer"]}
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":split_text(riddle["question"]),"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer":{"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"🔜","data":"riddle_next"}},
                {"type":"button","action":{"type":"postback","label":"💡","data":"riddle_hint"}},
                {"type":"button","action":{"type":"postback","label":"☑️","data":"riddle_show"}},
                {"type":"button","action":{"type":"postback","label":"🔙","data":"riddle_prev"}}
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

        # --- أمثال ---
        if data == "proverb_show" and session.get("type")=="proverb":
            text = session["text"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 المعنى: {text}"))

        # --- ألغاز ---
        elif data == "riddle_show" and session.get("type")=="riddle":
            answer = session["answer"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"☑️ الإجابة: {answer}"))
        elif data == "riddle_hint" and session.get("type")=="riddle":
            question = session["question"]
            hint = question[:int(len(question)/2)] + "..."  # مثال للتلميح: نصف السؤال
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 التلميح: {hint}"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
