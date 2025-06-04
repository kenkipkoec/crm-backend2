# routes/accounts.py
from flask import Blueprint, request, jsonify
from models import db, Account, JournalLine
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/', methods=['GET'])
@jwt_required()
def get_accounts():
    user_id = get_jwt_identity()
    accounts = Account.query.filter_by(user_id=user_id).all()
    return jsonify([{
        'id': acc.id,
        'name': acc.name,
        'type': acc.type,
        'code': acc.code
    } for acc in accounts])

@accounts_bp.route('', methods=['POST'])
@jwt_required()
def add_account():
    user_id = get_jwt_identity()
    data = request.get_json()
    try:
        account = Account(
            name=data['name'],
            type=data['type'],
            code=data['code'],
            user_id=user_id
        )
        db.session.add(account)
        db.session.commit()
        return jsonify({'id': account.id}), 201
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({'error': 'Account code or name already exists.'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@accounts_bp.route('/<int:account_id>', methods=['PUT'])
@jwt_required()
def edit_account(account_id):
    user_id = get_jwt_identity()
    account = Account.query.filter_by(id=account_id, user_id=user_id).first_or_404()
    data = request.get_json()
    account.name = data.get('name', account.name)
    account.type = data.get('type', account.type)
    account.code = data.get('code', account.code)
    db.session.commit()
    return jsonify({'message': 'Account updated'})

@accounts_bp.route('/<int:account_id>', methods=['DELETE'])
@jwt_required()
def delete_account(account_id):
    user_id = get_jwt_identity()
    account = Account.query.filter_by(id=account_id, user_id=user_id).first_or_404()
    # Prevent deletion if account is used in journal lines
    if JournalLine.query.filter_by(account_id=account.id).first():
        return jsonify({'error': 'Cannot delete account: it is used in journal entries.'}), 400
    db.session.delete(account)
    db.session.commit()
    return jsonify({'message': 'Account deleted'})