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

# --- 🎟️ 1-90 నంబర్లు అన్నీ పక్కాగా వచ్చేలా లాజిక్ ---
def generate_full_sheet_for_six():
    # 1 నుండి 90 వరకు ఉన్న అన్ని నంబర్లను తీసుకోవడం
    all_nums = list(range(1, 91))
    random.shuffle(all_nums)
    
    # 6 టికెట్లు (6 * 15 = 90 నంబర్లు)
    tickets = []
    for i in range(6):
        # ప్రతి టికెట్ కు 15 యూనిక్ నంబర్లు
        t_nums = sorted(all_nums[i*15 : (i+1)*15])
        ticket = [[0]*9 for _ in range(3)]
        
        for n in t_nums:
            col = (n-1)//10 if n < 90 else 8
            # ఖాళీగా ఉన్న రో లో ప్లేస్ చేయడం
            placed = False
            rows = [0, 1, 2]
            random.shuffle(rows)
            for r in rows:
                if ticket[r][col] == 0 and sum(1 for x in ticket[r] if x != 0) < 5:
                    ticket[r][col] = n
                    placed = True
                    break
            if not placed: # ఫోర్స్ ప్లేస్‌మెంట్
                for r in range(3):
                    if ticket[r][col] == 0:
                        ticket[r][col] = n
                        break
        tickets.append(ticket)
    return tickets

def generate_proper_tickets(count):
    if count == 6:
        return generate_full_sheet_for_six()
    
    # 6 కంటే తక్కువ అయితే నార్మల్ లాజిక్
    final_tickets = []
    for _ in range(count):
        ticket = [[0 for _ in range(9)] for _ in range(3)]
        for col in range(9):
            start, end = col*10+1, (col+1)*10
            if col == 8: end = 90
            ticket[random.randint(0, 2)][col] = random.randint(start, end)
        
        while sum(1 for r in ticket for c in r if c != 0) < 15:
            r, c = random.randint(0, 2), random.randint(0, 8)
            start, end = c*10+1, (c+1)*10
            if c == 8: end = 90
            num = random.randint(start, end)
            if ticket[r][c] == 0 and num not in [ticket[i][c] for i in range(3)] and sum(1 for x in ticket[r] if x != 0) < 5:
                ticket[r][c] = num
        final_tickets.append(ticket)
    return final_tickets

# --- విన్నర్ చెకింగ్ ---
def auto_check_winners():
    called = set(game_state["called_numbers"])
    for token, data in game_state["users"].items():
        phone = data.get("phone", "Unknown")
        for ticket in data["tickets"]:
            t_nums = [n for row in ticket for n in row if n != 0]
            matched = [n for n in t_nums if n in called]
            winner_id = phone
            if len(matched) >= 5 and winner_id not in game_state["winners"]["jaldhi"]:
                if len(game_state["winners"]["jaldhi"]) < 3: game_state["winners"]["jaldhi"].append(winner_id)
            rows_map = {0: "top", 1: "middle", 2: "bottom"}
            for i in range(3):
                row_nums = [n for n in ticket[i] if n != 0]
                if row_nums and all(n in called for n in row_nums):
                    if winner_id not in game_state["winners"][rows_map[i]]:
                        if len(game_state["winners"][rows_map[i]]) < 3: game_state["winners"][rows_map[i]].append(winner_id)
            if len(matched) == 15 and winner_id not in game_state["winners"]["full"]:
                if len(game_state["winners"]["full"]) < 3: game_state["winners"]["full"].append(winner_id)

# --- Routes ---
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
    count = int(request.form.get('ticket_count', 1))
    token = str(uuid.uuid4())[:8]
    game_state["users"][token] = {"tickets": generate_proper_tickets(count), "phone": phone}
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
    auto_check_winners() 
    return jsonify({"number": num, "history": game_state["called_numbers"]})

@app.route('/get_updates')
def get_updates():
    return jsonify({"called": game_state["called_numbers"], "winners": game_state["winners"]})

@app.route('/restart_game', methods=['POST'])
def restart_game():
    game_state["called_numbers"], game_state["users"] = [], {}
    game_state["winners"] = {k: [] for k in game_state["winners"]}
    return jsonify({"status": "restarted"})

@app.route('/ticket/<token>')
def show_ticket(token):
    user_data = game_state["users"].get(token)
    if not user_data: return "<h1>Ticket Not Found!</h1>"
    return render_template('user_ticket.html', tickets=user_data['tickets'], voice_id=game_state["voice_room_id"])
if __name__ == '__main__':
    # లోకల్ హోస్ట్ (127.0.0.1) కాకుండా 0.0.0.0 వాడాలి
    # పోర్ట్ నంబర్ సర్వర్ ఇచ్చే దాని ప్రకారం ఉండాలి
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)