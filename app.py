import json, os, random
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, FlexSendMessage, PostbackEvent

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- تحميل الملفات ---
with open("proverbs.json", "r", encoding="utf-8") as f:
    proverbs = json.load(f)

with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

# --- جلسات لكل مستخدم/مجموعة ---
sessions = {}

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
            current_line = f"{current_line} {word}".strip() if current_line else word
    if current_line:
        lines.append(current_line)
    return "\n".join(lines)

# --- إنشاء نافذة Flex للأمثال أو الألغاز ---
def make_flex(session_type, index, show_hint=False, show_answer=False):
    if session_type=="proverb":
        item = proverbs[index]
        main_text = split_text(item["emoji"])
        hint = item["text"] if show_hint else ""
        answer = item["text"] if show_answer else ""
    else:
        item = riddles[index]
        main_text = split_text(item["question"])
        hint = item.get("hint","لا يوجد تلميح") if show_hint else ""
        answer = item["answer"] if show_answer else ""

    contents = [
        {"type":"text","text":main_text,"wrap":True,"weight":"bold"}
    ]
    if hint:
        contents.append({"type":"text","text":f"💡 التلميح: {hint}","wrap":True,"color":"#555555"})
    if answer:
        contents.append({"type":"text","text":f"💡 الإجابة: {answer}","wrap":True,"color":"#0000FF"})
    contents.append({"type":"separator"})
    contents.append({"type":"box","layout":"horizontal","contents":[
        {"type":"button","action":{"type":"postback","label":"السابق","data":"prev"}},
        {"type":"button","action":{"type":"postback","label":"تلميح","data":"hint"}},
        {"type":"button","action":{"type":"postback","label":"الإجابة","data":"answer"}},
        {"type":"button","action":{"type":"postback","label":"التالي","data":"next"}}
    ]})
    bubble = {"type":"bubble","body":{"type":"box","layout":"vertical","contents":contents}}
    return bubble

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
    source_id = getattr(event.source, f"{source_type}_id")

    if text == "امثله":
        index = random.randint(0, len(proverbs)-1)
        sessions[source_id] = {"type":"proverb","index":index,"show_hint":False,"show_answer":False}
        bubble = make_flex("proverb", index)
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="أمثال", contents=bubble))
        return

    if text == "لغز":
        index = random.randint(0, len(riddles)-1)
        sessions[source_id] = {"type":"riddle","index":index,"show_hint":False,"show_answer":False}
        bubble = make_flex("riddle", index)
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="لغز", contents=bubble))
        return

    if text == "مساعدة":
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":"أوامر البوت:\nامثله → أمثال مصورة مع زر لإظهار المعنى\nلغز → ألغاز مع زر لإظهار الإجابة","wrap":True,"size":"md"},
                {"type":"separator"},
                {"type":"box","layout":"horizontal","contents":[
                    {"type":"button","action":{"type":"postback","label":"السابق","data":"help_prev"}},
                    {"type":"button","action":{"type":"postback","label":"تلميح","data":"help_hint"}},
                    {"type":"button","action":{"type":"postback","label":"الإجابة","data":"help_answer"}},
                    {"type":"button","action":{"type":"postback","label":"التالي","data":"help_next"}}
                ]}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="مساعدة", contents=bubble))
        return

# --- الرد على أزرار Flex ---
@handler.add(PostbackEvent)
def handle_postback(event):
    source_type = event.source.type
    source_id = getattr(event.source, f"{source_type}_id")
    data = event.postback.data

    if source_id not in sessions:
        return
    session = sessions[source_id]
    index = session["index"]
    session_type = session["type"]

    if data=="prev":
        index = (index - 1) % (len(proverbs) if session_type=="proverb" else len(riddles))
        session["show_hint"] = False
        session["show_answer"] = False
    elif data=="next":
        index = (index + 1) % (len(proverbs) if session_type=="proverb" else len(riddles))
        session["show_hint"] = False
        session["show_answer"] = False
    elif data=="hint":
        session["show_hint"] = True
    elif data=="answer":
        session["show_answer"] = True

    session["index"] = index
    bubble = make_flex(session_type, index, show_hint=session.get("show_hint",False), show_answer=session.get("show_answer",False))
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text=session_type.capitalize(), contents=bubble))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
