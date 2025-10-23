
import random, json, os, typing
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, PostbackEvent, PostbackAction
)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def load_file_lines(filename: str) -> typing.List[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

def load_json_file(filename: str) -> dict:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

questions = load_file_lines("questions.txt")
challenges = load_file_lines("challenges.txt")
confessions = load_file_lines("confessions.txt")
personal_questions = load_file_lines("personality.txt")
games_data = load_json_file("games.txt")
game_weights = load_json_file("game_weights.json")
personality_descriptions = load_json_file("characters.txt")

sessions = {}
general_indices = {"سؤال":0, "تحدي":0, "اعتراف":0, "شخصي":0}

emoji_proverbs = {
    "👊 😭🏃👄": "ضربني وبكى، سبقني واشتكى",
    "👋💦👋🔥": "من يده في الماء ليس كالذي يده في النار",
    "🐒👀👩": "القرد في عين أمه غزال",
    "💤👑": "النوم سلطان",
    "✈🐦👆✈👇": "الوقت كالسيف، إن لم تقطعه قطعك",
    "📖💡👽🌊": "العلم نور والجهل ظلام",
    "👄🐎✋👍😝👎": "لسانك حصانك، إن صنته صانك وإن خنته خانك",
    "👋1⃣👏": "يد واحدة لا تصفق",
    "🐧✊🐧🐧🐧🐧🌴": "عصفور في اليد خير من عشرة على الشجرة",
    "🤝👬": "الصاحب ساحب"
}

riddles = [
    {"question": "ما هو الشيء الذي كلما أخذت منه يكبر؟", "answer": "الحفرة"},
    {"question": "له أوراق وليس شجرة، له جلد وليس حيوان، ما هو؟", "answer": "الكتاب"},
    {"question": "ما هو الشيء الذي يتكلم جميع لغات العالم؟", "answer": "الصدى"},
    {"question": "ما هو الشيء الذي يمشي بلا قدمين؟", "answer": "الزمن"}
]

def calculate_personality(user_answers: typing.List[int]) -> str:
    scores = game_weights.copy()
    for i, ans in enumerate(user_answers):
        weight = games_data["game"][i]["answers"].get(str(ans), {}).get("weight", {})
        for key, val in weight.items():
            if key in scores:
                scores[key] += val
    return max(scores, key=scores.get)

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

    arabic_to_english = {"١":"1","٢":"2","٣":"3","٤":"4"}
    text_conv = arabic_to_english.get(text,text)

    if text == "مساعدة":
        reply = (
            "أوامر البوت:\n"
            "سؤال → سؤال عام\n"
            "تحدي → تحدي\n"
            "اعتراف → اعتراف\n"
            "شخصي → سؤال شخصي\n"
            "لعبه → لعبة الأسئلة\n"
            "امثله → الأمثال المصورة\n"
            "لغز → ألغاز\n"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if text == "امثله":
        key, val = random.choice(list(emoji_proverbs.items()))
        reply_text = f"{key}\n\n(اضغط 'مساعدة' لمعرفة المعنى)\n{val}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    if text == "لغز":
        riddle = random.choice(riddles)
        sessions[source_id] = {"type":"riddle","answer":riddle["answer"]}
        bubble = {
            "type": "bubble",
            "body": {"type":"box","layout":"vertical","contents":[
                {"type":"text","text":riddle["question"],"wrap":True,"weight":"bold"}
            ]},
            "footer": {"type":"box","layout":"vertical","contents":[
                {"type":"button","action":{"type":"postback","label":"اظهر الإجابة","data":"show_riddle_answer"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="لغز", contents=bubble))
        return

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
    if data == "show_riddle_answer" and source_id in sessions and sessions[source_id].get("type")=="riddle":
        answer = sessions[source_id]["answer"]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 الإجابة: {answer}"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
