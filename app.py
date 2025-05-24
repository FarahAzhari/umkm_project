from flask import Flask, render_template, jsonify, request
import dashscope
import config
from dashscope import Generation

app = Flask(__name__)

# DashScope config
dashscope.api_key = config.API_KEY
dashscope.base_http_api_url = config.BASE_HTTP_URL

def ask_qwen(prompt):
    try:
        response = Generation.call(
            model='qwen-plus-latest',
            prompt=prompt
        )
        return response.output.text
    except Exception as e:
        return f"Gagal mengambil respon dari Qwen: {str(e)}"


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/listen')
def listen():
    text = request.args.get('text', '').strip()
    if not text:
        return jsonify({'response': 'Tidak ada input suara.'})
    
    answer = ask_qwen(text)
    return jsonify({'response': answer})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
