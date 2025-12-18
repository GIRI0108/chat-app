from flask import Blueprint, render_template, request

private_room = Blueprint("private_room", __name__)

ROOMS = {}   # stores active rooms

@private_room.route("/private-room")
def private_room_page():
    return render_template("private_room.html")

@private_room.route("/vibe/<code>")
def vibe_room(code):
    role = request.args.get("role")

    if role == "host":
        ROOMS[code] = True

    elif role == "user":
        if code not in ROOMS:
            return "❌ Invalid Room Code"

    return render_template(
        "vibe_dashboard.html",
        room_code=code,
        role=role
    )
