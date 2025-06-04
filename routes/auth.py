from flask import Blueprint, request, jsonify
from db import db
from models import User
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    required = ['username', 'firstName', 'lastName', 'email', 'contact', 'password']
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
        firstName=data['firstName'],
        lastName=data['lastName'],
        email=data['email'],
        contact=data['contact'],
        password=hashed_pw
    )
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=str(user.id))
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'firstName': user.firstName,
            'lastName': user.lastName,
            'email': user.email,
            'contact': user.contact
        }
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    login = data.get('login')
    password = data.get('password')
    user = User.query.filter(
        (User.username == login) | (User.email == login)
    ).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'firstName': user.firstName,
            'lastName': user.lastName,
            'email': user.email,
            'contact': user.contact
        }
    })

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'id': user.id,
        'username': user.username,
        'firstName': user.firstName,
        'lastName': user.lastName,
        'email': user.email,
        'contact': user.contact
    })