
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chinchilla_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', ping_timeout=60, ping_interval=25)

players = {}  # sid: {name, xp, room, match_id}
waiting_queue = []

@app.route('/')
def index():
    return "Chinchilla Samurai Online Server is Running."

@socketio.on('connect')
def handle_connect():
    pass

@socketio.on('register_player')
def handle_register(data):
    players[request.sid] = {
        'id': request.sid,
        'name': data.get('name', 'プレイヤー'),
        'xp': data.get('xp', 100),
        'match_id': None
    }
    broadcast_player_list()

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in players:
        match_id = players[request.sid].get('match_id')
        if match_id:
            # 対戦中の切断を相手に通知
            socketio.emit('opponent_disconnected', room=match_id)
        del players[request.sid]
    if request.sid in waiting_queue:
        waiting_queue.remove(request.sid)
    broadcast_player_list()

def broadcast_player_list():
    active_players = [p for p in players.values() if p['match_id'] is None]
    socketio.emit('player_list_update', active_players)

@socketio.on('send_challenge')
def handle_challenge(data):
    target_id = data.get('target_id')
    match_id = str(uuid.uuid4())
    if target_id in players:
        socketio.emit('challenge_received', {
            'match_id': match_id,
            'challenger_id': request.sid,
            'challenger_name': data.get('name'),
            'challenger_xp': data.get('xp')
        }, room=target_id)

@socketio.on('accept_challenge')
def handle_accept(data):
    match_id = data.get('match_id')
    p1 = request.sid
    # チャレンジを送った側を探す（簡易的に全プレイヤーから検索またはroom管理）
    join_room(match_id, sid=p1)
    
    # 相手（challenger）のsidを特定するため、クライアントからの情報を紐付け
    # ここではルームに参加させた上で対戦開始を通知
    opponent_name = players.get(p1, {}).get('name', '相手')
    emit('start_online_battle', {'match_id': match_id, 'opponent_name': opponent_name, 'is_host': False}, room=p1)

@socketio.on('reject_challenge')
def handle_reject(data):
    match_id = data.get('match_id')
    socketio.emit('challenge_rejected', room=match_id)

@socketio.on('start_random_match')
def handle_random_match(data):
    sid = request.sid
    if sid not in waiting_queue:
        waiting_queue.append(sid)
    
    if len(waiting_queue) >= 2:
        p1 = waiting_queue.pop(0)
        p2 = waiting_queue.pop(0)
        match_id = str(uuid.uuid4())
        
        join_room(match_id, sid=p1)
        join_room(match_id, sid=p2)
        
        if p1 in players: players[p1]['match_id'] = match_id
        if p2 in players: players[p2]['match_id'] = match_id
        
        name1 = players.get(p1, {}).get('name', 'プレイヤー1')
        name2 = players.get(p2, {}).get('name', 'プレイヤー2')
        
        socketio.emit('start_online_battle', {'match_id': match_id, 'opponent_name': name2, 'is_host': True}, room=p1)
        socketio.emit('start_online_battle', {'match_id': match_id, 'opponent_name': name1, 'is_host': False}, room=p2)
        broadcast_player_list()

@socketio.on('player_action')
def handle_player_action(data):
    match_id = data.get('match_id')
    # ルーム内のもう一人のプレイヤーにアクションを中継
    socketio.emit('opponent_action_received', data, room=match_id, include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
