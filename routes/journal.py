from flask import Blueprint, request, jsonify
from models import db, JournalEntry, JournalLine, Account
from datetime import datetime

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None

journal_bp = Blueprint('journal', __name__)

@journal_bp.route('/', methods=['GET'])
def get_entries():
    start_date = parse_date(request.args.get('start_date')) if request.args.get('start_date') else None
    end_date = parse_date(request.args.get('end_date')) if request.args.get('end_date') else None

    query = JournalEntry.query
    if start_date:
        query = query.filter(JournalEntry.date >= start_date)
    if end_date:
        query = query.filter(JournalEntry.date <= end_date)

    entries = query.all()
    result = []
    for entry in entries:
        lines = [{
            'id': line.id,
            'account_id': line.account_id,
            'account_name': line.account.name,
            'debit': float(line.debit),
            'credit': float(line.credit)
        } for line in entry.lines]
        result.append({
            'id': entry.id,
            'date': entry.date.isoformat(),
            'description': entry.description,
            'lines': lines
        })
    return jsonify(result)

@journal_bp.route('/', methods=['POST'])
def add_entry():
    data = request.get_json()
    # Validate required fields
    if not data or 'date' not in data or 'lines' not in data or not data['lines']:
        return jsonify({'error': 'Date and at least one journal line are required.'}), 400

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
        debit = float(line.get('debit', 0))
        credit = float(line.get('credit', 0))
        total_debit += debit
        total_credit += credit

    if round(total_debit, 2) != round(total_credit, 2):
        return jsonify({'error': 'Total debits and credits must be equal.'}), 400

    # Create entry and lines
    entry = JournalEntry(
        date=entry_date,
        description=data.get('description', '')
    )
    db.session.add(entry)
    db.session.flush()  # Get entry.id before adding lines

    for line in data['lines']:
        journal_line = JournalLine(
            entry_id=entry.id,
            account_id=line['account_id'],
            debit=line.get('debit', 0),
            credit=line.get('credit', 0)
        )
        db.session.add(journal_line)
    db.session.commit()
    return jsonify({'message': 'Journal entry created'}), 201

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
def trial_balance():
    start_date = parse_date(request.args.get('start_date')) if request.args.get('start_date') else None
    end_date = parse_date(request.args.get('end_date')) if request.args.get('end_date') else None

    accounts = Account.query.all()
    result = []
    total_debit = 0
    total_credit = 0
    for acc in accounts:
        lines_query = JournalLine.query.filter_by(account_id=acc.id)
        if start_date:
            lines_query = lines_query.join(JournalEntry).filter(JournalEntry.date >= start_date)
        if end_date:
            lines_query = lines_query.join(JournalEntry).filter(JournalEntry.date <= end_date)
        debit = db.session.query(db.func.sum(JournalLine.debit)).filter(JournalLine.id.in_([l.id for l in lines_query])).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).filter(JournalLine.id.in_([l.id for l in lines_query])).scalar() or 0
        balance = float(debit) - float(credit)
        result.append({
            'account_id': acc.id,
            'account_name': acc.name,
            'account_code': acc.code,
            'debit': float(debit),
            'credit': float(credit),
            'balance': balance
        })
        total_debit += float(debit)
        total_credit += float(credit)
    return jsonify({
        'accounts': result,
        'total_debit': total_debit,
        'total_credit': total_credit
    })

@journal_bp.route('/income-statement', methods=['GET'])
def income_statement():
    start_date = parse_date(request.args.get('start_date')) if request.args.get('start_date') else None
    end_date = parse_date(request.args.get('end_date')) if request.args.get('end_date') else None

    income_types = ['Revenue', 'Income']
    expense_types = ['Expense']

    income_accounts = Account.query.filter(Account.type.in_(income_types)).all()
    expense_accounts = Account.query.filter(Account.type.in_(expense_types)).all()

    total_income = 0
    total_expense = 0
    income_details = []
    expense_details = []

    for acc in income_accounts:
        lines_query = JournalLine.query.filter_by(account_id=acc.id)
        if start_date:
            lines_query = lines_query.join(JournalEntry).filter(JournalEntry.date >= start_date)
        if end_date:
            lines_query = lines_query.join(JournalEntry).filter(JournalEntry.date <= end_date)
        credit = db.session.query(db.func.sum(JournalLine.credit)).filter(JournalLine.id.in_([l.id for l in lines_query])).scalar() or 0
        debit = db.session.query(db.func.sum(JournalLine.debit)).filter(JournalLine.id.in_([l.id for l in lines_query])).scalar() or 0
        amount = float(credit) - float(debit)
        total_income += amount
        income_details.append({
            'account_id': acc.id,
            'account_name': acc.name,
            'amount': amount
        })

    for acc in expense_accounts:
        lines_query = JournalLine.query.filter_by(account_id=acc.id)
        if start_date:
            lines_query = lines_query.join(JournalEntry).filter(JournalEntry.date >= start_date)
        if end_date:
            lines_query = lines_query.join(JournalEntry).filter(JournalEntry.date <= end_date)
        debit = db.session.query(db.func.sum(JournalLine.debit)).filter(JournalLine.id.in_([l.id for l in lines_query])).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).filter(JournalLine.id.in_([l.id for l in lines_query])).scalar() or 0
        amount = float(debit) - float(credit)
        total_expense += amount
        expense_details.append({
            'account_id': acc.id,
            'account_name': acc.name,
            'amount': amount
        })

    net_income = total_income - total_expense

    return jsonify({
        'income': income_details,
        'expense': expense_details,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_income': net_income
    })

@journal_bp.route('/balance-sheet', methods=['GET'])
def balance_sheet():
    asset_types = ['Asset']
    liability_types = ['Liability']
    equity_types = ['Equity']

    def get_accounts_by_type(types):
        return Account.query.filter(Account.type.in_(types)).all()

    def get_balance(acc):
        debit = db.session.query(db.func.sum(JournalLine.debit)).filter_by(account_id=acc.id).scalar() or 0
        credit = db.session.query(db.func.sum(JournalLine.credit)).filter_by(account_id=acc.id).scalar() or 0
        if acc.type == 'Asset':
            return float(debit) - float(credit)
        else:
            return float(credit) - float(debit)

    assets = get_accounts_by_type(asset_types)
    liabilities = get_accounts_by_type(liability_types)
    equity = get_accounts_by_type(equity_types)

    asset_total = 0
    liability_total = 0
    equity_total = 0

    asset_details = []
    for acc in assets:
        bal = get_balance(acc)
        asset_total += bal
        asset_details.append({'account_id': acc.id, 'account_name': acc.name, 'balance': bal})

    liability_details = []
    for acc in liabilities:
        bal = get_balance(acc)
        liability_total += bal
        liability_details.append({'account_id': acc.id, 'account_name': acc.name, 'balance': bal})

    equity_details = []
    for acc in equity:
        bal = get_balance(acc)
        equity_total += bal
        equity_details.append({'account_id': acc.id, 'account_name': acc.name, 'balance': bal})

    return jsonify({
        'assets': asset_details,
        'liabilities': liability_details,
        'equity': equity_details,
        'total_assets': asset_total,
        'total_liabilities': liability_total,
        'total_equity': equity_total
    })