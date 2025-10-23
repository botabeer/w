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

# --- جلسات لكل مصدر (فرد أو مجموعة) ---
sessions = {}

# --- تحميل الملفات ---
with open("proverbs.json", "r", encoding="utf-8") as f:
    emoji_proverbs = json.load(f)

with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

# --- تقسيم النص الطويل ---
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
        try:
            display_name = line_bot_api.get_profile(source_id).display_name
        except:
            display_name = "صديق"
    elif source_type == "group":
        source_id = event.source.group_id
        display_name = "المجموعة"
    else:
        return

    # --- مساعدة ---
    if text == "مساعدة":
        reply = (
            "أوامر البوت:\n"
            "امثله → أمثال مصورة\n"
            "لغز → ألغاز"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # --- أمثال مصورة ---
    if text == "امثله":
        index = 0
        sessions[source_id] = {"type": "proverb", "index": index}
        proverb = emoji_proverbs[index]
        emoji_text = split_text(proverb["emoji"])
        bubble = {
            "type": "bubble",
            "body": {"type":"box","layout":"vertical","contents":[
                {"type":"text","text":emoji_text,"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer":{"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"🔜","data":"prev_proverb"}},
                {"type":"button","action":{"type":"postback","label":"☑️","data":"show_proverb"}},
                {"type":"button","action":{"type":"postback","label":"🔙","data":"next_proverb"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))
        return

    # --- ألغاز ---
    if text == "لغز":
        index = 0
        sessions[source_id] = {"type":"riddle", "index": index}
        riddle = riddles[index]
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
    else:
        return

    data = event.postback.data
    if source_id not in sessions:
        return

    session = sessions[source_id]
    # --- أمثال ---
    if session["type"] == "proverb":
        idx = session.get("index",0)
        if data == "show_proverb":
            text = emoji_proverbs[idx]["text"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"☑️ المعنى: {text}"))
        elif data == "next_proverb":
            idx = (idx + 1) % len(emoji_proverbs)
            session["index"] = idx
        elif data == "prev_proverb":
            idx = (idx - 1 + len(emoji_proverbs)) % len(emoji_proverbs)
            session["index"] = idx

        # إعادة عرض النافذة
        proverb = emoji_proverbs[idx]
        emoji_text = split_text(proverb["emoji"])
        bubble = {
            "type": "bubble",
            "body": {"type":"box","layout":"vertical","contents":[
                {"type":"text","text":emoji_text,"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer":{"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"🔜","data":"prev_proverb"}},
                {"type":"button","action":{"type":"postback","label":"☑️","data":"show_proverb"}},
                {"type":"button","action":{"type":"postback","label":"🔙","data":"next_proverb"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))

    # --- ألغاز ---
    elif session["type"] == "riddle":
        idx = session.get("index",0)
        riddle = riddles[idx]
        if data == "show_riddle":
            answer = riddle["answer"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"☑️ الإجابة: {answer}"))
        elif data == "hint_riddle":
            hint = riddle.get("hint","💡 التلميح غير متوفر")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 التلميح: {hint}"))
        elif data == "next_riddle":
            idx = (idx + 1) % len(riddles)
            session["index"] = idx
        elif data == "prev_riddle":
            idx = (idx - 1 + len(riddles)) % len(riddles)
            session["index"] = idx

        # إعادة عرض نافذة اللغز
        riddle = riddles[idx]
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
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="لغز", contents=bubble))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
