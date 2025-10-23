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

# --- تحميل البيانات من الملفات ---
with open("proverbs.json", "r", encoding="utf-8") as f:
    emoji_proverbs = json.load(f)

with open("riddles.json", "r", encoding="utf-8") as f:
    riddles = json.load(f)

# --- جلسات لكل مصدر ---
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
            current_line = f"{current_line} {word}" if current_line else word
    if current_line:
        lines.append(current_line)
    return "\n".join(lines)

# --- نافذة مساعدة ---
def send_help(event):
    bubble = {
        "type": "bubble",
        "body": {
            "type":"box","layout":"vertical","contents":[
                {"type":"text","text":"مساعدة البوت","weight":"bold","size":"xl","wrap":True,"align":"center","color":"#1A237E"},
                {"type":"text","text":"💡 أمثال مصورة: أمثال مع زر لإظهار المعنى","wrap":True,"margin":"md"},
                {"type":"button","style":"primary","action":{"type":"postback","label":"تجربة أمثال","data":"help_proverb"}},
                {"type":"text","text":"🧩 ألغاز: ألغاز مع زر التلميح / الإجابة والسابق / التالي","wrap":True,"margin":"md"},
                {"type":"button","style":"primary","action":{"type":"postback","label":"تجربة ألغاز","data":"help_riddle"}}
            ]
        },
        "styles":{"body":{"backgroundColor":"#E8EAF6"}}
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage("مساعدة", bubble))

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
        send_help(event)
        return

    # --- أمثال مصورة ---
    if text in ["امثله","تجربة أمثال","help_proverb"]:
        proverb = random.choice(emoji_proverbs)
        sessions[source_id] = {"type":"proverb","index":None,"data":proverb}
        emoji_text = split_text(proverb["emoji"])
        bubble = {
            "type": "bubble",
            "body": {"type":"box","layout":"vertical","contents":[
                {"type":"text","text":emoji_text,"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer": {"type":"box","layout":"vertical","contents":[
                {"type":"button","action":{"type":"postback","label":"اظهر المعنى","data":"show_proverb"}} 
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage("أمثال", bubble))
        return

    # --- ألغاز ---
    if text in ["لغز","تجربة ألغاز","help_riddle"]:
        index = 0
        riddle = riddles[index]
        sessions[source_id] = {"type":"riddle","index":index}
        riddle_text = split_text(riddle["question"])
        bubble = {
            "type":"bubble",
            "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text","text":riddle_text,"weight":"bold","size":"lg","wrap":True}
            ]},
            "footer":{"type":"box","layout":"horizontal","contents":[
                {"type":"button","action":{"type":"postback","label":"💡 تلميح","data":"hint"}},
                {"type":"button","action":{"type":"postback","label":"الإجابة","data":"answer"}},
                {"type":"button","action":{"type":"postback","label":"⏮️ السابق","data":"prev"}},
                {"type":"button","action":{"type":"postback","label":"⏭️ التالي","data":"next"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage("ألغاز", bubble))
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
        if session.get("type")=="proverb" and data=="show_proverb":
            proverb = session["data"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 المعنى: {proverb['text']}"))
        elif session.get("type")=="riddle":
            index = session["index"]
            riddle = riddles[index]
            if data=="hint":
                hint = riddle.get("hint","💡 لا يوجد تلميح")
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{hint}"))
            elif data=="answer":
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 الإجابة: {riddle['answer']}"))
            elif data=="prev":
                index = (index-1) % len(riddles)
                session["index"] = index
                riddle_text = split_text(riddles[index]["question"])
                send_riddle_flex(event, riddle_text)
            elif data=="next":
                index = (index+1) % len(riddles)
                session["index"] = index
                riddle_text = split_text(riddles[index]["question"])
                send_riddle_flex(event, riddle_text)

def send_riddle_flex(event, riddle_text):
    bubble = {
        "type":"bubble",
        "body":{"type":"box","layout":"vertical","contents":[
            {"type":"text","text":riddle_text,"weight":"bold","size":"lg","wrap":True}
        ]},
        "footer":{"type":"box","layout":"horizontal","contents":[
            {"type":"button","action":{"type":"postback","label":"💡 تلميح","data":"hint"}},
            {"type":"button","action":{"type":"postback","label":"الإجابة","data":"answer"}},
            {"type":"button","action":{"type":"postback","label":"⏮️ السابق","data":"prev"}},
            {"type":"button","action":{"type":"postback","label":"⏭️ التالي","data":"next"}}
        ]}
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage("ألغاز", bubble))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
