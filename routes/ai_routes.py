from flask import Blueprint, request, jsonify
from flask_login import login_required
from openai import OpenAI
import os

ai_bp = Blueprint("ai", __name__)
client = OpenAI(api_key=os.getenv("AI_API_KEY"))

@ai_bp.route("/assistant", methods=["POST"])
@login_required
def ai_assistant():
    data = request.json
    action = data.get("action")
    text = data.get("text")

    prompt = ""

    if action == "summarize":
        prompt = f"Summarize this chat conversation in short, clear points:\n\n{text}"

    elif action == "translate":
        lang = data.get("lang")
        prompt = f"Translate the following text to {lang}:\n\n{text}"

    elif action == "improve":
        prompt = f"Rewrite this message with better grammar and clarity:\n\n{text}"

    elif action == "explain":
        prompt = f"Explain the meaning of this text in simple words:\n\n{text}"

    elif action == "reply":
        prompt = f"Generate a natural chat reply for this message:\n\n{text}"

    else:
        return jsonify({"error": "Unknown action"}), 400

    # AI Call
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt}]
    )

    ai_output = response.choices[0].message["content"]
    return jsonify({"output": ai_output})
