from flask import Flask, render_template, jsonify, request
import dashscope
import config
from dashscope import Generation
import json
import db

app = Flask(__name__)

# DashScope config
dashscope.api_key = config.API_KEY
dashscope.base_http_api_url = config.BASE_HTTP_URL
# def ask_qwen(prompt):
#     response = Generation.call(
#         model='qwen-plus',
#         prompt=prompt
#     )
#     return response.output.text

def ask_qwen(user_text):
    system_prompt = (
        "Kamu adalah asisten inventory. "
        "Jika user menyuruh menambah stok, membuang stok, atau menanyakan stok produk, "
        "jawab dalam format JSON seperti ini:\n"
        '{"action": "tambah", "produk": "bakso", "jumlah": 5}\n'
        'atau {"action": "cek", "produk": "bakso"}\n'
        "Jika user hanya mengobrol biasa, balas dengan {'action': 'jawab', 'response': 'jawaban kamu'}.\n"
        "Sekarang, proses perintah berikut:"
    )
    full_prompt = f"{system_prompt}\nUser: {user_text}"
    response = Generation.call(
        model='qwen-plus',
        prompt=full_prompt
    )
    return response.output.text

def ask_qwen(prompt):
    try:
        response = Generation.call(
            model='qwen-plus-latest',
            prompt=prompt
        )
        return response.output.text
    except Exception as e:
        return f"Gagal mengambil respon dari Qwen: {str(e)}"


def cek_stok_produk(nama_produk):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stok FROM produk WHERE nama = ?", (nama_produk,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else 0

def tambah_stok_produk(nama_produk, jumlah=1):
    import db  # jika fungsi ini di app.py, pastikan db.py sudah ada
    conn = db.get_connection()
    cursor = conn.cursor()
    # Cek apakah produk sudah ada
    cursor.execute("SELECT stok FROM produk WHERE nama = ?", (nama_produk,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE produk SET stok = stok + ? WHERE nama = ?", (jumlah, nama_produk))
    else:
        cursor.execute("INSERT INTO produk (nama, stok) VALUES (?, ?)", (nama_produk, jumlah))
    conn.commit()
    cursor.close()
    conn.close()

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

@app.route('/listen')
def listen():
    user_text = request.args.get('text', '').strip()
    if not user_text:
        return jsonify({'response': 'Tidak ada input suara.'})

    llm_result = ask_qwen(user_text)
    try:
        result = json.loads(llm_result)
    except Exception:
        # Jika gagal parsing, balas hasil mentah
        return jsonify({'response': llm_result})

    # Eksekusi aksi sesuai hasil LLM
    if result.get('action') == 'tambah':
        tambah_stok_produk(result['produk'], result.get('jumlah', 1))
        return jsonify({'response': f"Stok {result['produk']} bertambah {result.get('jumlah', 1)}."})
    elif result.get('action') == 'cek':
        stok = cek_stok_produk(result['produk'])
        return jsonify({'response': f"Stok {result['produk']}: {stok}"})
    elif result.get('action') == 'jawab':
        return jsonify({'response': result.get('response', '')})
    else:
        return jsonify({'response': llm_result})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
