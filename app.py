import glob
import os

import streamlit as st
import assemblyai as aai
import moviepy.video.io.VideoFileClip as vfc
import moviepy.video.VideoClip as vc
import moviepy.video.compositing.CompositeVideoClip as cvc
import moviepy.video.tools.subtitles as sub

# إعدادات الصفحة والـ Theme المظلم البريميوم
st.set_page_config(page_title="AI Auto Subtitles Bot", page_icon="🎬", layout="centered")

# تصميم الـ Dark Mode الفخم عبر CSS
st.markdown("""
    <style>
    .main { background-color: #0d0f12; color: #f0f2f5; }
    h1 { color: #f4d03f; font-family: 'Cairo', sans-serif; text-align: center; font-weight: 800; }
    .stButton>button { background-color: #f4d03f; color: #0d0f12; font-weight: bold; border-radius: 12px; width: 100%; padding: 10px; border: none; }
    .stButton>button:hover { background-color: #f1c40f; color: #0d0f12; box-shadow: 0px 4px 15px rgba(244, 208, 63, 0.4); }
    .stFileUploader { background-color: #1a1e24; border-radius: 10px; padding: 15px; border: 1px dashed #34495e; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# مفتاح الـ API: لا تكتبه مباشرة في الكود أبداً.
# ضِفه في Streamlit Cloud تحت: Settings -> Secrets، بهذا الشكل:
#   ASSEMBLYAI_API_KEY = "your_real_key_here"
# ثم شغّل التطبيق محلياً بملف .streamlit/secrets.toml بنفس المتغير.
# -----------------------------------------------------------------------
try:
    aai.settings.api_key = st.secrets["ASSEMBLYAI_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("⚠️ لم يتم العثور على مفتاح AssemblyAI. أضفه في Secrets باسم ASSEMBLYAI_API_KEY.")
    st.stop()


def find_font_path():
    """
    يبحث عن خط DejaVuSans صالح للاستخدام، بترتيب أولوية:
    1) الخط المرفق مسبقاً مع مكتبة matplotlib (لا يحتاج apt-get إطلاقاً، وموجود دائماً
       لأن matplotlib غالباً مثبتة كاعتماد ضمني ضمن بيئة Python العلمية).
    2) خط النظام (لو apt.txt نجح في تثبيته).
    3) أي ملف .ttf آخر متاح على السيرفر كحل أخير.
    """
    # 1) خط matplotlib المدمج
    try:
        import matplotlib
        mpl_font = os.path.join(
            os.path.dirname(matplotlib.__file__),
            "mpl-data", "fonts", "ttf", "DejaVuSans.ttf"
        )
        if os.path.exists(mpl_font):
            return mpl_font
    except ImportError:
        pass

    # 2) خط النظام عبر apt.txt
    candidates = glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans*.ttf")
    if candidates:
        return candidates[0]

    # 3) أي خط ttf آخر كحل أخير
    fallback = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    if fallback:
        return fallback[0]

    return None


FONT_PATH = find_font_path()

if FONT_PATH is None:
    st.error(
        "⚠️ لم يتم العثور على أي خط TTF على السيرفر. "
        "أضف ملف apt.txt في جذر المشروع يحتوي على السطر: fonts-dejavu-core"
    )
    st.stop()


def create_srt_batches(words, batch_size=3):
    srt_content = ""
    counter = 1
    for i in range(0, len(words), batch_size):
        batch = words[i:i + batch_size]
        start_time = batch[0].start
        end_time = batch[-1].end

        def format_time(ms):
            hrs = ms // 3600000
            mins = (ms % 3600000) // 60000
            secs = (ms % 60000) // 1000
            msecs = ms % 1000
            return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

        start_srt = format_time(start_time)
        end_srt = format_time(end_time)
        batch_text = " ".join([word.text for word in batch])
        srt_content += f"{counter}\n{start_srt} --> {end_srt}\n{batch_text}\n\n"
        counter += 1
    return srt_content


def create_styled_text(txt):
    # ملاحظة مهمة: في MoviePy 2.x يجب أن يكون "font" مساراً حقيقياً لملف .ttf
    # وليس اسم عائلة الخط فقط (مثل 'DejaVuSans').
    return vc.TextClip(
        text=txt,
        font_size=40,
        color='white',
        bg_color='black',
        font=FONT_PATH
    )


st.title("🎬 مصنع الترجمة الذكي")
st.write(
    "<p style='text-align: center; color: #bdc3c7;'>"
    "أهلاً بك يا بطل! ارفع فيديو وسيتولى الذكاء الاصطناعي هندسة النصوص وتلوينها فوراً."
    "</p>",
    unsafe_allow_html=True
)

# صندوق رفع الفيديو
uploaded_file = st.file_uploader("📥 اسحب وأفلت مقطع الفيديو هنا (MP4)...", type=["mp4"])

if uploaded_file is not None:
    with open("temp_input.mp4", "wb") as f:
        f.write(uploaded_file.read())

    st.video("temp_input.mp4")

    if st.button("🚀 ابدأ السحر واطبخ الفيديو الحين!"):

        # عبارات انتظار بشرية وحماسية
        with st.spinner("🧠 قاعدين نسمع المقطع الحين ونفكك الكلمات بدقة.. ثواني وبنبهرك!"):
            config = aai.TranscriptionConfig(language_detection=True)
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe("temp_input.mp4", config=config)

            if transcript.status == aai.TranscriptStatus.error:
                st.error(f"❌ أوبس! حصلت مشكلة بالذكاء الاصطناعي: {transcript.error}")
                st.stop()

            lang = transcript.json_response.get('language_code')
            st.success(f"🌍 لقطنا لغة الفيديو! طلعت: ({lang})")

            srt_data = create_srt_batches(transcript.words, batch_size=3)
            with open("temp_subtitles.srt", "w", encoding="utf-8") as s_file:
                _ = s_file.write(srt_data)

        with st.spinner("🎨 الحين جاري دمج النصوص وتلوينها بالستايل الجديد في أسفل الشاشة.. اجهز للنتيجة!"):
            video = vfc.VideoFileClip("temp_input.mp4")
            subtitles = sub.SubtitlesClip("temp_subtitles.srt", make_textclip=create_styled_text)

            # ضبط الموقع ليكون أسفل الفيديو (80% من الارتفاع) ومتمركز في العرض
            subtitles = subtitles.with_position(('center', 0.8), relative=True)

            final_video = cvc.CompositeVideoClip([video, subtitles])
            final_video.write_videofile(
                "temp_output.mp4",
                codec='libx264',
                audio_codec='aac',
                preset='ultrafast',
                logger=None
            )

        st.success("🎉 يسلّم راسك! المقطع جاهز ومطبوخ بأعلى جودة!")
        st.write("### 🔥 الق نظرة على مقطعك الرهيب:")
        st.video("temp_output.mp4")

        with open("temp_output.mp4", "rb") as file:
            st.download_button(
                label="📥 تحميل الفيديو المترجم فوراً بجهازك",
                data=file,
                file_name="styled_subtitled_video.mp4",
                mime="video/mp4"
            )
