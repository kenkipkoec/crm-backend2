# app.py
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
import os

from db import db
from routes.auth import auth_bp
from routes.tasks import tasks_bp
from routes.contacts import contacts_bp
from routes.accounts import accounts_bp
from routes.journal import journal_bp

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv("SECRET_KEY")
    db.init_app(app)
    jwt = JWTManager(app)  # <-- Make sure this is here!
    CORS(app, supports_credentials=True)
    app.url_map.strict_slashes = False  # Allow both /api/tasks and /api/tasks/
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(contacts_bp, url_prefix="/api/contacts")
    app.register_blueprint(accounts_bp, url_prefix="/api/accounts")
    app.register_blueprint(journal_bp, url_prefix="/api/journal")
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)