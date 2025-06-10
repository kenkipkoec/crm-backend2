from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, AccountingBook, Account, JournalEntry

books_bp = Blueprint('books', __name__)

@books_bp.route('/', methods=['GET'])
@jwt_required()
def list_books():
    user_id = get_jwt_identity()
    books = AccountingBook.query.filter_by(user_id=user_id).all()
    return jsonify([{"id": b.id, "name": b.name, "created_at": b.created_at.isoformat()} for b in books])

@books_bp.route('/', methods=['POST'])
@jwt_required()
def create_book():
    user_id = get_jwt_identity()
    data = request.get_json()
    book = AccountingBook(user_id=user_id, name=data['name'])
    db.session.add(book)
    db.session.commit()
    return jsonify({"id": book.id, "name": book.name}), 201

@books_bp.route('/<int:book_id>', methods=['PUT'])
@jwt_required()
def rename_book(book_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    book = AccountingBook.query.filter_by(id=book_id, user_id=user_id).first()
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    book.name = name
    db.session.commit()
    return jsonify({'message': 'Book renamed'})

@books_bp.route('/<int:book_id>', methods=['DELETE'])
@jwt_required()
def delete_book(book_id):
    user_id = get_jwt_identity()
    book = AccountingBook.query.filter_by(id=book_id, user_id=user_id).first()
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    # Prevent delete if book has accounts or journal entries
    if Account.query.filter_by(book_id=book_id).first() or JournalEntry.query.filter_by(book_id=book_id).first():
        return jsonify({'error': 'Book is not empty'}), 400
    db.session.delete(book)
    db.session.commit()
    return jsonify({'message': 'Book deleted'})