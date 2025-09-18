#!/usr/bin/env python3
import os, sqlite3, json, hashlib, datetime, io, csv, traceback
from flask import Flask, request, jsonify, session, redirect, send_from_directory, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE, "static")
ML_DIR = os.path.join(BASE, "ml_module")
DB_PATH = os.path.join(ML_DIR, "medcare.db")

os.makedirs(ML_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
app.secret_key = os.environ.get("MEDCARE_SECRET", "medcare_prod_secret")
ADMIN_PASSWORD = os.environ.get("MEDCARE_ADMIN_PWD", "medcare_admin_pass")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user_id TEXT UNIQUE, password_hash TEXT, name TEXT, email TEXT, created_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS consent (id INTEGER PRIMARY KEY, user_id TEXT, consent INTEGER, ts TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS assessments (id INTEGER PRIMARY KEY, user_id TEXT, score INTEGER, label TEXT, answers TEXT, ts TEXT)')
    conn.commit(); conn.close()

init_db()

# load model if available
behavior_model = None
model_path = os.path.join(ML_DIR, "model.pkl")
if os.path.exists(model_path):
    try:
        import joblib
        behavior_model = joblib.load(model_path)
        print("Loaded model at", model_path)
    except Exception as e:
        print("Failed loading model:", e)

# serve pages with unique endpoints
pages = ["index","login","dashboard","assessment","emergency","resources"]
for p in pages:
    app.add_url_rule(f'/{p}' if p!='index' else '/', endpoint=f'page_{p}', view_func=(lambda p=p: send_from_directory(STATIC_DIR, f"{p}.html")))

@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory(os.path.join(STATIC_DIR, "assets"), filename)

# auth
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    uid = data.get('user_id'); pwd = data.get('password'); name = data.get('name','')
    if not uid or not pwd: return jsonify({'error':'user_id and password required'}),400
    ph = generate_password_hash(pwd)
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    try:
        c.execute("INSERT INTO users (user_id,password_hash,name,created_at) VALUES (?,?,?,?)",(uid,ph,name,datetime.datetime.utcnow().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close(); return jsonify({'error':'user_exists'}),409
    conn.close(); session['user_id']=uid
    return jsonify({'status':'ok','user_id':uid})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    uid = data.get('user_id'); pwd = data.get('password')
    if not uid or not pwd: return jsonify({'error':'user_id and password required'}),400
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    row = c.execute("SELECT password_hash FROM users WHERE user_id=?",(uid,)).fetchone()
    conn.close()
    if not row or not check_password_hash(row[0], pwd): return jsonify({'error':'invalid_credentials'}),401
    session['user_id']=uid
    return jsonify({'status':'logged_in','user_id':uid})

@app.route('/api/assessment', methods=['POST'])
def api_assessment():
    data = request.get_json() or {}
    uid = data.get('user_id') or session.get('user_id','guest')
    score = int(data.get('score',0))
    label = data.get('label') or ('Severe' if score>=75 else 'Moderate' if score>=45 else 'Mild')
    answers = json.dumps(data.get('answers',{}))
    ts = data.get('ts') or datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("INSERT INTO assessments (user_id,score,label,answers,ts) VALUES (?,?,?,?,?)",(hashlib.sha256(uid.encode()).hexdigest()[:12],score,label,answers,ts))
    conn.commit(); conn.close()
    # if severe, indicate redirect
    if label=='Severe':
        return jsonify({'status':'saved','label':label,'redirect':'/emergency'})
    return jsonify({'status':'saved','label':label})

@app.route('/api/user/<uid>/history', methods=['GET'])
def user_history(uid):
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    rows = c.execute("SELECT score,label,answers,ts FROM assessments WHERE user_id=? ORDER BY ts DESC",(hashlib.sha256(uid.encode()).hexdigest()[:12],)).fetchall()
    conn.close()
    data = [{'score':r[0],'label':r[1],'answers': json.loads(r[2]) if r[2] else {}, 'ts': r[3]} for r in rows]
    return jsonify(data)

@app.route('/admin/export', methods=['GET'])
def admin_export():
    pwd = request.args.get('admin_pwd') or request.headers.get('X-ADMIN-PWD')
    if pwd != ADMIN_PASSWORD: return jsonify({'error':'admin pwd required'}),401
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    rows = c.execute("SELECT user_id,score,label,answers,ts FROM assessments ORDER BY ts DESC").fetchall()
    conn.close()
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(['anon_user','score','label','answers','ts'])
    for r in rows: writer.writerow(r)
    out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='assessments.csv')

@app.route('/health')
def health():
    return jsonify({'status':'ok','ml': bool(behavior_model is not None)})

if __name__ == '__main__':
    print('Starting MEDCARE premium app')
    app.run(host='0.0.0.0', port=5000, debug=False)
