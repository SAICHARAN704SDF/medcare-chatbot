import os
try:
    import joblib
except Exception:
    joblib = None

MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model", "trained_model.joblib")

def load_model():
    if joblib and os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None

MODEL = load_model()

def predict_from_features(features):
    if MODEL:
        return MODEL.predict([features])[0]
    # fallback rule-based placeholder
    s = sum(features) if isinstance(features, (list,tuple)) else 0
    if s>10:
        return "high"
    elif s>5:
        return "moderate"
    return "low"