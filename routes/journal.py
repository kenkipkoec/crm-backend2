from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Account, JournalEntry, JournalLine, AccountingBook
from datetime import datetime
import os
from werkzeug.utils import secure_filename

journal_bp = Blueprint("journal", __name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None

# --- Filter by user_id and book_id everywhere ---

@journal_bp.route("/", methods=["GET"])
@jwt_required()
def get_journal_entries():
    user_id = get_jwt_identity()
    book_id = request.args.get("book_id", type=int)
    if not book_id:
        return jsonify({"error": "book_id is required"}), 400
    # Check if book exists for this user
    book = AccountingBook.query.filter_by(id=book_id, user_id=user_id).first()
    if not book:
        return jsonify({"error": "Book not found"}), 404
    entries = (
        JournalEntry.query.filter_by(user_id=user_id, book_id=book_id)
        .order_by(JournalEntry.date.desc())
        .all()
    )
    result = []
    for entry in entries:
        lines = JournalLine.query.filter_by(entry_id=entry.id).all()
        result.append({
            "id": entry.id,
            "date": entry.date.strftime("%Y-%m-%d"),
            "description": entry.description,
            "status": entry.status,
            "attachment": entry.attachment,
            "lines": [
                {
                    "account_id": l.account_id,
                    "debit": l.debit,
                    "credit": l.credit
                } for l in lines
            ]
        })
    return jsonify(result)

@journal_bp.route("", methods=["POST"])
@jwt_required()
def add_journal_entry():
    user_id = get_jwt_identity()
    data = request.get_json()
    book_id = data.get("book_id")
    if not book_id:
        return jsonify({"error": "book_id is required"}), 400

    # Prevent cross-book references
    lines = data.get("lines", [])
    for line in lines:
        acc = Account.query.filter_by(id=line["account_id"], user_id=user_id, book_id=book_id).first()
        if not acc:
            return jsonify({"error": f"Account ID {line['account_id']} does not exist in this book."}), 400

    # Optional: Prevent unbalanced entries
    total_debit = sum(float(l.get("debit", 0)) for l in lines)
    total_credit = sum(float(l.get("credit", 0)) for l in lines)
    if round(total_debit, 2) != round(total_credit, 2):
        return jsonify({"error": "Debits and credits must balance."}), 400

    entry = JournalEntry(
        user_id=user_id,
        book_id=book_id,
        date=parse_date(data["date"]),
        description=data.get("description", ""),
        status="draft"
    )
    db.session.add(entry)
    db.session.flush()
    for line in lines:
        db.session.add(JournalLine(
            entry_id=entry.id,
            account_id=line["account_id"],
            debit=float(line.get("debit", 0)),
            credit=float(line.get("credit", 0))
        ))
    db.session.commit()
    return jsonify({"id": entry.id, "message": "Journal entry created"}), 201

@journal_bp.route("/<int:entry_id>", methods=["PUT"])
@jwt_required()
def edit_journal_entry(entry_id):
    user_id = get_jwt_identity()
    entry = JournalEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()
    data = request.get_json()
    book_id = entry.book_id

    # Prevent cross-book references
    lines = data.get("lines", [])
    for line in lines:
        acc = Account.query.filter_by(id=line["account_id"], user_id=user_id, book_id=book_id).first()
        if not acc:
            return jsonify({"error": f"Account ID {line['account_id']} does not exist in this book."}), 400

    # Optional: Prevent unbalanced entries
    total_debit = sum(float(l.get("debit", 0)) for l in lines)
    total_credit = sum(float(l.get("credit", 0)) for l in lines)
    if round(total_debit, 2) != round(total_credit, 2):
        return jsonify({"error": "Debits and credits must balance."}), 400

    entry.date = parse_date(data.get("date")) or entry.date
    entry.description = data.get("description", entry.description)
    JournalLine.query.filter_by(entry_id=entry.id).delete()
    for line in lines:
        db.session.add(JournalLine(
            entry_id=entry.id,
            account_id=line["account_id"],
            debit=float(line.get("debit", 0)),
            credit=float(line.get("credit", 0))
        ))
    db.session.commit()
    return jsonify({"message": "Journal entry updated"})

# --- Attachments: Upload and Download ---

@journal_bp.route("/upload/<int:entry_id>", methods=["POST"])
@jwt_required()
def upload_attachment(entry_id):
    user_id = get_jwt_identity()
    entry = JournalEntry.query.filter_by(id=entry_id, user_id=user_id).first()
    if not entry:
        return jsonify({"error": "Entry not found"}), 404
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{entry_id}_{file.filename}")
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        entry.attachment = filename
        db.session.commit()
        return jsonify({"message": "File uploaded", "attachment": filename})
    return jsonify({"error": "Invalid file type"}), 400

@journal_bp.route("/attachment/<filename>", methods=["GET"])
@jwt_required()
def get_attachment(filename):
    # Optionally: check user permissions here
    return send_from_directory(UPLOAD_FOLDER, filename)

# --- Reports: Always filter by user_id and book_id ---

@journal_bp.route("/trial-balance", methods=["GET"])
@jwt_required()
def trial_balance():
    user_id = get_jwt_identity()
    book_id = request.args.get("book_id", type=int)
    if not book_id:
        return jsonify({"error": "book_id is required"}), 400
    # Check if book exists for this user
    book = AccountingBook.query.filter_by(id=book_id, user_id=user_id).first()
    if not book:
        return jsonify({"error": "Book not found"}), 404
    accounts = Account.query.filter_by(user_id=user_id, book_id=book_id).all()
    result = []
    total_debit = 0.0
    total_credit = 0.0
    for acc in accounts:
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        balance = debit - credit
        result.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "debit": float(debit),
            "credit": float(credit),
            "balance": float(balance)
        })
        total_debit += float(debit)
        total_credit += float(credit)
    return jsonify({
        "accounts": result,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit)
    })

@journal_bp.route("/income-statement", methods=["GET"])
@jwt_required()
def income_statement():
    user_id = get_jwt_identity()
    book_id = request.args.get("book_id", type=int)
    if not book_id:
        return jsonify({"error": "book_id is required"}), 400
    # Income accounts
    income_accounts = Account.query.filter_by(user_id=user_id, book_id=book_id, type="Income").all()
    income = []
    total_income = 0.0
    for acc in income_accounts:
        amount = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        income.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "amount": float(amount)
        })
        total_income += float(amount)
    # Expense accounts
    expense_accounts = Account.query.filter_by(user_id=user_id, book_id=book_id, type="Expense").all()
    expense = []
    total_expense = 0.0
    for acc in expense_accounts:
        amount = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        expense.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "amount": float(amount)
        })
        total_expense += float(amount)
    net_income = total_income - total_expense
    return jsonify({
        "income": income,
        "expense": expense,
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net_income": float(net_income)
    })

@journal_bp.route("/balance-sheet", methods=["GET"])
@jwt_required()
def balance_sheet():
    user_id = get_jwt_identity()
    book_id = request.args.get("book_id", type=int)
    if not book_id:
        return jsonify({"error": "book_id is required"}), 400
    # Assets
    asset_accounts = Account.query.filter_by(user_id=user_id, book_id=book_id, type="Asset").all()
    assets = []
    total_assets = 0.0
    for acc in asset_accounts:
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        balance = debit - credit
        assets.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "balance": float(balance)
        })
        total_assets += float(balance)
    # Liabilities
    liability_accounts = Account.query.filter_by(user_id=user_id, book_id=book_id, type="Liability").all()
    liabilities = []
    total_liabilities = 0.0
    for acc in liability_accounts:
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        balance = credit - debit
        liabilities.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "balance": float(balance)
        })
        total_liabilities += float(balance)
    # Equity
    equity_accounts = Account.query.filter_by(user_id=user_id, book_id=book_id, type="Equity").all()
    equity = []
    total_equity = 0.0
    for acc in equity_accounts:
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0.0
        balance = credit - debit
        equity.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "balance": float(balance)
        })
        total_equity += float(balance)
    return jsonify({
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": float(total_assets),
        "total_liabilities": float(total_liabilities),
        "total_equity": float(total_equity)
    })

@journal_bp.route("/<int:entry_id>", methods=["DELETE"])
@jwt_required()
def delete_journal_entry(entry_id):
    user_id = get_jwt_identity()
    entry = JournalEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"message": "Journal entry deleted"})

@journal_bp.route("/<int:entry_id>/submit", methods=["POST"])
@jwt_required()
def submit_entry(entry_id):
    entry = JournalEntry.query.get(entry_id)
    entry.status = "Submitted"
    db.session.commit()
    return jsonify({"message": "Entry submitted"})

@journal_bp.route("/<int:entry_id>/approve", methods=["POST"])
@jwt_required()
def approve_entry(entry_id):
    entry = JournalEntry.query.get(entry_id)
    entry.status = "Approved"
    db.session.commit()
    return jsonify({"message": "Entry approved"})

@journal_bp.route("/<int:entry_id>/reject", methods=["POST"])
@jwt_required()
def reject_entry(entry_id):
    entry = JournalEntry.query.get(entry_id)
    entry.status = "Rejected"
    db.session.commit()
    return jsonify({"message": "Entry rejected"})