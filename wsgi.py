"""Ponto de entrada: `flask --app wsgi run` (desenvolvimento) ou `gunicorn wsgi:app` (produção)."""
from knazh import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False)
