web: flask db upgrade; flask data load-doc-types; flask data load-event-types; gunicorn -b 0.0.0.0:$PORT application.wsgi:app
