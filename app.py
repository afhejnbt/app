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
# الهوية البصرية — نسخة داكنة احترافية
# ثنائية "البرتقالي والسماوي" (Teal & Orange) هي بالضبط لغة تصحيح الألوان
# السينمائي المستخدمة في صناعة الفيديو، لذا اعتُمدت هنا كإشارة بصرية مقصودة:
# البرتقالي = هوية العلامة والإجراء الأساسي، السماوي = التقدّم والاكتمال.
# =============================================================================
BG_BASE = "#0B0C10"
BG_SURFACE = "#14151B"
BG_SURFACE_2 = "#1B1D25"
BORDER = "#272932"
BORDER_SOFT = "#1F212A"
TEXT_PRIMARY = "#F2F3F5"
TEXT_SECONDARY = "#9497A3"
TEXT_MUTED = "#5C5F6B"

BRAND_ORANGE = "#F26921"
BRAND_ORANGE_BRIGHT = "#FF8142"
BRAND_ORANGE_SOFT = "rgba(242,105,33,0.14)"

TEAL = "#2DD4BF"
TEAL_SOFT = "rgba(45,212,191,0.14)"

DANGER = "#F2555A"

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
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/3.44.0/tabler-icons.min.css">

<style>
html, body, [class*="css"] {{ font-family: 'Tajawal', 'Inter', sans-serif; }}
.mono {{ font-family: 'JetBrains Mono', monospace !important; }}

.stApp {{ background: {BG_BASE}; color: {TEXT_PRIMARY}; }}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 0 !important; padding-bottom: 3rem; max-width: 720px; }}

/* ---------- الشريط العلوي ---------- */
.top-bar {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    background: {BG_SURFACE};
    border-bottom: 1px solid {BORDER};
    margin: 0 -1rem 28px -1rem;
    padding: 16px 1rem;
}}
.top-bar img {{ width: 28px; height: 28px; border-radius: 6px; }}
.top-bar .wordmark {{ font-size: 1.02rem; font-weight: 800; color: {TEXT_PRIMARY}; letter-spacing: .2px; }}
.top-bar .wordmark span {{ color: {BRAND_ORANGE}; }}
.top-bar .tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: .68rem;
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    padding: 2px 8px;
    border-radius: 999px;
    margin-inline-start: 6px;
}}

/* ---------- عنوان مختصر للأداة ---------- */
.page-head {{ padding: 4px 2px 22px 2px; }}
.page-head h1 {{
    font-size: 1.5rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    margin: 0 0 6px 0;
}}
.page-head p {{ color: {TEXT_SECONDARY}; font-size: .88rem; margin: 0; line-height: 1.7; }}

/* ---------- شريط الخطوات (سكربتر / تايم‌لاين) ---------- */
.scrubber {{ margin: 6px 2px 30px 2px; }}
.scrubber-track {{
    position: relative;
    height: 3px;
    background: {BORDER};
    border-radius: 3px;
    margin: 0 4px 14px 4px;
}}
.scrubber-fill {{
    position: absolute;
    inset-inline-start: 0;
    top: 0;
    height: 100%;
    border-radius: 3px;
    background: linear-gradient(90deg, {TEAL}, {BRAND_ORANGE});
    transition: width .35s ease;
}}
.scrubber-nodes {{ display: flex; justify-content: space-between; direction: ltr; }}
.scrubber-node {{ display: flex; flex-direction: column; align-items: center; gap: 6px; width: 25%; }}
.scrubber-node .dot {{
    width: 26px; height: 26px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace; font-size: .68rem; font-weight: 700;
    border: 2px solid {BORDER}; color: {TEXT_MUTED}; background: {BG_SURFACE};
    transition: all .25s ease;
}}
.scrubber-node.done .dot {{ border-color: {TEAL}; color: {TEAL}; background: {TEAL_SOFT}; }}
.scrubber-node.active .dot {{
    border-color: {BRAND_ORANGE}; color: {BRAND_ORANGE_BRIGHT}; background: {BRAND_ORANGE_SOFT};
    box-shadow: 0 0 0 4px {BRAND_ORANGE_SOFT};
}}
.scrubber-node .lbl {{ font-size: .74rem; color: {TEXT_MUTED}; font-weight: 600; direction: rtl; }}
.scrubber-node.active .lbl {{ color: {TEXT_PRIMARY}; }}
.scrubber-node.done .lbl {{ color: {TEXT_SECONDARY}; }}

/* ---------- بطاقة عامة ---------- */
.card-wrap {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 24px 22px 12px 22px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.28);
    margin-bottom: 22px;
}}

/* ---------- عناوين الأقسام ---------- */
.section-heading {{ display: flex; align-items: center; gap: 9px; margin: 0 0 4px 0; }}
.section-heading i {{ font-size: 17px; color: {BRAND_ORANGE}; }}
.section-heading h3 {{ font-size: 1rem; font-weight: 700; color: {TEXT_PRIMARY}; margin: 0; }}
.section-desc {{ color: {TEXT_SECONDARY}; font-size: .82rem; margin: 3px 0 18px 0; }}

/* ---------- شارات معلومات الملف ---------- */
.chip-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 4px 0; }}
.chip {{
    font-family: 'JetBrains Mono', monospace;
    font-size: .72rem;
    color: {TEXT_SECONDARY};
    background: {BG_SURFACE_2};
    border: 1px solid {BORDER};
    padding: 5px 10px;
    border-radius: 8px;
}}
.chip b {{ color: {TEXT_PRIMARY}; font-weight: 600; }}

/* ---------- رفع الفيديو ---------- */
section[data-testid="stFileUploaderDropzone"] {{
    background-color: {BG_SURFACE_2} !important;
    border: 1.5px dashed {BORDER} !important;
    border-radius: 14px !important;
}}
section[data-testid="stFileUploaderDropzone"]:hover {{ border-color: {BRAND_ORANGE} !important; }}
section[data-testid="stFileUploaderDropzone"] * {{ color: {TEXT_SECONDARY} !important; }}
div[data-testid="stFileUploaderDropzoneInstructions"] svg {{ fill: {TEXT_MUTED} !important; }}

/* ---------- عناصر الإدخال ---------- */
div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
    background-color: {BG_SURFACE_2} !important;
    color: {TEXT_PRIMARY} !important;
    border-radius: 9px !important;
    border-color: {BORDER} !important;
}}
div[data-baseweb="popover"] li {{ background-color: {BG_SURFACE_2} !important; color: {TEXT_PRIMARY} !important; }}
.stSlider [data-baseweb="slider"] > div > div {{ background: {BRAND_ORANGE} !important; }}
.stSlider [role="slider"] {{ background: {BRAND_ORANGE_BRIGHT} !important; }}
label p, .stMarkdown p {{ color: {TEXT_PRIMARY} !important; }}
label p {{ font-size: 0.85rem !important; font-weight: 600 !important; }}
.stRadio label p, .stCheckbox label p {{ font-weight: 500 !important; }}
[data-testid="stWidgetLabel"] {{ color: {TEXT_PRIMARY} !important; }}
[data-testid="stMarkdownContainer"] p {{ color: {TEXT_SECONDARY}; }}
.stCaption, [data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED} !important; }}

/* ---------- الأزرار ---------- */
.stButton>button {{
    background: {BRAND_ORANGE};
    color: #0B0C10;
    font-weight: 700;
    font-size: .95rem;
    border-radius: 11px;
    width: 100%;
    padding: 12px;
    border: none;
    box-shadow: 0 4px 14px rgba(242,105,33,0.22);
    transition: all 0.15s ease;
}}
.stButton>button:hover {{ background: {BRAND_ORANGE_BRIGHT}; transform: translateY(-1px); }}
.stButton>button:active {{ transform: translateY(0); }}
.stButton>button p {{ color: #0B0C10 !important; font-weight: 700 !important; }}

button[kind="secondary"] {{
    background: {BG_SURFACE_2} !important;
    border: 1px solid {BORDER} !important;
}}
button[kind="secondary"] p {{ color: {TEXT_PRIMARY} !important; }}

.stDownloadButton>button {{
    background: {TEAL};
    color: #0B0C10;
    border: none;
    font-weight: 700;
    border-radius: 11px;
    width: 100%;
    padding: 12px;
}}
.stDownloadButton>button p {{ color: #0B0C10 !important; font-weight: 700 !important; }}
.stDownloadButton>button:hover {{ filter: brightness(1.08); }}

/* ---------- تنبيهات ---------- */
div[data-testid="stAlert"] {{ border-radius: 11px; }}

/* ---------- الفوتر ---------- */
.app-footer {{
    text-align: center;
    color: {TEXT_MUTED};
    font-size: 0.78rem;
    padding-top: 26px;
    margin-top: 16px;
    border-top: 1px solid {BORDER};
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
            <div class="tag">STUDIO</div>
        </div>
    """, unsafe_allow_html=True)


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


def format_time(ms):
    hrs = ms // 3600000
    mins = (ms % 3600000) // 60000
    secs = (ms % 60000) // 1000
    msecs = ms % 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"


def create_srt_batches(words, batch_size=3, min_duration_ms=300, gap_ms=40):
    """
    يبني ملف SRT من كلمات AssemblyAI على شكل دفعات.

    -- إصلاح جوهري --
    كان يُفرض حدّ أدنى لمدة عرض كل شريحة (300ms) دون التحقّق من موعد بداية
    الشريحة التالية. في الكلام السريع (كلمات قصيرة ومتقاربة) كانت مدة العرض
    الممتدة تتجاوز بداية الشريحة التالية، فتظهر شريحتان مختلفتان من الترجمة
    في نفس اللحظة وفوق بعضهما في نفس الموضع على الشاشة — وهذا هو سبب ظهور
    "نص مأكول من نص" في الفيديو الناتج. الإصلاح: قصّ نهاية كل شريحة بحيث لا
    تتجاوز أبداً بداية الشريحة التي تليها (مع هامش أمان صغير gap_ms).
    """
    srt_content = ""
    counter = 1
    n = len(words)
    for i in range(0, n, batch_size):
        batch = words[i:i + batch_size]
        batch_text = " ".join(w.text for w in batch).strip()
        if not batch_text:
            continue

        start_time = batch[0].start
        end_time = max(batch[-1].end, start_time + min_duration_ms)

        next_batch = words[i + batch_size:i + batch_size + 1]
        if next_batch:
            next_start = next_batch[0].start
            if end_time > next_start - gap_ms:
                end_time = max(start_time + 1, next_start - gap_ms)

        if end_time <= start_time:
            end_time = start_time + 1

        srt_content += f"{counter}\n{format_time(start_time)} --> {format_time(end_time)}\n{batch_text}\n\n"
        counter += 1
    return srt_content


def human_size(num_bytes):
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# =============================================================================
# حالة المعالج متعدد الخطوات (Wizard)
# =============================================================================
STEPS = [
    ("01", "الفيديو"),
    ("02", "الترجمة"),
    ("03", "التنسيق"),
    ("04", "النتيجة"),
]

if "step" not in st.session_state:
    st.session_state.step = 1
if "video_ready" not in st.session_state:
    st.session_state.video_ready = False
if "processed" not in st.session_state:
    st.session_state.processed = False


def go_to(step_num):
    st.session_state.step = step_num


def render_scrubber(current):
    nodes_html = ""
    fill_pct = max(0, (current - 1)) / (len(STEPS) - 1) * 100
    for idx, (num, label) in enumerate(STEPS, start=1):
        state = "done" if idx < current else ("active" if idx == current else "")
        marker = '<i class="ti ti-check" style="font-size:13px"></i>' if idx < current else num
        nodes_html += f"""
            <div class="scrubber-node {state}">
                <div class="dot mono">{marker}</div>
                <div class="lbl">{label}</div>
            </div>
        """
    st.markdown(f"""
        <div class="scrubber">
            <div class="scrubber-track"><div class="scrubber-fill" style="width:{fill_pct}%"></div></div>
            <div class="scrubber-nodes">{nodes_html}</div>
        </div>
    """, unsafe_allow_html=True)


# =============================================================================
# رأس الصفحة + شريط الخطوات
# =============================================================================
st.markdown("""
    <div class="page-head">
        <h1>استوديو الترجمة</h1>
        <p>ارفع فيديوك، اضبط شكل الترجمة والتنسيق، واحصل على نسخة جاهزة للنشر خلال دقائق.</p>
    </div>
""", unsafe_allow_html=True)

render_scrubber(st.session_state.step)

# =============================================================================
# الخطوة 1 — رفع الفيديو
# =============================================================================
if st.session_state.step == 1:
    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-video", "رفع الفيديو", "صيغة MP4. يتم تحليل الصوت وتحديد اللغة تلقائياً بعد المتابعة.")
    uploaded_file = st.file_uploader(" ", type=["mp4"], label_visibility="collapsed", key="uploaded_file")

    if uploaded_file is not None:
        with open("temp_input.mp4", "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.video_ready = True

        st.video("temp_input.mp4")
        st.markdown(f"""
            <div class="chip-row">
                <div class="chip">الاسم: <b>{uploaded_file.name}</b></div>
                <div class="chip">الحجم: <b>{human_size(uploaded_file.size)}</b></div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.session_state.video_ready = False

    st.markdown('</div>', unsafe_allow_html=True)

    st.button(
        "التالي: إعدادات الترجمة  ←",
        disabled=not st.session_state.video_ready,
        on_click=go_to, args=(2,),
    )

# =============================================================================
# الخطوة 2 — إعدادات الترجمة النصية
# =============================================================================
elif st.session_state.step == 2:
    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-letter-case", "شكل الترجمة النصية", "التحكم بالخط، اللون، الموضع، والحدّ الخارجي.")

    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("وزن الخط", list(FONT_LIBRARY.keys()), index=2, key="font_style")
        st.color_picker("لون النص", "#FFFFFF", key="text_color")
        st.slider("حجم الخط", 32, 90, 48, key="font_size")
    with c2:
        st.selectbox(
            "موضع الترجمة",
            ["أسفل الشاشة (موصى به)", "منتصف الشاشة", "أعلى الشاشة"],
            index=0,
            help="الموضع الافتراضي محسوب لتجنّب مناطق واجهة إنستغرام وتيك توك.",
            key="caption_position",
        )
        st.toggle("حدّ خارجي للنص (Outline)", value=True, key="use_stroke")
        st.color_picker("لون الحدّ الخارجي", "#000000", disabled=not st.session_state.get("use_stroke", True), key="stroke_color")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.radio(
        "خلفية الترجمة",
        ["بدون خلفية", "صندوق أسود شفاف", "صندوق بلون العلامة"],
        horizontal=True,
        key="bg_style",
    )
    st.slider("عدد الكلمات في الشريحة الواحدة", 1, 6, 3, key="words_per_caption")
    st.markdown('</div>', unsafe_allow_html=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("→ رجوع", on_click=go_to, args=(1,), type="secondary")
    with nav2:
        st.button("التالي: التنسيق والنشر  ←", on_click=go_to, args=(3,))

# =============================================================================
# الخطوة 3 — الإطار والأبعاد ونص الافتتاح
# =============================================================================
elif st.session_state.step == 3:
    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-aspect-ratio", "الإطار والأبعاد", "اختر مقاس النشر المناسب للمنصة المستهدفة.")

    st.selectbox(
        "تنسيق النشر",
        ["الأبعاد الأصلية", "عمودي 9:16 — Reels / Shorts / TikTok", "مربع 1:1 — Instagram Feed"],
        index=1,
        key="aspect_choice",
    )
    c3, c4 = st.columns(2)
    with c3:
        st.color_picker("لون الخلفية أو الإطار", "#0A0A0C", key="frame_color")
    with c4:
        st.slider("سماكة الإطار (بكسل)", 0, 60, 0, key="border_thickness")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-typography", "نص الافتتاح (Hook)", "نص قصير يظهر أعلى الفيديو في أول ثوانٍ لجذب الانتباه.")

    st.toggle("عرض نص افتتاحي أعلى الفيديو", value=False, key="use_hook")
    st.text_input("نص الافتتاح", "لن تصدق ما ستراه الآن", disabled=not st.session_state.get("use_hook", False), key="hook_text")
    c5, c6 = st.columns(2)
    with c5:
        st.slider("مدة العرض (ثوانٍ)", 1, 8, 3, disabled=not st.session_state.get("use_hook", False), key="hook_duration")
    with c6:
        st.color_picker("لون نص الافتتاح", BRAND_ORANGE, disabled=not st.session_state.get("use_hook", False), key="hook_color")
    st.markdown('</div>', unsafe_allow_html=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("→ رجوع", on_click=go_to, args=(2,), type="secondary")
    with nav2:
        st.button("التالي: المعالجة  ←", on_click=go_to, args=(4,))

# =============================================================================
# الخطوة 4 — المعالجة والنتيجة
# =============================================================================
elif st.session_state.step == 4:
    font_style = st.session_state.font_style
    text_color = st.session_state.text_color
    font_size = st.session_state.font_size
    caption_position = st.session_state.caption_position
    use_stroke = st.session_state.use_stroke
    stroke_color = st.session_state.stroke_color
    bg_style = st.session_state.bg_style
    words_per_caption = st.session_state.words_per_caption
    aspect_choice = st.session_state.aspect_choice
    frame_color = st.session_state.frame_color
    border_thickness = st.session_state.border_thickness
    use_hook = st.session_state.use_hook
    hook_text = st.session_state.hook_text
    hook_duration = st.session_state.hook_duration
    hook_color = st.session_state.hook_color

    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-player-play", "جاهز للمعالجة", "راجع الملخص أدناه، ثم ابدأ المعالجة.")
    st.markdown(f"""
        <div class="chip-row">
            <div class="chip">الخط: <b>{font_style}</b></div>
            <div class="chip">الموضع: <b>{caption_position}</b></div>
            <div class="chip">النشر: <b>{aspect_choice}</b></div>
            <div class="chip">الهووك: <b>{"مفعّل" if use_hook else "غير مفعّل"}</b></div>
        </div>
    """, unsafe_allow_html=True)
    process_clicked = st.button("▶ ابدأ المعالجة")
    st.markdown('</div>', unsafe_allow_html=True)

    if process_clicked:
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

            # هامش أمان أفقي: لا يُسمح لأي نص أن يتجاوز 92% من عرض الفيديو،
            # لتفادي قص الكلمات من الجانبين على الفيديوهات الضيقة (كالعمودية).
            max_text_width = int(canvas_w * 0.92)

            def fit_font_size(text, font_path, desired_size, min_size=20, extra_stroke_margin=0):
                """
                يقيس عرض النص فعلياً بنفس الخط، ويصغّر الحجم تدريجياً فقط إذا
                تجاوز عرض الفيديو المتاح، بدل قصّ الحروف من الأطراف.

                extra_stroke_margin: هامش إضافي يعكس اتساع الحدّ الخارجي
                (stroke) الذي يُضاف لاحقاً عند الرسم الفعلي ولا يظهر في
                getbbox العادي؛ بدونه قد يتجاوز العرض النهائي المُصدَّر حدود
                max_text_width فيضطر _clamp_width لتصغير الصورة (blur/تراكب
                بصري للحروف الرفيعة في الخط العربي).
                """
                size = desired_size
                while size > min_size:
                    measured = ImageFont.truetype(font_path, size).getbbox(text)
                    width = (measured[2] - measured[0]) + 2 * extra_stroke_margin
                    if width <= max_text_width:
                        return size
                    size -= 2
                return min_size

            def _clamp_width(clip):
                """
                ضمان صارم ونهائي: حتى لو اختلف قياس الخط المسبق عن الحجم الفعلي
                المُصدَّر (بسبب فروق دقيقة بين إصدارات الخطوط أو المكتبات بين
                الأجهزة)، يعاد ضبط حجم الصورة الناتجة نفسها لتلتزم بعرض الفيديو
                إجبارياً. هذا مستقل تماماً عن أي حساب تقديري سابق.
                """
                if clip.w > max_text_width:
                    return clip.resized(max_text_width / clip.w)
                return clip

            def create_styled_text(txt):
                display_text = prepare_text_for_rendering(txt)
                chosen_font = pick_font_for_text(txt, font_style)
                stroke_margin_estimate = max(2, font_size // 18) if use_stroke else 0
                fitted_size = fit_font_size(
                    display_text, chosen_font, font_size,
                    extra_stroke_margin=stroke_margin_estimate,
                )

                kwargs = dict(
                    text=display_text,
                    font_size=fitted_size,
                    color=text_color,
                    font=chosen_font,
                    method="label",
                )
                if use_stroke:
                    kwargs["stroke_color"] = stroke_color
                    kwargs["stroke_width"] = max(2, fitted_size // 18)
                if bg_style == "صندوق أسود شفاف":
                    kwargs["bg_color"] = (0, 0, 0, 140)
                elif bg_style == "صندوق بلون العلامة":
                    kwargs["bg_color"] = hex_to_rgb(BRAND_ORANGE) + (255,)

                try:
                    clip = vc.TextClip(**kwargs)
                except Exception:
                    kwargs["font"] = FALLBACK_FONT
                    clip = vc.TextClip(**kwargs)
                return _clamp_width(clip)

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
                hook_stroke_margin_estimate = max(2, int(font_size * 1.2) // 15)
                hook_fitted_size = fit_font_size(
                    hook_display, hook_font, int(font_size * 1.2),
                    extra_stroke_margin=hook_stroke_margin_estimate,
                )
                hook_kwargs = dict(
                    text=hook_display,
                    font_size=hook_fitted_size,
                    color=hook_color,
                    font=hook_font,
                    method="label",
                    stroke_color="#000000",
                    stroke_width=max(2, hook_fitted_size // 15),
                    bg_color=(0, 0, 0, 130),
                )
                try:
                    hook_clip = vc.TextClip(**hook_kwargs)
                except Exception:
                    hook_kwargs["font"] = FALLBACK_FONT
                    hook_clip = vc.TextClip(**hook_kwargs)
                hook_clip = _clamp_width(hook_clip)

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
            st.session_state.processed = True

    if st.session_state.processed and os.path.exists("temp_output.mp4"):
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
        section_heading("ti-circle-check", "الفيديو النهائي", "المعالجة اكتملت بنجاح.")
        st.video("temp_output.mp4")

        with open("temp_output.mp4", "rb") as file:
            st.download_button(
                label="⭳ تنزيل الفيديو",
                data=file,
                file_name="edit73_video.mp4",
                mime="video/mp4",
            )
        st.markdown('</div>', unsafe_allow_html=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("→ رجوع للإعدادات", on_click=go_to, args=(3,), type="secondary")
    with nav2:
        st.button("⟲ فيديو جديد", on_click=lambda: (go_to(1), st.session_state.update(processed=False, video_ready=False)))

st.markdown('<div class="app-footer">edit73 — استوديو الترجمة الذكي</div>', unsafe_allow_html=True)
