# app.py
from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set in environment")

# Replace model path if you prefer a different Gemini model.
# Keep the :generateContent suffix.
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

app = Flask(__name__, template_folder="templates", static_folder="static")

# Very simple content-safety keyword filter (basic). We'll block obvious dangerous topics.
BLOCKED_WORDS = {"bomb", "weapon", "kill", "suicide", "explode", "terror", "drugs"}

def is_safe_text(text: str):
    t = (text or "").lower()
    for w in BLOCKED_WORDS:
        if w in t:
            return False, w
    return True, None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True, silent=True) or {}
    message = body.get("message", "").strip()
    subject = (body.get("subject") or "general").strip().lower()
    grade = int(body.get("grade") or 5)

    if not message:
        return jsonify({"error":"Please type a question."}), 400

    safe, bad = is_safe_text(message)
    if not safe:
        return jsonify({"reply": "Sorry, I can't help with that. If you need help, please ask your teacher or an adult."}), 403

    # Build a kid-friendly system prompt
    # Keep it short; Gemini will be instructed about tone and length
    system_prompt = (
        f"You are a friendly, encouraging {subject} tutor for a Grade {grade} student. "
        "Use very simple words and short steps. Give a short explanation (2-5 sentences) "
        "and end with a 1-line practice question or small exercise. Use positive language and an emoji."
    )

    final_prompt = f"{system_prompt}\n\nStudent asks: {message}\n\nAnswer:"

    payload = {
        "contents": [
            {"parts": [{"text": final_prompt}]}
        ]
    }

    try:
        # Use API key as query param (works with API key). Timeout to avoid hangs.
        resp = requests.post(f"{BASE_URL}?key={API_KEY}", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return jsonify({"reply": f"❌ Error contacting Gemini API: {str(e)}"}), 500

    # Extract reply safely (defensive)
    reply = "⚠️ No answer returned"
    try:
        # old-style response: "candidates" -> first -> content -> parts -> first -> text
        candidates = data.get("candidates")
        if isinstance(candidates, list) and len(candidates) > 0:
            reply = candidates[0].get("content", {}).get("parts", [])[0].get("text", reply)
        else:
            # newer variants may put text elsewhere; attempt other keys
            if "output" in data:
                reply = data["output"].get("text", reply)
            elif "result" in data:
                reply = str(data["result"])
            else:
                # fallback to whole JSON as string (for debugging)
                reply = str(data)
    except Exception:
        reply = str(data)

    return jsonify({"reply": reply})

if __name__ == "__main__":
    # Run with: python app.py
    app.run(host="127.0.0.1", port=5000, debug=True)
