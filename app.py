from flask import Flask, render_template, jsonify, request
import dashscope
import config
from dashscope import Generation
import db
import re
import json

app = Flask(__name__)

dashscope.api_key = config.API_KEY
dashscope.base_http_api_url = config.BASE_HTTP_URL

def ask_qwen(user_text):
    system_prompt = (
    "Kamu adalah asisten inventory. "
    "Jika user menyuruh menambah stok, mengurangi stok, atau menanyakan stok beberapa produk sekaligus, "
    "jawab dalam format JSON array seperti ini:\n"
    '[{"action": "tambah", "produk": "bakso", "jumlah": 2}, '
    '{"action": "tambah", "produk": "mie", "jumlah": 3}]\n'
    'atau [{"action": "cek", "produk": "bakso"}, {"action": "cek", "produk": "mie"}]\n'
    'atau campuran seperti [{"action": "kurangi", "produk": "bakso", "jumlah": 1}, {"action": "cek", "produk": "mie"}]\n'
    'Jika user berkata "cek semua produk", jawab dengan {"action": "cek_semua"}\n'
    'Jika ada gabungan perintah seperti "cek semua produk dan jelaskan apa itu", '
    'kembalikan array JSON campuran seperti [{"action": "cek_semua"}, {"action": "jawab", "response": "penjelasanmu"}]\n'
    "Jika hanya satu perintah, cukup satu objek JSON.\n"
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

def kurangi_stok_produk(nama_produk, jumlah=1):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stok FROM produk WHERE LOWER(nama) = LOWER(?)", (nama_produk,))
    row = cursor.fetchone()
    if row:
        current_stok = row[0]
        if current_stok < jumlah:
            cursor.close()
            conn.close()
            raise ValueError(f"Stok {nama_produk} tidak cukup untuk dikurangi {jumlah}.")
        cursor.execute("UPDATE produk SET stok = stok - ? WHERE LOWER(nama) = LOWER(?)", (jumlah, nama_produk))
        conn.commit()
    else:
        cursor.close()
        conn.close()
        raise ValueError(f"Produk {nama_produk} tidak ditemukan.")
    cursor.close()
    conn.close()

def cek_semua_produk():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nama, stok FROM produk")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows



@app.route('/')
def index():
    return render_template('index.html')  # gunakan HTML utama dengan chatbot

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_text = data.get('message', '').strip()
    if not user_text:
        return jsonify({'reply': 'Tidak ada input.'})

    llm_result = ask_qwen(user_text)
    print("[DEBUG] LLM RAW:", llm_result)

    # Bersihkan block code markdown jika ada
    llm_result_clean = re.sub(r"^```[a-zA-Z]*\n?", "", llm_result.strip())
    llm_result_clean = re.sub(r"```$", "", llm_result_clean.strip())
    print("[DEBUG] LLM CLEAN:", llm_result_clean)

    try:
        parsed = json.loads(llm_result_clean)
        actions = parsed if isinstance(parsed, list) else [parsed]
    except Exception as e:
        return jsonify({'reply': f'Gagal parsing hasil LLM: {e}\n{llm_result}'})

    replies = []
    for result in actions:
        action = result.get('action')
        produk = result.get('produk')
        jumlah = int(result.get('jumlah', 1)) if 'jumlah' in result else None

        if action == 'tambah':
            if not produk:
                replies.append("Nama produk tidak terdeteksi.")
                continue
            tambah_stok_produk(produk, jumlah)
            replies.append(f"stok {produk} bertambah {jumlah}")

        elif action == 'kurangi':
            if not produk:
                replies.append("Nama produk tidak terdeteksi.")
                continue
            try:
                kurangi_stok_produk(produk, jumlah)
                replies.append(f"stok {produk} berkurang {jumlah}")
            except ValueError as e:
                replies.append(str(e))

        elif action == 'cek':
            if not produk:
                replies.append("Nama produk tidak terdeteksi.")
                continue
            stok = cek_stok_produk(produk)
            replies.append(f"stok {produk}: {stok}")

        elif action == 'cek_semua':
            semua = cek_semua_produk()
            if semua:
                summary = ', '.join([f"{row[0]}: {row[1]}" for row in semua])
                replies.append(f"Stok semua produk: {summary}")
            else:
                replies.append("Tidak ada produk dalam database.")

        elif action == 'jawab':
            replies.append(result.get('response', ''))

        else:
            replies.append(f"Aksi tidak dikenali: {action}")

    # Gabungkan jawaban akhir secara natural
    if len(replies) == 1:
        reply_text = replies[0]
    elif len(replies) == 2:
        reply_text = f"{replies[0]} dan {replies[1]}"
    else:
        reply_text = ", ".join(replies[:-1]) + f", dan {replies[-1]}"

    return jsonify({'reply': reply_text})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
