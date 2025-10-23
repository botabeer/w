from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
    ButtonsTemplate, PostbackAction
)
import os, json, random

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# تحميل الألغاز من ملف خارجي
with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

# حفظ حالة كل مستخدم (رقم اللغز الحالي)
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

def create_riddle_message(user_id):
    idx = user_state.get(user_id, 0)
    riddle = riddles[idx]
    text = f"🧩 {riddle['لغز']}"
    buttons = [
        PostbackAction(label="💡 تلميح/إجابة", data=f"hint_{idx}"),
        PostbackAction(label="⬅️ السابق", data="prev"),
        PostbackAction(label="➡️ التالي", data="next")
    ]
    return TemplateSendMessage(
        alt_text="لغز", 
        template=ButtonsTemplate(title="لغز اليوم", text=text, actions=buttons)
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()
    
    if text in ["لغز", "riddle"]:
        user_state[user_id] = 0
        message = create_riddle_message(user_id)
        line_bot_api.reply_message(event.reply_token, message)
    
    elif text == "مساعدة":
        help_text = (
            "🛠️ أوامر البوت:\n"
            "• 'لغز' : يعطيك لغز جديد.\n"
            "• أزرار اللغز:\n"
            "  💡 : يظهر التلميح أولاً، وإذا ضغط مرة ثانية يظهر الإجابة.\n"
            "  ⬅️ : لغز السابق\n"
            "  ➡️ : اللغز التالي\n"
            "• 'مساعدة' : يوضح هذه الرسالة."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))

@handler.add(MessageEvent, message=TextMessage)
def handle_postback(event):
    if not hasattr(event.message, "text"):
        return
    user_id = event.source.user_id
    data = event.message.text

    idx = user_state.get(user_id, 0)

    if data.startswith("hint_"):
        hint_idx = int(data.split("_")[1])
        riddle = riddles[hint_idx]
        reply = f"💡 تلميح: {riddle.get('تلميح','لا يوجد')} \n🔑 إجابة: {riddle.get('الإجابة','...')}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

    elif data == "next":
        idx = (idx + 1) % len(riddles)
        user_state[user_id] = idx
        message = create_riddle_message(user_id)
        line_bot_api.reply_message(event.reply_token, message)

    elif data == "prev":
        idx = (idx - 1) % len(riddles)
        user_state[user_id] = idx
        message = create_riddle_message(user_id)
        line_bot_api.reply_message(event.reply_token, message)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
