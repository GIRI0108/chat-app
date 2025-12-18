from flask import Blueprint, render_template

call_bp = Blueprint("call", __name__)

@call_bp.route("/call")
def call_page():
    return render_template("call.html")
