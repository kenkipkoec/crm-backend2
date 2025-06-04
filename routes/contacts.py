from flask import Blueprint, request, jsonify
from models import db, Contact
from flask_jwt_extended import jwt_required, get_jwt_identity
import re

contacts_bp = Blueprint('contacts', __name__)

def validate_contact(data):
    if not data.get('name'):
        return 'Name is required.'
    if data.get('email') and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', data['email']):
        return 'Invalid email format.'
    if data.get('phone') and not re.match(r'^\d{10,15}$', data['phone']):
        return 'Invalid phone number.'
    return None

@contacts_bp.route("", methods=["GET"])  # <-- NO trailing slash
@jwt_required()
def get_contacts():
    user_id = get_jwt_identity()
    contacts = Contact.query.filter_by(user_id=user_id).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'email': c.email,
        'phone': c.phone,
        'company': c.company,
        'notes': c.notes
    } for c in contacts])

@contacts_bp.route("", methods=["POST"])  # <-- NO trailing slash
@jwt_required()
def add_contact():
    user_id = get_jwt_identity()
    data = request.get_json()
    error = validate_contact(data)
    if error:
        return jsonify({'error': error}), 400
    contact = Contact(
        user_id=user_id,
        name=data['name'],
        email=data.get('email'),
        phone=data.get('phone'),
        company=data.get('company'),
        notes=data.get('notes')
    )
    db.session.add(contact)
    db.session.commit()
    # Return the full contact object
    return jsonify({
        'id': contact.id,
        'name': contact.name,
        'email': contact.email,
        'phone': contact.phone,
        'company': contact.company,
        'notes': contact.notes
    }), 201

@contacts_bp.route('/<int:contact_id>', methods=['PUT'])
@jwt_required()
def update_contact(contact_id):
    user_id = get_jwt_identity()
    contact = Contact.query.filter_by(id=contact_id, user_id=user_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found.'}), 404
    data = request.get_json()
    error = validate_contact({**data, 'name': data.get('name', contact.name)})
    if error:
        return jsonify({'error': error}), 400
    for field in ['name', 'email', 'phone', 'company', 'notes']:
        if field in data:
            setattr(contact, field, data[field])
    db.session.commit()
    return jsonify({'message': 'Contact updated'})

@contacts_bp.route('/<int:contact_id>', methods=['DELETE'])
@jwt_required()
def delete_contact(contact_id):
    user_id = get_jwt_identity()
    contact = Contact.query.filter_by(id=contact_id, user_id=user_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found.'}), 404
    db.session.delete(contact)
    db.session.commit()
    return jsonify({'message': 'Contact deleted'})