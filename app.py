import os, random, json
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, PostbackEvent

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- تحميل البيانات ---
with open("proverbs.json", "r", encoding="utf-8") as f:
    proverbs = json.load(f)

with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

# --- جلسات لكل مصدر ---
sessions = {}

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
            current_line = current_line + " " + word if current_line else word
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
        reply = "أوامر البوت:\nامثله\nلغز"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # --- أمثال ---
    if text == "امثله":
        index = random.randint(0, len(proverbs)-1)
        sessions[source_id] = {"type":"proverb", "index":index}
        show_proverb(event, source_id)
        return

    # --- ألغاز ---
    if text == "لغز":
        index = random.randint(0, len(riddles)-1)
        sessions[source_id] = {"type":"riddle", "index":index, "hint_shown":False}
        show_riddle(event, source_id)
        return

# --- أزرار Flex ---
def show_proverb(event, source_id):
    session = sessions[source_id]
    proverb = proverbs[session["index"]]
    emoji_text = split_text(proverb["emoji"])
    bubble = {
        "type":"bubble",
        "body":{"type":"box","layout":"vertical","contents":[
            {"type":"text","text":emoji_text,"weight":"bold","size":"lg","wrap":True}
        ]},
        "footer":{"type":"box","layout":"horizontal","contents":[
            {"type":"button","action":{"type":"postback","label":"🔜","data":"prev_proverb"}},
            {"type":"button","action":{"type":"postback","label":"☑️","data":"show_proverb"}},
            {"type":"button","action":{"type":"postback","label":"🔙","data":"next_proverb"}}
        ]}
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))

def show_riddle(event, source_id):
    session = sessions[source_id]
    riddle = riddles[session["index"]]
    riddle_text = split_text(riddle["question"])
    bubble = {
        "type":"bubble",
        "body":{"type":"box","layout":"vertical","contents":[
            {"type":"text","text":riddle_text,"weight":"bold","size":"lg","wrap":True}
        ]},
        "footer":{"type":"box","layout":"horizontal","contents":[
            {"type":"button","action":{"type":"postback","label":"🔜","data":"prev_riddle"}},
            {"type":"button","action":{"type":"postback","label":"💡","data":"hint_riddle"}},
            {"type":"button","action":{"type":"postback","label":"☑️","data":"show_riddle"}},
            {"type":"button","action":{"type":"postback","label":"🔙","data":"next_riddle"}}
        ]}
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="ألغاز", contents=bubble))

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

    if session["type"]=="proverb":
        if data=="show_proverb":
            proverb = proverbs[session["index"]]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 المعنى: {proverb['text']}"))
        elif data=="prev_proverb":
            session["index"] = (session["index"] - 1) % len(proverbs)
            show_proverb(event, source_id)
        elif data=="next_proverb":
            session["index"] = (session["index"] + 1) % len(proverbs)
            show_proverb(event, source_id)

    elif session["type"]=="riddle":
        riddle = riddles[session["index"]]
        if data=="hint_riddle":
            session["hint_shown"] = True
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 التلميح: {riddle.get('hint','')}" ))
        elif data=="show_riddle":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"☑️ الإجابة: {riddle['answer']}"))
        elif data=="prev_riddle":
            session["index"] = (session["index"] - 1) % len(riddles)
            session["hint_shown"] = False
            show_riddle(event, source_id)
        elif data=="next_riddle":
            session["index"] = (session["index"] + 1) % len(riddles)
            session["hint_shown"] = False
            show_riddle(event, source_id)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
