# routes/accounts.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Account, AccountingBook, JournalLine
from sqlalchemy.exc import IntegrityError

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/', methods=['GET'])
@jwt_required()
def get_accounts():
    user_id = get_jwt_identity()
    book_id = request.args.get('book_id', type=int)
    if not book_id:
        return jsonify({'error': 'book_id is required'}), 400
    # Check if book exists for this user
    book = AccountingBook.query.filter_by(id=book_id, user_id=user_id).first()
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    accounts = Account.query.filter_by(user_id=user_id, book_id=book_id).all()
    return jsonify([{
        'id': acc.id,
        'name': acc.name,
        'type': acc.type,
        'code': acc.code,
        'category': acc.category,
        'parent_id': acc.parent_id
    } for acc in accounts])

@accounts_bp.route('/', methods=['POST'])
@jwt_required()
def add_account():
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    book_id = data.get('book_id')
    name = data.get('name')
    type_ = data.get('type')
    code = data.get('code')
    category = data.get('category')
    parent_id = data.get('parent_id')

    # Validate required fields
    if not all([book_id, name, type_, code, category]):
        return jsonify({'error': 'All fields (book_id, name, type, code, category) are required'}), 400

    # Check if book exists for this user
    book = AccountingBook.query.filter_by(id=book_id, user_id=user_id).first()
    if not book:
        return jsonify({'error': 'Book not found'}), 404

    # Check for duplicate code in this book
    if Account.query.filter_by(user_id=user_id, book_id=book_id, code=code).first():
        return jsonify({'error': 'Account code already exists in this book'}), 400

    acc = Account(
        user_id=user_id,
        book_id=book_id,
        name=name,
        type=type_,
        code=code,
        category=category,
        parent_id=parent_id
    )
    db.session.add(acc)
    db.session.commit()
    return jsonify({'message': 'Account added', 'id': acc.id}), 201

@accounts_bp.route('/<int:account_id>', methods=['PUT'])
@jwt_required()
def edit_account(account_id):
    user_id = get_jwt_identity()
    account = Account.query.filter_by(id=account_id, user_id=user_id).first_or_404()
    data = request.get_json()
    account.name = data.get('name', account.name)
    account.type = data.get('type', account.type)
    account.code = data.get('code', account.code)
    account.category = data.get('category', account.category)
    account.parent_id = data.get('parent_id', account.parent_id)
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