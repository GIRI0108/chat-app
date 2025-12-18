import time
from flask import Blueprint, render_template, request, redirect, url_for
from flask_socketio import emit

watch_bp = Blueprint("watch", __name__)

# In-memory room state
watch_rooms = {}

@watch_bp.route("/watch/<room_id>")
def watch_room(room_id):
    return render_template("watch.html", room_id=room_id)


@watch_bp.route("/watch/join/<room_id>")
def join_watch(room_id):
    room = watch_rooms.get(room_id)

    if not room:
        return "Room not found", 404

    return render_template(
        "watch_join.html",
        video_id=room["video_id"],
        started_at=room["started_at"]
    )


# SOCKET — host loads video
def register_watch_socket(socketio):

    @socketio.on("watch:load")
    def handle_watch_load(data):
        room_id = data["room"]
        video_id = data["video_id"]

        watch_rooms[room_id] = {
            "video_id": video_id,
            "started_at": time.time()
        }

        emit("watch:loaded", {"status": "ok"}, room=room_id)
