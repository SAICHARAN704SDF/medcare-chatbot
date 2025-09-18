

Docker / Deployment notes:
- Build & run with docker-compose from project root:
  docker-compose up --build
- ml-api will be on port 5000, static site served by nginx on port 8080.
- For production, run the ml-api with Gunicorn and behind a reverse proxy.
