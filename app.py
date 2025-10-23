import random, json, threading, os, typing
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    FlexSendMessage, BubbleContainer, BoxComponent, TextComponent
)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- تحميل الملفات ---
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
games_data = load_json_file("games.txt")          # أسئلة لعبة الأسئلة
game_weights = load_json_file("game_weights.json")  
personality_descriptions = load_json_file("characters.txt")  

# --- جلسات المستخدمين ---
sessions = {}
general_indices = {"سؤال":0, "تحدي":0, "اعتراف":0, "شخصي":0}
time_limit = 15  # ثواني لكل مثل مصور

# --- أمثال مصورة ---
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

# --- ألغاز ---
riddles = [
    {"question": "ما هو الشيء الذي كلما أخذت منه يكبر؟", "answer": "الحفرة"},
    {"question": "له أوراق وليس شجرة، له جلد وليس حيوان، ما هو؟", "answer": "الكتاب"},
    {"question": "ما هو الشيء الذي يتكلم جميع لغات العالم؟", "answer": "الصدى"},
    {"question": "ما هو الشيء الذي يمشي بلا قدمين؟", "answer": "الزمن"}
]

# --- رسائل مرحبة ---
welcome_messages = [
    "🎮 أهلاً بك! استعد للمرح والإثارة!",
    "🕹️ جاهز لتحديات جديدة؟ لنبدأ!",
    "✨ لنرى مهاراتك في الإجابة! حظاً سعيداً!"
]

# --- وظائف Flex Messages ---
def create_flex_game_question(question_data, step, total):
    bubble = BubbleContainer(
        size="giga",
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(text=f"السؤال {step} من {total}", weight="bold", size="lg", color="#006064", align="center"),
                TextComponent(text=question_data['question'], wrap=True, size="xl", align="center", color="#004D40"),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(text=f"1️⃣ {question_data['answers']['1']['text']}", wrap=True, size="md", color="#00796B"),
                        TextComponent(text=f"2️⃣ {question_data['answers']['2']['text']}", wrap=True, size="md", color="#00796B"),
                        TextComponent(text=f"3️⃣ {question_data['answers']['3']['text']}", wrap=True, size="md", color="#00796B"),
                        TextComponent(text=f"4️⃣ {question_data['answers']['4']['text']}", wrap=True, size="md", color="#00796B"),
                    ]
                )
            ]
        ),
        styles={"footer": {"separator": True}}
    )
    return FlexSendMessage(alt_text="سؤال", contents=bubble)

def create_flex_proverb(emoji, remaining_time):
    bubble = BubbleContainer(
        size="mega",
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(text="احزر المثل المصور", weight="bold", size="lg", align="center", color="#F57F17"),
                TextComponent(text=emoji, size="6xl", align="center"),
                TextComponent(text=f"⏳ تبقى {remaining_time} ثانية", size="md", align="center", color="#D50000")
            ]
        )
    )
    return FlexSendMessage(alt_text="مثل مصور", contents=bubble)

def create_flex_riddle(riddle_text, step, total):
    bubble = BubbleContainer(
        size="mega",
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(text=f"لغز {step} من {total}", weight="bold", size="md", color="#6A1B9A", align="center"),
                TextComponent(text=riddle_text, wrap=True, size="xl", align="center", color="#4A148C"),
                TextComponent(text="💡 حاول الإجابة!", size="md", align="center", color="#1B5E20")
            ]
        )
    )
    return FlexSendMessage(alt_text="لغز", contents=bubble)

# --- عد تنازلي متحرك للأمثال ---
def countdown_live_flex(user_id, remaining_seconds):
    if user_id not in sessions or sessions[user_id].get("type") != "امثال":
        return

    session = sessions[user_id]
    step = session["step"]
    current_emoji, correct_answer = session["questions"][step]

    if remaining_seconds <= 0:
        session["step"] += 1
        if session["step"] >= len(session["questions"]):
            msg = f"🎉 انتهت اللعبة! حصلت على {session['score']} من {len(session['questions'])} نقطة."
            line_bot_api.push_message(user_id, TextSendMessage(text=msg))
            del sessions[user_id]
            return
        else:
            next_emoji, _ = session["questions"][session["step"]]
            line_bot_api.push_message(user_id, create_flex_proverb(next_emoji, time_limit))
            threading.Timer(1, lambda: countdown_live_flex(user_id, time_limit)).start()
            return

    line_bot_api.push_message(user_id, create_flex_proverb(current_emoji, remaining_seconds))
    threading.Timer(1, lambda: countdown_live_flex(user_id, remaining_seconds-1)).start()

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

# --- حساب الشخصية ---
def calculate_personality(user_answers: typing.List[int]) -> str:
    scores = game_weights.copy()
    for i, ans in enumerate(user_answers):
        weight = games_data["game"][i]["answers"].get(str(ans), {}).get("weight", {})
        for key, val in weight.items():
            if key in scores:
                scores[key] += val
    return max(scores, key=scores.get)

# --- إرسال اللغز التالي ---
def send_next_riddle(user_id):
    session = sessions[user_id]
    step = session["step"]
    if step >= len(session["questions"]):
        line_bot_api.push_message(user_id, TextSendMessage(
            text=f"🎯 انتهت جميع الألغاز! حصلت على {session['score']} من {len(session['questions'])} لغز بشكل صحيح."
        ))
        del sessions[user_id]
        return
    riddle = session["questions"][step]
    msg = create_flex_riddle(riddle["question"], step+1, len(session["questions"]))
    line_bot_api.push_message(user_id, msg)

# --- معالجة الرسائل ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    display_name = line_bot_api.get_profile(user_id).display_name
    arabic_to_english = {"١":"1","٢":"2","٣":"3","٤":"4"}
    text_conv = arabic_to_english.get(text,text)

    # --- المساعدة ---
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

    # --- أسئلة عامة ---
    if text in ["سؤال","تحدي","اعتراف","شخصي"]:
        qlist = {"سؤال": questions, "تحدي": challenges, "اعتراف": confessions, "شخصي": personal_questions}.get(text, [])
        if not qlist:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{display_name}: لا توجد أسئلة حالياً."))
            return
        index = general_indices[text] % len(qlist)
        general_indices[text] += 1
        q_text = qlist[index]
        sessions[user_id] = {"step":0,"answers":[],"questions":[q_text]}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{display_name}\n\n{q_text}"))
        return

    # --- لعبة الأسئلة Flex ---
    if text == "لعبه":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(welcome_messages)))
        shuffled_questions = games_data["game"][:]
        random.shuffle(shuffled_questions)
        sessions[user_id] = {"step":0,"answers":[],"questions":shuffled_questions,"type":"لعبة_أسئلة","score":0}
        first_question = shuffled_questions[0]
        msg = create_flex_game_question(first_question, 1, len(shuffled_questions))
        line_bot_api.reply_message(event.reply_token, msg)
        return

    # --- الأمثال المصورة ---
    if text == "امثله":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(welcome_messages)))
        shuffled_emojis = list(emoji_proverbs.items())
        random.shuffle(shuffled_emojis)
        sessions[user_id] = {"step":0,"questions":shuffled_emojis,"type":"امثال","score":0}
        first_emoji, _ = shuffled_emojis[0]
        line_bot_api.reply_message(event.reply_token, create_flex_proverb(first_emoji, time_limit))
        countdown_live_flex(user_id, time_limit)
        return

    # --- ألغاز ---
    if text == "لغز":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(welcome_messages)))
        shuffled_riddles = riddles[:]
        random.shuffle(shuffled_riddles)
        sessions[user_id] = {"step":0,"questions":shuffled_riddles,"type":"لغز","score":0}
        send_next_riddle(user_id)
        return

    # --- حل الأمثال ---
    if user_id in sessions and sessions[user_id].get("type")=="امثال":
        session = sessions[user_id]
        step = session["step"]
        current_emoji, correct_answer = session["questions"][step]
        if text == correct_answer:
            session["score"] += 1
            reply_text = "✅ صحيح! أحسنت"
        else:
            reply_text = f"❌ خطأ! الإجابة الصحيحة: {correct_answer}"
        session["step"] += 1
        if session["step"] >= len(session["questions"]):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"{display_name}\n\n{reply_text}\n\n🎉 انتهت اللعبة! حصلت على {session['score']} من {len(session['questions'])} نقطة."
            ))
            del sessions[user_id]
        else:
            next_emoji, _ = session["questions"][session["step"]]
            line_bot_api.push_message(user_id, create_flex_proverb(next_emoji, time_limit))
            countdown_live_flex(user_id, time_limit)
        return

    # --- حل الألغاز ---
    if user_id in sessions and sessions[user_id].get("type")=="لغز":
        session = sessions[user_id]
        step = session["step"]
        current_riddle = session["questions"][step]
        correct_answer = current_riddle["answer"]
        if text.strip() == correct_answer:
            session["score"] += 1
            reply_text = "✅ صحيح! أحسنت"
        else:
            reply_text = f"❌ خطأ! الإجابة الصحيحة هي: {correct_answer}"
        session["step"] += 1
        if session["step"] >= len(session["questions"]):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"{display_name}\n\n{reply_text}\n\n🎯 انتهت جميع الألغاز! حصلت على {session['score']} من {len(session['questions'])} لغز بشكل صحيح."
            ))
            del sessions[user_id]
        else:
            next_riddle = session["questions"][session["step"]]["question"]
            line_bot_api.push_message(user_id, create_flex_riddle(next_riddle, session["step"]+1, len(session["questions"])))
        return

    # --- حل لعبة الأسئلة ---
    if user_id in sessions and sessions[user_id].get("type")=="لعبة_أسئلة":
        session = sessions[user_id]
        step = session["step"]
        current_question = session["questions"][step]
        
        if text_conv not in ["1","2","3","4"]:
            return
        
        session["answers"].append(int(text_conv))
        
        # تحليل مؤقت بعد كل 5 أسئلة
        if (step+1) % 5 == 0:
            trait = calculate_personality(session["answers"])
            desc = personality_descriptions.get(trait,"وصف الشخصية غير متوفر.")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"{display_name}\n\nتحليل الشخصية بعد {step+1} أسئلة ({trait}):\n{desc}"
            ))
        
        session["step"] += 1
        
        if session["step"] >= len(session["questions"]):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"🎉 انتهت اللعبة! تم إنهاء جميع الأسئلة."
            ))
            del sessions[user_id]
        else:
            next_question = session["questions"][session["step"]]
            msg = create_flex_game_question(next_question, session["step"]+1, len(session["questions"]))
            line_bot_api.reply_message(event.reply_token, msg)
        return

# --- تشغيل السيرفر ---
if __name__ == "__main__":
    port = int(os.getenv("PORT",5000))
    app.run(host="0.0.0.0", port=port)
