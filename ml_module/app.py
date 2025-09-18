from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, pickle, json, sqlite3, hashlib, datetime, numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE, "rf_stress_model.pkl")

# Load behavior model (prototype). If not found, behavior_model remains None.
behavior_model = None
label_encoder = None
feature_order = None
if os.path.exists(MODEL_PATH):
    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)
        behavior_model = data.get("model")
        label_encoder = data.get("label_encoder")
        feature_order = data.get("features")

# Simple questionnaire model: map numeric score to Low/Medium/High
def questionnaire_label(score):
    if score is None:
        return "Unknown"
    try:
        s = float(score)
    except:
        s = 0.0
    if s >= 8:
        return "High"
    if s >= 4:
        return "Medium"
    return "Low"

# Utility: anonymize ID
def anonymize_id(s):
    if s is None:
        s = "anon"
    return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:12]

# Database (SQLite) setup
DBPATH = os.path.join(BASE, "medcare.db")
def init_db():
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS consent (id INTEGER PRIMARY KEY, user_id TEXT, consent INTEGER, ts TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS assessments (id INTEGER PRIMARY KEY, user_id TEXT, score INTEGER, label TEXT, answers TEXT, ts TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user_id TEXT, name TEXT, email TEXT, created_at TEXT)')
    conn.commit(); conn.close()

init_db()

app = Flask(__name__)
CORS(app)

SUGGESTIONS = {
    "Low": ["Keep regular sleep, short daily walks, one weekly journal entry."],
    "Medium": ["Try 10 minutes breathing twice a day, reduce continuous screen time, brief walk."],
    "High": ["Consider contacting a mental health professional. Start daily grounding exercises."]
}

@app.route("/consent", methods=["POST"])
def consent():
    payload = request.get_json() or {}
    user_id = payload.get("user_id") or "anonymous"
    consent_flag = 1 if payload.get("consent", True) else 0
    ts = payload.get("ts") or datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("INSERT INTO consent (user_id, consent, ts) VALUES (?,?,?)", (anonymize_id(user_id), consent_flag, ts))
    conn.commit(); conn.close()
    return jsonify({"status":"ok"}), 201

@app.route("/api/assessment", methods=["POST"])
def store_assessment():
    payload = request.get_json() or {}
    user_id = payload.get("user_id") or "guest"
    score = int(payload.get("score", 0))
    label = payload.get("label") or questionnaire_label(score)
    answers = json.dumps(payload.get("answers", []))
    ts = payload.get("ts") or datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("INSERT INTO assessments (user_id, score, label, answers, ts) VALUES (?,?,?,?,?)", (anonymize_id(user_id), score, label, answers, ts))
    conn.commit(); conn.close()
    return jsonify({"status":"saved","label":label}), 201

@app.route("/api/user/<uid>/history", methods=["GET"])
def user_history(uid):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    rows = c.execute("SELECT id, score, label, answers, ts FROM assessments WHERE user_id=? ORDER BY ts DESC", (anonymize_id(uid),)).fetchall()
    conn.close()
    data = [{"id":r[0],"score":r[1],"label":r[2],"answers": json.loads(r[3]) if r[3] else [], "ts": r[4]} for r in rows]
    return jsonify(data)

@app.route("/admin/export", methods=["GET"])
def admin_export():
    # Return anonymized CSV of assessments
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    rows = c.execute("SELECT user_id, score, label, answers, ts FROM assessments ORDER BY ts DESC").fetchall()
    conn.close()
    import csv, io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["anon_user","score","label","answers","ts"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4]])
    out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='assessments_export.csv')

@app.route("/api/delete_user/<uid>", methods=["DELETE"])
def delete_user(uid):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("DELETE FROM assessments WHERE user_id=?", (anonymize_id(uid),))
    c.execute("DELETE FROM consent WHERE user_id=?", (anonymize_id(uid),))
    conn.commit(); conn.close()
    return jsonify({"status":"deleted"})

@app.route("/predict", methods=["POST"])
def predict():
    # Behavior-only prediction (keeps backward compatibility)
    payload = request.get_json() or {}
    if behavior_model is None or feature_order is None:
        return jsonify({"error":"behavior model not available"}), 500
    try:
        x = [float(payload.get(f, 0.0)) for f in feature_order]
        pred = behavior_model.predict([x])[0]
        label = label_encoder.inverse_transform([pred])[0] if label_encoder is not None else str(pred)
        probs = behavior_model.predict_proba([x])[0].tolist() if hasattr(behavior_model, "predict_proba") else []
        return jsonify({"prediction": label, "probabilities": probs, "suggestions": SUGGESTIONS.get(label,[]) })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/predict_fused", methods=["POST"])
def predict_fused():
    """
    Accepts JSON with:
     - questionnaire_score (numeric)
     - behavior_features: dict of features matching feature_order
    Returns fused label, probabilities, and explanation.
    """
    payload = request.get_json() or {}
    q_score = payload.get("questionnaire_score", None)
    behavior_features = payload.get("behavior_features", {})
    q_label = questionnaire_label(q_score)
    b_label = None
    b_probs = None
    if behavior_model is not None and feature_order is not None:
        try:
            x = [float(behavior_features.get(f, 0.0)) for f in feature_order]
            pred = behavior_model.predict([x])[0]
            b_label = label_encoder.inverse_transform([pred])[0] if label_encoder is not None else str(pred)
            b_probs = behavior_model.predict_proba([x])[0].tolist() if hasattr(behavior_model, "predict_proba") else None
        except Exception as e:
            b_label = None
    # Fusion strategy: prefer High if either indicates High; else use weighted preference to questionnaire
    final_label = "Unknown"
    if q_label == "High" or b_label == "High":
        final_label = "High"
    else:
        # use questionnaire as primary
        final_label = q_label if q_label is not None else (b_label or "Unknown")
    explanation = {"questionnaire_label": q_label, "behavior_label": b_label, "method": "rule_based_fusion"}
    suggestions = SUGGESTIONS.get(final_label, [])
    return jsonify({"label": final_label, "explanation": explanation, "behavior_probs": b_probs, "suggestions": suggestions})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
