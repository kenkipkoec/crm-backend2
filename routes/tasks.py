from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import db
from models import Task
from datetime import datetime

tasks_bp = Blueprint("tasks", __name__)

def validate_task(data):
    if not data.get("description"):
        return "Description is required."
    return None

@tasks_bp.route("", methods=["GET", "POST"])
@jwt_required()
def tasks():
    user_id = get_jwt_identity()
    if request.method == "GET":
        tasks = Task.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": t.id,
            "description": t.description,
            "dueDate": t.dueDate,  # <-- use dueDate
            "category": t.category,
            "recurrence": t.recurrence,
            "notes": t.notes,
            "priority": t.priority,
            "completed": t.completed,
            "createdAt": t.created_at.isoformat() if t.created_at else None
        } for t in tasks])
    else:
        data = request.get_json()
        error = validate_task(data)
        if error:
            return jsonify({"error": error}), 400
        task = Task(
            user_id=user_id,
            description=data["description"],
            dueDate=data.get("dueDate"),  # <-- use dueDate
            category=data.get("category"),
            recurrence=data.get("recurrence"),
            notes=data.get("notes"),
            priority=data.get("priority"),
            completed=data.get("completed", False)
        )
        db.session.add(task)
        db.session.commit()
        return jsonify({
            "id": task.id,
            "description": task.description,
            "dueDate": task.dueDate,
            "category": task.category,
            "recurrence": task.recurrence,
            "notes": task.notes,
            "priority": task.priority,
            "completed": task.completed,
            "createdAt": task.created_at.isoformat() if task.created_at else None
        }), 201

@tasks_bp.route("/<int:id>", methods=["PUT", "DELETE"])
@jwt_required()
def task_detail(id):
    user_id = get_jwt_identity()
    task = Task.query.filter_by(id=id, user_id=user_id).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if request.method == "PUT":
        data = request.get_json()
        for field in ["description", "dueDate", "category", "recurrence", "notes", "priority", "completed"]:
            if field in data:
                setattr(task, field, data[field])
        db.session.commit()
        return jsonify({
            "id": task.id,
            "description": task.description,
            "dueDate": task.dueDate,
            "category": task.category,
            "recurrence": task.recurrence,
            "notes": task.notes,
            "priority": task.priority,
            "completed": task.completed,
            "createdAt": task.created_at.isoformat() if task.created_at else None
        })
    else:
        db.session.delete(task)
        db.session.commit()
        return jsonify({"message": "Task deleted"})