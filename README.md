# edit73 — مصنع الترجمة الذكي 🎬

## طريقة النشر على Streamlit Cloud

1. ارفع محتويات هذا المجلد بالكامل إلى مستودع GitHub (بنفس الهيكل، خصوصاً مجلدي `fonts/` و `assets/`).
2. من [share.streamlit.io](https://share.streamlit.io) أنشئ تطبيق جديد يشير إلى `app.py`.
3. من **Settings → Secrets** أضف مفتاح AssemblyAI الخاص بك:
   ```toml
   ASSEMBLYAI_API_KEY = "your_real_key_here"
   ```
4. احفظ، وانتظر حتى يكتمل النشر.

## هيكل المشروع (لا تغيّره)

```
edit73_app/
├── app.py
├── requirements.txt
├── apt.txt
├── README.md
├── fonts/
│   ├── Tajawal-Bold.ttf
│   ├── Tajawal-ExtraBold.ttf
│   ├── Tajawal-Black.ttf
│   ├── NotoNaskhArabic-Regular.ttf
│   ├── Poppins-Bold.ttf
│   ├── Poppins-ExtraBold.ttf
│   └── Poppins-Black.ttf
└── assets/
    └── logo.png
```

## المميزات
- كشف تلقائي للغة الفيديو (عربي / إنجليزي) وتشكيل صحيح للنص العربي (ربط الحروف + اتجاه الكتابة).
- اختيار وزن الخط (Bold / Extra Bold / Black) — يُطبَّق تلقائياً بالخط الصحيح حسب لغة كل جملة.
- تحكم كامل بلون النص، حجم الخط، الحدّ الخارجي (Outline)، وخلفية الترجمة.
- ثلاث تنسيقات فيديو جاهزة للسوشال ميديا: الأصلي، عمودي 9:16 (Reels/Shorts/TikTok)، ومربع 1:1 (Instagram).
- إطار ملوّن قابل للتخصيص حول الفيديو.
- جملة "هووك" جاذبة تظهر أعلى الفيديو في الثواني الأولى لزيادة نسبة المشاهدة الكاملة.
