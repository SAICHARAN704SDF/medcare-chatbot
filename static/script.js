// helper functions
async function apiLogin(uid){ return fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body: JSON.stringify({user_id:uid})}).then(r=>r.json()); }
async function apiAssessment(obj){ return fetch('/api/assessment',{method:'POST',headers:{'Content-Type':'application/json'},body: JSON.stringify(obj)}).then(r=>r.json()); }
async function apiPredictFused(obj){ return fetch('/predict_fused',{method:'POST',headers:{'Content-Type':'application/json'},body: JSON.stringify(obj)}).then(r=>r.json()); }
