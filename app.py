from flask import Flask, render_template, jsonify
import speech_recognition as sr
import dashscope
import config
from dashscope import Generation
import configparser

app = Flask(__name__)

# --- Konfigurasi DashScope ---
dashscope.api_key = config.API_KEY
dashscope.base_http_api_url = config.BASE_HTTP_URL

# --- Fungsi rekam dan ubah ke teks ---
def listen_and_convert():
    logs = []
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        logs.append("🎤 Mendengarkan...")
        recognizer.adjust_for_ambient_noise(source)
        audio_data = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio_data, language='id-ID')
            logs.append(f"✅ Suara dikenali: {text}")
            return text, logs
        except sr.UnknownValueError:
            logs.append("❌ Tidak bisa mengenali suara.")
            return "Maaf, saya tidak bisa memahami suara Anda.", logs
        except sr.RequestError:
            logs.append("❌ Gagal menghubungi layanan pengenalan suara.")
            return "Terjadi kesalahan saat menghubungi layanan pengenalan suara.", logs


# --- Kirim ke Qwen ---
def ask_qwen(prompt):
    response = Generation.call(
        model='qwen-plus',
        prompt=prompt
    )
    return response.output.text

# --- Halaman utama ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Endpoint API untuk suara ---
@app.route('/listen', methods=['GET'])
def listen():
    user_speech, logs = listen_and_convert()
    answer = ask_qwen(user_speech) if user_speech else "Tidak ada input suara."
    logs.append(f"💬 Qwen menjawab: {answer}")
    return jsonify({
        'input': user_speech,
        'response': answer,
        'logs': logs
    })


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)