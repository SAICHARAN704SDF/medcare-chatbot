SIH2025 Final Project (with ML integration)

ML module:
  - Folder: ml_module
  - Run locally: see ml_module/README_ML.txt
  - Docker compose is provided to run ML API + static site:
      docker-compose up --build
  - Static demo page: static/predict.html (served by nginx on port 8080 if using docker-compose)

Notes:
  - The model is a prototype (Random Forest) trained on provided CSVs. Accuracy is ~0.55 on test split.
  - Improve model by adding more labeled data, better features, and hyperparameter tuning.
