FLASK_DEBUG=True
FLASK_CONFIG=application.config.DevelopmentConfig
FLASK_APP=application.wsgi:app
SECRET_KEY=replaceinprod
DATABASE_URL=postgresql://localhost/local_plans
FLASK_RUN_PORT=5050
LOCAL_PLANS_REPO_NAME=digital-land/local-plans-explorer
LOCAL_PLANS_REPO_DATA_PATH=data/export
