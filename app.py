import os
os.system("apt-get update && apt-get install -y imagemagick")
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

# ضع مفتاح الـ API الخاص بك هنا
aai.settings.api_key = "5f06039b401740c49a845ab4db2a0421"

def create_srt_batches(words, batch_size=3):
    srt_content = ""
    counter = 1
    for i in range(0, len(words), batch_size):
        batch = words[i:i+batch_size]
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
    return vc.TextClip(
        text=txt, 
        font='DejaVuSans-Bold',
        font_size=40, 
        color='black', 
        bg_color='white',
        method='label'          # حذفنا الـ size والـ margin تماماً لمنع أي تعارض
    )


st.title("🎬 مصنع الترجمة الذكي")
st.write("<p style='text-align: center; color: #bdc3c7;'>أهلاً بك يا بطل! ارفع فيديو وسيتولى الذكاء الاصطناعي هندسة النصوص وتلوينها فوراً.</p>", unsafe_allow_html=True)

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
            else:
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
