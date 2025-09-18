MEDCARE Professional Package
---------------------------
This package contains MEDCARE with extended functionality to meet the project statement:
- Consent & onboarding (static/onboarding.html + /consent endpoint)
- Server-side assessment storage (/api/assessment) in SQLite (medcare.db)
- Admin export (admin.html + /admin/export)
- Fused prediction endpoint /predict_fused combining questionnaire + behavior model
- Student resources and privacy/ethics documentation

Deployment notes:
- Run ml API: python ml_module/app.py (or use docker-compose)
- Ensure rf_stress_model.pkl is present in ml_module/ (behavior model). If not, use train scripts to create one.
- For production, replace SQLite with a managed DB, enable HTTPS, and secure admin endpoints.
