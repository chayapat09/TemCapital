from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///investment_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Replace with a secure key

db = SQLAlchemy(app)

# -----------------------------
# Centralized Price Data Functions (Mocked)
# -----------------------------
def get_price(symbol):
    # Mock function: return a dummy price based on symbol hash (for demo purposes)
    return round(50 + (hash(symbol) % 100) * 0.1, 2)

def get_history_price(symbol, start_date, end_date):
    # Mock function: return a list of daily data between start_date and end_date.
    history = []
    current = start_date
    while current <= end_date:
        history.append({
            'date': current.strftime("%Y-%m-%d"),
            'open': get_price(symbol),
            'close': get_price(symbol),
            'high': get_price(symbol) + 1,
            'low': get_price(symbol) - 1,
        })
        current += timedelta(days=1)
    return history

# -----------------------------
# Models
# -----------------------------
class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    asset_class = db.Column(db.String(50), nullable=False)  # e.g. Stock, Fixed Income Bond, Crypto, Commodities, Other
    currency = db.Column(db.String(3), nullable=False, default='USD')  # Investment’s trading currency
    total_equity = db.Column(db.Float, default=0.0)
    cost_basis = db.Column(db.Float, default=0.0)
    # current_price will be updated from get_price()
    current_price = db.Column(db.Float, default=0.0)
    transactions = db.relationship('Transaction', backref='investment', lazy=True)

    @property
    def total_value(self):
        # Always use centralized price data for the latest value.
        price = get_price(self.symbol)
        return self.total_equity * price

    @property
    def profit_loss(self):
        return self.total_value - self.cost_basis

    @property
    def average_cost(self):
        return self.cost_basis / self.total_equity if self.total_equity > 0 else 0

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'Buy' or 'Sell'
    transaction_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    broker_note = db.Column(db.String(255), nullable=True)

class CashAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_name = db.Column(db.String(50), nullable=False)
    currency = db.Column(db.String(3), nullable=False)  # USD, THB, SGD
    balance = db.Column(db.Float, default=0.0)

class CashTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdraw, conversion
    from_account_id = db.Column(db.Integer, db.ForeignKey('cash_account.id'), nullable=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey('cash_account.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    conversion_rate = db.Column(db.Float, nullable=True)  # Only for conversion transactions

# -----------------------------
# Currency Conversion Rates (stub)
# -----------------------------
conversion_rates = {
    ('USD', 'THB'): 34.0,
    ('USD', 'SGD'): 1.35,
    ('THB', 'USD'): 1/34.0,
    ('THB', 'SGD'): 1/34.0 * 1.35,
    ('SGD', 'USD'): 1/1.35,
    ('SGD', 'THB'): 1/1.35 * 34.0,
}

def convert_currency(amount, from_currency, to_currency):
    if from_currency == to_currency:
        return amount
    rate = conversion_rates.get((from_currency, to_currency))
    if rate:
        return amount * rate
    else:
        return amount  # Fallback if conversion rate not found

# -----------------------------
# Routes
# -----------------------------

# Dashboard: Investment positions
@app.route('/')
def dashboard():
    investments = Investment.query.all()
    # Update each investment's current_price using centralized data.
    for inv in investments:
        inv.current_price = get_price(inv.symbol)
    return render_template('dashboard.html', investments=investments)

# Transaction Page: Record a transaction (with option to add new investment)
@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
    investments = Investment.query.all()
    cash_accounts = CashAccount.query.all()
    if request.method == 'POST':
        # Check if adding a new investment
        is_new_investment = request.form.get('is_new_investment')
        if is_new_investment == 'on':
            new_symbol = request.form.get('new_symbol')
            new_description = request.form.get('new_description')
            new_asset_class = request.form.get('new_asset_class')
            new_currency = request.form.get('new_currency')
            # Create new investment; initial current_price will be updated via get_price().
            new_investment = Investment(
                symbol=new_symbol,
                description=new_description,
                asset_class=new_asset_class,
                currency=new_currency,
                total_equity=0,
                cost_basis=0,
                current_price=get_price(new_symbol)
            )
            db.session.add(new_investment)
            db.session.commit()
            investment_id = new_investment.id
        else:
            inv_id = request.form.get('investment_id')
            investment_id = int(inv_id) if inv_id and inv_id != 'None' else None

        # Transaction details
        transaction_date = request.form.get('date')
        transaction_type = request.form.get('transaction_type')
        transaction_price = float(request.form.get('transaction_price'))
        quantity = float(request.form.get('quantity'))
        cash_account_id = request.form.get('cash_account_id')
        date_obj = datetime.strptime(transaction_date, '%Y-%m-%d').date()

        # If an investment is selected, verify that the cash account’s currency matches the investment’s currency
        if investment_id:
            inv = Investment.query.get(investment_id)
            if cash_account_id:
                cash_acc = CashAccount.query.get(int(cash_account_id))
                if cash_acc.currency != inv.currency:
                    flash(f"Error: Investment currency ({inv.currency}) does not match cash account currency ({cash_acc.currency}).", "danger")
                    return redirect(url_for('transaction'))

        # Create and record the transaction
        new_txn = Transaction(
            investment_id=investment_id,
            date=date_obj,
            transaction_type=transaction_type,
            transaction_price=transaction_price,
            quantity=quantity
        )
        db.session.add(new_txn)

        # Update Investment if applicable
        if investment_id:
            inv = Investment.query.get(investment_id)
            if transaction_type.lower() == 'buy':
                inv.total_equity += quantity
                inv.cost_basis += transaction_price * quantity
                # Update current price from centralized data.
                inv.current_price = get_price(inv.symbol)
            elif transaction_type.lower() == 'sell':
                if inv.total_equity >= quantity:
                    avg_cost = inv.cost_basis / inv.total_equity if inv.total_equity > 0 else 0
                    inv.total_equity -= quantity
                    inv.cost_basis -= avg_cost * quantity
                    inv.current_price = get_price(inv.symbol)
                else:
                    flash('Not enough equity to sell', 'danger')
                    return redirect(url_for('transaction'))

        # Update CashAccount and record a CashTransaction
        if cash_account_id:
            cash_acc = CashAccount.query.get(int(cash_account_id))
            amount = transaction_price * quantity
            if transaction_type.lower() == 'buy':
                cash_acc.balance -= amount
                txn_type = 'investment_buy'
            elif transaction_type.lower() == 'sell':
                cash_acc.balance += amount
                txn_type = 'investment_sell'
            ct = CashTransaction(
                date=date_obj,
                transaction_type=txn_type,
                from_account_id=cash_acc.id if transaction_type.lower() == 'buy' else None,
                to_account_id=cash_acc.id if transaction_type.lower() == 'sell' else None,
                amount=amount
            )
            db.session.add(ct)
        
        db.session.commit()
        flash('Transaction recorded successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('transaction.html', investments=investments, cash_accounts=cash_accounts)

# Transaction Management: List, search, edit, and delete transactions
@app.route('/transactions', methods=['GET'])
def transactions():
    search = request.args.get('search', '')
    if search:
        txns = Transaction.query.join(Investment, isouter=True).filter(
            or_(Investment.symbol.ilike(f"%{search}%"),
                Transaction.broker_note.ilike(f"%{search}%"))
        ).order_by(Transaction.date.desc()).all()
    else:
        txns = Transaction.query.order_by(Transaction.date.desc()).all()

    return render_template('transactions.html', transactions=txns, search=search)

@app.route('/transaction/edit/<int:transaction_id>', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    investments = Investment.query.all()
    if request.method == 'POST':
        txn.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        txn.transaction_type = request.form.get('transaction_type')
        txn.transaction_price = float(request.form.get('transaction_price'))
        txn.quantity = float(request.form.get('quantity'))
        inv_id = request.form.get('investment_id')
        txn.investment_id = int(inv_id) if inv_id and inv_id != 'None' else None
        db.session.commit()
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('transactions'))
    return render_template('edit_transaction.html', transaction=txn, investments=investments)

@app.route('/transaction/delete/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    db.session.delete(txn)
    db.session.commit()
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('transactions'))

# Cash Management: List cash accounts and allow CRUD operations
@app.route('/cash', methods=['GET'])
def cash_list():
    accounts = CashAccount.query.all()
    # Also list recent cash transactions if desired
    cash_txns = CashTransaction.query.order_by(CashTransaction.date.desc()).all()
    return render_template('cash.html', cash_accounts=accounts, cash_transactions=cash_txns)

@app.route('/cash/add', methods=['GET', 'POST'])
def add_cash():
    if request.method == 'POST':
        account_name = request.form.get('account_name')
        currency = request.form.get('currency')
        balance = float(request.form.get('balance'))
        new_acc = CashAccount(account_name=account_name, currency=currency, balance=balance)
        db.session.add(new_acc)
        # Also record a deposit transaction for initial balance
        ct = CashTransaction(
            date=datetime.utcnow().date(),
            transaction_type='deposit',
            to_account_id=new_acc.id,
            amount=balance
        )
        db.session.add(ct)
        db.session.commit()
        flash('Cash account added successfully!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('add_cash.html')

@app.route('/cash/edit/<int:cash_id>', methods=['GET', 'POST'])
def edit_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    if request.method == 'POST':
        acc.account_name = request.form.get('account_name')
        acc.currency = request.form.get('currency')
        acc.balance = float(request.form.get('balance'))
        db.session.commit()
        flash('Cash account updated successfully!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('edit_cash.html', cash_account=acc)

@app.route('/cash/delete/<int:cash_id>', methods=['POST'])
def delete_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    db.session.delete(acc)
    db.session.commit()
    flash('Cash account deleted successfully!', 'success')
    return redirect(url_for('cash_list'))

# New routes for Cash Operations: Deposit, Withdraw, Convert
@app.route('/cash/deposit/<int:cash_id>', methods=['GET', 'POST'])
def deposit_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        acc.balance += amount
        ct = CashTransaction(
            date=datetime.utcnow().date(),
            transaction_type='deposit',
            to_account_id=acc.id,
            amount=amount
        )
        db.session.add(ct)
        db.session.commit()
        flash('Deposit successful!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('deposit_cash.html', cash_account=acc)

@app.route('/cash/withdraw/<int:cash_id>', methods=['GET', 'POST'])
def withdraw_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        if acc.balance >= amount:
            acc.balance -= amount
            ct = CashTransaction(
                date=datetime.utcnow().date(),
                transaction_type='withdraw',
                from_account_id=acc.id,
                amount=amount
            )
            db.session.add(ct)
            db.session.commit()
            flash('Withdrawal successful!', 'success')
        else:
            flash('Insufficient funds!', 'danger')
        return redirect(url_for('cash_list'))
    return render_template('withdraw_cash.html', cash_account=acc)

@app.route('/cash/convert/<int:from_id>', methods=['GET', 'POST'])
def convert_cash(from_id):
    from_acc = CashAccount.query.get_or_404(from_id)
    accounts = CashAccount.query.filter(CashAccount.id != from_id).all()
    if request.method == 'POST':
        to_id = int(request.form.get('to_account_id'))
        amount = float(request.form.get('amount'))
        conversion_rate = float(request.form.get('conversion_rate'))
        to_acc = CashAccount.query.get_or_404(to_id)
        # Check that the from_acc has sufficient funds
        if from_acc.balance < amount:
            flash('Insufficient funds in source account!', 'danger')
            return redirect(url_for('convert_cash', from_id=from_id))
        # Deduct from source account
        from_acc.balance -= amount
        # Add to destination account with conversion
        converted_amount = amount * conversion_rate
        to_acc.balance += converted_amount
        ct = CashTransaction(
            date=datetime.utcnow().date(),
            transaction_type='conversion',
            from_account_id=from_acc.id,
            to_account_id=to_acc.id,
            amount=amount,  # original amount deducted
            conversion_rate=conversion_rate
        )
        db.session.add(ct)
        db.session.commit()
        flash('Conversion successful!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('convert_cash.html', from_account=from_acc, accounts=accounts)

# Investment Position Edit: Update investment details (including currency)
@app.route('/position/edit/<int:investment_id>', methods=['GET', 'POST'])
def edit_position(investment_id):
    inv = Investment.query.get_or_404(investment_id)
    asset_classes = ["Stock", "Fixed Income Bond", "Crypto", "Commodities", "Other"]
    currencies = ["USD", "THB", "SGD"]
    if request.method == 'POST':
        inv.symbol = request.form.get('symbol')
        inv.description = request.form.get('description')
        inv.asset_class = request.form.get('asset_class')
        inv.currency = request.form.get('currency')
        inv.current_price = get_price(inv.symbol)
        db.session.commit()
        flash('Investment updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_position.html', investment=inv, asset_classes=asset_classes, currencies=currencies)

# Summary: Monthly wealth evolution and breakdown by asset category, with charts
@app.route('/summary')
def summary():
    selected_currency = request.args.get('currency', 'USD')
    # Retrieve all investments (update current prices from centralized data)
    investments = Investment.query.all()
    for inv in investments:
        inv.current_price = get_price(inv.symbol)
    # For monthly evolution, we use transactions.
    txns = Transaction.query.order_by(Transaction.date).all()
    if txns:
        first_date = txns[0].date
        start_date = first_date if isinstance(first_date, date) else first_date.date()
    else:
        start_date = datetime.utcnow().date()
    end_date = datetime.utcnow().date()
    
    timeline = []
    current_date = start_date
    # Build timeline by month
    while current_date <= end_date:
        timeline.append(current_date)
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year+1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month+1)
    
    monthly_data = []
    # For each month, aggregate investments (converting each investment’s value into selected currency)
    for month_start in timeline:
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year+1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month+1)
        # For simplicity, we sum over current investments (ignoring historical transaction details)
        total_asset_value = 0
        total_cost_basis = 0
        for inv in investments:
            # Only include investments whose transactions occurred before next_month
            inv_txns = [t for t in inv.transactions if t.date < next_month]
            if not inv_txns:
                continue
            # Recalculate total equity and cost_basis from these transactions:
            equity = 0
            cost = 0
            for t in inv_txns:
                if t.transaction_type.lower() == 'buy':
                    equity += t.quantity
                    cost += t.transaction_price * t.quantity
                elif t.transaction_type.lower() == 'sell':
                    avg_cost = (cost / equity) if equity > 0 else 0
                    equity -= t.quantity
                    cost -= avg_cost * t.quantity
            # Get current price from centralized data and compute values in investment currency.
            price = get_price(inv.symbol)
            asset_value = equity * price
            # Convert values from inv.currency to selected_currency.
            asset_value_conv = convert_currency(asset_value, inv.currency, selected_currency)
            cost_conv = convert_currency(cost, inv.currency, selected_currency)
            total_asset_value += asset_value_conv
            total_cost_basis += cost_conv
        profit_loss = total_asset_value - total_cost_basis
        monthly_data.append({
            'month': month_start.strftime("%Y-%m"),
            'asset_value': round(total_asset_value, 2),
            'cost_basis': round(total_cost_basis, 2),
            'profit_loss': round(profit_loss, 2)
        })
    
    # Breakdown by asset category: aggregate each investment's current value and cost basis (converted)
    category_data = {}
    for inv in investments:
        price = get_price(inv.symbol)
        asset_value = inv.total_equity * price
        asset_value_conv = convert_currency(asset_value, inv.currency, selected_currency)
        cost_conv = convert_currency(inv.cost_basis, inv.currency, selected_currency)
        cat = inv.asset_class
        if cat in category_data:
            category_data[cat]['asset_value'] += asset_value_conv
            category_data[cat]['cost_basis'] += cost_conv
        else:
            category_data[cat] = {'asset_value': asset_value_conv, 'cost_basis': cost_conv}
    for cat in category_data:
        category_data[cat]['profit_loss'] = round(category_data[cat]['asset_value'] - category_data[cat]['cost_basis'], 2)
        category_data[cat]['asset_value'] = round(category_data[cat]['asset_value'], 2)
        category_data[cat]['cost_basis'] = round(category_data[cat]['cost_basis'], 2)
    
    return render_template('summary.html', 
                           monthly_data=monthly_data, 
                           category_data=category_data,
                           currency=selected_currency)

# -----------------------------
# Database Initialization
# -----------------------------
def init_db():
    db.create_all()
    # Create a default cash account if none exist
    if not CashAccount.query.first():
        default_account = CashAccount(account_name='Main Account', currency='USD', balance=10000)
        db.session.add(default_account)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True , port=8080)
