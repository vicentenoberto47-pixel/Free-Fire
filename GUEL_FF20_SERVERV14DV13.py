import http.server
import socketserver
import json
import os
import hashlib
import random
import time
import threading

PORT = 8080
DB_FILE = "contas.json"
SENHA_MESTRA = "GUELFF2013"
NOME_VIP = "[0000FF]GUELFF20[-]"
NOME_VIP2 = "[00FF00]SUB_LIDER[-]"
NOME_GUILDA = "[FF0000]Equipe Revival[-]"
GUILDA_ID = "50001"
SERVER_NAME = "GUEL_FF20_SERVERV14DV13"

# =========================================================================
# !!! IMPORTANTE: COLOQUE O SEU IP AQUI PARA ATIVAR A TRAVA DA CONTA VIP !!!
# Quando o seu celular for liberado, descubra o seu IP (ex: no Google, digite "meu ip")
# e substitua o None pelo seu IP. Exemplo: MEU_IP_ATUAL = "189.120.45.10"
# Se o seu IP mudar, você precisará atualizar aqui.
MEU_IP_ATUAL = None # <--- SUBSTITUA 'None' PELO SEU IP QUANDO FOR USAR A CONTA VIP
# =========================================================================

# LÓGICA DE MATCHMAKING E COMBATE
queues = {
    "SOLO": {"players": [], "timer": None, "min": 5, "max": 10},
    "DUO": {"players": [], "timer": None, "min": 8, "max": 10}
}
active_matches = {} 
queue_lock = threading.Lock()
match_lock = threading.Lock()
db_lock = threading.Lock() # Trava para evitar corrupção do JSON
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
    print(f"   [PARTIDA INICIADA {SERVER_NAME}] - ID: {match_id} | MODO {mode}")
    print(f"   JOGADORES: {len(players)}")
    for p_id, p_info in match_data["players"].items():
        print(f"   - {p_info['nickname']} ({p_id}) | HP: {p_info['hp']}")
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
                            print(f"!!! [MATCHMAKING {mode}] {len(q['players'])} jogadores. Timer de {TIMER_DURATION}s...")
                            q["timer"] = time.time()
                        
                        elapsed = time.time() - q["timer"]
                        if len(q["players"]) >= q["max"] or elapsed >= TIMER_DURATION:
                            count = len(q["players"])
                            if mode == "DUO" and count % 2 != 0: count -= 1
                            
                            players_to_start = q["players"][:count]
                            q["players"] = q["players"][count:]
                            q["timer"] = None
                            if players_to_start:
                                start_match(mode, players_to_start)
                    else:
                        q["timer"] = None
        except Exception as e:
            print(f"Erro no matchmaking_tick: {e}")
        time.sleep(1)

threading.Thread(target=matchmaking_tick, daemon=True).start()

class FreeFireMockHandler(http.server.BaseHTTPRequestHandler):
    def get_db(self):
        default_db = {
            "config": {"admin_ip_lock": MEU_IP_ATUAL},
            "guilds": {
                GUILDA_ID: {
                    "name": NOME_GUILDA, "leader_id": "1000001", "level": 4,
                    "members": ["1000001", "1000002"], "slogan": "Revivendo o Free Fire Classico"
                }
            },
            "players": {
                "1000001": {
                    "nickname": NOME_VIP, "diamonds": 9999, "gold": 9999, "level": 100,
                    "rank": 6, "rank_points": 3200, "guild_id": GUILDA_ID, "friends": ["1000002"],
                    "password": hashlib.sha256(SENHA_MESTRA.encode()).hexdigest(),
                    "inventory": [i for i in range(1000, 1500)]
                },
                "1000002": {
                    "nickname": NOME_VIP2, "diamonds": 5000, "gold": 5000, "level": 80,
                    "rank": 5, "rank_points": 2800, "guild_id": GUILDA_ID, "friends": ["1000001"],
                    "password": hashlib.sha256(SENHA_MESTRA.encode()).hexdigest(),
                    "inventory": [i for i in range(1000, 1300)]
                }
            },
            "device_to_account": {}
        }
        with db_lock:
            if not os.path.exists(DB_FILE):
                self._save_db_no_lock(default_db)
                return default_db
            try:
                with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                print(f"!!! [ERRO] Falha ao ler {DB_FILE}: {e}. Recriando... !!!")
                self._save_db_no_lock(default_db)
                return default_db

    def save_db(self, db):
        with db_lock:
            self._save_db_no_lock(db)

    def _save_db_no_lock(self, db):
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4)
        except Exception as e:
            print(f"!!! [ERRO] Falha ao salvar {DB_FILE}: {e} !!!")

    def send_json_response(self, status_code, data):
        try:
            self.send_response(status_code)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            print(f"!!! [ERRO] Falha ao enviar resposta: {e} !!!")

    def do_POST(self):
        db = self.get_db()
        client_ip = self.client_address[0]
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        try: data = json.loads(post_data.decode("utf-8")) if post_data else {}
        except json.JSONDecodeError:
            self.send_json_response(400, {"status": 1, "message": "JSON inválido"})
            return
        except Exception as e:
            print(f"!!! [ERRO] Falha ao decodificar POST: {e} !!!")
            self.send_json_response(500, {"status": 1, "message": "Erro interno do servidor"})
            return

        # LÓGICA DE COMBATE
        if "game_event" in self.path:
            match_id = data.get("match_id")
            victim_id = data.get("victim_id")
            attacker_id = data.get("attacker_id")
            damage = data.get("damage", 0)

            with match_lock:
                if match_id in active_matches:
                    match = active_matches[match_id]
                    if victim_id in match["players"] and match["players"][victim_id]["status"] == "ALIVE":
                        match["players"][victim_id]["hp"] -= damage
                        print(f"--- [COMBATE] {match['players'].get(attacker_id, {'nickname': 'Desconhecido'})['nickname']} causou {damage} de dano em {match['players'][victim_id]['nickname']} (HP: {match['players'][victim_id]['hp']}) ---")
                        
                        if match["players"][victim_id]["hp"] <= 0:
                            match["players"][victim_id]["hp"] = 0
                            match["players"][victim_id]["status"] = "DEAD"
                            if attacker_id in match["players"]:
                                match["players"][attacker_id]["kills"] += 1
                            print(f"!!! [KILLFEED] {match['players'].get(attacker_id, {'nickname': 'Desconhecido'})['nickname']} ELIMINOU {match['players'][victim_id]['nickname']} !!!")
                        
                        self.send_json_response(200, {"status": 0, "victim_hp": match["players"][victim_id]["hp"]})
                        return
            self.send_json_response(404, {"status": 1, "message": "Partida ou jogador não encontrado"})
            return

        # LÓGICA DE MATCHMAKING
        if "start_match" in self.path:
            player_id = data.get("account_id")
            mode = data.get("mode", "SOLO").upper() # SOLO ou DUO
            if player_id not in db["players"] or mode not in queues:
                self.send_json_response(400, {"status": 1, "message": "Dados inválidos para matchmaking"})
                return
            
            player_info = {"id": player_id, "nickname": db["players"][player_id]["nickname"]}
            with queue_lock:
                if player_info not in queues[mode]["players"]:
                    queues[mode]["players"].append(player_info)
                    print(f"+++ [FILA {mode}] {player_info['nickname']} ({player_id}) entrou na fila. Total: {len(queues[mode]['players'])} +++")
            self.send_json_response(200, {"status": 0, "message": "Entrou na fila de matchmaking"})
            return

        # LOGIN E REGISTRO COM TRAVA DE IP
        if "guest_login" in self.path or "login" in self.path:
            device_id = data.get("device_id") or data.get("udid")
            if not device_id:
                self.send_json_response(400, {"status": 1, "message": "Device ID ausente"})
                return

            player_id = None
            # === LÓGICA DA TRAVA DE IP PARA A CONTA VIP 1000001 ===
            is_vip_device = db["device_to_account"].get(device_id) == "1000001"
            
            if is_vip_device:
                if MEU_IP_ATUAL and client_ip != MEU_IP_ATUAL:
                    print(f"!!! [ALERTA DE SEGURANÇA] Tentativa de login na conta VIP de IP não autorizado: {client_ip} !!!")
                    self.send_json_response(403, {"status": 1, "message": "Acesso Negado: IP não autorizado para esta conta."})
                    return
                else:
                    player_id = "1000001"
                    print(f">>> [LOGIN] LÍDER ({player_id}) logou do IP: {client_ip} <<<")

            # Se não for o ADM, ou se o IP não bateu, tenta criar uma conta nova ou logar em uma existente
            if not player_id:
                player_id = db["device_to_account"].get(device_id)
                if not player_id:
                    # Auto-registro obrigatório para novos jogadores
                    player_id = str(random.randint(2000000, 9999999))
                    db["players"][player_id] = {
                        "nickname": f"Player_{player_id[:4]}", "diamonds": 100, "gold": 1000,
                        "level": 1, "rank": 1, "rank_points": 0, "guild_id": GUILDA_ID, "friends": [],
                        "password": hashlib.sha256("123456".encode()).hexdigest(), "inventory": [1001, 1002]
                    }
                    db["device_to_account"][device_id] = player_id
                    print(f"+++ [REGISTRO] Novo jogador ({player_id}) registrado para Device ID: {device_id} +++")

            # Adiciona à guilda e faz amizade com o Líder (1000001)
            if GUILDA_ID in db["guilds"]:
                if player_id not in db["guilds"][GUILDA_ID]["members"]:
                    db["guilds"][GUILDA_ID]["members"].append(player_id)
                    print(f"+++ [GUILDA] {db['players'][player_id]['nickname']} ({player_id}) adicionado à Equipe Revival! +++")
                
                # Garante que o Líder (1000001) seja amigo de todos
                if player_id != "1000001":
                    db["players"][player_id].setdefault("friends", [])
                    if "1000001" not in db["players"][player_id]["friends"]:
                        db["players"][player_id]["friends"].append("1000001")
                    if "1000001" in db["players"]:
                        db["players"]["1000001"].setdefault("friends", [])
                        if player_id not in db["players"]["1000001"]["friends"]:
                            db["players"]["1000001"]["friends"].append(player_id)

            self.save_db(db)
            response = {
                "status": 0, "account_id": player_id, "nickname": db["players"][player_id]["nickname"],
                "diamonds": db["players"][player_id]["diamonds"], "gold": db["players"][player_id]["gold"],
                "level": db["players"][player_id]["level"], "rank": db["players"][player_id]["rank"],
                "guild_id": db["players"][player_id]["guild_id"], "friends": db["players"][player_id].get("friends", []),
                "session_key": "guelff_v14dv13_" + hashlib.md5(player_id.encode()).hexdigest()[:8]
            }
            self.send_json_response(200, response)
            return

        # ENDPOINT PARA ADICIONAR AMIGO
        if "add_friend" in self.path:
            requester_id = data.get("requester_id")
            target_id = data.get("target_id")
            if requester_id in db["players"] and target_id in db["players"]:
                db["players"][requester_id].setdefault("friends", [])
                if target_id not in db["players"][requester_id]["friends"]:
                    db["players"][requester_id]["friends"].append(target_id)
                db["players"][target_id].setdefault("friends", [])
                if requester_id not in db["players"][target_id]["friends"]:
                    db["players"][target_id]["friends"].append(requester_id)
                self.save_db(db)
                self.send_json_response(200, {"status": 0, "message": "Amizade adicionada"})
                return
            self.send_json_response(400, {"status": 1, "message": "Erro na amizade"})
            return

        self.send_json_response(404, {"status": 1, "message": "Endpoint não encontrado"})

    def do_GET(self):
        db = self.get_db()
        if "ver.php" in self.path or "version" in self.path:
            self.send_json_response(200, {"status": 0, "version": "1.11.2"})
            return
        
        if self.path.startswith("/guild/"):
            parts = self.path.split("/")
            if len(parts) >= 3:
                guild_id = parts[2]
                guild_data = db["guilds"].get(guild_id)
                if guild_data:
                    self.send_json_response(200, {"status": 0, "guild": guild_data})
                    return
            self.send_json_response(404, {"status": 1, "message": "Guilda não encontrada"})
            return

        self.send_json_response(404, {"status": 1, "message": "Endpoint não encontrado"})

class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    print(f"====================================================")
    print(f"   {SERVER_NAME} INICIADO")
    print(f"   PORTA: {PORT}")
    print(f"   STATUS: ONLINE")
    print(f"====================================================")
    with ReusableTCPServer(("", PORT), FreeFireMockHandler) as httpd:
        httpd.serve_forever()
