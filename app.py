import base64
import os
import re

import numpy as np
import streamlit as st
import assemblyai as aai
from PIL import Image, ImageDraw, ImageFont

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
from moviepy.video.VideoClip import ColorClip, ImageClip
import moviepy.video.compositing.CompositeVideoClip as cvc
import moviepy.video.tools.subtitles as sub
import arabic_reshaper
from bidi.algorithm import get_display

# =============================================================================
# الهوية البصرية — أحادية اللون (أسود / أبيض / رمادي) بالكامل، بلا أي لون علامة.
# التباين العالي هو "اللون" الوحيد المستخدم للتمييز بين الحالات.
# =============================================================================
BG_BASE = "#0A0A0B"
BG_SURFACE = "#131315"
BG_SURFACE_2 = "#1C1C1F"
BG_SURFACE_3 = "#242428"
BORDER = "#2A2A2E"
BORDER_STRONG = "#3A3A40"
TEXT_PRIMARY = "#F5F5F7"
TEXT_SECONDARY = "#A1A1A8"
TEXT_MUTED = "#616166"
WHITE = "#FFFFFF"
GLOW = "rgba(255,255,255,0.14)"
DANGER = "#F2554F"
DANGER_SOFT = "rgba(242,85,79,0.12)"

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


def _b64_or_none(path):
    if path and os.path.exists(path):
        return _b64(path)
    return None


LOGO_B64 = _b64_or_none(LOGO_SMALL_PATH)

# =============================================================================
# مفتاح AssemblyAI عبر Secrets فقط
# =============================================================================
try:
    aai.settings.api_key = st.secrets["ASSEMBLYAI_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("لم يتم العثور على مفتاح AssemblyAI. أضفه في Secrets باسم ASSEMBLYAI_API_KEY.")
    st.stop()

# =============================================================================
# الخطوط والألوان الجاهزة (Presets)
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

CAPTION_PRESETS = [
    {
        "name": "أبيض كلاسيكي",
        "font_style": "أسود ثقيل (Black)",
        "text_color": "#FFFFFF",
        "use_stroke": True,
        "stroke_color": "#000000",
        "bg_style": "بدون خلفية",
        "caption_mode": "ثابتة (كتلة نصية)",
    },
    {
        "name": "🆕 كاريوكي CapCut",
        "font_style": "أسود ثقيل (Black)",
        "text_color": "#FFFFFF",
        "use_stroke": True,
        "stroke_color": "#000000",
        "bg_style": "بدون خلفية",
        "caption_mode": "كاريوكي (تمييز الكلمة المنطوقة)",
        "highlight_bg_color": "#FFFFFF",
        "highlight_text_color": "#000000",
    },
    {
        "name": "صندوق داكن",
        "font_style": "عريض جداً (Extra Bold)",
        "text_color": "#FFFFFF",
        "use_stroke": False,
        "stroke_color": "#000000",
        "bg_style": "صندوق أسود شفاف",
        "caption_mode": "ثابتة (كتلة نصية)",
    },
    {
        "name": "أصفر بارز",
        "font_style": "عريض (Bold)",
        "text_color": "#FFE14D",
        "use_stroke": True,
        "stroke_color": "#000000",
        "bg_style": "بدون خلفية",
        "caption_mode": "ثابتة (كتلة نصية)",
    },
]

# =============================================================================
# مناطق الأمان (Safe Zones) — نسب مبنية على تحليل واجهات إنستغرام Reels وTikTok
# وYouTube Shorts الفعلية لعام 2026: الجزء السفلي محجوب بالتعليق وأزرار
# التفاعل، والجانب الأيمن محجوب بأزرار الإعجاب/المشاركة، وأعلى الشاشة محجوب
# بشريط الحساب. القيم أدناه نسب مئوية من أبعاد الكانفاس النهائي.
# =============================================================================
SAFE_ZONES = {
    "عمودي 9:16 — Reels / Shorts / TikTok": {
        "top": 8, "bottom": 22, "right": 10, "left": 3,
        "label": "Reels · TikTok · Shorts",
    },
    "مربع 1:1 — Instagram Feed": {
        "top": 5, "bottom": 6, "right": 0, "left": 0,
        "label": "Instagram Feed",
    },
    "الأبعاد الأصلية": {
        "top": 3, "bottom": 8, "right": 0, "left": 0,
        "label": "بدون قيود منصة محددة",
    },
}

ASPECT_OPTIONS = [
    "الأبعاد الأصلية",
    "عمودي 9:16 — Reels / Shorts / TikTok",
    "مربع 1:1 — Instagram Feed",
]
ASPECT_RATIO_MAP = {
    "عمودي 9:16 — Reels / Shorts / TikTok": 9 / 16,
    "مربع 1:1 — Instagram Feed": 1 / 1,
}
ASPECT_FILE_SUFFIX = {
    "الأبعاد الأصلية": "original",
    "عمودي 9:16 — Reels / Shorts / TikTok": "reels_9x16",
    "مربع 1:1 — Instagram Feed": "feed_1x1",
}

# =============================================================================
# التصميم — أحادي اللون بالكامل
# =============================================================================
FONT_FACE_CSS = ""
_preview_font_b64 = None
_preview_font_path = os.path.join(FONTS_DIR, "Tajawal-Black.ttf")
if os.path.exists(_preview_font_path):
    _preview_font_b64 = _b64(_preview_font_path)
    FONT_FACE_CSS = f"""
    @font-face {{
        font-family: 'PreviewCaptionFont';
        src: url(data:font/ttf;base64,{_preview_font_b64}) format('truetype');
    }}
    """

st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tabler-icons/3.44.0/tabler-icons.min.css">

<style>
{FONT_FACE_CSS}
html, body, [class*="css"] {{ font-family: 'Tajawal', 'Inter', sans-serif; }}
.mono {{ font-family: 'JetBrains Mono', monospace !important; }}

.stApp {{ background: {BG_BASE}; color: {TEXT_PRIMARY}; }}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 0 !important; padding-bottom: 3rem; max-width: 720px; }}

/* ---------- الشريط العلوي ---------- */
.top-bar {{
    display: flex; align-items: center; justify-content: center; gap: 10px;
    background: {BG_SURFACE}; border-bottom: 1px solid {BORDER};
    margin: 0 -1rem 26px -1rem; padding: 16px 1rem;
}}
.top-bar img {{ width: 28px; height: 28px; border-radius: 7px; }}
.top-bar .wordmark {{ font-size: 1.02rem; font-weight: 800; color: {TEXT_PRIMARY}; letter-spacing: .2px; }}
.top-bar .tag {{
    font-family: 'JetBrains Mono', monospace; font-size: .66rem; color: {TEXT_MUTED};
    border: 1px solid {BORDER}; padding: 2px 8px; border-radius: 999px; margin-inline-start: 6px;
}}

.page-head {{ padding: 4px 2px 20px 2px; }}
.page-head h1 {{ font-size: 1.55rem; font-weight: 800; color: {TEXT_PRIMARY}; margin: 0 0 6px 0; letter-spacing: -.2px; }}
.page-head p {{ color: {TEXT_SECONDARY}; font-size: .87rem; margin: 0; line-height: 1.7; }}

/* ---------- شريط الخطوات (موجة صوتية) ---------- */
.waveband {{ margin: 4px 2px 28px 2px; }}
.waveband-bars {{ display: flex; align-items: flex-end; gap: 3px; height: 30px; direction: ltr; margin-bottom: 12px; }}
.waveband-bars .bar {{ flex: 1; background: {BORDER}; border-radius: 2px; transition: background .3s ease, opacity .3s ease; }}
.waveband-bars .bar.on {{ background: {WHITE}; }}
.waveband-nodes {{ display: flex; justify-content: space-between; direction: ltr; }}
.waveband-node {{ display: flex; flex-direction: column; align-items: center; gap: 4px; width: 20%; }}
.waveband-node .num {{ font-family: 'JetBrains Mono', monospace; font-size: .66rem; color: {TEXT_MUTED}; font-weight: 600; }}
.waveband-node.active .num {{ color: {TEXT_PRIMARY}; }}
.waveband-node.done .num {{ color: {TEXT_SECONDARY}; }}
.waveband-node .lbl {{ font-size: .72rem; color: {TEXT_MUTED}; font-weight: 600; }}
.waveband-node.active .lbl {{ color: {TEXT_PRIMARY}; }}
.waveband-node.done .lbl {{ color: {TEXT_SECONDARY}; }}

/* ---------- بطاقة عامة ---------- */
.card-wrap {{
    background: {BG_SURFACE}; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 24px 22px 12px 22px; box-shadow: 0 1px 3px rgba(0,0,0,0.35); margin-bottom: 22px;
}}
.section-heading {{ display: flex; align-items: center; gap: 9px; margin: 0 0 4px 0; }}
.section-heading i {{ font-size: 17px; color: {TEXT_PRIMARY}; }}
.section-heading h3 {{ font-size: 1rem; font-weight: 700; color: {TEXT_PRIMARY}; margin: 0; }}
.section-desc {{ color: {TEXT_SECONDARY}; font-size: .82rem; margin: 3px 0 18px 0; }}

/* ---------- شارات معلومات ---------- */
.chip-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 4px 0; }}
.chip {{
    font-family: 'JetBrains Mono', monospace; font-size: .72rem; color: {TEXT_SECONDARY};
    background: {BG_SURFACE_2}; border: 1px solid {BORDER}; padding: 5px 10px; border-radius: 8px;
}}
.chip b {{ color: {TEXT_PRIMARY}; font-weight: 600; }}
.chip.warn {{ border-color: {DANGER}; color: {DANGER}; background: {DANGER_SOFT}; }}

/* ---------- شبكة أنماط جاهزة (presets) ---------- */
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {{
    background: {BG_SURFACE_2} !important; border: 1px solid {BORDER} !important;
    color: {TEXT_PRIMARY} !important; font-weight: 600 !important; font-size: .82rem !important;
    padding: 10px 6px !important; box-shadow: none !important;
}}
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button:hover {{
    border-color: {BORDER_STRONG} !important; background: {BG_SURFACE_3} !important;
}}
div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button p {{ color: {TEXT_PRIMARY} !important; }}

/* ---------- رفع الفيديو ---------- */
section[data-testid="stFileUploaderDropzone"] {{
    background-color: {BG_SURFACE_2} !important; border: 1.5px dashed {BORDER} !important; border-radius: 14px !important;
}}
section[data-testid="stFileUploaderDropzone"]:hover {{ border-color: {BORDER_STRONG} !important; }}
section[data-testid="stFileUploaderDropzone"] * {{ color: {TEXT_SECONDARY} !important; }}

/* ---------- عناصر الإدخال ---------- */
div[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{
    background-color: {BG_SURFACE_2} !important; color: {TEXT_PRIMARY} !important;
    border-radius: 9px !important; border-color: {BORDER} !important;
}}
div[data-baseweb="popover"] li {{ background-color: {BG_SURFACE_2} !important; color: {TEXT_PRIMARY} !important; }}
.stSlider [data-baseweb="slider"] > div > div {{ background: {WHITE} !important; }}
.stSlider [role="slider"] {{ background: {WHITE} !important; border: 2px solid {BG_BASE} !important; }}
label p, .stMarkdown p {{ color: {TEXT_PRIMARY} !important; }}
label p {{ font-size: 0.85rem !important; font-weight: 600 !important; }}
[data-testid="stWidgetLabel"] {{ color: {TEXT_PRIMARY} !important; }}
[data-testid="stMarkdownContainer"] p {{ color: {TEXT_SECONDARY}; }}
.stCaption, [data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED} !important; }}
[data-baseweb="tag"] {{ background: {BG_SURFACE_3} !important; }}
.stToggle label div[data-baseweb="checkbox"] > div {{ background: {BORDER} !important; }}
div[data-testid="stCheckbox"] label span {{ border-color: {BORDER_STRONG} !important; }}

/* ---------- الأزرار ---------- */
.stButton>button {{
    background: {WHITE}; color: {BG_BASE}; font-weight: 700; font-size: .95rem;
    border-radius: 11px; width: 100%; padding: 12px; border: none;
    box-shadow: 0 4px 14px rgba(0,0,0,0.3); transition: all 0.15s ease;
}}
.stButton>button:hover {{ background: #E4E4E7; transform: translateY(-1px); }}
.stButton>button:active {{ transform: translateY(0); }}
.stButton>button p {{ color: {BG_BASE} !important; font-weight: 700 !important; }}

button[kind="secondary"] {{ background: {BG_SURFACE_2} !important; border: 1px solid {BORDER} !important; box-shadow: none !important; }}
button[kind="secondary"] p {{ color: {TEXT_PRIMARY} !important; }}

.stDownloadButton>button {{
    background: {WHITE}; color: {BG_BASE}; border: none; font-weight: 700;
    border-radius: 11px; width: 100%; padding: 12px;
}}
.stDownloadButton>button p {{ color: {BG_BASE} !important; font-weight: 700 !important; }}
.stDownloadButton>button:hover {{ filter: brightness(0.92); }}

/* ---------- تنبيهات أحادية اللون ---------- */
div[data-testid="stAlert"] {{
    border-radius: 11px !important; background: {BG_SURFACE_2} !important;
    border: 1px solid {BORDER} !important;
}}
div[data-testid="stAlert"] p {{ color: {TEXT_PRIMARY} !important; }}

/* ---------- إطار المعاينة الحية ---------- */
.preview-shell {{
    background: {BG_SURFACE_2}; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 16px; display: flex; justify-content: center; margin-bottom: 6px;
}}
.preview-canvas {{
    position: relative; background-size: cover; background-position: center;
    border-radius: 10px; overflow: hidden; box-shadow: 0 8px 30px rgba(0,0,0,0.45);
}}
.safe-zone-band {{
    position: absolute; left: 0; right: 0; background: repeating-linear-gradient(
        45deg, rgba(242,85,79,0.16), rgba(242,85,79,0.16) 6px, rgba(242,85,79,0.28) 6px, rgba(242,85,79,0.28) 12px
    );
    border: 1px dashed rgba(242,85,79,0.65);
    pointer-events: none;
}}
.safe-zone-side {{
    position: absolute; top: 0; bottom: 0; background: repeating-linear-gradient(
        45deg, rgba(242,85,79,0.16), rgba(242,85,79,0.16) 6px, rgba(242,85,79,0.28) 6px, rgba(242,85,79,0.28) 12px
    );
    border: 1px dashed rgba(242,85,79,0.65);
    pointer-events: none;
}}
.preview-caption {{
    position: absolute; left: 50%; transform: translate(-50%, 0);
    text-align: center; white-space: nowrap; font-family: 'PreviewCaptionFont','Tajawal',sans-serif;
    font-weight: 900; direction: rtl;
}}
.preview-caption .word {{ display: inline-block; }}
.preview-caption .word.active {{ border-radius: 8px; padding: 2px 10px; }}
.preview-hook {{
    position: absolute; left: 50%; transform: translate(-50%, 0);
    text-align: center; white-space: nowrap; font-family: 'PreviewCaptionFont','Tajawal',sans-serif;
    font-weight: 900; direction: rtl; padding: 4px 14px; border-radius: 8px;
}}
.legend-row {{ display: flex; gap: 14px; justify-content: center; margin: 14px 0 4px 0; flex-wrap: wrap; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: .74rem; color: {TEXT_SECONDARY}; }}
.legend-swatch {{ width: 12px; height: 12px; border-radius: 3px; }}

/* ---------- الفوتر ---------- */
.app-footer {{
    text-align: center; color: {TEXT_MUTED}; font-size: 0.78rem; padding-top: 26px;
    margin-top: 16px; border-top: 1px solid {BORDER};
}}
</style>
""", unsafe_allow_html=True)

if LOGO_B64:
    st.markdown(f"""
        <div class="top-bar">
            <img src="data:image/png;base64,{LOGO_B64}" alt="edit73" />
            <div class="wordmark">edit73</div>
            <div class="tag mono">STUDIO</div>
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


def human_size(num_bytes):
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def human_duration(seconds):
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_time(ms):
    hrs = ms // 3600000
    mins = (ms % 3600000) // 60000
    secs = (ms % 60000) // 1000
    msecs = ms % 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"


# =============================================================================
# تجميع الكلمات إلى دفعات (شرائح ترجمة) — المصدر الوحيد للحقيقة لكل من
# ملف SRT ومقاطع الكاريوكي، حتى لا يتكرر المنطق في مكانين.
#
# -- إصلاح جوهري تم اكتشافه عند تشخيص مشكلة "النص المتراكب" --
# كان يُفرض حدّ أدنى لمدة عرض كل شريحة (300ms) دون التحقّق من موعد بداية
# الشريحة التالية. في الكلام السريع، كانت مدة العرض الممتدة تتجاوز بداية
# الشريحة التالية، فتظهر شريحتان مختلفتان من الترجمة في نفس اللحظة وفوق
# بعضهما في نفس الموضع. الإصلاح: قصّ نهاية كل شريحة بحيث لا تتجاوز أبداً
# بداية الشريحة التي تليها (مع هامش أمان صغير gap_ms).
# =============================================================================
def build_word_groups(words, batch_size=3, min_duration_ms=300, gap_ms=40):
    groups = []
    n = len(words)
    for i in range(0, n, batch_size):
        batch = [w for w in words[i:i + batch_size]]
        text = " ".join(w.text for w in batch).strip()
        if not text:
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

        groups.append({"words": batch, "start": start_time, "end": end_time, "text": text})
    return groups


def create_srt_from_groups(groups):
    srt_content = ""
    for idx, g in enumerate(groups, start=1):
        srt_content += f"{idx}\n{format_time(g['start'])} --> {format_time(g['end'])}\n{g['text']}\n\n"
    return srt_content


# =============================================================================
# حالة المعالج متعدد الخطوات (Wizard)
# =============================================================================
STEPS = [
    ("01", "الفيديو"),
    ("02", "النمط"),
    ("03", "التنسيق"),
    ("04", "المعاينة"),
    ("05", "النتيجة"),
]

_DEFAULTS = {
    "step": 1,
    "video_ready": False,
    "processed": False,
    "output_files": [],
    "font_style": "أسود ثقيل (Black)",
    "text_color": "#FFFFFF",
    "font_size": 48,
    "caption_position": "تلقائي (حسب المنصة) — موصى به",
    "use_stroke": True,
    "stroke_color": "#000000",
    "bg_style": "بدون خلفية",
    "caption_mode": "ثابتة (كتلة نصية)",
    "highlight_bg_color": "#FFFFFF",
    "highlight_text_color": "#000000",
    "words_per_caption": 3,
    "aspect_choice": "عمودي 9:16 — Reels / Shorts / TikTok",
    "frame_color": "#0A0A0C",
    "border_thickness": 0,
    "use_hook": False,
    "hook_text": "لن تصدق ما ستراه الآن",
    "hook_duration": 3,
    "hook_color": "#FFFFFF",
    "multi_export": False,
    "show_safe_zones": True,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def go_to(step_num):
    st.session_state.step = step_num


def apply_preset(preset):
    for k, v in preset.items():
        if k == "name":
            continue
        st.session_state[k] = v


def render_waveband(current):
    total = len(STEPS)
    bars_html = ""
    n_bars = 28
    filled_bars = int(n_bars * (current - 1) / (total - 1)) if total > 1 else n_bars
    for i in range(n_bars):
        height = 6 + int(24 * abs(np.sin(i * 0.7)) ** 0.6)
        on = "on" if i <= filled_bars else ""
        bars_html += f'<div class="bar {on}" style="height:{height}px"></div>'

    nodes_html = ""
    for idx, (num, label) in enumerate(STEPS, start=1):
        state = "done" if idx < current else ("active" if idx == current else "")
        nodes_html += f"""
            <div class="waveband-node {state}">
                <div class="num mono">{num}</div>
                <div class="lbl">{label}</div>
            </div>
        """
    st.markdown(f"""
        <div class="waveband">
            <div class="waveband-bars">{bars_html}</div>
            <div class="waveband-nodes">{nodes_html}</div>
        </div>
    """, unsafe_allow_html=True)


st.markdown("""
    <div class="page-head">
        <h1>استوديو الترجمة</h1>
        <p>ارفع فيديوك، اختر نمط الترجمة، وعاين شكلها فوق الفيديو فعلياً قبل التصدير النهائي.</p>
    </div>
""", unsafe_allow_html=True)

render_waveband(st.session_state.step)

# =============================================================================
# الخطوة 1 — رفع الفيديو
# =============================================================================
if st.session_state.step == 1:
    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-video", "رفع الفيديو", "صيغة MP4. تُستخرج معاينة فورية بعد الرفع مباشرة.")
    uploaded_file = st.file_uploader(" ", type=["mp4"], label_visibility="collapsed", key="uploaded_file")

    if uploaded_file is not None:
        with open("temp_input.mp4", "wb") as f:
            f.write(uploaded_file.getbuffer())

        if not st.session_state.video_ready or st.session_state.get("_last_upload_name") != uploaded_file.name:
            with st.spinner("جارٍ قراءة بيانات الفيديو..."):
                try:
                    with vfc.VideoFileClip("temp_input.mp4") as _v:
                        st.session_state.video_duration = _v.duration
                        st.session_state.video_w = _v.w
                        st.session_state.video_h = _v.h
                        st.session_state.video_fps = _v.fps
                        mid_t = min(1.0, _v.duration / 2) if _v.duration else 0
                        frame = _v.get_frame(mid_t)
                    frame_img = Image.fromarray(frame)
                    buf_path = "temp_preview_frame.png"
                    frame_img.save(buf_path)
                    st.session_state.preview_frame_b64 = _b64(buf_path)
                except Exception as e:
                    st.session_state.preview_frame_b64 = None
                    st.warning(f"تعذّر توليد معاينة سريعة للفيديو ({e}). ستظل المعالجة النهائية تعمل بشكل طبيعي.")
            st.session_state._last_upload_name = uploaded_file.name

        st.session_state.video_ready = True
        st.video("temp_input.mp4")

        dur_label = human_duration(st.session_state.get("video_duration", 0))
        res_label = f"{st.session_state.get('video_w','?')}×{st.session_state.get('video_h','?')}"
        st.markdown(f"""
            <div class="chip-row">
                <div class="chip">الاسم: <b>{uploaded_file.name}</b></div>
                <div class="chip">الحجم: <b>{human_size(uploaded_file.size)}</b></div>
                <div class="chip">المدة: <b>{dur_label}</b></div>
                <div class="chip">الدقة: <b>{res_label}</b></div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.session_state.video_ready = False

    st.markdown('</div>', unsafe_allow_html=True)

    st.button(
        "التالي: نمط الترجمة  ←",
        disabled=not st.session_state.video_ready,
        on_click=go_to, args=(2,),
    )

# =============================================================================
# الخطوة 2 — نمط الترجمة (بما فيها الأنماط الجاهزة ووضع الكاريوكي الجديد)
# =============================================================================
elif st.session_state.step == 2:
    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-sparkles", "أنماط جاهزة", "ابدأ من نمط جاهز ثم عدّله كما تشاء.")
    preset_cols = st.columns(len(CAPTION_PRESETS))
    for col, preset in zip(preset_cols, CAPTION_PRESETS):
        with col:
            st.button(preset["name"], key=f"preset_{preset['name']}", on_click=apply_preset, args=(preset,))
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-letter-case", "شكل الترجمة النصية", "التحكم بالخط، اللون، الموضع، ووضع العرض.")

    st.radio(
        "وضع عرض الترجمة",
        ["ثابتة (كتلة نصية)", "كاريوكي (تمييز الكلمة المنطوقة)"],
        horizontal=True,
        key="caption_mode",
        help="الكاريوكي يميّز كل كلمة لحظة نطقها — نفس أسلوب CapCut وTikTok الشائع حالياً.",
    )

    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("وزن الخط", list(FONT_LIBRARY.keys()), key="font_style")
        st.color_picker("لون النص الأساسي", key="text_color")
        st.slider("حجم الخط", 32, 90, key="font_size")
    with c2:
        st.selectbox(
            "موضع الترجمة",
            ["تلقائي (حسب المنصة) — موصى به", "أسفل الشاشة", "منتصف الشاشة", "أعلى الشاشة"],
            key="caption_position",
            help="الوضع التلقائي يحسب أفضل ارتفاع بعيداً عن أزرار ومناطق واجهة المنصة المختارة في الخطوة التالية.",
        )
        st.toggle("حدّ خارجي للنص (Outline)", key="use_stroke")
        st.color_picker("لون الحدّ الخارجي", disabled=not st.session_state.use_stroke, key="stroke_color")

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    if st.session_state.caption_mode.startswith("كاريوكي"):
        c3, c4 = st.columns(2)
        with c3:
            st.color_picker("خلفية الكلمة النشطة", key="highlight_bg_color")
        with c4:
            st.color_picker("لون نص الكلمة النشطة", key="highlight_text_color")
        st.caption("الكلمة قيد النطق تظهر داخل صندوق مميز، بينما تبقى بقية الكلمات بلونها الأساسي.")
    else:
        st.radio(
            "خلفية الترجمة",
            ["بدون خلفية", "صندوق أسود شفاف", "صندوق بلون العلامة"],
            horizontal=True,
            key="bg_style",
        )

    st.slider("عدد الكلمات في الشريحة الواحدة", 1, 6, key="words_per_caption")
    st.markdown('</div>', unsafe_allow_html=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("→ رجوع", on_click=go_to, args=(1,), type="secondary")
    with nav2:
        st.button("التالي: التنسيق والنشر  ←", on_click=go_to, args=(3,))

# =============================================================================
# الخطوة 3 — الإطار والأبعاد ونص الافتتاح والتصدير المتعدد
# =============================================================================
elif st.session_state.step == 3:
    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-aspect-ratio", "الإطار والأبعاد", "اختر مقاس النشر المناسب للمنصة المستهدفة.")

    st.selectbox("تنسيق النشر", ASPECT_OPTIONS, key="aspect_choice")
    c3, c4 = st.columns(2)
    with c3:
        st.color_picker("لون الخلفية أو الإطار", key="frame_color")
    with c4:
        st.slider("سماكة الإطار (بكسل)", 0, 60, key="border_thickness")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.toggle(
        "🆕 تصدير لجميع المقاسات الثلاثة دفعة واحدة",
        key="multi_export",
        help="ينتج ثلاثة ملفات فيديو: الأبعاد الأصلية، عمودي 9:16، ومربع 1:1 — مفيد للنشر متعدد المنصات دون تكرار العملية.",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-typography", "نص الافتتاح (Hook)", "نص قصير يظهر أعلى الفيديو في أول ثوانٍ لجذب الانتباه.")

    st.toggle("عرض نص افتتاحي أعلى الفيديو", key="use_hook")
    st.text_input("نص الافتتاح", disabled=not st.session_state.use_hook, key="hook_text")
    c5, c6 = st.columns(2)
    with c5:
        st.slider("مدة العرض (ثوانٍ)", 1, 8, disabled=not st.session_state.use_hook, key="hook_duration")
    with c6:
        st.color_picker("لون نص الافتتاح", disabled=not st.session_state.use_hook, key="hook_color")
    st.markdown('</div>', unsafe_allow_html=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("→ رجوع", on_click=go_to, args=(2,), type="secondary")
    with nav2:
        st.button("التالي: المعاينة الحية  ←", on_click=go_to, args=(4,))

# =============================================================================
# الخطوة 4 — معاينة حية فوق إطار حقيقي من الفيديو + مناطق الأمان
# =============================================================================
elif st.session_state.step == 4:
    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-eye", "معاينة حية", "شكل تقريبي للترجمة فوق إطار فعلي من فيديوك، مع حدود مناطق واجهة المنصة.")

    st.toggle("إظهار مناطق الأمان (مناطق تحجبها واجهة المنصة)", key="show_safe_zones")

    aspect = st.session_state.aspect_choice
    zone = SAFE_ZONES[aspect]
    ratio = ASPECT_RATIO_MAP.get(aspect)
    video_w = st.session_state.get("video_w", 1080) or 1080
    video_h = st.session_state.get("video_h", 1920) or 1920
    if ratio is None:
        ratio = video_w / video_h if video_h else 9 / 16

    preview_h = 480
    preview_w = int(preview_h * ratio)
    preview_w = max(220, min(preview_w, 420))
    preview_h = int(preview_w / ratio)

    frame_b64 = st.session_state.get("preview_frame_b64")
    bg_style_css = f"background-image:url(data:image/png;base64,{frame_b64});" if frame_b64 else ""
    frame_color = st.session_state.frame_color

    zones_html = ""
    if st.session_state.show_safe_zones:
        if zone["top"] > 0:
            zones_html += f'<div class="safe-zone-band" style="top:0; height:{zone["top"]}%;"></div>'
        if zone["bottom"] > 0:
            zones_html += f'<div class="safe-zone-band" style="bottom:0; height:{zone["bottom"]}%;"></div>'
        if zone["right"] > 0:
            zones_html += f'<div class="safe-zone-side" style="right:0; width:{zone["right"]}%;"></div>'
        if zone["left"] > 0:
            zones_html += f'<div class="safe-zone-side" style="left:0; width:{zone["left"]}%;"></div>'

    # موضع الترجمة التقريبي (نفس منطق المعالجة الفعلية)
    pos_choice = st.session_state.caption_position
    if pos_choice.startswith("تلقائي"):
        caption_y_pct = 100 - (zone["bottom"] + 6)
    elif pos_choice == "أسفل الشاشة":
        caption_y_pct = 72
    elif pos_choice == "منتصف الشاشة":
        caption_y_pct = 46
    else:
        caption_y_pct = 16
    caption_y_pct = max(10, min(caption_y_pct, 92))

    sample_words = ["هذا", "مثال", "للترجمة"]
    text_color = st.session_state.text_color
    stroke_color = st.session_state.stroke_color if st.session_state.use_stroke else "transparent"
    stroke_css = f"-1px -1px 0 {stroke_color}, 1px -1px 0 {stroke_color}, -1px 1px 0 {stroke_color}, 1px 1px 0 {stroke_color}, 0 0 6px rgba(0,0,0,.5)" if st.session_state.use_stroke else "0 0 6px rgba(0,0,0,.6)"

    if st.session_state.caption_mode.startswith("كاريوكي"):
        active_i = 1
        words_html = ""
        for i, w in enumerate(sample_words):
            if i == active_i:
                words_html += (
                    f'<span class="word active" style="background:{st.session_state.highlight_bg_color};'
                    f'color:{st.session_state.highlight_text_color};">{w}</span> '
                )
            else:
                words_html += f'<span class="word" style="color:{text_color}; text-shadow:{stroke_css};">{w}</span> '
        caption_inner = words_html
    else:
        bg_css = ""
        if st.session_state.bg_style == "صندوق أسود شفاف":
            bg_css = "background:rgba(0,0,0,0.55); padding:4px 14px; border-radius:8px;"
        elif st.session_state.bg_style == "صندوق بلون العلامة":
            bg_css = "background:rgba(255,255,255,0.9); color:#000; padding:4px 14px; border-radius:8px;"
        caption_inner = f'<span style="color:{text_color}; text-shadow:{stroke_css}; {bg_css}">{" ".join(sample_words)}</span>'

    font_size_preview = max(14, int(st.session_state.font_size * (preview_w / (video_w or preview_w)) * 1.4))

    hook_html = ""
    if st.session_state.use_hook and st.session_state.hook_text.strip():
        hook_html = f"""
        <div class="preview-hook" style="top:14%; font-size:{max(12, font_size_preview*0.8)}px;
            color:{st.session_state.hook_color}; background:rgba(0,0,0,0.5);">
            {st.session_state.hook_text}
        </div>
        """

    st.markdown(f"""
        <div class="preview-shell">
            <div class="preview-canvas" style="width:{preview_w}px; height:{preview_h}px; background-color:{frame_color}; {bg_style_css}">
                {zones_html}
                <div class="preview-caption" style="top:{caption_y_pct}%; font-size:{font_size_preview}px; max-width:92%;">
                    {caption_inner}
                </div>
                {hook_html}
            </div>
        </div>
    """, unsafe_allow_html=True)

    legend = '<div class="legend-row">'
    if st.session_state.show_safe_zones:
        legend += f'<div class="legend-item"><span class="legend-swatch" style="background:rgba(242,85,79,0.5)"></span> منطقة محجوبة بواجهة {zone["label"]}</div>'
    legend += '</div>'
    st.markdown(legend, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.info("هذه معاينة تقريبية للموضع والألوان. الشكل النهائي الدقيق يظهر بعد المعالجة في الخطوة التالية.")

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("→ رجوع", on_click=go_to, args=(3,), type="secondary")
    with nav2:
        st.button("التالي: المعالجة  ←", on_click=go_to, args=(5,))

# =============================================================================
# الخطوة 5 — المعالجة والنتيجة
# =============================================================================
elif st.session_state.step == 5:
    font_style = st.session_state.font_style
    text_color = st.session_state.text_color
    font_size = st.session_state.font_size
    caption_position = st.session_state.caption_position
    use_stroke = st.session_state.use_stroke
    stroke_color = st.session_state.stroke_color
    bg_style = st.session_state.bg_style
    caption_mode = st.session_state.caption_mode
    highlight_bg_color = st.session_state.highlight_bg_color
    highlight_text_color = st.session_state.highlight_text_color
    words_per_caption = st.session_state.words_per_caption
    aspect_choice = st.session_state.aspect_choice
    frame_color = st.session_state.frame_color
    border_thickness = st.session_state.border_thickness
    use_hook = st.session_state.use_hook
    hook_text = st.session_state.hook_text
    hook_duration = st.session_state.hook_duration
    hook_color = st.session_state.hook_color
    multi_export = st.session_state.multi_export

    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
    section_heading("ti-player-play", "جاهز للمعالجة", "راجع الملخص أدناه، ثم ابدأ المعالجة.")
    st.markdown(f"""
        <div class="chip-row">
            <div class="chip">الخط: <b>{font_style}</b></div>
            <div class="chip">الوضع: <b>{caption_mode}</b></div>
            <div class="chip">النشر: <b>{"كل المقاسات" if multi_export else aspect_choice}</b></div>
            <div class="chip">الهووك: <b>{"مفعّل" if use_hook else "غير مفعّل"}</b></div>
        </div>
    """, unsafe_allow_html=True)
    process_clicked = st.button("▶ ابدأ المعالجة")
    st.markdown('</div>', unsafe_allow_html=True)

    def compute_auto_caption_y(canvas_h, aspect_label):
        z = SAFE_ZONES.get(aspect_label, SAFE_ZONES["الأبعاد الأصلية"])
        return int(canvas_h * (1 - (z["bottom"] + 6) / 100))

    def fit_font_size(text, font_path, desired_size, max_text_width, min_size=20, extra_stroke_margin=0):
        size = desired_size
        while size > min_size:
            measured = ImageFont.truetype(font_path, size).getbbox(text)
            width = (measured[2] - measured[0]) + 2 * extra_stroke_margin
            if width <= max_text_width:
                return size
            size -= 2
        return min_size

    def image_rgba_to_clip(pil_img):
        arr = np.array(pil_img.convert("RGBA"))
        rgb = arr[:, :, :3]
        alpha = (arr[:, :, 3] / 255.0).astype(np.float64)
        base = ImageClip(rgb)
        mask = ImageClip(alpha, is_mask=True)
        return base.with_mask(mask)

    def draw_karaoke_image(visual_words, active_visual_index, font, base_color, stroke_col,
                            stroke_w, hl_bg, hl_text, gap=16, pad_x=18, pad_y=14):
        metrics = []
        for w in visual_words:
            bbox = font.getbbox(w, stroke_width=stroke_w)
            metrics.append((bbox[2] - bbox[0], bbox[1], bbox[3]))
        content_w = sum(m[0] for m in metrics) + gap * max(0, len(visual_words) - 1)
        top_min = min(m[1] for m in metrics)
        bot_max = max(m[2] for m in metrics)
        content_h = bot_max - top_min
        total_w = content_w + 2 * pad_x
        total_h = content_h + 2 * pad_y
        img = Image.new("RGBA", (max(1, total_w), max(1, total_h)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        x = pad_x
        for idx, (w, (w_width, top, bot)) in enumerate(zip(visual_words, metrics)):
            y = pad_y - top_min
            if idx == active_visual_index:
                draw.rounded_rectangle(
                    [x - 8, pad_y - 4, x + w_width + 8, total_h - pad_y + 4],
                    radius=10, fill=hex_to_rgb(hl_bg) + (255,),
                )
                draw.text((x, y), w, font=font, fill=hex_to_rgb(hl_text) + (255,))
            else:
                draw.text((x, y), w, font=font, fill=hex_to_rgb(base_color) + (255,),
                          stroke_width=stroke_w, stroke_fill=hex_to_rgb(stroke_col) + (255,))
            x += w_width + gap
        return img

    def build_video(aspect_label, output_path, words, has_speech, groups):
        video = vfc.VideoFileClip("temp_input.mp4")

        frame_rgb = hex_to_rgb(frame_color)
        bw = video.w + 2 * border_thickness
        bh = video.h + 2 * border_thickness
        border_bg = ColorClip(size=(bw, bh), color=frame_rgb, duration=video.duration)
        video_positioned = video.with_position((border_thickness, border_thickness))
        bordered_video = cvc.CompositeVideoClip([border_bg, video_positioned], size=(bw, bh))

        if aspect_label in ASPECT_RATIO_MAP:
            target_ratio = ASPECT_RATIO_MAP[aspect_label]
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

        max_text_width = int(canvas_w * 0.92)

        if caption_position.startswith("تلقائي"):
            caption_y = compute_auto_caption_y(canvas_h, aspect_label)
        elif caption_position == "أسفل الشاشة":
            caption_y = int(canvas_h * 0.72)
        elif caption_position == "منتصف الشاشة":
            caption_y = int(canvas_h * 0.46)
        else:
            caption_y = int(canvas_h * 0.16)

        def _clamp_width(clip):
            if clip.w > max_text_width:
                return clip.resized(max_text_width / clip.w)
            return clip

        def create_styled_text(txt):
            display_text = prepare_text_for_rendering(txt)
            chosen_font = pick_font_for_text(txt, font_style)
            stroke_margin_estimate = max(2, font_size // 18) if use_stroke else 0
            fitted_size = fit_font_size(display_text, chosen_font, font_size, max_text_width,
                                        extra_stroke_margin=stroke_margin_estimate)
            kwargs = dict(text=display_text, font_size=fitted_size, color=text_color,
                          font=chosen_font, method="label")
            if use_stroke:
                kwargs["stroke_color"] = stroke_color
                kwargs["stroke_width"] = max(2, fitted_size // 18)
            if bg_style == "صندوق أسود شفاف":
                kwargs["bg_color"] = (0, 0, 0, 140)
            elif bg_style == "صندوق بلون العلامة":
                kwargs["bg_color"] = (255, 255, 255, 255)
            try:
                clip = vc.TextClip(**kwargs)
            except Exception:
                kwargs["font"] = FALLBACK_FONT
                clip = vc.TextClip(**kwargs)
            return _clamp_width(clip)

        layers = [final_frame]

        if has_speech:
            if caption_mode.startswith("كاريوكي"):
                for group in groups:
                    logical_words = [w.text for w in group["words"]]
                    full_text = group["text"]
                    if not full_text:
                        continue
                    rtl = is_mostly_arabic(full_text)
                    display_words = [prepare_text_for_rendering(w) for w in logical_words]
                    order = list(range(len(logical_words)))
                    if rtl:
                        order = order[::-1]
                    visual_words = [display_words[i] for i in order]

                    chosen_font_path = pick_font_for_text(full_text, font_style)
                    joined_for_fit = " ".join(visual_words)
                    stroke_w_estimate = max(2, font_size // 18) if use_stroke else 2
                    fitted_size = fit_font_size(joined_for_fit, chosen_font_path, font_size,
                                                 max_text_width, extra_stroke_margin=stroke_w_estimate)
                    try:
                        font_obj = ImageFont.truetype(chosen_font_path, fitted_size)
                    except Exception:
                        font_obj = ImageFont.truetype(FALLBACK_FONT, fitted_size)

                    for logical_idx, w in enumerate(group["words"]):
                        visual_idx = order.index(logical_idx)
                        img = draw_karaoke_image(
                            visual_words, visual_idx, font_obj,
                            text_color, stroke_color if use_stroke else text_color,
                            max(2, fitted_size // 18) if use_stroke else 0,
                            highlight_bg_color, highlight_text_color,
                        )
                        w_start = max(w.start, group["start"]) / 1000.0
                        w_end = min(w.end, group["end"]) / 1000.0
                        if w_end <= w_start:
                            w_end = w_start + 0.05
                        img_clip = image_rgba_to_clip(img)
                        img_clip = (
                            img_clip
                            .with_position(("center", caption_y))
                            .with_start(w_start)
                            .with_duration(w_end - w_start)
                        )
                        layers.append(img_clip)
            else:
                srt_data = create_srt_from_groups(groups)
                with open("temp_subtitles.srt", "w", encoding="utf-8") as s_file:
                    s_file.write(srt_data)
                subtitles = sub.SubtitlesClip("temp_subtitles.srt", make_textclip=create_styled_text)
                subtitles = subtitles.with_position(("center", caption_y))
                layers.append(subtitles)

        if use_hook and hook_text.strip():
            hook_display = prepare_text_for_rendering(hook_text)
            hook_font = pick_font_for_text(hook_text, font_style)
            hook_stroke_margin_estimate = max(2, int(font_size * 1.2) // 15)
            hook_fitted_size = fit_font_size(hook_display, hook_font, int(font_size * 1.2),
                                              max_text_width, extra_stroke_margin=hook_stroke_margin_estimate)
            hook_kwargs = dict(
                text=hook_display, font_size=hook_fitted_size, color=hook_color, font=hook_font,
                method="label", stroke_color="#000000", stroke_width=max(2, hook_fitted_size // 15),
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
        final_video.write_videofile(output_path, **write_kwargs)
        video.close()
        return output_path

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
            groups = build_word_groups(words, batch_size=words_per_caption) if has_speech else []
            has_speech = has_speech and len(groups) > 0

            if has_speech:
                st.success(f"تم تحليل الصوت. اللغة المكتشفة: {lang}")
                srt_data = create_srt_from_groups(groups)
                with open("temp_subtitles.srt", "w", encoding="utf-8") as s_file:
                    s_file.write(srt_data)
                st.session_state.srt_data = srt_data
            else:
                st.warning("لم يتم رصد كلام واضح في الفيديو. سيُنتَج الفيديو بدون ترجمة نصية.")
                st.session_state.srt_data = None

        aspect_list = ASPECT_OPTIONS if multi_export else [aspect_choice]
        output_files = []
        with st.spinner("جارٍ تجهيز الفيديو بالتنسيق المختار..."):
            for aspect_label in aspect_list:
                suffix = ASPECT_FILE_SUFFIX.get(aspect_label, "video")
                out_path = f"temp_output_{suffix}.mp4"
                build_video(aspect_label, out_path, words, has_speech, groups)
                output_files.append((aspect_label, out_path))
        st.session_state.output_files = output_files
        st.session_state.processed = True

    if st.session_state.processed and st.session_state.output_files:
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-wrap">', unsafe_allow_html=True)
        section_heading("ti-circle-check", "الفيديو النهائي", "المعالجة اكتملت بنجاح.")

        for aspect_label, path in st.session_state.output_files:
            if not os.path.exists(path):
                continue
            st.markdown(f'<div class="chip" style="margin-bottom:8px;">{aspect_label}</div>', unsafe_allow_html=True)
            st.video(path)
            with open(path, "rb") as file:
                st.download_button(
                    label=f"⭳ تنزيل — {ASPECT_FILE_SUFFIX.get(aspect_label,'video')}",
                    data=file,
                    file_name=f"edit73_{ASPECT_FILE_SUFFIX.get(aspect_label,'video')}.mp4",
                    mime="video/mp4",
                    key=f"dl_{aspect_label}",
                )
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        if st.session_state.get("srt_data"):
            st.download_button(
                label="⭳ تنزيل ملف الترجمة (SRT)",
                data=st.session_state.srt_data.encode("utf-8"),
                file_name="edit73_subtitles.srt",
                mime="text/plain",
            )
        st.markdown('</div>', unsafe_allow_html=True)

    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("→ رجوع للإعدادات", on_click=go_to, args=(4,), type="secondary")
    with nav2:
        def _reset():
            go_to(1)
            st.session_state.processed = False
            st.session_state.video_ready = False
            st.session_state.output_files = []
        st.button("⟲ فيديو جديد", on_click=_reset)

st.markdown('<div class="app-footer">edit73 — استوديو الترجمة الذكي</div>', unsafe_allow_html=True)
