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

sessions = {}

# --- تحميل الملفات ---
with open("proverbs.json", "r", encoding="utf-8") as f:
    emoji_proverbs = json.load(f)

with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

# --- تقسيم النص ---
def split_text(text, max_chars=50):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 > max_chars:
            lines.append(current_line)
            current_line = word
        else:
            current_line = f"{current_line} {word}" if current_line else word
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

# --- الرسائل ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    source_type = event.source.type
    source_id = getattr(event.source, f"{source_type}_id", None)
    if not source_id:
        return

    # --- نافذة المساعدة ---
    if text == "مساعدة":
        bubble = {
            "type":"bubble",
            "body":{
                "type":"box",
                "layout":"vertical",
                "contents":[
                    {"type":"text","text":"أوامر البوت","weight":"bold","size":"lg","wrap":True},
                    {"type":"separator","margin":"md"}  # خط فاصل
                ]
            },
            "footer":{
                "type":"box",
                "layout":"horizontal",
                "contents":[
                    {"type":"button","action":{"type":"postback","label":"امثله","data":"help_proverb"}},
                    {"type":"button","action":{"type":"postback","label":"لغز","data":"help_riddle"}}
                ]
            }
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="مساعدة", contents=bubble))
        return

    # --- أمر "امثله" يشتغل من الكتابة ---
    if text == "امثله":
        proverb = random.choice(emoji_proverbs)
        sessions[source_id] = {"type":"proverb", "text":proverb["text"]}
        emoji_text = split_text(proverb["emoji"])
        bubble = {
            "type": "bubble",
            "body": {"type":"box","layout":"vertical","contents":[
                {"type":"text","text":emoji_text,"weight":"bold","size":"lg","wrap":True},
                {"type":"separator","margin":"md"}  # خط فاصل
            ]},
            "footer": {"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"الإجابة","data":"show_proverb"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))
        return

    # --- أمر "لغز" يشتغل من الكتابة ---
    if text == "لغز":
        riddle = random.choice(riddles)
        sessions[source_id] = {"type":"riddle", "answer":riddle["answer"], "hint":riddle.get("hint","")}
        riddle_text = split_text(riddle["question"])
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":riddle_text,"weight":"bold","size":"lg","wrap":True},
                {"type":"separator","margin":"md"}  # خط فاصل
            ]},
            "footer":{"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"تلميح","data":"riddle_hint"}},
                {"type":"button","action":{"type":"postback","label":"الإجابة","data":"show_riddle"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="لغز", contents=bubble))
        return

# --- Postback Events ---
@handler.add(PostbackEvent)
def handle_postback(event):
    source_type = event.source.type
    source_id = getattr(event.source, f"{source_type}_id", None)
    if not source_id:
        return

    data = event.postback.data

    # --- مساعدة أمثال ---
    if data == "help_proverb":
        proverb = random.choice(emoji_proverbs)
        sessions[source_id] = {"type":"proverb", "text":proverb["text"]}
        emoji_text = split_text(proverb["emoji"])
        bubble = {
            "type": "bubble",
            "body": {"type":"box","layout":"vertical","contents":[
                {"type":"text","text":emoji_text,"weight":"bold","size":"lg","wrap":True},
                {"type":"separator","margin":"md"}  # خط فاصل
            ]},
            "footer": {"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"الإجابة","data":"show_proverb"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))
        return

    # --- مساعدة ألغاز ---
    elif data == "help_riddle":
        riddle = random.choice(riddles)
        sessions[source_id] = {"type":"riddle", "answer":riddle["answer"], "hint":riddle.get("hint","")}
        riddle_text = split_text(riddle["question"])
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":riddle_text,"weight":"bold","size":"lg","wrap":True},
                {"type":"separator","margin":"md"}  # خط فاصل
            ]},
            "footer":{"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"تلميح","data":"riddle_hint"}},
                {"type":"button","action":{"type":"postback","label":"الإجابة","data":"show_riddle"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="لغز", contents=bubble))
        return

    # --- عرض الإجابة أو التلميح ---
    if source_id in sessions:
        session = sessions[source_id]
        if data == "show_riddle" and session.get("type")=="riddle":
            answer = session["answer"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"الإجابة: {answer}"))
        elif data == "riddle_hint" and session.get("type")=="riddle":
            hint = session.get("hint", "لا يوجد تلميح")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"تلميح: {hint}"))
        elif data == "show_proverb" and session.get("type")=="proverb":
            text = session["text"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"الإجابة: {text}"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
