# -*- coding: utf-8 -*-
import os


class Config(object):
    APP_ROOT = os.path.abspath(os.path.dirname(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(APP_ROOT, os.pardir))
    SECRET_KEY = os.environ["SECRET_KEY"]
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = False
    DEBUG = False
    WTF_CSRF_ENABLED = True
    AUTHENTICATION_ON = True
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
    SAFE_URLS = set(os.getenv("SAFE_URLS", "").split(","))
    LOCAL_PLANS_REPO_NAME = os.getenv("LOCAL_PLANS_REPO_NAME")
    LOCAL_PLANS_REPO_DATA_PATH = os.getenv("LOCAL_PLANS_REPO_DATA_PATH")


class DevelopmentConfig(Config):
    DEBUG = True
    WTF_CSRF_ENABLED = False
    AUTHENTICATION_ON = False
    SQLALCHEMY_RECORD_QUERIES = True


class TestConfig(Config):
    TESTING = True
