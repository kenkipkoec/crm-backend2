from flask import Blueprint, request, jsonify
from models import db, JournalEntry, JournalLine, Account
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None

journal_bp = Blueprint('journal', __name__)

@journal_bp.route('', methods=['GET', 'POST'])
@jwt_required()
def journal_entries():
    user_id = get_jwt_identity()
    if request.method == 'GET':
        entries = JournalEntry.query.filter_by(user_id=user_id).order_by(JournalEntry.date.desc()).all()
        result = []
        for entry in entries:
            lines = []
            for line in entry.lines:
                acc = Account.query.get(line.account_id)
                lines.append({
                    "account_id": line.account_id,
                    "account_code": acc.code if acc else "",
                    "account_name": acc.name if acc else "",
                    "debit": float(line.debit),
                    "credit": float(line.credit)
                })
            result.append({
                "id": entry.id,
                "date": entry.date.isoformat(),
                "description": entry.description,
                "lines": lines
            })
        return jsonify(result)
    else:
        data = request.get_json()
        # Validate required fields
        if not data or 'date' not in data or 'lines' not in data or not data['lines']:
            return jsonify({'error': 'Date and at least two journal lines are required.'}), 400

        if len(data['lines']) < 2:
            return jsonify({'error': 'At least two journal lines are required.'}), 400

        # Validate date format
        entry_date = parse_date(data['date'])
        if not entry_date:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

        # Validate accounts and sum debits/credits
        total_debit = 0
        total_credit = 0
        for line in data['lines']:
            if 'account_id' not in line:
                return jsonify({'error': 'Each line must have an account_id.'}), 400
            account = Account.query.get(line['account_id'])
            if not account:
                return jsonify({'error': f"Account ID {line['account_id']} does not exist."}), 400
            try:
                debit = float(line.get('debit', 0))
                credit = float(line.get('credit', 0))
            except Exception:
                return jsonify({'error': 'Debit and credit must be numbers.'}), 400
            total_debit += debit
            total_credit += credit

        if round(total_debit, 2) != round(total_credit, 2):
            return jsonify({'error': 'Total debits and credits must be equal.'}), 400

        try:
            entry = JournalEntry(
                user_id=user_id,
                date=entry_date,
                description=data.get('description', '')
            )
            db.session.add(entry)
            db.session.flush()  # Get entry.id before adding lines

            for line in data['lines']:
                journal_line = JournalLine(
                    entry_id=entry.id,
                    account_id=line['account_id'],
                    debit=float(line.get('debit', 0)),
                    credit=float(line.get('credit', 0))
                )
                db.session.add(journal_line)
            db.session.commit()
            return jsonify({'id': entry.id, 'message': 'Journal entry created'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to create journal entry: {str(e)}'}), 500

@journal_bp.route('/ledger/<int:account_id>', methods=['GET'])
def general_ledger(account_id):
    start_date = parse_date(request.args.get('start_date')) if request.args.get('start_date') else None
    end_date = parse_date(request.args.get('end_date')) if request.args.get('end_date') else None

    account = Account.query.get(account_id)
    if not account:
        return jsonify({'error': 'Account not found'}), 404

    lines_query = JournalLine.query.filter_by(account_id=account_id)
    if start_date:
        lines_query = lines_query.join(JournalEntry).filter(JournalEntry.date >= start_date)
    if end_date:
        lines_query = lines_query.join(JournalEntry).filter(JournalEntry.date <= end_date)
    lines = lines_query.order_by(JournalLine.id).all()
    running_balance = 0
    ledger = []
    for line in lines:
        running_balance += float(line.debit) - float(line.credit)
        ledger.append({
            'entry_id': line.entry_id,
            'date': line.entry.date.isoformat(),
            'description': line.entry.description,
            'debit': float(line.debit),
            'credit': float(line.credit),
            'balance': running_balance
        })
    return jsonify({
        'account': {
            'id': account.id,
            'name': account.name,
            'type': account.type,
            'code': account.code
        },
        'ledger': ledger
    })

@journal_bp.route('/trial-balance', methods=['GET'])
@jwt_required()
def trial_balance():
    user_id = get_jwt_identity()
    accounts = Account.query.filter_by(user_id=user_id).all()
    result = []
    total_debit = 0
    total_credit = 0
    for acc in accounts:
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id
        ).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id
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

@journal_bp.route('/income-statement')
@jwt_required()
def income_statement():
    user_id = get_jwt_identity()
    income_accounts = Account.query.filter_by(user_id=user_id, type="Income").all()
    expense_accounts = Account.query.filter_by(user_id=user_id, type="Expense").all()

    def sum_account(acc):
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id
        ).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id
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

@journal_bp.route('/balance-sheet')
@jwt_required()
def balance_sheet():
    user_id = get_jwt_identity()
    asset_accounts = Account.query.filter_by(user_id=user_id, type="Asset").all()
    liability_accounts = Account.query.filter_by(user_id=user_id, type="Liability").all()
    equity_accounts = Account.query.filter_by(user_id=user_id, type="Equity").all()
    income_accounts = Account.query.filter_by(user_id=user_id, type="Income").all()
    expense_accounts = Account.query.filter_by(user_id=user_id, type="Expense").all()

    def sum_account(acc):
        debit = db.session.query(db.func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id
        ).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.user_id == user_id
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

@journal_bp.route('/<int:entry_id>', methods=['PUT'])
@jwt_required()
def edit_journal_entry(entry_id):
    user_id = get_jwt_identity()
    entry = JournalEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()
    data = request.get_json()
    entry.date = data.get('date', entry.date)
    entry.description = data.get('description', entry.description)
    # Remove old lines
    JournalLine.query.filter_by(entry_id=entry.id).delete()
    # Add new lines
    for line in data['lines']:
        db.session.add(JournalLine(
            entry_id=entry.id,
            account_id=line['account_id'],
            debit=line['debit'],
            credit=line['credit']
        ))
    db.session.commit()
    return jsonify({'message': 'Journal entry updated'})

@journal_bp.route('/<int:entry_id>', methods=['DELETE'])
@jwt_required()
def delete_journal_entry(entry_id):
    user_id = get_jwt_identity()
    entry = JournalEntry.query.filter_by(id=entry_id, user_id=user_id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'message': 'Journal entry deleted'})