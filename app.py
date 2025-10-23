from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, PostbackEvent
import json, os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# تحميل الأمثال
with open("proverbs.json", "r", encoding="utf-8") as f:
    proverbs = json.load(f)

# تحميل الألغاز
with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

# حفظ حالة المستخدم (مؤقت)
user_state = {}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # أمر مساعدة
    if text == "مساعدة":
        help_bubble = {
            "type": "bubble",
            "header": {"type": "box", "layout": "vertical", "contents":[
                {"type":"text","text":"📜 أوامر البوت","weight":"bold","size":"lg"}
            ]},
            "body": {"type":"box","layout":"vertical","contents":[
                {"type":"text","text":"أمثلة → عرض الأمثال"},
                {"type":"text","text":"لغز → عرض لغز"},
                {"type":"text","text":"💡 → يظهر التلميح أولاً، وإذا ضغط مرة ثانية يظهر الإجابة"},
                {"type":"text","text":"⬅️ → السابق"},
                {"type":"text","text":"➡️ → التالي"}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="مساعدة", contents=help_bubble))
        return

    # بدء أمثال
    if text == "أمثلة":
        user_state[user_id] = {"type": "proverb", "index": 0}
        proverb = proverbs[0]["text"]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(proverb))
        return

    # بدء ألغاز
    if text == "لغز":
        user_state[user_id] = {"type": "riddle", "index": 0, "show_hint": False}
        r = riddles[0]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(f"🔹 {r['question']}"))
        return

    # زر 💡
    if text == "💡" and user_id in user_state:
        state = user_state[user_id]
        if state["type"] == "riddle":
            idx = state["index"]
            r = riddles[idx]
            if not state.get("show_hint"):
                state["show_hint"] = True
                line_bot_api.reply_message(event.reply_token, TextSendMessage(f"💡 تلميح: {r['hint']}"))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(f"✅ الإجابة: {r['answer']}"))
        return

    # التنقل ⬅️ ➡️
    if text in ["⬅️", "➡️"] and user_id in user_state:
        state = user_state[user_id]
        idx = state["index"]
        data_list = proverbs if state["type"] == "proverb" else riddles
        if text == "⬅️":
            idx = (idx - 1) % len(data_list)
        else:
            idx = (idx + 1) % len(data_list)
        state["index"] = idx
        state["show_hint"] = False
        content = data_list[idx]["text"] if state["type"] == "proverb" else data_list[idx]["question"]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(content))
        return

    # أي رسالة أخرى
    line_bot_api.reply_message(event.reply_token, TextSendMessage("اكتب 'مساعدة' لرؤية الأوامر"))

if __name__ == "__main__":
    app.run()
