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
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Sedang mendengarkan... Silakan bicara")
        recognizer.adjust_for_ambient_noise(source)
        audio_data = recognizer.listen(source)
        print("🔊 Mengenali suara...")

        try:
            text = recognizer.recognize_google(audio_data, language='id-ID')
            return text
        except sr.UnknownValueError:
            return "Maaf, saya tidak bisa memahami suara Anda."
        except sr.RequestError:
            return "Terjadi kesalahan saat menghubungi layanan pengenalan suara."

# --- Kirim ke Qwen ---
def ask_qwen(prompt):
    response = Generation.call(
        model=cfg['model'],
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
    user_speech = listen_and_convert()
    answer = ask_qwen(user_speech) if user_speech else "Tidak ada input suara."
    return jsonify({
        'input': user_speech,
        'response': answer
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)