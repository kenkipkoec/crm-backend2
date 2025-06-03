from flask import Blueprint, request, jsonify
from models import db, Task
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

tasks_bp = Blueprint('tasks', __name__)

def validate_task(data):
    if not data.get('description'):
        return 'Description is required.'
    if data.get('due_date'):
        try:
            datetime.fromisoformat(data['due_date'])
        except Exception:
            return 'Invalid due_date format. Use ISO format.'
    return None

@tasks_bp.route('/', methods=['GET'])
@jwt_required()
def get_tasks():
    user_id = get_jwt_identity()
    tasks = Task.query.filter_by(user_id=user_id).all()
    return jsonify([{
        'id': t.id,
        'description': t.description,
        'due_date': t.due_date.isoformat() if t.due_date else None,
        'category': t.category,
        'recurrence': t.recurrence,
        'notes': t.notes,
        'priority': t.priority,
        'completed': t.completed,
        'created_at': t.created_at.isoformat() if t.created_at else None
    } for t in tasks])

@tasks_bp.route('/', methods=['POST'])
@jwt_required()
def add_task():
    user_id = get_jwt_identity()
    data = request.get_json()
    error = validate_task(data)
    if error:
        return jsonify({'error': error}), 400
    task = Task(
        user_id=user_id,
        description=data['description'],
        due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
        category=data.get('category'),
        recurrence=data.get('recurrence'),
        notes=data.get('notes'),
        priority=data.get('priority'),
        completed=data.get('completed', False)
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({'message': 'Task created', 'id': task.id}), 201

@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    user_id = get_jwt_identity()
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        return jsonify({'error': 'Task not found.'}), 404
    data = request.get_json()
    error = validate_task({**data, 'description': data.get('description', task.description)})
    if error:
        return jsonify({'error': error}), 400
    for field in ['description', 'due_date', 'category', 'recurrence', 'notes', 'priority', 'completed']:
        if field in data:
            if field == 'due_date' and data[field]:
                setattr(task, field, datetime.fromisoformat(data[field]))
            else:
                setattr(task, field, data[field])
    db.session.commit()
    return jsonify({'message': 'Task updated'})

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    user_id = get_jwt_identity()
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        return jsonify({'error': 'Task not found.'}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({'message': 'Task deleted'})