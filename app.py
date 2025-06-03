# app.py
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
import os

load_dotenv()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY')
    db.init_app(app)
    CORS(app)
    JWTManager(app)

    # Register blueprints here
    from routes.accounts import accounts_bp
    app.register_blueprint(accounts_bp, url_prefix='/api/accounts')
    from routes.journal import journal_bp
    app.register_blueprint(journal_bp, url_prefix='/api/journal')
    from routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    from routes.tasks import tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    from routes.contacts import contacts_bp
    app.register_blueprint(contacts_bp, url_prefix='/api/contacts')

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)