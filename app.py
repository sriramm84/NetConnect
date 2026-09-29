# app.py
import os, json, bcrypt, base64, secrets
from datetime import datetime
from flask import (Flask, render_template, request, jsonify, session,
                   redirect, url_for, send_from_directory)
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect

# --- App setup ---
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "super_secret_key_replace_this"
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

@app.after_request
def add_ngrok_skip_warning_header(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


# --- File paths & ensure directories ---
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")
MESSAGES_DIR = os.path.join(DATA_DIR, "messages")
UPLOADS_DIR = "uploads"

APPEAL_CHATS_DIR = os.path.join(DATA_DIR, "appeal_chats")
os.makedirs(APPEAL_CHATS_DIR, exist_ok=True)

APPEALS_FILE = os.path.join(DATA_DIR, "appeals.json")
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(APPEALS_FILE):
    with open(APPEALS_FILE, "w") as f:
        json.dump({}, f, indent=2)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MESSAGES_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# --- Helpers ---
def load_json(path, default=None):
    if default is None: default = {}
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2)
        return default.copy()
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default.copy()

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def append_message(room, text):
    os.makedirs(MESSAGES_DIR, exist_ok=True)
    fname = os.path.join(MESSAGES_DIR, f"{room}.txt")
    with open(fname, "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()} {text}\n")

# --- Initialize defaults if missing ---
if not os.path.exists(USERS_FILE):
    hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    save_json(USERS_FILE, {"admin": {"password": hashed, "role": "admin", "banned": False, "muted": False, "approved_rooms": []}})
if not os.path.exists(ROOMS_FILE):
    save_json(ROOMS_FILE, {"general": {"locked": False, "members": []}})

# --- In-memory state ---
connected_sids = {}   # sid -> username
user_sids = {}        # username -> set(sids)
room_requests = {}    # room -> list(username)
user_rooms = {}       # username -> current room (string)  (students only; admin may be None)

# --- Routes ---
@app.route("/")
def index():
    return render_template("login.html")

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role") or "student"
    if not username or not password:
        return jsonify({"status": "error", "message": "username and password required"}), 400
    users = load_json(USERS_FILE, {})
    if username in users:
        return jsonify({"status": "error", "message": "username exists"}), 409
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {"password": hashed, "role": role, "banned": False, "muted": False, "approved_rooms": []}
    save_json(USERS_FILE, users)
    return jsonify({"status": "success"})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    users = load_json(USERS_FILE, {})

    if username not in users:
        return jsonify({"status": "error", "message": "User not found"}), 404
    if not bcrypt.checkpw(password.encode(), users[username]["password"].encode()):
        return jsonify({"status": "error", "message": "Invalid password"}), 401
    if users[username].get("banned"):
        return jsonify({"status": "error", "message": "You are banned"}), 403

    session["username"] = username
    session["role"] = users[username]["role"]

    return jsonify({
        "status": "success",
        "username": username,
        "role": users[username]["role"]
    })

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# Role-based chat page routes (inject identity)
@app.route("/admin")
def admin_page():
    if "role" in session and session["role"] == "admin":
        return render_template("chat.html")
    return redirect(url_for("index"))

@app.route("/student")
def student_page():
    if "role" in session and session["role"] == "student":
        return render_template("chat.html")
    return redirect(url_for("index"))

@app.route("/whoami")
def whoami():
    if "username" in session and "role" in session:
        return jsonify({"username": session["username"], "role": session["role"]})
    return jsonify({"username": None, "role": None}), 401

@app.route("/rooms")
def rooms_list():
    rooms = load_json(ROOMS_FILE, {})
    out = {r: {"locked": rooms[r].get("locked", False), "members": rooms[r].get("members", [])} for r in rooms}
    return jsonify(out)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename, as_attachment=True)

@app.route("/appeal_chat_history/<username>")
def appeal_chat_history(username):
    # Only admin or the same student can access
    current = session.get("username")
    role = session.get("role")
    if role != "admin" and current != username:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    history = load_chat_history(username)
    return jsonify({"status": "success", "history": history})


# --- Socket handlers ---
@socketio.on("connect")
def on_connect():
    sid = request.sid
    username = session.get("username")
    print(f"[connect] sid={sid} username={username}")
    if username:
        connected_sids[sid] = username
        user_sids.setdefault(username, set()).add(sid)
        # update online list for clients
        emit("online_users", {"users": sorted(list(set(connected_sids.values())))}, broadcast=True)
        # send pending requests to admin sockets only
        if session.get("role") == "admin":
            emit("pending_requests", {"queue": room_requests}, room=sid)
    else:
        emit("system_message", {"msg": "Connected as guest. Please login to chat."}, room=sid)

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    username = connected_sids.pop(sid, None)
    print(f"[disconnect] sid={sid} username={username}")
    if username:
        user_sids.get(username, set()).discard(sid)
        if not user_sids.get(username):
            user_sids.pop(username, None)
        # if user had a recorded room, we keep that until they /leave or rejoin; members persisted in files
        emit("online_users", {"users": sorted(list(set(connected_sids.values())))}, broadcast=True)

# create room (admin)
@socketio.on("create_room")
def on_create_room(data):
    username = session.get("username")
    role = session.get("role")
    room = (data.get("room") or "").strip() if isinstance(data, dict) else ""
    # Basic validations
    if not username:
        emit("system_message", {"msg": "You must be logged in to create rooms."}, room=request.sid)
        return
    if role != "admin":
        emit("system_message", {"msg": "Only admins can create rooms."}, room=request.sid)
        return
    if not room:
        emit("system_message", {"msg": "Room name required."}, room=request.sid)
        return

    rooms = load_json(ROOMS_FILE, {})
    if room in rooms:
        emit("system_message", {"msg": f"Room '{room}' already exists."}, room=request.sid)
        return

    # Create and persist
    rooms[room] = {"locked": False, "members": []}
    save_json(ROOMS_FILE, rooms)

    # Broadcast to everyone so UI updates
    emit("new_room", {"room": room}, broadcast=True)
    emit("system_message", {"msg": f"Room '{room}' created by {username}."}, broadcast=True)
    # Also send a fresh rooms list to clients (optional but helpful)
    emit("rooms_list", {r: {"locked": rooms[r].get("locked", False)} for r in rooms}, broadcast=True)

# delete room (admin)
@socketio.on("delete_room")
def on_delete_room(data):
    username = session.get("username")
    print(f"[delete_room] by {username} -> {data}")
    if session.get("role") != "admin":
        emit("system_message", {"msg": "Only admins can delete rooms."}, room=request.sid)
        return
    room = (data.get("room") or "").strip()
    if not room:
        emit("system_message", {"msg": "Room name required."}, room=request.sid)
        return
    rooms = load_json(ROOMS_FILE, {})
    if room not in rooms:
        emit("system_message", {"msg": f"Room '{room}' not found."}, room=request.sid)
        return
    if room == "general":
        emit("system_message", {"msg": "Cannot delete default 'general' room."}, room=request.sid)
        return

    # --- Remove from rooms file ---
    rooms.pop(room, None)
    save_json(ROOMS_FILE, rooms)

    # --- Delete messages file ---
    try:
        os.remove(os.path.join(MESSAGES_DIR, f"{room}.txt"))
    except OSError:
        pass

    # --- Clean up requests and approvals ---
    room_requests.pop(room, None)
    users = load_json(USERS_FILE, {})
    changed = False
    for u, v in users.items():
        if "approved_rooms" in v and room in v["approved_rooms"]:
            v["approved_rooms"].remove(room)
            changed = True
    if changed:
        save_json(USERS_FILE, users)

    # --- Broadcast to everyone ---
    emit("room_deleted", {"room": room}, broadcast=True)
    emit("system_message", {"msg": f"Room '{room}' deleted by {username}"}, broadcast=True)

    # --- Force everyone in that room to leave ---
    emit("force_leave_room", {"room": room, "msg": f"The room '{room}' was deleted by admin. Please join another room."}, room=room)

# request join (student)
@socketio.on("request_join")
def on_request_join(data):
    username = session.get("username")
    room = data.get("room")
    print(f"[request_join] {username} -> {room}")
    if not username:
        emit("system_message", {"msg":"login required"}, room=request.sid); return
    rooms = load_json(ROOMS_FILE, {})
    if room not in rooms:
        emit("system_message", {"msg": f"Room '{room}' does not exist."}, room=request.sid); return
    if not rooms[room].get("locked", False):
        # auto join
        join_room(room)
        rooms[room].setdefault("members", [])
        if username not in rooms[room]["members"]:
            rooms[room]["members"].append(username)
            save_json(ROOMS_FILE, rooms)
        user_rooms[username] = room
        emit("system_message", {"msg": f"You joined '{room}'"}, room=request.sid)
        emit("system_message", {"msg": f"{username} joined '{room}'"}, room=room)
        append_message(room, f"{username} joined")
        return
    # locked -> queue
    room_requests.setdefault(room, [])
    if username in room_requests[room]:
        emit("system_message", {"msg":"Already requested"}, room=request.sid); return
    room_requests[room].append(username)
    emit("room_request", {"room": room, "user": username}, broadcast=True)
    emit("system_message", {"msg": f"Requested to join '{room}'. Await approval."}, room=request.sid)

# admin approve/deny
@socketio.on("approve_request")
def on_approve_request(data):
    admin = session.get("username")
    print(f"[approve_request] by {admin} -> {data}")
    if session.get("role") != "admin":
        emit("system_message", {"msg":"Only admins can approve."}, room=request.sid); return
    room = data.get("room"); target = data.get("user")
    rooms = load_json(ROOMS_FILE, {}); users = load_json(USERS_FILE, {})
    if room not in room_requests or target not in room_requests[room]:
        emit("system_message", {"msg":"No such pending request."}, room=request.sid); return
    users.setdefault(target, {}).setdefault("approved_rooms", [])
    if room not in users[target]["approved_rooms"]:
        users[target]["approved_rooms"].append(room)
    save_json(USERS_FILE, users)
    room_requests[room].remove(target)
    for sid in list(user_sids.get(target, [])):
        emit("system_message", {"msg": f"You were approved to join '{room}' by {admin}"}, room=sid)
    emit("system_message", {"msg": f"{admin} approved {target} for '{room}'"}, broadcast=True)
    emit("pending_requests", {"queue": room_requests}, broadcast=True)

@socketio.on("deny_request")
def on_deny_request(data):
    admin = session.get("username")
    print(f"[deny_request] by {admin} -> {data}")
    if session.get("role") != "admin":
        emit("system_message", {"msg":"Only admins can deny."}, room=request.sid); return
    room = data.get("room"); target = data.get("user")
    if room in room_requests and target in room_requests[room]:
        room_requests[room].remove(target)
    emit("system_message", {"msg": f"{admin} denied {target} for '{room}'"}, broadcast=True)
    emit("pending_requests", {"queue": room_requests}, broadcast=True)

# join_room (after approval or auto join)
@socketio.on("join_room")
def on_join_room_event(data):
    room = data.get("room")
    username = session.get("username")
    role = session.get("role")
    print(f"[join_room] {username} -> {room} (role={role})")
    if not username:
        emit("system_message", {"msg": "Please login before joining a room."}, room=request.sid)
        return
    rooms = load_json(ROOMS_FILE, {})
    users = load_json(USERS_FILE, {})
    if room not in rooms:
        emit("system_message", {"msg": f"Room '{room}' does not exist."}, room=request.sid)
        return
    locked = rooms[room].get("locked", False)
    approved_rooms = users.get(username, {}).get("approved_rooms", [])
    if locked and room not in approved_rooms and role != "admin":
        emit("system_message", {"msg": f"'{room}' is locked. Request access first using /request {room}."}, room=request.sid)
        return
    # student: enforce single-room membership
    if role == "student":
        for rname, rinfo in rooms.items():
            if username in rinfo.get("members", []) and rname != room:
                rinfo["members"].remove(username)
        save_json(ROOMS_FILE, rooms)
    # join socket.io room (for this socket)
    join_room(room)
    rooms[room].setdefault("members", [])
    if username not in rooms[room]["members"]:
        rooms[room]["members"].append(username)
    save_json(ROOMS_FILE, rooms)
    user_rooms[username] = room
    emit("system_message", {"msg": f"You joined '{room}'"}, room=request.sid)
    emit("system_message", {"msg": f"{username} joined '{room}'"}, room=room)
    append_message(room, f"{username} joined the room")
    print(f"[JOIN] {username} joined {room} (role={role})")

# chat messages (and commands)
@socketio.on("chat_message")
def on_chat_message(data):
    username = session.get("username")
    room = data.get("room")
    msg = data.get("msg", "")
    print(f"[chat_message] {username} @ {room}: {msg[:80]}")
    if not username:
        emit("system_message", {"msg": "Login required to send messages."}, room=request.sid)
        return
    users = load_json(USERS_FILE, {})
    role = users.get(username, {}).get("role", "student")
    if users.get(username, {}).get("banned"):
        emit("system_message", {"msg": "You are banned."}, room=request.sid)
        return
    if users.get(username, {}).get("muted"):
        emit("system_message", {"msg": "You are muted."}, room=request.sid)
        return
    if not room:
        emit("system_message", {"msg": "Choose a room first."}, room=request.sid)
        return
    # Non-admins must be in the room to send messages/commands
    if role != "admin" and user_rooms.get(username) != room:
        emit("system_message", {"msg": "You must join that room before chatting."}, room=request.sid)
        return
    # Commands
    if msg.startswith("/"):
        handle_command(username, room, msg)
        return
    timestamp = datetime.utcnow().strftime("%H:%M")
    append_message(room, f"[{timestamp}] {username}: {msg}")
    # Broadcast to everyone who has joined that Socket.IO room
    emit("message", {
        "user": username,
        "role": role,
        "msg": msg,
        "time": timestamp
    }, room=room)

# file upload (client sends dataURL string)
@socketio.on("file_upload")
def on_file_upload(data):
    username = session.get("username")
    room = data.get("room")
    filename = data.get("filename")
    dataurl = data.get("data")  # data:[type];base64,AAAA...
    print(f"[file_upload] {username} @ {room}: {filename}")
    if not (username and room and filename and dataurl):
        emit("system_message", {"msg":"Invalid file upload"}, room=request.sid); return
    users = load_json(USERS_FILE, {})
    role = users.get(username, {}).get("role", "student")
    # Non-admins must be in the room
    if role != "admin" and user_rooms.get(username) != room:
        emit("system_message", {"msg": "You must join that room before sending files."}, room=request.sid)
        return
    # decode base64
    try:
        header, b64 = dataurl.split(",",1)
        binary = base64.b64decode(b64)
    except Exception as e:
        emit("system_message", {"msg":"Failed to decode file"}, room=request.sid); return
    safe = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{os.path.basename(filename)}"
    path = os.path.join(UPLOADS_DIR, safe)
    with open(path, "wb") as f:
        f.write(binary)
    url = url_for("uploaded_file", filename=safe)
    append_message(room, f"{username} sent file {filename} -> {safe}")
    emit("file_shared", {"user": username, "name": filename, "url": url}, room=room)

def load_appeals():
    return load_json(APPEALS_FILE, {})

def save_appeals(data):
    save_json(APPEALS_FILE, data)

# commands handler
def handle_command(username, room, msg):
    users = load_json(USERS_FILE, {})
    rooms = load_json(ROOMS_FILE, {})
    parts = msg.strip().split()
    cmd = parts[0].lower()
    role = users.get(username, {}).get("role", "student")

    admin_cmds = {"/mute","/unmute","/ban","/unban","/kick","/lock","/unlock","/approve","/deny","/delete"}
    student_cmds = {"/who","/help","/leave","/request"}

    # Non-admins must be in a room to execute commands
    if role != "admin" and user_rooms.get(username) != room:
        emit("system_message", {"msg":"Join a room first to run commands."}, room=request.sid); return

    if cmd == "/help":
        if role == "admin":
            help_text = "Admin: /who /help /create <room> /delete <room> /lock <room> /unlock <room> /mute <user> /unmute <user> /ban <user> /unban <user> /approve <user> <room> /deny <user> <room> /kick <user>"
        else:
            help_text = "Student: /who /help /leave /request <room>"
        emit("system_message", {"msg": help_text}, room=request.sid); return

    if cmd == "/who":
        online = sorted(list(set(connected_sids.values())))
        emit("system_message", {"msg": "Online: " + ", ".join(online)}, room=request.sid); return

    if cmd == "/leave":
        # let user leave the room
        leave_room(room)
        if room in rooms and username in rooms[room].get("members", []):
            rooms[room]["members"].remove(username)
            save_json(ROOMS_FILE, rooms)
        user_rooms.pop(username, None)
        emit("system_message", {"msg": f"{username} left {room}"}, room=room)
        emit("system_message", {"msg": f"You left {room}"}, room=request.sid); return

    if cmd == "/request":
        if len(parts) < 2:
            emit("system_message", {"msg":"Use /request <room>"}, room=request.sid); return
        r = parts[1]
        if r not in rooms:
            emit("system_message", {"msg":f"Room '{r}' not found"}, room=request.sid); return
        socketio.emit("room_request", {"room": r, "user": username}, broadcast=True)
        room_requests.setdefault(r, [])
        if username not in room_requests[r]:
            room_requests[r].append(username)
        emit("system_message", {"msg": f"Requested to join {r}"}, room=request.sid); return

    # Admin actions (must be admin)
    if cmd in admin_cmds and role != "admin":
        emit("system_message", {"msg":"Admin-only command"}, room=request.sid); return

    if cmd == "/mute" and len(parts) >= 2:
        t = parts[1]; users.setdefault(t, {})["muted"] = True; save_json(USERS_FILE, users)
        emit("system_message", {"msg": f"{t} muted by {username}"}, broadcast=True); return
    if cmd == "/unmute" and len(parts) >= 2:
        t = parts[1]; users.setdefault(t, {})["muted"] = False; save_json(USERS_FILE, users)
        emit("system_message", {"msg": f"{t} unmuted by {username}"}, broadcast=True); return
    if cmd == "/ban" and len(parts) >= 2:
        t = parts[1]; users.setdefault(t, {})["banned"] = True; save_json(USERS_FILE, users)
        for sid in list(user_sids.get(t, [])):
            try:
                emit("system_message", {"msg":"You have been banned. Please visit /appeal to request unban."}, room=sid)
                disconnect(sid)
            except: pass
        emit("system_message", {"msg": f"{t} banned by {username}"}, broadcast=True); return
    if cmd == "/unban" and len(parts) >= 2:
        t = parts[1]; users.setdefault(t, {})["banned"] = False; save_json(USERS_FILE, users)
        emit("system_message", {"msg": f"{t} unbanned by {username}"}, broadcast=True); return
    if cmd == "/kick" and len(parts) >= 2:
        t = parts[1]
        for sid in list(user_sids.get(t, [])):
            try:
                emit("system_message", {"msg":"You were kicked by admin. Visit /appeal to request access again."}, room=sid)

                disconnect(sid)
            except: pass
        emit("system_message", {"msg": f"{t} kicked by {username}"}, broadcast=True); return
    if cmd == "/lock" and len(parts) >= 2:
        r = parts[1]; rooms.setdefault(r, {})["locked"] = True; save_json(ROOMS_FILE, rooms)
        emit("system_message", {"msg": f"Room {r} locked by {username}"}, broadcast=True); return
    if cmd == "/unlock" and len(parts) >= 2:
        r = parts[1]; rooms.setdefault(r, {})["locked"] = False; save_json(ROOMS_FILE, rooms)
        emit("system_message", {"msg": f"Room {r} unlocked by {username}"}, broadcast=True); return
    if cmd == "/approve" and len(parts) >= 3:
        t = parts[1]; r = parts[2]
        udata = load_json(USERS_FILE, {})
        udata.setdefault(t, {}).setdefault("approved_rooms", [])
        if r not in udata[t]["approved_rooms"]:
            udata[t]["approved_rooms"].append(r)
        save_json(USERS_FILE, udata)
        if r in room_requests and t in room_requests[r]:
            room_requests[r].remove(t)
        emit("system_message", {"msg": f"{t} approved for {r} by {username}"}, broadcast=True)
        for sid in list(user_sids.get(t, [])):
            emit("system_message", {"msg": f"You were approved to join {r} by {username}"}, room=sid)
        emit("pending_requests", {"queue": room_requests}, broadcast=True); return
    if cmd == "/deny" and len(parts) >= 3:
        t = parts[1]; r = parts[2]
        if r in room_requests and t in room_requests[r]:
            room_requests[r].remove(t)
        emit("system_message", {"msg": f"{t} denied for {r} by {username}"}, broadcast=True)
        emit("pending_requests", {"queue": room_requests}, broadcast=True); return
    if cmd == "/delete" and len(parts) >= 2:
        # admin shortcut: /delete roomname
        r = parts[1]
        # re-use delete_room logic -> call the handler by emitting internally
        on_delete_room({"room": r})
        return

    emit("system_message", {"msg":"Unknown command or wrong usage."}, room=request.sid)
# --- Appeal form for banned/kicked users ---
@app.route("/appeal")
def appeal_page():
    return render_template("appeal.html")

@app.route("/appeal_chat/<username>")
def appeal_chat(username):
    current_user = session.get("username")
    role = session.get("role")

    # ✅ Admin opens chat with any student
    if role == "admin":
        return render_template("appeal_chat.html", user=username)

    # ✅ Student opens chat only with admin
    if current_user == username and role == "student":
        return render_template("appeal_chat.html", user="admin")

    # ❌ Everyone else is redirected
    return redirect(url_for("index"))


@app.route("/submit_appeal", methods=["POST"])
def submit_appeal():
    data = request.get_json() or {}
    username = data.get("username")
    reason = data.get("reason", "").strip()
    if not username or not reason:
        return jsonify({"status":"error","message":"Missing username or reason"}),400

    appeals = load_appeals()
    appeals[username] = {"reason":reason, "timestamp": datetime.utcnow().isoformat()}
    save_appeals(appeals)

    # ✅ Notify all connected admins in real-time
    for sid, uname in connected_sids.items():
        user_data = load_json(USERS_FILE, {})
        if uname in user_data and user_data[uname].get("role") == "admin":
            socketio.emit("new_appeal", {"user": username, "reason": reason}, room=sid)

    return jsonify({"status":"success"})


# --- Admin view for all appeals ---
@app.route("/appeals")
def view_appeals():
    if session.get("role") != "admin":
        return redirect(url_for("index"))
    appeals = load_appeals()
    return render_template("appeal_table.html", appeals=appeals)


# --- Unban handler from admin ---
@app.route("/unban_user", methods=["POST"])
def unban_user():
    if session.get("role") != "admin":
        return jsonify({"status":"error","message":"Unauthorized"}),403
    data = request.get_json() or {}
    target = data.get("username")
    users = load_json(USERS_FILE, {})
    appeals = load_appeals()
    if target in users:
        users[target]["banned"] = False
        save_json(USERS_FILE, users)
        if target in appeals:
            appeals.pop(target)
            save_appeals(appeals)
        return jsonify({"status":"success"})
    return jsonify({"status":"error","message":"User not found"}),404
# --- Private chat between admin and banned/kicked users ---@socketio.on("appeal_chat_message")
@socketio.on("appeal_chat_message")
def handle_appeal_chat(data):
    sender = session.get("username")
    role = session.get("role")
    target = data.get("to")
    msg = data.get("msg", "").strip()
    print(f"[appeal_chat_message] {sender} -> {target}: {msg}")

    if not sender or not msg:
        return

    # Student → Admin
    if target == "admin":
        save_chat_message(sender, sender, msg)
        users = load_json(USERS_FILE, {})
        for sid, uname in connected_sids.items():
            if uname in users and users[uname].get("role") == "admin":
                emit("appeal_chat_message", {"from": sender, "msg": msg}, room=sid)
                emit("new_appeal_message", {"from": sender, "msg": msg}, room=sid)

    # Admin → Student
    elif target:
        save_chat_message(target, sender, msg)
        if target in user_sids:
            for sid in user_sids[target]:
                emit("appeal_chat_message", {"from": sender, "msg": msg}, room=sid)

    # Echo back to sender
    emit("appeal_chat_message", {"from": sender, "msg": msg}, room=request.sid)

@app.route("/appeal_chat/<username>")
def appeal_chat_admin(username):
    if session.get("role") != "admin":
        return redirect(url_for("index"))
    return render_template("appeal_chat.html", user=username)

def load_chat_history(username):
    path = os.path.join(APPEAL_CHATS_DIR, f"{username}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_chat_message(username, sender, msg):
    path = os.path.join(APPEAL_CHATS_DIR, f"{username}.json")
    history = load_chat_history(username)
    history.append({
        "from": sender,
        "msg": msg,
        "timestamp": datetime.utcnow().strftime("%H:%M")
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

# --- Run ---
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5002, debug=True)
