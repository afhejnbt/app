import glob
import os
import re

import streamlit as st
import assemblyai as aai
import moviepy.video.io.VideoFileClip as vfc
import moviepy.video.VideoClip as vc
from moviepy.video.VideoClip import ColorClip
import moviepy.video.compositing.CompositeVideoClip as cvc
import moviepy.video.tools.subtitles as sub
import arabic_reshaper
from bidi.algorithm import get_display

# =============================================================================
# إعدادات عامة وهوية بصرية (Brand Identity) — مبنية على شعار edit73
# =============================================================================
BRAND_ORANGE = "#F26921"
BRAND_ORANGE_HOVER = "#FF7E32"
BRAND_BLACK = "#0B0B0D"
BRAND_DARK_CARD = "#17181C"
BRAND_WHITE = "#F5F5F7"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(APP_DIR, "fonts")
ASSETS_DIR = os.path.join(APP_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

st.set_page_config(
    page_title="edit73 — مصنع الترجمة الذكي",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🎬",
    layout="centered",
)

# =============================================================================
# مفتاح AssemblyAI عبر Secrets فقط (لا يُكتب أبداً داخل الكود)
# =============================================================================
try:
    aai.settings.api_key = st.secrets["ASSEMBLYAI_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("⚠️ لم يتم العثور على مفتاح AssemblyAI. أضفه في Secrets باسم ASSEMBLYAI_API_KEY.")
    st.stop()

# =============================================================================
# تحميل CSS مخصص بالهوية البصرية
# =============================================================================
st.markdown(f"""
    <style>
    .stApp {{
        background: radial-gradient(circle at 20% 0%, #1a1b1f 0%, {BRAND_BLACK} 55%);
        color: {BRAND_WHITE};
    }}
    #MainMenu, footer, header {{ visibility: hidden; }}

    .brand-header {{
        text-align: center;
        padding: 8px 0 4px 0;
    }}
    .brand-title {{
        font-size: 2.1rem;
        font-weight: 800;
        color: {BRAND_WHITE};
        margin: 4px 0 0 0;
    }}
    .brand-title span {{ color: {BRAND_ORANGE}; }}
    .brand-subtitle {{
        color: #9a9ba3;
        font-size: 0.95rem;
        margin-top: 2px;
    }}

    section[data-testid="stFileUploaderDropzone"] {{
        background-color: {BRAND_DARK_CARD};
        border: 1.5px dashed {BRAND_ORANGE}55;
        border-radius: 16px;
    }}

    .stButton>button {{
        background: linear-gradient(135deg, {BRAND_ORANGE}, {BRAND_ORANGE_HOVER});
        color: #0d0f12;
        font-weight: 800;
        font-size: 1.05rem;
        border-radius: 14px;
        width: 100%;
        padding: 12px;
        border: none;
        box-shadow: 0 6px 20px {BRAND_ORANGE}33;
        transition: all 0.2s ease;
    }}
    .stButton>button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 10px 24px {BRAND_ORANGE}55;
    }}

    .stDownloadButton>button {{
        background: {BRAND_DARK_CARD};
        color: {BRAND_ORANGE};
        border: 1.5px solid {BRAND_ORANGE};
        font-weight: 700;
        border-radius: 14px;
        width: 100%;
        padding: 12px;
    }}
    .stDownloadButton>button:hover {{
        background: {BRAND_ORANGE}22;
    }}

    div[data-testid="stExpander"] {{
        background-color: {BRAND_DARK_CARD};
        border-radius: 14px;
        border: 1px solid #2a2c33;
    }}

    div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
        background-color: #1f2128 !important;
        color: {BRAND_WHITE} !important;
        border-radius: 10px !important;
    }}

    .stSlider [data-baseweb="slider"] > div > div {{ background: {BRAND_ORANGE} !important; }}

    footer-credit {{
        text-align: center; color: #55565c; font-size: 0.8rem;
    }}
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# رأس الصفحة: الشعار + العنوان
# =============================================================================
col_a, col_b, col_c = st.columns([1, 1.3, 1])
with col_b:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)

st.markdown(f"""
    <div class="brand-header">
        <div class="brand-title">edit<span>73</span></div>
        <div class="brand-subtitle">مصنع الترجمة الذكي — حوّل فيديوهاتك لمحتوى جاهز للانتشار 🚀</div>
    </div>
""", unsafe_allow_html=True)

st.write("")

# =============================================================================
# الخطوط: عربي وإنجليزي، بأوزان متعددة (Bold / ExtraBold / Black)
# =============================================================================
FONT_LIBRARY = {
    "عريض (Bold)": {
        "ar": os.path.join(FONTS_DIR, "Tajawal-Bold.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Bold.ttf"),
    },
    "عريض جداً (Extra Bold)": {
        "ar": os.path.join(FONTS_DIR, "Tajawal-ExtraBold.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-ExtraBold.ttf"),
    },
    "أسود ثقيل (Black) — الأكثر انتشاراً": {
        "ar": os.path.join(FONTS_DIR, "Tajawal-Black.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Black.ttf"),
    },
    "كلاسيكي (Naskh)": {
        "ar": os.path.join(FONTS_DIR, "NotoNaskhArabic-Regular.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Bold.ttf"),
    },
}

_ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F]')


def is_mostly_arabic(txt):
    letters = re.findall(r'[^\s\d\W]', txt, re.UNICODE)
    if not letters:
        return False
    arabic_letters = _ARABIC_RE.findall(txt)
    return len(arabic_letters) >= max(1, len(letters) // 2)


def prepare_text_for_rendering(txt):
    """
    يعالج تشكيل الحروف العربية (ربط الحروف) وترتيب اتجاه النص (Bidi) يدوياً،
    لأن ImageMagick لا يطبّق هذا المنطق تلقائياً على السيرفر.
    """
    if _ARABIC_RE.search(txt):
        reshaped = arabic_reshaper.reshape(txt)
        return get_display(reshaped)
    return txt


def pick_font_for_text(txt, font_style_key):
    fonts = FONT_LIBRARY[font_style_key]
    return fonts["ar"] if is_mostly_arabic(txt) else fonts["en"]


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


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
        srt_content += f"{counter}\n{format_time(start_time)} --> {format_time(end_time)}\n{batch_text}\n\n"
        counter += 1
    return srt_content


# =============================================================================
# واجهة رفع الفيديو
# =============================================================================
uploaded_file = st.file_uploader("📥 اسحب وأفلت مقطع الفيديو هنا (MP4)...", type=["mp4"])

if uploaded_file is not None:
    with open("temp_input.mp4", "wb") as f:
        f.write(uploaded_file.read())

    st.video("temp_input.mp4")

    # =========================================================================
    # خيارات التصميم
    # =========================================================================
    st.markdown("### 🎛️ خصص شكل فيديوك")

    tab_caption, tab_frame, tab_hook = st.tabs(["🎨 الترجمة", "🖼️ الإطار والشكل", "🪝 الهووك الافتتاحي"])

    with tab_caption:
        c1, c2 = st.columns(2)
        with c1:
            font_style = st.selectbox("وزن الخط (عربي + إنجليزي تلقائياً)", list(FONT_LIBRARY.keys()), index=2)
            text_color = st.color_picker("لون الكتابة", "#FFFFFF")
            font_size = st.slider("حجم الخط", 20, 90, 46)
        with c2:
            caption_position = st.selectbox("موضع الترجمة", ["أسفل الفيديو", "منتصف الفيديو", "أعلى الفيديو"], index=0)
            use_stroke = st.toggle("إضافة حدّ خارجي (Outline) للنص", value=True)
            stroke_color = st.color_picker("لون الحدّ الخارجي", "#000000", disabled=not use_stroke)

        bg_style = st.radio(
            "خلفية الترجمة",
            ["بدون خلفية (شفافة)", "صندوق أسود شفاف", "صندوق بلون العلامة (Brand)"],
            horizontal=True,
        )
        words_per_caption = st.slider("عدد الكلمات بكل شريحة ترجمة", 1, 6, 3)

    with tab_frame:
        aspect_choice = st.selectbox(
            "شكل الفيديو (تنسيق النشر)",
            ["الأصلي بدون تغيير", "عمودي 9:16 (Reels / Shorts / TikTok)", "مربع 1:1 (Instagram)"],
            index=1,
        )
        c3, c4 = st.columns(2)
        with c3:
            frame_color = st.color_picker("لون الإطار / الخلفية", BRAND_BLACK)
        with c4:
            border_thickness = st.slider("سُمك الإطار حول الفيديو (px)", 0, 60, 0)

    with tab_hook:
        use_hook = st.toggle("إظهار جملة جذب (Hook) في أعلى الفيديو بالبداية", value=False)
        hook_text = st.text_input("نص الهووك", "أنتَ لن تصدق ما سيحدث 👀", disabled=not use_hook)
        c5, c6 = st.columns(2)
        with c5:
            hook_duration = st.slider("مدة ظهور الهووك (ثواني)", 1, 8, 3, disabled=not use_hook)
        with c6:
            hook_color = st.color_picker("لون نص الهووك", BRAND_ORANGE, disabled=not use_hook)

    st.write("")

    if st.button("🚀 ابدأ السحر واطبخ الفيديو الحين!"):

        with st.spinner("🧠 قاعدين نسمع المقطع الحين ونفكك الكلمات بدقة.. ثواني وبنبهرك!"):
            config = aai.TranscriptionConfig(language_detection=True)
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe("temp_input.mp4", config=config)

            if transcript.status == aai.TranscriptStatus.error:
                st.error(f"❌ أوبس! حصلت مشكلة بالذكاء الاصطناعي: {transcript.error}")
                st.stop()

            lang = transcript.json_response.get('language_code')
            st.success(f"🌍 لقطنا لغة الفيديو! طلعت: ({lang})")

            srt_data = create_srt_batches(transcript.words, batch_size=words_per_caption)
            with open("temp_subtitles.srt", "w", encoding="utf-8") as s_file:
                _ = s_file.write(srt_data)

        with st.spinner("🎨 الحين جاري دمج النصوص وتلوينها بالستايل الجديد.. اجهز للنتيجة!"):

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
                elif bg_style == "صندوق بلون العلامة (Brand)":
                    kwargs["bg_color"] = hex_to_rgb(BRAND_ORANGE) + (255,)

                return vc.TextClip(**kwargs)

            video = vfc.VideoFileClip("temp_input.mp4")

            # ---- بناء الإطار (Border) حول الفيديو ----
            frame_rgb = hex_to_rgb(frame_color)
            bw = video.w + 2 * border_thickness
            bh = video.h + 2 * border_thickness
            border_bg = ColorClip(size=(bw, bh), color=frame_rgb, duration=video.duration)
            video_positioned = video.with_position((border_thickness, border_thickness))
            bordered_video = cvc.CompositeVideoClip([border_bg, video_positioned], size=(bw, bh))

            # ---- ضبط نسبة العرض للطول (Aspect Ratio) لتنسيقات السوشال ميديا ----
            target_ratio_map = {
                "عمودي 9:16 (Reels / Shorts / TikTok)": 9 / 16,
                "مربع 1:1 (Instagram)": 1 / 1,
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

            # ---- الترجمة (Subtitles) ----
            subtitles = sub.SubtitlesClip("temp_subtitles.srt", make_textclip=create_styled_text)

            position_map = {
                "أسفل الفيديو": int(canvas_h * 0.80),
                "منتصف الفيديو": int(canvas_h * 0.46),
                "أعلى الفيديو": int(canvas_h * 0.14),
            }
            subtitles = subtitles.with_position(("center", position_map[caption_position]))

            layers = [final_frame, subtitles]

            # ---- الهووك الافتتاحي ----
            if use_hook and hook_text.strip():
                hook_display = prepare_text_for_rendering(hook_text)
                hook_font = pick_font_for_text(hook_text, font_style)
                hook_clip = vc.TextClip(
                    text=hook_display,
                    font_size=int(font_size * 1.25),
                    color=hook_color,
                    font=hook_font,
                    method="label",
                    stroke_color="#000000",
                    stroke_width=max(2, font_size // 15),
                    bg_color=(0, 0, 0, 130),
                )
                hook_clip = (
                    hook_clip
                    .with_position(("center", int(canvas_h * 0.06)))
                    .with_start(0)
                    .with_duration(min(hook_duration, video.duration))
                )
                layers.append(hook_clip)

            final_video = cvc.CompositeVideoClip(layers, size=(canvas_w, canvas_h))
            final_video.write_videofile(
                "temp_output.mp4",
                codec='libx264',
                audio_codec='aac',
                preset='ultrafast',
                fps=video.fps or 30,
                logger=None
            )

        st.success("🎉 يسلّم راسك! المقطع جاهز ومطبوخ بأعلى جودة!")
        st.write("### 🔥 الق نظرة على مقطعك الرهيب:")
        st.video("temp_output.mp4")

        with open("temp_output.mp4", "rb") as file:
            st.download_button(
                label="📥 تحميل الفيديو المترجم فوراً بجهازك",
                data=file,
                file_name="edit73_video.mp4",
                mime="video/mp4"
            )

st.markdown("<p class='footer-credit'>Made with 🧡 by edit73</p>", unsafe_allow_html=True)
