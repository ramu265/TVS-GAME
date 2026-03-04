import os
import random
import uuid
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "housie_pro_secure_2026")

# --- Game Database ---
game_state = {
    "called_numbers": [], 
    "users": {}, 
    "winners": {"jaldhi": [], "top": [], "middle": [], "bottom": [], "full": []},
    "voice_room_id": "tambola-live-" + str(uuid.uuid4())[:6]
}

def generate_tambola_sheet():
    """6 టిక్కెట్ల సెట్ (1-90 నంబర్లు) జనరేట్ చేసే లాజిక్"""
    sheet = []
    # 1-90 నంబర్లను కాలమ్స్ వారీగా సర్దడం
    columns = [[] for _ in range(9)]
    for i in range(9):
        start = i * 10 + 1
        end = (i + 1) * 10
        if i == 8: end = 90
        nums = list(range(start, end + 1))
        random.shuffle(nums)
        columns[i] = nums

    for _ in range(6):
        ticket = [[0] * 9 for _ in range(3)]
        # ప్రతి కాలమ్ నుండి కనీసం ఒక నంబర్ ఉండేలా చూడటం
        col_indices = list(range(9))
        selected_cols = random.sample(col_indices, 9) 
        
        # 15 నంబర్లను 3 రోలలో సర్దడం (ప్రతి రోకి 5)
        count = 0
        for r in range(3):
            row_cols = random.sample(col_indices, 5)
            for c in row_cols:
                if columns[c]:
                    ticket[r][c] = columns[c].pop()
                    count += 1
        sheet.append(ticket)
    return sheet

@app.route('/')
def home(): return render_template('admin_login.html')

@app.route('/login', methods=['POST'])
def login():
    if request.form.get('username') == "admin" and request.form.get('password') == "admin123":
        session['admin'] = True
        return redirect(url_for('dashboard'))
    return "Invalid Credentials"

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'): return redirect(url_for('home'))
    return render_template('admin_dashboard.html', voice_id=game_state["voice_room_id"])

@app.route('/generate_link', methods=['POST'])
def generate_link():
    phone = request.form.get('phone')
    token = str(uuid.uuid4())[:8]
    # ఎల్లప్పుడూ 6 టిక్కెట్ల సెట్ జనరేట్ అవుతుంది (1-90 కవర్ అవ్వడానికి)
    game_state["users"][token] = {"tickets": generate_tambola_sheet(), "phone": phone}
    link = f"{request.host_url}ticket/{token}"
    msg = f"మీ తంబోలా టిక్కెట్లు ఇక్కడ ఉన్నాయి: {link}"
    whatsapp_url = f"https://api.whatsapp.com/send?phone={phone}&text={urllib.parse.quote(msg)}"
    return jsonify({"whatsapp_url": whatsapp_url})

@app.route('/call_number', methods=['POST'])
def call_number():
    available = [n for n in range(1, 91) if n not in game_state["called_numbers"]]
    if not available: return jsonify({"status": "over"})
    num = random.choice(available)
    game_state["called_numbers"].append(num)
    return jsonify({"number": num, "history": game_state["called_numbers"]})

@app.route('/get_updates')
def get_updates():
    return jsonify({"called": game_state["called_numbers"], "winners": game_state["winners"]})

@app.route('/ticket/<token>')
def show_ticket(token):
    user_data = game_state["users"].get(token)
    if not user_data: return "<h1>Ticket Not Found!</h1>"
    return render_template('user_ticket.html', tickets=user_data['tickets'], voice_id=game_state["voice_room_id"])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
