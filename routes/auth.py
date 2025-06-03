from flask import Blueprint, request, jsonify
from models import db, User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    required = ['username', 'name', 'email', 'contact', 'password']
    if not all(field in data and data[field] for field in required):
        return jsonify({'error': 'All fields are required.'}), 400
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', data['email']):
        return jsonify({'error': 'Invalid email format.'}), 400
    if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$', data['password']):
        return jsonify({'error': 'Password must be at least 8 characters and include a letter and a number.'}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists.'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists.'}), 400
    hashed_pw = generate_password_hash(data['password'])
    user = User(
        username=data['username'],
        name=data['name'],
        email=data['email'],
        contact=data['contact'],
        password=hashed_pw
    )
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=user.id)
    return jsonify({'token': token, 'user': {'id': user.id, 'username': user.username, 'name': user.name, 'email': user.email, 'contact': user.contact}}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required.'}), 400
    user = User.query.filter_by(username=data['username']).first()
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'error': 'Invalid credentials.'}), 401
    token = create_access_token(identity=user.id)
    return jsonify({'token': token, 'user': {'id': user.id, 'username': user.username, 'name': user.name, 'email': user.email, 'contact': user.contact}})