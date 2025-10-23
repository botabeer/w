import random, os
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

# جلسات لكل مصدر
sessions = {}

# دالة تقسيم النص الطويل
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

# أمثال مصورة
emoji_proverbs = [
    {"emoji":"👊 😭🏃👄", "text":"ضربني وبكى، سبقني واشتكى"},
    {"emoji":"👋💦👋🔥", "text":"من يده في الماء ليس كالذي يده في النار"},
    {"emoji":"🐒👀👩", "text":"القرد في عين أمه غزال"},
    {"emoji":"💤👑", "text":"النوم سلطان"},
    {"emoji":"✈🐦👆✈👇", "text":"الوقت كالسيف، إن لم تقطعه قطعك"},
    {"emoji":"📖💡👽🌊", "text":"العلم نور والجهل ظلام"},
]

# ألغاز
riddles = [
    {"question": "ما هو الشيء الذي كلما أخذت منه يكبر؟", "hint": "غالبًا نجده في الأرض", "answer": "الحفرة"},
    {"question": "له أوراق وليس شجرة، له جلد وليس حيوان، ما هو؟", "hint": "يقرأه الناس", "answer": "الكتاب"},
    {"question": "ما هو الشيء الذي يتكلم جميع لغات العالم؟", "hint": "تكراره يسمعه الجميع", "answer": "الصدى"},
]

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
    else:
        return

    # مساعدة - Flex
    if text == "مساعدة":
        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "📌 أوامر البوت", "weight": "bold", "size": "lg", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {"type": "button", "action": {"type": "postback", "label": "امثله", "data": "cmd_emoji_proverbs"}, "margin": "sm"},
                    {"type": "button", "action": {"type": "postback", "label": "لغز", "data": "cmd_riddle"}, "margin": "sm"}
                ]
            }
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أوامر البوت", contents=bubble))
        return

# --- الرد على أزرار Flex ---
@handler.add(PostbackEvent)
def handle_postback(event):
    source_type = event.source.type
    if source_type == "user":
        source_id = event.source.user_id
    elif source_type == "group":
        source_id = event.source.group_id
    else:
        return

    data = event.postback.data

    # أمر أمثال
    if data == "cmd_emoji_proverbs":
        proverb = random.choice(emoji_proverbs)
        sessions[source_id] = {"type":"proverb", "text":proverb["text"]}
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":split_text(proverb["emoji"]),"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer":{"type":"box","layout":"vertical","contents":[
                {"type":"button","action":{"type":"postback","label":"اظهر المعنى","data":"show_proverb"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))

    # أمر ألغاز
    elif data == "cmd_riddle":
        riddle = random.choice(riddles)
        sessions[source_id] = {"type":"riddle", "answer":riddle["answer"], "hint":riddle["hint"]}
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":split_text(riddle["question"]),"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer":{"type":"box","layout":"vertical","contents":[
                {"type":"button","action":{"type":"postback","label":"تلميح","data":"show_hint"}},
                {"type":"button","action":{"type":"postback","label":"اظهر الإجابة","data":"show_riddle"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="لغز", contents=bubble))

    # عرض الإجابة أو التلميح
    elif source_id in sessions:
        session = sessions[source_id]
        if data == "show_riddle" and session.get("type")=="riddle":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 الإجابة: {session['answer']}"))
        elif data == "show_proverb" and session.get("type")=="proverb":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 المعنى: {session['text']}"))
        elif data == "show_hint" and session.get("type")=="riddle":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 التلميح: {session['hint']}"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
