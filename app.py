from flask import Flask, render_template, jsonify, request
import dashscope
import config
from dashscope import Generation
import db
import re
import json

app = Flask(__name__)

# DashScope config
dashscope.api_key = config.API_KEY
dashscope.base_http_api_url = config.BASE_HTTP_URL

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
    try:
        response = Generation.call(
            model='qwen-plus',
            prompt=full_prompt
        )
        return response.output.text
    except Exception as e:
        return json.dumps({'action': 'jawab', 'response': f'Gagal mengambil respon dari Qwen: {str(e)}'})

def cek_stok_produk(nama_produk):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stok FROM produk WHERE LOWER(nama) = LOWER(?)", (nama_produk,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else 0

def tambah_stok_produk(nama_produk, jumlah=1):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stok FROM produk WHERE LOWER(nama) = LOWER(?)", (nama_produk,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE produk SET stok = stok + ? WHERE LOWER(nama) = LOWER(?)", (jumlah, nama_produk))
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
    user_text = request.args.get('text', '').strip()
    if not user_text:
        return jsonify({'response': 'Tidak ada input suara.'})

    llm_result = ask_qwen(user_text)
    print("[DEBUG] LLM RAW:", llm_result)

    # Bersihkan block code markdown jika ada
    llm_result_clean = re.sub(r"^```[a-zA-Z]*\n?", "", llm_result.strip())
    llm_result_clean = re.sub(r"```$", "", llm_result_clean.strip())
    print("[DEBUG] LLM CLEAN:", llm_result_clean)

    try:
        result = json.loads(llm_result_clean)
    except Exception as e:
        return jsonify({'response': f'Gagal parsing hasil LLM: {e}\n{llm_result}'})

    if result.get('action') == 'tambah':
        produk = result.get('produk')
        jumlah = int(result.get('jumlah', 1))
        if not produk:
            return jsonify({'response': 'Nama produk tidak terdeteksi.'})
        tambah_stok_produk(produk, jumlah)
        return jsonify({'response': f"Stok {produk} bertambah {jumlah}."})
    elif result.get('action') == 'cek':
        produk = result.get('produk')
        if not produk:
            return jsonify({'response': 'Nama produk tidak terdeteksi.'})
        stok = cek_stok_produk(produk)
        return jsonify({'response': f"Stok {produk}: {stok}"})
    elif result.get('action') == 'jawab':
        return jsonify({'response': result.get('response', '')})
    else:
        return jsonify({'response': llm_result})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
