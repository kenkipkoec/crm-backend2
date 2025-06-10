from db import db
from datetime import datetime

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    category = db.Column(db.String(50))  # NEW: e.g. "Current Asset", "Fixed Asset"
    parent_id = db.Column(db.Integer, db.ForeignKey('account.id'))  # NEW: hierarchy
    parent = db.relationship('Account', remote_side=[id], backref='children')
    book_id = db.Column(db.Integer, db.ForeignKey('accounting_book.id'), nullable=False)

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255))
    attachment = db.Column(db.String(255))  # NEW: file path or URL
    status = db.Column(db.String(20), default="Draft")  # NEW: Draft, Submitted, Approved, Rejected
    lines = db.relationship('JournalLine', backref='entry', lazy=True)
    book_id = db.Column(db.Integer, db.ForeignKey('accounting_book.id'), nullable=False)

class JournalLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    debit = db.Column(db.Numeric(12, 2), default=0)
    credit = db.Column(db.Numeric(12, 2), default=0)
    account = db.relationship('Account')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    firstName = db.Column(db.String(80), nullable=False)
    lastName = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contact = db.Column(db.String(20))
    password = db.Column(db.String(200), nullable=False)
    tasks = db.relationship('Task', backref='user', lazy=True, cascade="all, delete-orphan")
    contacts = db.relationship('Contact', backref='user', lazy=True, cascade="all, delete-orphan")

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    dueDate = db.Column(db.String(50))  # <-- use dueDate, not due_date
    category = db.Column(db.String(50))
    recurrence = db.Column(db.String(50))
    notes = db.Column(db.Text)
    priority = db.Column(db.String(20))
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    company = db.Column(db.String(120))
    notes = db.Column(db.Text)

class AccountingBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Optionally: description, period_start, period_end, etc.