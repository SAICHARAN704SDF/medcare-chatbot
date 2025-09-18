#!/usr/bin/env python3
"""MEDCARE integrated app.py with optional LLM support (OpenAI).
Set OPENAI_API_KEY in environment to enable LLM features in /llm_chat and /summarize_assessment.
"""

import os, sqlite3, json, hashlib, datetime, pickle, io, csv, traceback
from flask import Flask, request, jsonify, session, redirect, send_from_directory, send_file, abort

# Optional LLM client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
use_openai = False
try:
    if OPENAI_API_KEY:
        import openai
        openai.api_key = OPENAI_API_KEY
        use_openai = True
except Exception as e:
    print("OpenAI not available:", e)

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE, "static")
ML_DIR = os.path.join(BASE, "ml_module")
DB_PATH = os.path.join(ML_DIR, "medcare.db")

os.makedirs(ML_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user_id TEXT UNIQUE, name TEXT, email TEXT, created_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS consent (id INTEGER PRIMARY KEY, user_id TEXT, consent INTEGER, ts TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS assessments (id INTEGER PRIMARY KEY, user_id TEXT, score INTEGER, label TEXT, answers TEXT, ts TEXT)')
    conn.commit(); conn.close()

init_db()

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
app.secret_key = os.environ.get("MEDCARE_SECRET","medcare_dev_secret_change_me")
ADMIN_PASSWORD = os.environ.get("MEDCARE_ADMIN_PWD", "medcare_admin_pass")

# try loading model
behavior_model = None
label_encoder = None
feature_order = None
for fname in ["rf_stress_model.pkl","rf_stress_model_kaggle.pkl","ensemble_model.pkl"]:
    p = os.path.join(ML_DIR, fname)
    if os.path.exists(p):
        try:
            with open(p,"rb") as f:
                data = pickle.load(f)
                if isinstance(data, dict) and "model" in data:
                    behavior_model = data.get("model")
                    label_encoder = data.get("label_encoder", None)
                    feature_order = data.get("features", None)
                else:
                    behavior_model = data
                print("Loaded model from", p)
                break
        except Exception as e:
            print("Error loading model:", e)

def anonymize_id(s):
    return hashlib.sha256(str(s).encode('utf-8')).hexdigest()[:12]

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

# serve known static pages explicitly to avoid route conflicts
pages = ["onboarding","dashboard","assessment","admin","chatbot","music","education","plan","student_resources","predict","signup","login","index"]
for pg in pages:
    @app.route(f"/{pg}")
    def serve_page(pg=pg):
        path = os.path.join(STATIC_DIR, f"{pg}.html")
        if os.path.exists(path):
            return send_from_directory(STATIC_DIR, f"{pg}.html")
        return abort(404)

@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(os.path.join(STATIC_DIR,"assets"), filename)

# Auth endpoints
@app.route("/register", methods=["POST"])
def register():
    payload = request.get_json() or {}
    user_id = payload.get("user_id")
    name = payload.get("name","")
    email = payload.get("email","")
    if not user_id:
        return jsonify({"error":"user_id required"}),400
    ts = datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id,name,email,created_at) VALUES (?,?,?,?)",(user_id,name,email,ts))
    conn.commit(); conn.close()
    session['user_id']=user_id
    return jsonify({"status":"ok","user_id":user_id})

@app.route("/login", methods=["POST"])
def login():
    payload = request.get_json() or {}
    user_id = payload.get("user_id")
    if not user_id:
        return jsonify({"error":"user_id required"}),400
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id,name,email,created_at) VALUES (?,?,?,?)",(user_id,"","",datetime.datetime.utcnow().isoformat()))
    conn.commit(); conn.close()
    session['user_id']=user_id
    return jsonify({"status":"logged_in","user_id":user_id})

@app.route("/logout")
def logout():
    session.pop('user_id',None)
    return redirect("/")

@app.route("/consent", methods=["POST"])
def consent():
    payload = request.get_json() or {}
    user_id = payload.get("user_id", session.get("user_id","guest"))
    consent_flag = 1 if payload.get("consent", True) else 0
    ts = payload.get("ts") or datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("INSERT INTO consent (user_id,consent,ts) VALUES (?,?,?)",(anonymize_id(user_id),consent_flag,ts))
    conn.commit(); conn.close()
    return jsonify({"status":"ok"})

@app.route("/api/assessment", methods=["POST"])
def api_assessment():
    payload = request.get_json() or {}
    user_id = payload.get("user_id", session.get("user_id","guest"))
    score = int(payload.get("score",0))
    label = payload.get("label") or ("High" if score>=75 else "Medium" if score>=45 else "Low")
    answers = json.dumps(payload.get("answers",[]))
    ts = payload.get("ts") or datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("INSERT INTO assessments (user_id,score,label,answers,ts) VALUES (?,?,?,?,?)",(anonymize_id(user_id),score,label,answers,ts))
    conn.commit(); conn.close()
    return jsonify({"status":"saved","label":label})

@app.route("/api/user/<uid>/history", methods=["GET"])
def user_history(uid):
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    rows = c.execute("SELECT id,score,label,answers,ts FROM assessments WHERE user_id=? ORDER BY ts DESC",(anonymize_id(uid),)).fetchall()
    conn.close()
    data = [{"id":r[0],"score":r[1],"label":r[2],"answers": json.loads(r[3]) if r[3] else [], "ts": r[4]} for r in rows]
    return jsonify(data)

def is_admin_request(r):
    pwd = request.args.get("admin_pwd") or request.headers.get("X-ADMIN-PWD")
    return pwd == ADMIN_PASSWORD

@app.route("/admin/export", methods=["GET"])
def admin_export():
    if not is_admin_request(request):
        return jsonify({"error":"admin pwd required as query param ?admin_pwd=..."}),401
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    rows = c.execute("SELECT user_id,score,label,answers,ts FROM assessments ORDER BY ts DESC").fetchall()
    conn.close()
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(["anon_user","score","label","answers","ts"])
    for r in rows: writer.writerow(r)
    out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='assessments_export.csv')

@app.route("/api/delete_user/<uid>", methods=["DELETE"])
def api_delete_user(uid):
    if not is_admin_request(request):
        return jsonify({"error":"admin pwd required"}),401
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("DELETE FROM assessments WHERE user_id=?", (anonymize_id(uid),))
    c.execute("DELETE FROM consent WHERE user_id=?", (anonymize_id(uid),))
    conn.commit(); conn.close()
    return jsonify({"status":"deleted"})

@app.route("/predict", methods=["POST"])
def predict():
    if behavior_model is None:
        return jsonify({"error":"behavior model not available"}), 500
    payload = request.get_json() or {}
    if feature_order:
        try:
            x = [float(payload.get(f,0.0)) for f in feature_order]
        except Exception as e:
            return jsonify({"error":"invalid features", "details": str(e)}),400
    else:
        fv = payload.get("features") or payload
        if isinstance(fv, list): x = fv
        else:
            keys = sorted(list(fv.keys())); x = [float(fv[k]) for k in keys]
    try:
        pred = behavior_model.predict([x])[0]
        probs = behavior_model.predict_proba([x])[0].tolist() if hasattr(behavior_model,"predict_proba") else []
        label = None
        if label_encoder is not None:
            try:
                label = label_encoder.inverse_transform([pred])[0]
            except:
                label = str(pred)
        else:
            label = str(pred)
        return jsonify({"prediction":label,"probabilities":probs})
    except Exception as e:
        traceback.print_exc(); return jsonify({"error":str(e)}),500

@app.route("/predict_fused", methods=["POST"])
def predict_fused():
    payload = request.get_json() or {}
    q_score = payload.get("questionnaire_score", None)
    behavior = payload.get("behavior_features", {})
    def q_label(s):
        try: s=float(s)
        except: s=0.0
        if s>=75: return "High"
        if s>=45: return "Medium"
        return "Low"
    qlbl = q_label(q_score); blbl=None
    if behavior_model is not None and feature_order is not None:
        try:
            x = [float(behavior.get(f,0.0)) for f in feature_order]
            p = behavior_model.predict([x])[0]
            blbl = label_encoder.inverse_transform([p])[0] if label_encoder is not None else str(p)
        except Exception as e:
            blbl = None
    final = "Unknown"
    if qlbl=="High" or blbl=="High": final="High"
    else: final = qlbl if qlbl else (blbl or "Unknown")
    return jsonify({"label":final,"questionnaire_label":qlbl,"behavior_label":blbl})

@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json() or {}
    user_id = payload.get("user_id", session.get("user_id","guest"))
    msg = (payload.get("message") or "").strip()
    if not msg: return jsonify({"reply":"I didn't get that. Can you tell me more?"})
    l = msg.lower()
    # emergency checks
    if any(x in l for x in ["panic","panic attack","can't breathe","panicattack"]):
        return jsonify({"reply":"Try 4-4-6 breathing. If you feel unsafe, contact local emergency services."})
    if any(x in l for x in ["suicid","kill myself","end my life","die"]):
        return jsonify({"reply":"I can't help in an emergency. Please contact local emergency services or a suicide prevention helpline immediately."})
    if "sleep" in l:
        return jsonify({"reply":"Try a consistent bedtime and avoid screens 1 hour before sleep. Want 3 sleep tips?"})
    if "exam" in l or "study" in l:
        return jsonify({"reply":"Break study into short focused blocks (25 mins) and take short walks between."})
    return jsonify({"reply":"Thanks for sharing — try a 2-minute grounding exercise: name 5 things you can see, 4 you can touch, 3 you can hear."})

# New LLM chat endpoint (optional OpenAI integration)
@app.route("/llm_chat", methods=["POST"])
def llm_chat():
    payload = request.get_json() or {}
    user_id = payload.get("user_id", session.get("user_id","guest"))
    msg = (payload.get("message") or "").strip()
    if not msg:
        return jsonify({"reply":"Please send a message."}), 400
    # Safety checks before sending to LLM
    lowered = msg.lower()
    if any(x in lowered for x in ["suicide","kill myself","end my life","hurt myself"]):
        return jsonify({"reply":"I can't assist with self-harm crisis. Please contact emergency services or a suicide prevention helpline immediately."})
    if use_openai:
        try:
            prompt = f"""You are MEDCARE assistant for students. Keep answers short, empathetic, and include coping strategies. User message: {msg}"""
            resp = openai.ChatCompletion.create(model='gpt-3.5-turbo', messages=[{'role':'system','content':'You are a compassionate mental health assistant for students.'},{'role':'user','content':prompt}], max_tokens=300)
            reply = resp['choices'][0]['message']['content'].strip()
            return jsonify({'reply': reply})
        except Exception as e:
            print('OpenAI call failed:', e)
            # fallback to rule-based
    # fallback responses (same as /chat)
    return chat()

# Summarize latest assessment & generate personalized plan using LLM (optional)
@app.route("/summarize_assessment", methods=["POST"])
def summarize_assessment():
    payload = request.get_json() or {}
    user_id = payload.get("user_id", session.get("user_id","guest"))
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    row = c.execute("SELECT score,label,answers,ts FROM assessments WHERE user_id=? ORDER BY ts DESC LIMIT 1",(anonymize_id(user_id),)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error":"no_assessment"}), 404
    score,label,answers_json,ts = row
    try:
        answers = json.loads(answers_json)
    except:
        answers = {}
    # If we have LLM, ask it to create a plan
    if use_openai:
        try:
            prompt = f"""The user is a student. Latest assessment: score={score}, label={label}, answers={answers}. Create a short personalized action plan (3-5 bullets), with resources and coping tips. Keep it concise and supportive."""
            resp = openai.ChatCompletion.create(model='gpt-3.5-turbo', messages=[{'role':'system','content':'You are a concise supportive mental health assistant for students.'},{'role':'user','content':prompt}], max_tokens=400)
            plan_text = resp['choices'][0]['message']['content'].strip()
            return jsonify({'plan':plan_text, 'label': label, 'score': score})
        except Exception as e:
            print('OpenAI plan failed:', e)
    # fallback deterministic plan
    if label=="Low":
        plan = "Mild stress — breathing exercises, schedule short study breaks, maintain sleep hygiene."
    elif label=="Medium":
        plan = "Moderate stress — try guided meditation, journaling, and reach out to peer support or counseling."
    else:
        plan = "Severe stress — strongly consider contacting a professional counselor. If you feel unsafe, contact emergency services."
    return jsonify({'plan':plan,'label':label,'score':score})

@app.route("/health")
def health():
    return jsonify({"status":"ok","model_loaded": bool(behavior_model is not None), "llm_enabled": use_openai})

if __name__ == "__main__":
    print("Starting MEDCARE. Static folder:", STATIC_DIR)
    app.run(host="0.0.0.0", port=5000, debug=True)
