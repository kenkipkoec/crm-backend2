# routes/accounts.py
from flask import Blueprint, request, jsonify
from models import db, Account

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/', methods=['GET'])
def get_accounts():
    accounts = Account.query.all()
    return jsonify([{
        'id': acc.id,
        'name': acc.name,
        'type': acc.type,
        'code': acc.code
    } for acc in accounts])

@accounts_bp.route('/', methods=['POST'])
def add_account():
    data = request.get_json()
    account = Account(
        name=data['name'],
        type=data['type'],
        code=data['code']
    )
    db.session.add(account)
    db.session.commit()
    return jsonify({'message': 'Account created'}), 201