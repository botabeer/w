import random, os, typing
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

# --- دالة تقسيم النص الطويل ---
def split_text(text, max_chars=50):
    """تقسيم النص إلى أسطر إذا تجاوز الحد المحدد"""
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

# --- دالة إنشاء Flex Message ---
def make_flex_message(title, content, button_label, postback_data):
    bubble = {
        "type": "bubble",
        "body": {
            "type":"box",
            "layout":"vertical",
            "contents":[
                {"type":"text", "text":split_text(title), "wrap":True, "weight":"bold", "size":"md"},
                {"type":"text", "text":split_text(content), "wrap":True, "size":"sm", "margin":"md"}
            ]
        },
        "footer": {
            "type":"box",
            "layout":"vertical",
            "contents":[
                {"type":"button", "action":{"type":"postback","label":button_label,"data":postback_data}}
            ]
        }
    }
    return FlexSendMessage(alt_text=title, contents=bubble)

# --- أمثال مصورة (20 مثال) ---
emoji_proverbs = [
    {"emoji":"👊 😭🏃👄", "text":"ضربني وبكى، سبقني واشتكى"},
    {"emoji":"👋💦👋🔥", "text":"من يده في الماء ليس كالذي يده في النار"},
    {"emoji":"🐒👀👩", "text":"القرد في عين أمه غزال"},
    {"emoji":"💤👑", "text":"النوم سلطان"},
    {"emoji":"✈🐦👆✈👇", "text":"الوقت كالسيف، إن لم تقطعه قطعك"},
    {"emoji":"📖💡👽🌊", "text":"العلم نور والجهل ظلام"},
    {"emoji":"👄🐎✋👍😝👎", "text":"لسانك حصانك، إن صنته صانك وإن خنته خانك"},
    {"emoji":"👋1⃣👏", "text":"يد واحدة لا تصفق"},
    {"emoji":"🐧✊🐧🐧🐧🐧🌴", "text":"عصفور في اليد خير من عشرة على الشجرة"},
    {"emoji":"🤝👬", "text":"الصاحب ساحب"},
    {"emoji":"🌟💪", "text":"العزم يصنع المعجزات"},
    {"emoji":"🦁👑", "text":"القوة في الشجاعة"},
    {"emoji":"🍎📚", "text":"التعليم مفتاح النجاح"},
    {"emoji":"🌊🛶", "text":"من جد وجد"},
    {"emoji":"🔥💨", "text":"الصبر مفتاح الفرج"},
    {"emoji":"🎯🏆", "text":"التركيز يحقق الهدف"},
    {"emoji":"🕊️✌️", "text":"السلام من شيم الكرام"},
    {"emoji":"🌳🌱", "text":"من زرع حصد"},
    {"emoji":"💎✨", "text":"القيمة في الجوهر لا في المظهر"},
    {"emoji":"🗝️🚪", "text":"الفرص تأتي لمن يبحث عنها"}
]

# --- ألغاز (15 لغز) ---
riddles = [
    {"question": "ما هو الشيء الذي كلما أخذت منه يكبر؟", "answer": "الحفرة"},
    {"question": "له أوراق وليس شجرة، له جلد وليس حيوان، ما هو؟", "answer": "الكتاب"},
    {"question": "ما هو الشيء الذي يتكلم جميع لغات العالم؟", "answer": "الصدى"},
    {"question": "ما هو الشيء الذي يمشي بلا قدمين؟", "answer": "الزمن"},
    {"question": "شيء يكون في السماء ويمطر على الأرض، ما هو؟", "answer": "السحاب"},
    {"question": "أبيض في الثلج وأسود في الليل، ما هو؟", "answer": "الظل"},
    {"question": "شيء له أسنان ولا يعض، ما هو؟", "answer": "المشط"},
    {"question": "ما هو الشيء الذي يملأ الغرفة ولكنه لا يشغل حيزا؟", "answer": "الضوء"},
    {"question": "ما هو الشيء الذي يكسر بمجرد ذكر اسمه؟", "answer": "الصمت"},
    {"question": "له مدينة وليس له ناس، ما هو؟", "answer": "الخريطة"},
    {"question": "شيء يُكتب ولا يُقرأ، ما هو؟", "answer": "القلم الفارغ"},
    {"question": "ما هو الشيء الذي يركض ولا يمشي؟", "answer": "الماء"},
    {"question": "له قلب ولا ينبض، ما هو؟", "answer": "الخس"},
    {"question": "ما هو الشيء الذي كلما زاد نقص؟", "answer": "العمر"},
    {"question": "شيء يسمع بلا أذن ويتكلم بلا لسان، ما هو؟", "answer": "الصدى"}
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
        reply = (
            "أوامر البوت:\n"
            "امثله → أمثال مصورة مع زر لإظهار المعنى\n"
            "لغز → ألغاز مع زر لإظهار الإجابة"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # --- أمثال مصورة ---
    if text == "امثله":
        proverb = random.choice(emoji_proverbs)
        sessions[source_id] = {"type":"proverb", "text":proverb["text"]}
        flex_msg = make_flex_message(proverb["emoji"], "", "اظهر المعنى", "show_proverb")
        line_bot_api.reply_message(event.reply_token, flex_msg)
        return

    # --- ألغاز ---
    if text == "لغز":
        riddle = random.choice(riddles)
        sessions[source_id] = {"type":"riddle", "answer":riddle["answer"]}
        flex_msg = make_flex_message(riddle["question"], "", "اظهر الإجابة", "show_riddle")
        line_bot_api.reply_message(event.reply_token, flex_msg)
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
        if data == "show_riddle" and session.get("type")=="riddle":
            answer = session["answer"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 الإجابة: {answer}"))
        elif data == "show_proverb" and session.get("type")=="proverb":
            text = session["text"]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💡 المعنى: {text}"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
