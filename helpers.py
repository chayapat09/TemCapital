from datetime import datetime, date, timedelta
from models import Investment, CashTransaction, CashAccount, Bond, Dividend, ActivityLog, db, Transaction
from flask_login import current_user

def get_price(symbol):
    # Returns a dummy price based on the symbol hash (for demo purposes)
    return round(50 + (hash(symbol) % 100) * 0.1, 2)

def get_history_price(symbol, start_date, end_date):
    history = []
    current = start_date
    while current <= end_date:
        price = get_price(symbol)
        history.append({
            'date': current.strftime("%Y-%m-%d"),
            'open': price,
            'close': price,
            'high': price + 1,
            'low': price - 1,
        })
        current += timedelta(days=1)
    return history

conversion_rates = {
    ('USD', 'THB'): 34.0,
    ('USD', 'SGD'): 1.35,
    ('THB', 'USD'): 1 / 34.0,
    ('THB', 'SGD'): 1 / 34.0 * 1.35,
    ('SGD', 'USD'): 1 / 1.35,
    ('SGD', 'THB'): 1 / 1.35 * 34.0,
}

def convert_currency(amount, from_currency, to_currency):
    if from_currency == to_currency:
        return amount
    rate = conversion_rates.get((from_currency, to_currency))
    if rate:
        return amount * rate
    else:
        return amount

def compute_user_investment(investment, user_id):
    """
    Compute the user's holding for a given investment using FIFO method.
    Returns (total_shares, average_cost).
    """
    txns = Transaction.query.filter_by(investment_id=investment.id, user_id=user_id).order_by(Transaction.date).all()
    lots = []
    for t in txns:
        if t.transaction_type.lower() == 'buy':
            lots.append({'quantity': t.quantity, 'price': t.transaction_price})
        elif t.transaction_type.lower() == 'sell':
            qty_to_sell = t.quantity
            while qty_to_sell > 0 and lots:
                lot = lots[0]
                if lot['quantity'] > qty_to_sell:
                    lot['quantity'] -= qty_to_sell
                    qty_to_sell = 0
                else:
                    qty_to_sell -= lot['quantity']
                    lots.pop(0)
    total_shares = sum(lot['quantity'] for lot in lots)
    total_cost = sum(lot['quantity'] * lot['price'] for lot in lots)
    avg_cost = total_cost / total_shares if total_shares > 0 else 0
    return total_shares, avg_cost

def compute_realized_gain(investment, user_id, start_date, end_date):
    """
    Compute the realized gain for an investment for a user using FIFO for transactions within the period.
    """
    txns = Transaction.query.filter_by(investment_id=investment.id, user_id=user_id).order_by(Transaction.date).all()
    lots = []
    realized_gain = 0
    for t in txns:
        if t.transaction_type.lower() == 'buy':
            lots.append({'quantity': t.quantity, 'price': t.transaction_price})
        elif t.transaction_type.lower() == 'sell':
            qty_to_sell = t.quantity
            if start_date <= t.date.date() <= end_date:
                while qty_to_sell > 0 and lots:
                    lot = lots[0]
                    if lot['quantity'] > qty_to_sell:
                        realized_gain += qty_to_sell * (t.transaction_price - lot['price'])
                        lot['quantity'] -= qty_to_sell
                        qty_to_sell = 0
                    else:
                        realized_gain += lot['quantity'] * (t.transaction_price - lot['price'])
                        qty_to_sell -= lot['quantity']
                        lots.pop(0)
            else:
                while qty_to_sell > 0 and lots:
                    lot = lots[0]
                    if lot['quantity'] > qty_to_sell:
                        lot['quantity'] -= qty_to_sell
                        qty_to_sell = 0
                    else:
                        qty_to_sell -= lot['quantity']
                        lots.pop(0)
    return realized_gain

def log_activity(action, details=""):
    user_id = current_user.id if current_user.is_authenticated else None
    log = ActivityLog(user_id=user_id, action=action, details=details)
    db.session.add(log)
    db.session.commit()

def get_period_range(period_type, period_value):
    if period_type == 'yearly':
        year = int(period_value)
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
    elif period_type == 'quarterly':
        try:
            year_str, quarter_str = period_value.split('-Q')
            year = int(year_str)
            quarter = int(quarter_str)
        except Exception:
            today = date.today()
            year = today.year
            quarter = (today.month - 1) // 3 + 1
        if quarter == 1:
            start_date = date(year, 1, 1)
            end_date = date(year, 3, 31)
        elif quarter == 2:
            start_date = date(year, 4, 1)
            end_date = date(year, 6, 30)
        elif quarter == 3:
            start_date = date(year, 7, 1)
            end_date = date(year, 9, 30)
        elif quarter == 4:
            start_date = date(year, 10, 1)
            end_date = date(year, 12, 31)
        else:
            start_date = date.today()
            end_date = date.today()
    else:
        start_date = date.today()
        end_date = date.today()
    return start_date, end_date

def calculate_cash_balance_as_of(acc, end_date):
    balance = 0
    transactions = CashTransaction.query.filter(CashTransaction.date <= end_date).all()
    for txn in transactions:
        if txn.transaction_type == 'deposit' and txn.to_account_id == acc.id:
            balance += txn.amount
        elif txn.transaction_type == 'withdraw' and txn.from_account_id == acc.id:
            balance -= txn.amount
        elif txn.transaction_type == 'investment_buy' and txn.from_account_id == acc.id:
            balance -= txn.amount
        elif txn.transaction_type == 'investment_sell' and txn.to_account_id == acc.id:
            balance += txn.amount
        elif txn.transaction_type == 'conversion':
            if txn.from_account_id == acc.id:
                balance -= txn.amount
            if txn.to_account_id == acc.id and txn.conversion_rate:
                balance += txn.amount * txn.conversion_rate
    return balance

def get_periods(period_type, request):
    periods = []
    today = date.today()
    if period_type == 'yearly':
        try:
            start_year = int(request.args.get('start_year', today.year))
            end_year = int(request.args.get('end_year', today.year))
        except ValueError:
            start_year = today.year
            end_year = today.year
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        if end_year > today.year:
            end_year = today.year
        if end_year - start_year + 1 > 5:
            end_year = start_year + 4
        for year in range(start_year, end_year + 1):
            s = date(year, 1, 1)
            e = date(year, 12, 31)
            label = str(year)
            if year == today.year and today < e:
                label += " (YTD)"
                e = today
            periods.append((label, s, e))
    elif period_type == 'quarterly':
        try:
            selected_year = int(request.args.get('year', today.year))
        except ValueError:
            selected_year = today.year
        if selected_year > today.year:
            selected_year = today.year
        quarters = [
            ('Q1', date(selected_year, 1, 1), date(selected_year, 3, 31)),
            ('Q2', date(selected_year, 4, 1), date(selected_year, 6, 30)),
            ('Q3', date(selected_year, 7, 1), date(selected_year, 9, 30)),
            ('Q4', date(selected_year, 10, 1), date(selected_year, 12, 31))
        ]
        for q, s, e in quarters:
            if s > today:
                continue
            label = f"{selected_year}-{q}"
            if s <= today < e:
                label += " (YTD)"
                e = today
            periods.append((label, s, e))
    return periods

def get_investment_quote_currency(investment, user_id):
    txns = Transaction.query.filter_by(investment_id=investment.id, user_id=user_id).all()
    if txns:
        return txns[0].quote_currency
    return 'USD'
