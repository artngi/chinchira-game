
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chinchilla_secret_key'
# eventletを確実に使用するためのasync_mode明示とCORS設定
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

players = {}  # sid: {name, xp, room}
waiting_queue = []

@app.route('/')
def index():
    return "Chinchilla Samurai Online Server is Running."

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
            'challenger_name': data.get('name'),
            'challenger_xp': data.get('xp')
        }, room=target_id)

@socketio.on('accept_challenge')
def handle_accept(data):
    match_id = data.get('match_id')
    p1 = request.sid
    join_room(match_id, sid=p1)
    emit('start_online_battle', {'match_id': match_id, 'opponent_name': players.get(p1, {}).get('name', '相手')}, room=match_id)

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
        
        players[p1]['match_id'] = match_id
        players[p2]['match_id'] = match_id
        
        socketio.emit('start_online_battle', {'match_id': match_id, 'opponent_name': players[p2]['name']}, room=p1)
        socketio.emit('start_online_battle', {'match_id': match_id, 'opponent_name': players[p1]['name']}, room=p2)
        broadcast_player_list()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
