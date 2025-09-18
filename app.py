
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect
import os, datetime, csv
from werkzeug.security import generate_password_hash, check_password_hash

# optional import if available
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    SIA_AVAILABLE = True
except Exception:
    SIA_AVAILABLE = False

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE, "static")

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=STATIC_DIR)
# Simple in-memory DB (demo)
DB = {"users": [], "chat_logs": [], "assessments": []}

# Serve homepage (login)
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "login.html")

# Serve any static page
@app.route("/<path:filename>")
def static_pages(filename):
    if os.path.exists(os.path.join(STATIC_DIR, filename)):
        return send_from_directory(STATIC_DIR, filename)
    # fallback to index
    return send_from_directory(STATIC_DIR, "login.html")

# Auth endpoints
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"message":"missing fields"}), 400
    if any(u["username"]==username for u in DB["users"]):
        return jsonify({"message":"user exists"}), 400
    DB["users"].append({"id":len(DB["users"])+1, "username":username, "password":generate_password_hash(password)})
    return jsonify({"ok":True}), 200

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    user = next((u for u in DB["users"] if u["username"]==username), None)
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"message":"invalid credentials"}), 401
    return jsonify({"ok":True, "user_id": user["id"]})

# Chatbot endpoint (simple sentiment responder + echo)
@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.json or {}
    text = payload.get("text","").strip()
    if not text:
        return jsonify({"reply":"Please send a message."})
    # analyze sentiment if available
    score = None
    label = "neutral"
    if SIA_AVAILABLE:
        sia = SentimentIntensityAnalyzer()
        s = sia.polarity_scores(text)
        score = s["compound"]
        if score >= 0.5:
            label = "positive"
        elif score <= -0.5:
            label = "negative"
        else:
            label = "neutral"
    else:
        score = 0.0
    reply = f"I hear you. (sentiment: {label}) — You said: {text}"
    # log
    DB["chat_logs"].append({"text":text, "label":label, "score": score, "timestamp":str(datetime.datetime.utcnow())})
    return jsonify({"reply":reply, "label":label, "score":score})

# Simple assessment endpoint (mirrors existing inference.py if present)
@app.route("/api/assess", methods=["POST"])
def assess():
    data = request.json or {}
    user_id = data.get("user_id", None)
    responses = data.get("responses", {})
    # Very simple risk logic
    score = sum([int(v) for v in responses.values() if str(v).isdigit()])
    risk = "low"
    if score > 7:
        risk = "high"
    elif score > 3:
        risk = "moderate"
    DB["assessments"].append({"user_id":user_id, "score":score, "risk":risk, "timestamp":str(datetime.datetime.utcnow())})
    return jsonify({"risk":risk, "score":score})

# Export logs
@app.route("/api/history", methods=["GET"])
def history():
    return jsonify(DB["chat_logs"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
