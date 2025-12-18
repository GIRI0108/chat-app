from flask import Blueprint, render_template

music_bp = Blueprint("music", __name__)

@music_bp.route("/music/<room_code>")
def music_room(room_code):
    return render_template(
        "private_modules/music.html",
        room_code=room_code
    )
