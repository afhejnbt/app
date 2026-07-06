import base64
import os
import re

import streamlit as st
import assemblyai as aai
import moviepy.video.io.VideoFileClip as vfc
import moviepy.video.VideoClip as vc
from moviepy.video.VideoClip import ColorClip
import moviepy.video.compositing.CompositeVideoClip as cvc
import moviepy.video.tools.subtitles as sub
from PIL import features as pil_features
import arabic_reshaper
from bidi.algorithm import get_display

# =============================================================================
# الهوية البصرية
# =============================================================================
BRAND_ORANGE = "#F26921"
BRAND_ORANGE_LIGHT = "#FF8A4C"
BRAND_BLACK = "#0A0A0C"
BRAND_SURFACE = "#141519"
BRAND_SURFACE_2 = "#1C1E24"
BRAND_BORDER = "#2A2C34"
BRAND_WHITE = "#F5F5F7"
BRAND_MUTED = "#9C9DA6"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(APP_DIR, "fonts")
ASSETS_DIR = os.path.join(APP_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
LOGO_SMALL_PATH = os.path.join(ASSETS_DIR, "logo_small.png")

st.set_page_config(
    page_title="edit73 — استوديو الترجمة الذكي",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🎬",
    layout="centered",
)


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


LOGO_B64 = _b64(LOGO_SMALL_PATH) if os.path.exists(LOGO_SMALL_PATH) else None

# =============================================================================
# مفتاح AssemblyAI عبر Secrets فقط
# =============================================================================
try:
    aai.settings.api_key = st.secrets["ASSEMBLYAI_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("لم يتم العثور على مفتاح AssemblyAI. أضفه في Secrets باسم ASSEMBLYAI_API_KEY.")
    st.stop()

# =============================================================================
# التصميم: خطوط الواجهة + الأنماط
# =============================================================================
st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/3.44.0/tabler-icons.min.css">

<style>
html, body, [class*="css"] {{ font-family: 'Tajawal', 'Inter', sans-serif; }}

.stApp {{
    background: {BRAND_BLACK};
    color: {BRAND_WHITE};
}}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 720px; }}

/* ---------- الهيدر ---------- */
.top-nav {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding-bottom: 8px;
}}
.top-nav img {{ width: 38px; height: 38px; }}
.top-nav .wordmark {{
    font-size: 1.3rem;
    font-weight: 800;
    color: {BRAND_WHITE};
    letter-spacing: -0.3px;
}}
.top-nav .wordmark span {{ color: {BRAND_ORANGE}; }}

.hero {{
    text-align: center;
    padding: 20px 0 34px 0;
    border-bottom: 1px solid {BRAND_BORDER};
    margin-bottom: 32px;
}}
.hero h1 {{
    font-size: 1.85rem;
    font-weight: 800;
    color: {BRAND_WHITE};
    margin: 0 0 10px 0;
    line-height: 1.4;
}}
.hero p {{
    color: {BRAND_MUTED};
    font-size: 0.96rem;
    max-width: 460px;
    margin: 0 auto;
    line-height: 1.7;
}}

/* ---------- شريط الخطوات ---------- */
.steps-row {{
    display: flex;
    justify-content: center;
    gap: 28px;
    margin-bottom: 36px;
}}
.step-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    color: {BRAND_MUTED};
    font-size: 0.85rem;
    font-weight: 500;
}}
.step-item i {{
    font-size: 16px;
    color: {BRAND_ORANGE};
}}

/* ---------- عناوين الأقسام ---------- */
.section-heading {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 0 0 4px 0;
}}
.section-heading i {{
    font-size: 19px;
    color: {BRAND_ORANGE};
}}
.section-heading h3 {{
    font-size: 1.02rem;
    font-weight: 700;
    color: {BRAND_WHITE};
    margin: 0;
}}
.section-desc {{
    color: {BRAND_MUTED};
    font-size: 0.84rem;
    margin: 2px 0 16px 0;
}}
.section-block {{ margin-bottom: 30px; }}

/* ---------- رفع الفيديو ---------- */
section[data-testid="stFileUploaderDropzone"] {{
    background-color: {BRAND_SURFACE} !important;
    border: 1px dashed {BRAND_BORDER} !important;
    border-radius: 12px !important;
}}
section[data-testid="stFileUploaderDropzone"]:hover {{
    border-color: {BRAND_ORANGE}88 !important;
}}

/* ---------- التبويبات ---------- */
.stTabs [data-baseweb="tab-list"] {{
    gap: 2px;
    background: {BRAND_SURFACE};
    padding: 4px;
    border-radius: 10px;
    border: 1px solid {BRAND_BORDER};
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 7px;
    color: {BRAND_MUTED};
    font-weight: 600;
    font-size: 0.86rem;
    padding: 8px 16px;
}}
.stTabs [aria-selected="true"] {{
    background: {BRAND_SURFACE_2} !important;
    color: {BRAND_ORANGE} !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    background: {BRAND_SURFACE};
    border: 1px solid {BRAND_BORDER};
    border-top: none;
    border-radius: 0 0 10px 10px;
    padding: 22px 18px 8px 18px;
}}

/* ---------- عناصر الإدخال ---------- */
div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
    background-color: {BRAND_SURFACE_2} !important;
    color: {BRAND_WHITE} !important;
    border-radius: 8px !important;
    border-color: {BRAND_BORDER} !important;
}}
.stSlider [data-baseweb="slider"] > div > div {{ background: {BRAND_ORANGE} !important; }}
div[role="radiogroup"] label p, .stRadio label p {{ color: {BRAND_WHITE} !important; }}
.stCheckbox p, .stToggle p {{ color: {BRAND_WHITE} !important; }}
label p {{ color: {BRAND_MUTED} !important; font-size: 0.85rem !important; font-weight: 500 !important; }}

/* ---------- الأزرار ---------- */
.stButton>button {{
    background: {BRAND_ORANGE};
    color: #14100c;
    font-weight: 700;
    font-size: 1rem;
    border-radius: 10px;
    width: 100%;
    padding: 13px;
    border: none;
    transition: background 0.15s ease;
}}
.stButton>button:hover {{ background: {BRAND_ORANGE_LIGHT}; }}
.stButton>button:active {{ transform: scale(0.99); }}

.stDownloadButton>button {{
    background: transparent;
    color: {BRAND_WHITE};
    border: 1px solid {BRAND_BORDER};
    font-weight: 600;
    border-radius: 10px;
    width: 100%;
    padding: 12px;
}}
.stDownloadButton>button:hover {{ border-color: {BRAND_ORANGE}; color: {BRAND_ORANGE}; }}

/* ---------- تنبيهات ---------- */
div[data-testid="stAlert"] {{ border-radius: 10px; }}

/* ---------- الفوتر ---------- */
.app-footer {{
    text-align: center;
    color: {BRAND_MUTED};
    font-size: 0.8rem;
    padding-top: 28px;
    margin-top: 12px;
    border-top: 1px solid {BRAND_BORDER};
}}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# الهيدر وقسم المقدمة
# =============================================================================
if LOGO_B64:
    st.markdown(f"""
        <div class="top-nav">
            <img src="data:image/png;base64,{LOGO_B64}" alt="edit73" />
            <div class="wordmark">edit<span>73</span></div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("""
    <div class="hero">
        <h1>ترجمة فيديو تلقائية بالذكاء الاصطناعي</h1>
        <p>يحلّل edit73 الصوت، يولّد ترجمة نصية مضبوطة التوقيت، ويهيئ الفيديو
        للنشر مباشرة على منصات التواصل الاجتماعي بالعربية والإنجليزية.</p>
    </div>

    <div class="steps-row">
        <div class="step-item"><i class="ti ti-upload"></i>رفع الفيديو</div>
        <div class="step-item"><i class="ti ti-adjustments"></i>ضبط الإعدادات</div>
        <div class="step-item"><i class="ti ti-download"></i>تنزيل النتيجة</div>
    </div>
""", unsafe_allow_html=True)


def section_heading(icon, title, desc):
    st.markdown(f"""
        <div class="section-heading"><i class="ti {icon}"></i><h3>{title}</h3></div>
        <div class="section-desc">{desc}</div>
    """, unsafe_allow_html=True)


# =============================================================================
# معالجة النص العربي: الاعتماد على raqm (Pillow) عند توفره
# =============================================================================
# Pillow يتضمن منذ إصدارات حديثة محرك raqm الذي يقوم تلقائياً بربط الحروف العربية
# (Shaping) وترتيب اتجاه الكتابة (Bidi) عبر جداول OpenType (GSUB) الخاصة بكل خط.
# هذا هو المسار الصحيح لأنه يعمل مع أي خط عربي مصمم بشكل قياسي (مثل Tajawal)
# بدل الاعتماد على تحويل يدوي لأشكال العرض (Presentation Forms) التي لا تغطيها
# أغلب الخطوط الحديثة بشكل كامل، وتتسبب بحروف مفقودة أو تنسيق غير صحيح.
RAQM_AVAILABLE = pil_features.check("raqm")

_ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F]')


def is_mostly_arabic(txt):
    letters = re.findall(r'[^\s\d\W]', txt, re.UNICODE)
    if not letters:
        return False
    arabic_letters = _ARABIC_RE.findall(txt)
    return len(arabic_letters) >= max(1, len(letters) // 2)


def prepare_text_for_rendering(txt):
    if RAQM_AVAILABLE:
        return txt
    if _ARABIC_RE.search(txt):
        return get_display(arabic_reshaper.reshape(txt))
    return txt


def pick_font_for_text(txt, font_style_key):
    fonts = FONT_LIBRARY[font_style_key]
    return fonts["ar"] if is_mostly_arabic(txt) else fonts["en"]


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


FONT_LIBRARY = {
    "عريض (Bold)": {
        "ar": os.path.join(FONTS_DIR, "Tajawal-Bold.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Bold.ttf"),
    },
    "عريض جداً (Extra Bold)": {
        "ar": os.path.join(FONTS_DIR, "Tajawal-ExtraBold.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-ExtraBold.ttf"),
    },
    "أسود ثقيل (Black)": {
        "ar": os.path.join(FONTS_DIR, "Tajawal-Black.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Black.ttf"),
    },
    "كلاسيكي (Naskh)": {
        "ar": os.path.join(FONTS_DIR, "NotoNaskhArabic-Regular.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Bold.ttf"),
    },
}
FALLBACK_FONT = os.path.join(FONTS_DIR, "NotoNaskhArabic-Regular.ttf")


def create_srt_batches(words, batch_size=3):
    """
    يبني ملف SRT من كلمات AssemblyAI، مع ضمان حد أدنى للمدة الزمنية لكل شريحة
    (300 مللي ثانية) لتفادي شرائح صفرية المدة قد تتسبب بفشل عملية التصدير،
    وتجاهل أي شريحة نصها فارغ بعد التنظيف.
    """
    srt_content = ""
    counter = 1
    for i in range(0, len(words), batch_size):
        batch = words[i:i + batch_size]
        batch_text = " ".join(w.text for w in batch).strip()
        if not batch_text:
            continue

        start_time = batch[0].start
        end_time = max(batch[-1].end, start_time + 300)

        def format_time(ms):
            hrs = ms // 3600000
            mins = (ms % 3600000) // 60000
            secs = (ms % 60000) // 1000
            msecs = ms % 1000
            return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

        srt_content += f"{counter}\n{format_time(start_time)} --> {format_time(end_time)}\n{batch_text}\n\n"
        counter += 1
    return srt_content


# =============================================================================
# قسم رفع الفيديو
# =============================================================================
section_heading("ti-video", "رفع الفيديو", "صيغة MP4. يتم تحليل الصوت وتحديد اللغة تلقائياً.")
uploaded_file = st.file_uploader(" ", type=["mp4"], label_visibility="collapsed")

if uploaded_file is not None:
    with open("temp_input.mp4", "wb") as f:
        f.write(uploaded_file.read())

    st.video("temp_input.mp4")

    st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
    section_heading("ti-settings", "إعدادات الفيديو", "تحكم كامل بالترجمة النصية، أبعاد الفيديو، ونص الافتتاح.")

    tab_caption, tab_frame, tab_hook = st.tabs(["الترجمة النصية", "الإطار والأبعاد", "نص الافتتاح"])

    with tab_caption:
        c1, c2 = st.columns(2)
        with c1:
            font_style = st.selectbox("وزن الخط", list(FONT_LIBRARY.keys()), index=2)
            text_color = st.color_picker("لون النص", "#FFFFFF")
            font_size = st.slider("حجم الخط", 32, 90, 48)
        with c2:
            caption_position = st.selectbox(
                "موضع الترجمة",
                ["أسفل الشاشة (موصى به)", "منتصف الشاشة", "أعلى الشاشة"],
                index=0,
                help="الموضع الافتراضي محسوب لتجنّب مناطق واجهة إنستغرام وتيك توك (الأزرار، اسم الحساب، والتعليقات)."
            )
            use_stroke = st.toggle("حدّ خارجي للنص (Outline)", value=True)
            stroke_color = st.color_picker("لون الحدّ الخارجي", "#000000", disabled=not use_stroke)

        bg_style = st.radio(
            "خلفية الترجمة",
            ["بدون خلفية", "صندوق أسود شفاف", "صندوق بلون العلامة"],
            horizontal=True,
        )
        words_per_caption = st.slider("عدد الكلمات في الشريحة الواحدة", 1, 6, 3)

    with tab_frame:
        aspect_choice = st.selectbox(
            "تنسيق النشر",
            ["الأبعاد الأصلية", "عمودي 9:16 — Reels / Shorts / TikTok", "مربع 1:1 — Instagram Feed"],
            index=1,
        )
        c3, c4 = st.columns(2)
        with c3:
            frame_color = st.color_picker("لون الخلفية أو الإطار", BRAND_BLACK)
        with c4:
            border_thickness = st.slider("سماكة الإطار (بكسل)", 0, 60, 0)

    with tab_hook:
        use_hook = st.toggle("عرض نص افتتاحي أعلى الفيديو", value=False)
        hook_text = st.text_input("نص الافتتاح", "لن تصدق ما ستراه الآن", disabled=not use_hook)
        c5, c6 = st.columns(2)
        with c5:
            hook_duration = st.slider("مدة العرض (ثوانٍ)", 1, 8, 3, disabled=not use_hook)
        with c6:
            hook_color = st.color_picker("لون نص الافتتاح", BRAND_ORANGE, disabled=not use_hook)

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    if st.button("معالجة الفيديو"):

        with st.spinner("جارٍ تحليل الصوت وتحويله إلى نص..."):
            config = aai.TranscriptionConfig(language_detection=True)
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe("temp_input.mp4", config=config)

            if transcript.status == aai.TranscriptStatus.error:
                st.error(f"تعذّرت معالجة الصوت: {transcript.error}")
                st.stop()

            words = transcript.words or []
            lang = transcript.json_response.get('language_code', 'غير معروف')

            has_speech = len(words) > 0
            if has_speech:
                st.success(f"تم تحليل الصوت. اللغة المكتشفة: {lang}")
                srt_data = create_srt_batches(words, batch_size=words_per_caption)
                with open("temp_subtitles.srt", "w", encoding="utf-8") as s_file:
                    _ = s_file.write(srt_data)
                has_speech = bool(srt_data.strip())
            if not has_speech:
                st.warning("لم يتم رصد كلام واضح في الفيديو. سيُنتَج الفيديو بدون ترجمة نصية.")

        with st.spinner("جارٍ تجهيز الفيديو بالتنسيق المختار..."):

            def create_styled_text(txt):
                display_text = prepare_text_for_rendering(txt)
                chosen_font = pick_font_for_text(txt, font_style)

                kwargs = dict(
                    text=display_text,
                    font_size=font_size,
                    color=text_color,
                    font=chosen_font,
                    method="label",
                )
                if use_stroke:
                    kwargs["stroke_color"] = stroke_color
                    kwargs["stroke_width"] = max(2, font_size // 18)
                if bg_style == "صندوق أسود شفاف":
                    kwargs["bg_color"] = (0, 0, 0, 140)
                elif bg_style == "صندوق بلون العلامة":
                    kwargs["bg_color"] = hex_to_rgb(BRAND_ORANGE) + (255,)

                try:
                    return vc.TextClip(**kwargs)
                except Exception:
                    # حماية إضافية: في حال تعذّر الرسم بالخط المختار لأي سبب،
                    # يُعاد المحاولة بالخط الاحتياطي بدل فشل العملية بالكامل.
                    kwargs["font"] = FALLBACK_FONT
                    return vc.TextClip(**kwargs)

            video = vfc.VideoFileClip("temp_input.mp4")

            # ---- الإطار حول الفيديو ----
            frame_rgb = hex_to_rgb(frame_color)
            bw = video.w + 2 * border_thickness
            bh = video.h + 2 * border_thickness
            border_bg = ColorClip(size=(bw, bh), color=frame_rgb, duration=video.duration)
            video_positioned = video.with_position((border_thickness, border_thickness))
            bordered_video = cvc.CompositeVideoClip([border_bg, video_positioned], size=(bw, bh))

            # ---- أبعاد النشر (Aspect Ratio) ----
            target_ratio_map = {
                "عمودي 9:16 — Reels / Shorts / TikTok": 9 / 16,
                "مربع 1:1 — Instagram Feed": 1 / 1,
            }
            if aspect_choice in target_ratio_map:
                target_ratio = target_ratio_map[aspect_choice]
                current_ratio = bw / bh
                if current_ratio > target_ratio:
                    canvas_w, canvas_h = bw, int(round(bw / target_ratio))
                else:
                    canvas_w, canvas_h = int(round(bh * target_ratio)), bh
                canvas_bg = ColorClip(size=(canvas_w, canvas_h), color=frame_rgb, duration=video.duration)
                centered_video = bordered_video.with_position("center")
                final_frame = cvc.CompositeVideoClip([canvas_bg, centered_video], size=(canvas_w, canvas_h))
            else:
                canvas_w, canvas_h = bw, bh
                final_frame = bordered_video

            layers = [final_frame]

            # ---- الترجمة النصية ----
            # المواضع محسوبة استناداً إلى مناطق الأمان المعتمدة في تصميم واجهات
            # إنستغرام وتيك توك: أسفل 15-20% من الشاشة وأعلى 10-12% منها
            # تُغطى غالباً بعناصر الواجهة (اسم الحساب، التعليق، وأزرار التفاعل).
            if has_speech:
                subtitles = sub.SubtitlesClip("temp_subtitles.srt", make_textclip=create_styled_text)
                position_map = {
                    "أسفل الشاشة (موصى به)": int(canvas_h * 0.72),
                    "منتصف الشاشة": int(canvas_h * 0.46),
                    "أعلى الشاشة": int(canvas_h * 0.16),
                }
                subtitles = subtitles.with_position(("center", position_map[caption_position]))
                layers.append(subtitles)

            # ---- نص الافتتاح ----
            if use_hook and hook_text.strip():
                hook_display = prepare_text_for_rendering(hook_text)
                hook_font = pick_font_for_text(hook_text, font_style)
                try:
                    hook_clip = vc.TextClip(
                        text=hook_display,
                        font_size=int(font_size * 1.2),
                        color=hook_color,
                        font=hook_font,
                        method="label",
                        stroke_color="#000000",
                        stroke_width=max(2, font_size // 15),
                        bg_color=(0, 0, 0, 130),
                    )
                except Exception:
                    hook_clip = vc.TextClip(
                        text=hook_display,
                        font_size=int(font_size * 1.2),
                        color=hook_color,
                        font=FALLBACK_FONT,
                        method="label",
                        stroke_color="#000000",
                        stroke_width=max(2, font_size // 15),
                        bg_color=(0, 0, 0, 130),
                    )
                hook_clip = (
                    hook_clip
                    .with_position(("center", int(canvas_h * 0.14)))
                    .with_start(0)
                    .with_duration(min(hook_duration, video.duration))
                )
                layers.append(hook_clip)

            final_video = cvc.CompositeVideoClip(layers, size=(canvas_w, canvas_h))

            write_kwargs = dict(
                codec='libx264',
                preset='ultrafast',
                fps=video.fps or 30,
                logger=None,
            )
            if final_video.audio is not None:
                write_kwargs["audio_codec"] = "aac"

            final_video.write_videofile("temp_output.mp4", **write_kwargs)

        st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
        section_heading("ti-circle-check", "الفيديو النهائي", "المعالجة اكتملت بنجاح.")
        st.video("temp_output.mp4")

        with open("temp_output.mp4", "rb") as file:
            st.download_button(
                label="تنزيل الفيديو",
                data=file,
                file_name="edit73_video.mp4",
                mime="video/mp4",
            )

st.markdown('<div class="app-footer">edit73 — استوديو الترجمة الذكي</div>', unsafe_allow_html=True)
