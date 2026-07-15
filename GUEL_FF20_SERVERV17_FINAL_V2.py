import http.server
import socketserver
import json
import os
import hashlib
import random
import time
import threading

PORT = 8080
ACCOUNTS_DIR = "com.garena.msdk"
DB_FILE = os.path.join(ACCOUNTS_DIR, "contas.json")
SENHA_MESTRA = "GUELFF2013"
NOME_VIP = "[0000FF]GUELFF20[-]"
NOME_VIP2 = "[00FF00]SUB_LIDER[-]"
NOME_GUILDA = "[FF0000]Guilda Guel[-]"
GUILDA_ID = "50001"
SERVER_NAME = "GUEL_FF20_SERVERV17"

# Garante que a pasta de contas exista
if not os.path.exists(ACCOUNTS_DIR):
    os.makedirs(ACCOUNTS_DIR)

# =========================================================================
# !!! ACESSO LIBERADO - RENDER 24H !!!
MEU_IP_ATUAL = "216.24.57.1" 
# =========================================================================

queues = {
    "SOLO": {"players": [], "timer": None, "min": 5, "max": 10, "ip": "216.24.57.1"},
    "DUO": {"players": [], "timer": None, "min": 8, "max": 10, "ip": "216.24.57.1"}
}
active_matches = {} 
queue_lock = threading.Lock()
match_lock = threading.Lock()
db_lock = threading.Lock()
TIMER_DURATION = 10

def start_match(mode, players):
    match_id = str(random.randint(1000, 9999))
    match_data = {
        "mode": mode,
        "players": {p["id"]: {"nickname": p["nickname"], "hp": 200, "kills": 0, "status": "ALIVE"} for p in players},
        "start_time": time.time()
    }
    with match_lock:
        active_matches[match_id] = match_data
    
    print(f"\n====================================================")
    print(f"   [PARTIDA INICIADA {SERVER_NAME}] - ID: {match_id}")
    print(f"   JOGADORES: {len(players)}")
    print(f"====================================================\n")
    return match_id

def matchmaking_tick():
    global queues
    while True:
        try:
            with queue_lock:
                for mode in queues:
                    q = queues[mode]
                    if len(q["players"]) >= q["min"]:
                        if q["timer"] is None:
                            q["timer"] = time.time()
                        
                        elapsed = time.time() - q["timer"]
                        if len(q["players"]) >= q["max"] or elapsed >= TIMER_DURATION:
                            count = len(q["players"])
                            if mode == "DUO" and count % 2 != 0: count -= 1
                            players_to_start = q["players"][:count]
                            q["players"] = q["players"][count:]
                            q["timer"] = None
                            if players_to_start: start_match(mode, players_to_start)
                    else:
                        q["timer"] = None
        except Exception as e:
            print(f"Erro no matchmaking: {e}")
        time.sleep(1)

threading.Thread(target=matchmaking_tick, daemon=True).start()

class FreeFireV17Handler(http.server.BaseHTTPRequestHandler):
    def get_db(self):
        default_db = {
            "config": {"admin_ip_lock": None},
            "guilds": {
                GUILDA_ID: {
                    "name": NOME_GUILDA, "leader_id": "1000001", "level": 4,
                    "members": ["1000001", "1000002"], "slogan": "Dominando o Free Fire Classico"
                }
            },
            "players": {
                "1000001": {
                    "nickname": NOME_VIP, "diamonds": 9999, "gold": 9999, "level": 100,
                    "rank": 6, "rank_points": 3200, "guild_id": GUILDA_ID, "friends": ["1000002"],
                    "password": hashlib.sha256(SENHA_MESTRA.encode()).hexdigest(),
                    "inventory": [i for i in range(1000, 1500)]
                }
            },
            "device_to_account": {}
        }
        with db_lock:
            if not os.path.exists(DB_FILE):
                with open(DB_FILE, 'w') as f: json.dump(default_db, f)
                # Salva o líder VIP na pasta de contas individualmente também
                self.save_individual_account("1000001", default_db["players"]["1000001"])
                return default_db
            with open(DB_FILE, 'r') as f: return json.load(f)

    def save_individual_account(self, player_id, player_data):
        # Salva a conta individualmente na pasta com.garena.msdk
        account_file = os.path.join(ACCOUNTS_DIR, f"{player_id}.json")
        with open(account_file, 'w') as f:
            json.dump(player_data, f, indent=4)

    def save_db(self, db):
        with db_lock:
            with open(DB_FILE, 'w') as f: json.dump(db, f, indent=4)
            # Ao salvar o DB, garantimos que cada jogador tenha seu arquivo individual atualizado
            for p_id, p_data in db["players"].items():
                self.save_individual_account(p_id, p_data)

    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        db = self.get_db()
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode("utf-8")) if post_data else {}

        if "login" in self.path or "guest_login" in self.path:
            device_id = data.get("device_id") or data.get("udid")
            player_id = db["device_to_account"].get(device_id)
            
            if not player_id:
                player_id = str(random.randint(2000000, 9999999))
                db["players"][player_id] = {
                    "nickname": f"Player_{player_id[:4]}", "diamonds": 100, "gold": 1000,
                    "level": 1, "rank": 1, "rank_points": 0, "guild_id": GUILDA_ID, "friends": ["1000001"],
                    "password": hashlib.sha256("123456".encode()).hexdigest(), "inventory": [1001, 1002]
                }
                db["device_to_account"][device_id] = player_id
                # Adiciona na Guilda Guel
                if player_id not in db["guilds"][GUILDA_ID]["members"]:
                    db["guilds"][GUILDA_ID]["members"].append(player_id)
                # Amizade com o Líder
                if player_id not in db["players"]["1000001"]["friends"]:
                    db["players"]["1000001"]["friends"].append(player_id)

            self.save_db(db)
            response = {
                "status": 0, "account_id": player_id, "nickname": db["players"][player_id]["nickname"],
                "diamonds": db["players"][player_id]["diamonds"], "gold": db["players"][player_id]["gold"],
                "level": db["players"][player_id]["level"], "rank": db["players"][player_id]["rank"],
                "guild_id": db["players"][player_id]["guild_id"], "friends": db["players"][player_id].get("friends", []),
                "session_key": "guelff_v17_render_" + hashlib.md5(player_id.encode()).hexdigest()[:8]
            }
            self.send_json_response(200, response)
            return

        self.send_json_response(404, {"status": 1, "message": "Not Found"})

    def do_GET(self):
        if "ver.php" in self.path or "version" in self.path or "free-fire-q96x" in self.path:
            self.send_json_response(200, {"status": 0, "version": "1.17.0"})
            return
        self.send_json_response(404, {"status": 1, "message": "Not Found"})

class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    print(f"====================================================")
    print(f"   {SERVER_NAME} - ONLINE")
    print(f"   GUILDA: {NOME_GUILDA}")
    print(f"   ACESSO: RENDER URL (HTTPS)")
    print(f"   PASTA DE CONTAS: {ACCOUNTS_DIR}")
    print(f"====================================================")
    
    # Render define a porta na variável de ambiente PORT
    port_to_use = int(os.environ.get('PORT', PORT))
    
    with ReusableTCPServer(("", port_to_use), FreeFireV17Handler) as httpd:
        httpd.serve_forever()
