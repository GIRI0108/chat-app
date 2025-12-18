import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from openai import OpenAI
from dotenv import load_dotenv
import random
import cloudinary
import cloudinary.uploader
import cloudinary.api
import eventlet
eventlet.monkey_patch()
load_dotenv()

from routes.ai_routes import ai_bp
from routes.private_room_routes import private_room
from routes.watch_routes import watch_bp
from routes.music_routes import music_bp
from routes.call_routes import call_bp

# Basic config
app = Flask(__name__, static_folder="static", template_folder="templates")
import os
from flask import request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 30MB

client = OpenAI(api_key=os.getenv("AI_API_KEY"))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg://postgres:admin@localhost:5433/app_1'
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 800 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

private_rooms = {}
# structure:
# private_rooms[room_key] = {
#   "host": user_id,
#   "users": set(user_ids),
#   "mode": None
# }


from extensions import db
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    contact = db.Column(db.String(120), unique=True, nullable=False)  # phone or email
    name = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # For 1:1 conversation, store sorted user ids to easily find room
    user_a = db.Column(db.Integer, nullable=False)
    user_b = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text)
    msg_type = db.Column(db.String(20), default='text')  # text, file, system
    file_url = db.Column(db.String(300))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    delivered = db.Column(db.Boolean, default=False)
    read = db.Column(db.Boolean, default=False)

class PrivateRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(20), unique=True, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Login loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helpers
def get_or_create_conversation(a, b):
    a_, b_ = (min(a,b), max(a,b))
    conv = Conversation.query.filter_by(user_a=a_, user_b=b_).first()
    if not conv:
        conv = Conversation(user_a=a_, user_b=b_)
        db.session.add(conv)
        db.session.commit()
    return conv

def generate_room_key():
    import secrets, string
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(6))


# Routes: auth pages and simple APIs
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('contacts'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        contact = request.form['contact']
        name = request.form['name']
        pwd = generate_password_hash(request.form['password'])
        if User.query.filter_by(contact=contact).first():
            return "Contact already exists", 400
        user = User(contact=contact, name=name, password=pwd)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('contacts'))
    return render_template('login.html', register=True)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        contact = request.form['contact']
        password = request.form['password']
        user = User.query.filter_by(contact=contact).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('contacts'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html', register=False)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/contacts')
@login_required
def contacts():
    # Return the contact page (frontend loads contact list via socket or API)
    return render_template('contacts.html')

@app.route('/chat/<int:other_id>')
@login_required
def chat_page(other_id):
    other = User.query.get_or_404(other_id)
    return render_template('chat.html', other=other)

@app.route("/call")
@login_required
def call_page():
    return render_template("call.html")


@app.route('/private-room')
@login_required
def private_room_page():
    return render_template('private_room.html')

@app.route('/create-room', methods=['POST'])
@login_required
def create_room():
    key = generate_room_key()
    room = PrivateRoom(key=key, creator_id=current_user.id)
    db.session.add(room)
    db.session.commit()
    return jsonify({'room_key': key})

@app.route('/join-room', methods=['POST'])
@login_required
def join_room_key():
    data = request.get_json()
    key = data.get('key')
    room = PrivateRoom.query.filter_by(key=key).first()
    if not room:
        return jsonify({'error': 'Invalid key'}), 404
    return jsonify({'room_key': room.key})


# in main.py (or game_routes.py blueprint)
from flask import render_template, abort
@app.route("/private/module/<module_name>")
@login_required
def private_module(module_name):
    allowed = {"chess", "checkers", "tictactoe", "music", "watch", "news", "weather", "ai"}
    if module_name not in allowed:
        return abort(404)
    return render_template(f"private_modules/{module_name}.html")


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file'}), 400

    try:
        result = cloudinary.uploader.upload(
            file,
            resource_type="raw",   # 🔥 FORCE RAW
            folder="chat_uploads",
            use_filename=True,
            unique_filename=True
        )

        return jsonify({
            "success": True,
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "resource_type": result["resource_type"]
        })

    except Exception as e:
        print("Upload error:", e)
        return jsonify({"error": "Upload failed"}), 500


@app.route("/api/ai/process", methods=["POST"])
def ai_process():
    try:
        data = request.get_json()
        text = data.get("text", "").strip()
        task = data.get("task", "").strip()
        lang = data.get("lang", "English").strip()

        if not text:
            return jsonify({"result": "Please enter some text."}), 400

        if task == "translate":
            prompt = f"Translate the following text into {lang}:\n{text}"
        elif task == "summarize":
            prompt = f"Summarize the following text clearly and concisely:\n{text}"
        elif task == "improve":
            prompt = f"Improve this text for clarity, tone, and grammar:\n{text}"
        elif task == "analyze":
            prompt = f"Analyze the sentiment and intent of this text:\n{text}"
        else:
            prompt = f"Process the following text in a helpful way:\n{text}"

        # 🔥 OpenAI call
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful multilingual AI assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        ai_output = response.choices[0].message.content.strip()
        return jsonify({"result": ai_output})

    except Exception as e:
        print("AI Process Error:", e)
        return jsonify({"result": f"Error: {str(e)}"}), 500

# Simple API to add contact
@app.route('/api/add_contact', methods=['POST'])
@login_required
def add_contact():
    contact_value = request.json.get('contact')
    user = User.query.filter_by(contact=contact_value).first()
    if not user:
        return jsonify({'error':'user not found'}), 404
    # Prevent duplicates
    existing = Contact.query.filter_by(owner_id=current_user.id, contact_user_id=user.id).first()
    if existing:
        return jsonify({'ok':True, 'contact_id':existing.id})
    c = Contact(owner_id=current_user.id, contact_user_id=user.id)
    db.session.add(c)
    db.session.commit()
    return jsonify({'ok':True, 'contact_user': {'id': user.id, 'name': user.name, 'contact': user.contact}})

# Socket.IO events: presence, messaging and WebRTC signalling
# We'll map user.id -> sid(s) (support multiple devices)
connected_users = {}  # user_id -> set of sid

@socketio.on('connect')
def handle_connect():
    if not current_user.is_authenticated:
        return

    sid = request.sid
    uid = current_user.id

    connected_users.setdefault(uid, set()).add(sid)

    # ✅ ADD THIS
    join_room(f"user_{uid}")

    emit('presence_update', {'user_id': uid, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    # find user by sid
    for uid, sids in list(connected_users.items()):
        if sid in sids:
            sids.remove(sid)
            if not sids:
                connected_users.pop(uid)
                # broadcast offline
                emit('presence_update', {'user_id': uid, 'status': 'offline'}, broadcast=True)
            break
    print("Disconnected", sid)

@socketio.on('get_contacts')
def handle_get_contacts():
    owner = current_user.id
    contacts = Contact.query.filter_by(owner_id=owner).all()
    payload = []
    for c in contacts:
        u = User.query.get(c.contact_user_id)
        payload.append({
            'id': u.id, 'name': u.name, 'contact': u.contact,
            'online': u.id in connected_users
        })
    emit('contacts_list', payload)

@socketio.on('start_conversation')
def handle_start_conv(data):
    other_id = int(data.get('other_id'))
    conv = get_or_create_conversation(current_user.id, other_id)
    room = f"conv_{conv.id}"
    join_room(room)
    # send back conversation id
    emit('conversation', {'conv_id': conv.id})

@socketio.on('join_conv')
def handle_join_conv(data):
    conv_id = int(data.get('conv_id'))
    room = f"conv_{conv_id}"
    join_room(room)
    # send last 50 messages
    msgs = Message.query.filter_by(conversation_id=conv_id).order_by(Message.timestamp.asc()).limit(200).all()
    out = []
    for m in msgs:
        out.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'content': m.content,
            'msg_type': m.msg_type,
            'file_url': m.file_url,
            'timestamp': m.timestamp.isoformat(),
            'read': m.read
        })
    emit('history', out)

@socketio.on("game:move")
def handle_game_move(data):
    room_key = data["room_key"]
    emit("game:update", data, room=room_key)


@socketio.on("watch:load")
def load(data):
    room_key = data["room_key"]

    if room_key not in private_rooms:
        private_rooms[room_key] = {
            "users": set(),
            "host": current_user.id
        }

    # 🔥 SAVE WATCH STATE
    private_rooms[room_key]["watch_state"] = data

    emit("watch:load", data, room=room_key, include_self=False)

@socketio.on("watch:play")
def play(data):
    emit("watch:play", data, room=data["room_key"], include_self=False)

@socketio.on("watch:pause")
def pause(data):
    emit("watch:pause", data, room=data["room_key"], include_self=False)

@socketio.on("watch:seek")
def seek(data):
    emit("watch:seek", data, room=data["room_key"], include_self=False)


@socketio.on("music:play")
def music_play(data):
    room_key = data["room_key"]
    room = private_rooms.get(room_key)
    if not room or current_user.id != room["host"]:
        return
    emit("music:play", data, room=room_key, include_self=False)

@socketio.on("music:pause")
def music_pause(data):
    room_key = data["room_key"]
    room = private_rooms.get(room_key)
    if not room or current_user.id != room["host"]:
        return
    emit("music:pause", data, room=room_key, include_self=False)

@socketio.on("music:seek")
def music_seek(data):
    room_key = data["room_key"]
    room = private_rooms.get(room_key)
    if not room or current_user.id != room["host"]:
        return
    emit("music:seek", data, room=room_key, include_self=False)



@socketio.on('send_message')
def handle_send_message(data):
    conv_id = int(data.get('conv_id'))
    content = data.get('content')
    msg_type = data.get('msg_type', 'text')
    file_url = data.get('file_url')
    m = Message(conversation_id=conv_id, sender_id=current_user.id, content=content, msg_type=msg_type, file_url=file_url)
    db.session.add(m)
    db.session.commit()
    out = {
        'id': m.id,
        'conversation_id': conv_id,
        'sender_id': m.sender_id,
        'content': m.content,
        'msg_type': m.msg_type,
        'file_url': m.file_url,
        'timestamp': m.timestamp.isoformat()
    }
    room = f"conv_{conv_id}"
    emit('new_message', out, room=room)
    # optionally mark delivered for recipients who are online
    # update delivered flags in DB if someone is connected
    # (left as exercise for maturity)

@socketio.on('typing')
def handle_typing(data):
    conv_id = int(data.get('conv_id'))
    state = data.get('state', True)
    room = f"conv_{conv_id}"
    emit('typing', {'user_id': current_user.id, 'state': state}, room=room, include_self=False)

@socketio.on('private:join')
def handle_private_join(data):
    room_key = data.get('room_key')

    room = PrivateRoom.query.filter_by(key=room_key).first()
    if not room:
        emit("error", {"msg": "Room not found"})
        return

    if room_key not in private_rooms:
        private_rooms[room_key] = {
            "host": room.creator_id,
            "users": set(),
            "mode": None
        }

    users = private_rooms[room_key]["users"]

    if len(users) >= 4:
        emit("error", {"msg": "Room full"})
        return

    users.add(current_user.id)
    join_room(room_key)

    emit("private:user_count", {
        "count": len(users),
        "host": private_rooms[room_key]["host"]
    }, room=room_key)

    if "watch_state" in private_rooms[room_key]:
        emit("watch:load", private_rooms[room_key]["watch_state"])



@socketio.on('private:message')
def handle_private_message(data):
    room_key = data.get('room_key')
    msg = data.get('message')
    emit('private:message', {'user': current_user.name, 'message': msg}, room=room_key)


# Read receipt
@socketio.on('message_read')
def handle_message_read(data):
    msg_id = int(data.get('msg_id'))
    m = Message.query.get(msg_id)
    if m:
        m.read = True
        db.session.commit()
        room = f"conv_{m.conversation_id}"
        emit('message_read', {'msg_id': msg_id, 'reader_id': current_user.id}, room=room)

# ---- WebRTC signalling for 1:1 calls ----
# We'll send events: 'call:offer', 'call:answer', 'call:ice', 'call:hangup'
@socketio.on("start_call")
def start_call(data):
    emit("incoming_call", data, room=f"user_{data['to']}")

@socketio.on("call:accept")
def call_accept(data):
    room = data["room"]
    join_room(room)
    emit("call:start", room=room)

@socketio.on("call:join")
def call_join(data):
    join_room(data["room"])
    emit("call:start", room=data["room"])

@socketio.on("call:offer")
def call_offer(data):
    emit("call:offer", data, room=data["room"], include_self=False)

@socketio.on("call:answer")
def call_answer(data):
    emit("call:answer", data, room=data["room"], include_self=False)

@socketio.on("call:ice")
def call_ice(data):
    emit("call:ice", data, room=data["room"], include_self=False)


# ================== WEBRTC CALL SIGNALING ==================

@socketio.on("start_call")
def start_call(data):
    from_user = data["from"]
    to_user = data["to"]
    room = data["room"]

    emit("call:incoming", {
        "room": room,
        "from": from_user
    }, room=f"user_{to_user}")


@socketio.on("call:accept")
def call_accept(data):
    room = data["room"]
    join_room(room)
    emit("call:start", {}, room=room)


@socketio.on("call:reject")
def call_reject(data):
    emit("call:rejected", {}, room=f"user_{current_user.id}")


@socketio.on("call:join")
def call_join(data):
    room = data["room"]
    join_room(room)

    if len(rooms(room)) == 1:
        emit("call:ready", room=room)



@socketio.on("call:offer")
def call_offer(data):
    emit("call:offer", data, room=data["room"], include_self=False)


@socketio.on("call:answer")
def call_answer(data):
    emit("call:answer", data, room=data["room"], include_self=False)


@socketio.on("call:ice")
def call_ice(data):
    emit("call:ice", data, room=data["room"], include_self=False)



@socketio.on("private:module:start")
def handle_private_module_start(data):
    room_key = data["room_key"]
    module = data["module"]

    room = private_rooms.get(room_key)
    if not room or current_user.id != room["host"]:
        return

    room["mode"] = module

    emit("private:module:started", {
        "module": module
    }, room=room_key)



@socketio.on("game:start")
def handle_game_start(data):
    room_key = data["room_key"]
    game = data["game"]

    room = private_rooms.get(room_key)
    if not room or current_user.id != room["host"]:
        return

    emit("game:started", {
        "game": game
    }, room=room_key)




# Initialize DB
with app.app_context():
    db.create_all()

app.register_blueprint(ai_bp, url_prefix="/api/ai")
app.register_blueprint(private_room)
app.register_blueprint(watch_bp)
app.register_blueprint(music_bp)
app.register_blueprint(call_bp)

if __name__ == "__main__":
    print("🚀 Server running at: http://127.0.0.1:5000")
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)

