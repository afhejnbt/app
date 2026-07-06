import base64
import os
import re

import streamlit as st
import assemblyai as aai
from PIL import ImageFont

# =============================================================================
# إصلاح جذري لعرض النص العربي: تعطيل محرك raqm نهائياً وفرض معالجة ثابتة
# (arabic_reshaper + bidi) على كل السيرفرات دون استثناء.
#
# السبب: بعض بيئات الاستضافة (مثل Streamlit Cloud) لا تملك مكتبة raqm النظامية،
# فتتحول المكتبة تلقائياً لأسلوب عرض مختلف قد ينتج حروفاً مفقودة مع خطوط لا
# تغطي كامل "أشكال العرض" العربية. بفرض نفس المسار دائماً (بدل ترك القرار
# لبيئة السيرفر)، تصبح النتيجة متطابقة ومضمونة على أي خادم.
# =============================================================================
_original_truetype = ImageFont.truetype


def _truetype_forced_basic(*args, **kwargs):
    kwargs["layout_engine"] = ImageFont.Layout.BASIC
    return _original_truetype(*args, **kwargs)


ImageFont.truetype = _truetype_forced_basic

import moviepy.video.io.VideoFileClip as vfc
import moviepy.video.VideoClip as vc
from moviepy.video.VideoClip import ColorClip
import moviepy.video.compositing.CompositeVideoClip as cvc
import moviepy.video.tools.subtitles as sub
import arabic_reshaper
from bidi.algorithm import get_display

# =============================================================================
# الهوية البصرية
# =============================================================================
BRAND_ORANGE = "#F26921"
BRAND_ORANGE_DARK = "#C8551A"
BRAND_ORANGE_SOFT = "#FDEEE5"
INK = "#15161A"
INK_SOFT = "#5B5D68"
LINE = "#E7E7EA"
SURFACE = "#FFFFFF"
PAGE_BG = "#FAFAFA"

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
# التصميم
# =============================================================================
st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/3.44.0/tabler-icons.min.css">

<style>
html, body, [class*="css"] {{ font-family: 'Tajawal', 'Inter', sans-serif; }}

.stApp {{ background: {PAGE_BG}; color: {INK}; }}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 0 !important; padding-bottom: 3rem; max-width: 760px; }}

/* ---------- الشريط العلوي ---------- */
.top-bar {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    background: {SURFACE};
    border-bottom: 1px solid {LINE};
    margin: 0 -1rem 0 -1rem;
    padding: 16px 1rem;
}}
.top-bar img {{ width: 30px; height: 30px; }}
.top-bar .wordmark {{ font-size: 1.05rem; font-weight: 800; color: {INK}; }}
.top-bar .wordmark span {{ color: {BRAND_ORANGE}; }}

/* ---------- الهيرو ---------- */
.hero {{ text-align: center; padding: 52px 0 40px 0; }}
.hero .badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: {BRAND_ORANGE_SOFT};
    color: {BRAND_ORANGE_DARK};
    font-size: 0.78rem;
    font-weight: 700;
    padding: 6px 14px;
    border-radius: 999px;
    margin-bottom: 18px;
}}
.hero h1 {{
    font-size: 2.15rem;
    font-weight: 800;
    color: {INK};
    margin: 0 0 14px 0;
    line-height: 1.35;
}}
.hero p {{
    color: {INK_SOFT};
    font-size: 1rem;
    max-width: 490px;
    margin: 0 auto;
    line-height: 1.75;
}}

/* ---------- بطاقات الميزات ---------- */
.feature-card {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 16px;
    padding: 20px 18px;
    height: 100%;
    box-shadow: 0 1px 2px rgba(16,16,20,0.04);
}}
.feature-card .icon-circle {{
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: {BRAND_ORANGE_SOFT};
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 12px;
}}
.feature-card .icon-circle i {{ font-size: 19px; color: {BRAND_ORANGE_DARK}; }}
.feature-card h4 {{ font-size: 0.94rem; font-weight: 700; color: {INK}; margin: 0 0 6px 0; }}
.feature-card p {{ font-size: 0.82rem; color: {INK_SOFT}; margin: 0; line-height: 1.6; }}

/* ---------- عناوين الأقسام ---------- */
.section-heading {{ display: flex; align-items: center; gap: 9px; margin: 0 0 4px 0; }}
.section-heading i {{ font-size: 18px; color: {BRAND_ORANGE}; }}
.section-heading h3 {{ font-size: 1.05rem; font-weight: 700; color: {INK}; margin: 0; }}
.section-desc {{ color: {INK_SOFT}; font-size: 0.85rem; margin: 3px 0 18px 0; }}

/* ---------- بطاقة عامة ---------- */
.card-wrap {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 18px;
    padding: 24px 22px 10px 22px;
    box-shadow: 0 1px 3px rgba(16,16,20,0.05);
    margin-bottom: 26px;
}}

/* ---------- رفع الفيديو ---------- */
section[data-testid="stFileUploaderDropzone"] {{
    background-color: #FCFCFD !important;
    border: 1.5px dashed {LINE} !important;
    border-radius: 14px !important;
}}
section[data-testid="stFileUploaderDropzone"]:hover {{ border-color: {BRAND_ORANGE} !important; }}

/* ---------- التبويبات (شكل شرائح مقسّمة) ---------- */
.stTabs [data-baseweb="tab-list"] {{
    gap: 2px;
    background: #F0F0F2;
    padding: 4px;
    border-radius: 11px;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px;
    color: {INK_SOFT};
    font-weight: 600;
    font-size: 0.87rem;
    padding: 9px 16px;
}}
.stTabs [aria-selected="true"] {{
    background: {SURFACE} !important;
    color: {BRAND_ORANGE_DARK} !important;
    box-shadow: 0 1px 2px rgba(16,16,20,0.08);
}}
.stTabs [data-baseweb="tab-panel"] {{ padding: 22px 2px 8px 2px; }}

/* ---------- عناصر الإدخال ---------- */
div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
    background-color: {SURFACE} !important;
    color: {INK} !important;
    border-radius: 9px !important;
    border-color: {LINE} !important;
}}
.stSlider [data-baseweb="slider"] > div > div {{ background: {BRAND_ORANGE} !important; }}
label p {{ color: {INK} !important; font-size: 0.85rem !important; font-weight: 600 !important; }}

/* ---------- الأزرار ---------- */
.stButton>button {{
    background: {BRAND_ORANGE};
    color: #FFFFFF;
    font-weight: 700;
    font-size: 1rem;
    border-radius: 11px;
    width: 100%;
    padding: 13px;
    border: none;
    box-shadow: 0 4px 10px rgba(242,105,33,0.28);
    transition: all 0.15s ease;
}}
.stButton>button:hover {{ background: {BRAND_ORANGE_DARK}; transform: translateY(-1px); }}
.stButton>button:active {{ transform: translateY(0); }}

.stDownloadButton>button {{
    background: {SURFACE};
    color: {INK};
    border: 1px solid {LINE};
    font-weight: 600;
    border-radius: 11px;
    width: 100%;
    padding: 12px;
}}
.stDownloadButton>button:hover {{ border-color: {BRAND_ORANGE}; color: {BRAND_ORANGE_DARK}; }}

/* ---------- تنبيهات ---------- */
div[data-testid="stAlert"] {{ border-radius: 11px; }}

/* ---------- الفوتر ---------- */
.app-footer {{
    text-align: center;
    color: {INK_SOFT};
    font-size: 0.8rem;
    padding-top: 26px;
    margin-top: 16px;
    border-top: 1px solid {LINE};
}}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# الشريط العلوي
# =============================================================================
if LOGO_B64:
    st.markdown(f"""
        <div class="top-bar">
            <img src="data:image/png;base64,{LOGO_B64}" alt="edit73" />
            <div class="wordmark">edit<span>73</span></div>
        </div>
    """, unsafe_allow_html=True)

# =============================================================================
# الهيرو
# =============================================================================
st.markdown("""
    <div class="hero">
        <div class="badge"><i class="ti ti-sparkles"></i>مدعوم بالذكاء الاصطناعي</div>
        <h1>ترجمة فيديو احترافية خلال دقائق</h1>
        <p>يحلّل edit73 حديثك المسجّل، يولّد ترجمة نصية مضبوطة التوقيت بالعربية
        والإنجليزية، ويهيئ الفيديو للنشر مباشرة على منصات التواصل الاجتماعي.</p>
    </div>
""", unsafe_allow_html=True)

fc1, fc2, fc3 = st.columns(3, gap="small")
with fc1:
    st.markdown("""
        <div class="feature-card">
            <div class="icon-circle"><i class="ti ti-language"></i></div>
            <h4>دعم عربي وإنجليزي</h4>
            <p>تعرّف تلقائي على اللغة، وضبط الخط المناسب لكل جملة.</p>
        </div>
    """, unsafe_allow_html=True)
with fc2:
    st.markdown("""
        <div class="feature-card">
            <div class="icon-circle"><i class="ti ti-aspect-ratio"></i></div>
            <h4>مقاسات جاهزة للنشر</h4>
            <p>عمودي، مربع، أو الأبعاد الأصلية بضغطة واحدة.</p>
        </div>
    """, unsafe_allow_html=True)
with fc3:
    st.markdown("""
        <div class="feature-card">
            <div class="icon-circle"><i class="ti ti-layout-navbar"></i></div>
            <h4>مواضع مدروسة</h4>
            <p>ترجمة وهووك بمواضع تراعي واجهات إنستغرام وتيك توك.</p>
        </div>
    """, unsafe_allow_html=True)

st.markdown('<div style="height:36px"></div>', unsafe_allow_html=True)


def section_heading(icon, title, desc):
    st.markdown(f"""
        <div class="section-heading"><i class="ti {icon}"></i><h3>{title}</h3></div>
        <div class="section-desc">{desc}</div>
    """, unsafe_allow_html=True)


# =============================================================================
# معالجة النص العربي (ثابتة على كل السيرفرات، راجع الشرح أعلى الملف)
# =============================================================================
_ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F]')


def is_mostly_arabic(txt):
    letters = re.findall(r'[^\s\d\W]', txt, re.UNICODE)
    if not letters:
        return False
    arabic_letters = _ARABIC_RE.findall(txt)
    return len(arabic_letters) >= max(1, len(letters) // 2)


def prepare_text_for_rendering(txt):
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
        "ar": os.path.join(FONTS_DIR, "NotoSansArabic-Bold.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Bold.ttf"),
    },
    "عريض جداً (Extra Bold)": {
        "ar": os.path.join(FONTS_DIR, "NotoSansArabic-ExtraBold.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-ExtraBold.ttf"),
    },
    "أسود ثقيل (Black)": {
        "ar": os.path.join(FONTS_DIR, "NotoSansArabic-Black.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Black.ttf"),
    },
    "كلاسيكي (Naskh)": {
        "ar": os.path.join(FONTS_DIR, "NotoNaskhArabic-Regular.ttf"),
        "en": os.path.join(FONTS_DIR, "Poppins-Bold.ttf"),
    },
}
FALLBACK_FONT = os.path.join(FONTS_DIR, "NotoNaskhArabic-Regular.ttf")


def create_srt_batches(words, batch_size=3):
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
st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
section_heading("ti-video", "رفع الفيديو", "صيغة MP4. يتم تحليل الصوت وتحديد اللغة تلقائياً.")
uploaded_file = st.file_uploader(" ", type=["mp4"], label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

if uploaded_file is not None:
    with open("temp_input.mp4", "wb") as f:
        f.write(uploaded_file.read())

    st.video("temp_input.mp4")
    st.markdown('<div style="height:26px"></div>', unsafe_allow_html=True)

    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
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
                help="الموضع الافتراضي محسوب لتجنّب مناطق واجهة إنستغرام وتيك توك."
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
            frame_color = st.color_picker("لون الخلفية أو الإطار", "#0A0A0C")
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

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

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
                    kwargs["font"] = FALLBACK_FONT
                    return vc.TextClip(**kwargs)

            video = vfc.VideoFileClip("temp_input.mp4")

            frame_rgb = hex_to_rgb(frame_color)
            bw = video.w + 2 * border_thickness
            bh = video.h + 2 * border_thickness
            border_bg = ColorClip(size=(bw, bh), color=frame_rgb, duration=video.duration)
            video_positioned = video.with_position((border_thickness, border_thickness))
            bordered_video = cvc.CompositeVideoClip([border_bg, video_positioned], size=(bw, bh))

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

            if has_speech:
                subtitles = sub.SubtitlesClip("temp_subtitles.srt", make_textclip=create_styled_text)
                position_map = {
                    "أسفل الشاشة (موصى به)": int(canvas_h * 0.72),
                    "منتصف الشاشة": int(canvas_h * 0.46),
                    "أعلى الشاشة": int(canvas_h * 0.16),
                }
                subtitles = subtitles.with_position(("center", position_map[caption_position]))
                layers.append(subtitles)

            if use_hook and hook_text.strip():
                hook_display = prepare_text_for_rendering(hook_text)
                hook_font = pick_font_for_text(hook_text, font_style)
                hook_kwargs = dict(
                    text=hook_display,
                    font_size=int(font_size * 1.2),
                    color=hook_color,
                    font=hook_font,
                    method="label",
                    stroke_color="#000000",
                    stroke_width=max(2, font_size // 15),
                    bg_color=(0, 0, 0, 130),
                )
                try:
                    hook_clip = vc.TextClip(**hook_kwargs)
                except Exception:
                    hook_kwargs["font"] = FALLBACK_FONT
                    hook_clip = vc.TextClip(**hook_kwargs)

                hook_clip = (
                    hook_clip
                    .with_position(("center", int(canvas_h * 0.14)))
                    .with_start(0)
                    .with_duration(min(hook_duration, video.duration))
                )
                layers.append(hook_clip)

            final_video = cvc.CompositeVideoClip(layers, size=(canvas_w, canvas_h))

            write_kwargs = dict(codec='libx264', preset='ultrafast', fps=video.fps or 30, logger=None)
            if final_video.audio is not None:
                write_kwargs["audio_codec"] = "aac"

            final_video.write_videofile("temp_output.mp4", **write_kwargs)

        st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
        section_heading("ti-circle-check", "الفيديو النهائي", "المعالجة اكتملت بنجاح.")
        st.video("temp_output.mp4")

        with open("temp_output.mp4", "rb") as file:
            st.download_button(
                label="تنزيل الفيديو",
                data=file,
                file_name="edit73_video.mp4",
                mime="video/mp4",
            )
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="app-footer">edit73 — استوديو الترجمة الذكي</div>', unsafe_allow_html=True)
