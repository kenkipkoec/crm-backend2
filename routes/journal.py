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
    accounts = Account.query.filter_by(user_id=user_id, book_id=book_id).all()
    result = []
    total_debit = 0
    total_credit = 0
    for acc in accounts:
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0
        balance = debit - credit
        result.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "debit": float(debit),
            "credit": float(credit),
            "balance": float(balance)
        })
        total_debit += debit
        total_credit += credit
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
    income_accounts = Account.query.filter_by(user_id=user_id, type="Income", book_id=book_id).all()
    expense_accounts = Account.query.filter_by(user_id=user_id, type="Expense", book_id=book_id).all()

    def sum_account(acc):
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0
        return credit - debit if acc.type == "Income" else debit - credit

    income = []
    expense = []
    for acc in income_accounts:
        amt = sum_account(acc)
        income.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "amount": float(amt)
        })
    for acc in expense_accounts:
        amt = sum_account(acc)
        expense.append({
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "amount": float(amt)
        })
    total_income = sum(i["amount"] for i in income)
    total_expense = sum(e["amount"] for e in expense)
    net_income = total_income - total_expense
    return jsonify({
        "income": income,
        "expense": expense,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_income": net_income
    })

@journal_bp.route("/balance-sheet", methods=["GET"])
@jwt_required()
def balance_sheet():
    user_id = get_jwt_identity()
    book_id = request.args.get("book_id", type=int)
    if not book_id:
        return jsonify({"error": "book_id is required"}), 400
    asset_accounts = Account.query.filter_by(user_id=user_id, type="Asset", book_id=book_id).all()
    liability_accounts = Account.query.filter_by(user_id=user_id, type="Liability", book_id=book_id).all()
    equity_accounts = Account.query.filter_by(user_id=user_id, type="Equity", book_id=book_id).all()
    income_accounts = Account.query.filter_by(user_id=user_id, type="Income", book_id=book_id).all()
    expense_accounts = Account.query.filter_by(user_id=user_id, type="Expense", book_id=book_id).all()

    def sum_account(acc):
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id,
            JournalEntry.book_id == book_id
        ).scalar() or 0
        if acc.type == "Asset":
            return debit - credit
        elif acc.type == "Liability" or acc.type == "Equity":
            return credit - debit
        elif acc.type == "Income":
            return credit - debit
        elif acc.type == "Expense":
            return debit - credit
        return 0

    assets = [{
        "account_id": acc.id,
        "account_code": acc.code,
        "account_name": acc.name,
        "balance": float(sum_account(acc))
    } for acc in asset_accounts]
    liabilities = [{
        "account_id": acc.id,
        "account_code": acc.code,
        "account_name": acc.name,
        "balance": float(sum_account(acc))
    } for acc in liability_accounts]
    equity = [{
        "account_id": acc.id,
        "account_code": acc.code,
        "account_name": acc.name,
        "balance": float(sum_account(acc))
    } for acc in equity_accounts]

    total_assets = sum(a["balance"] for a in assets)
    total_liabilities = sum(l["balance"] for l in liabilities)
    total_equity = sum(e["balance"] for e in equity)

    total_income = sum(float(sum_account(acc)) for acc in income_accounts)
    total_expense = sum(float(sum_account(acc)) for acc in expense_accounts)
    net_income = total_income - total_expense

    equity.append({
        "account_id": None,
        "account_code": "",
        "account_name": "Net Income",
        "balance": float(net_income)
    })
    total_equity += net_income

    return jsonify({
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": float(total_assets),
        "total_liabilities": float(total_liabilities),
        "total_equity": float(total_equity),
        "net_income": float(net_income)
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