from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
import csv, io

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///investment_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Replace with a secure key

db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# -----------------------------
# Models
# -----------------------------

# User Model for Authentication
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password , method='pbkdf2')
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Investment Model – used for Stocks, Crypto, Commodities, etc.
class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    asset_class = db.Column(db.String(50), nullable=False)  # e.g. Stock, Fixed Income Bond, Crypto, Commodities, Other
    currency = db.Column(db.String(3), nullable=False, default='USD')
    total_equity = db.Column(db.Float, default=0.0)  # number of units/shares held
    cost_basis = db.Column(db.Float, default=0.0)    # average acquisition price per unit
    current_price = db.Column(db.Float, default=0.0)
    wallet_address = db.Column(db.String(255), nullable=True)  # For crypto assets
    transactions = db.relationship('Transaction', backref='investment', lazy=True)

    @property
    def total_value(self):
        price = get_price(self.symbol)
        return self.total_equity * price

    @property
    def profit_loss(self):
        return (get_price(self.symbol) - self.cost_basis) * self.total_equity

# Transaction Model for Buy/Sell transactions
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'Buy' or 'Sell'
    transaction_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    broker_note = db.Column(db.String(255), nullable=True)

# Cash Account Model
class CashAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_name = db.Column(db.String(50), nullable=False)
    currency = db.Column(db.String(3), nullable=False)  # USD, THB, SGD
    balance = db.Column(db.Float, default=0.0)

# Cash Transaction Model – logs deposits, withdrawals, conversions, and investment cash moves
class CashTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdraw, conversion, investment_buy, investment_sell
    from_account_id = db.Column(db.Integer, db.ForeignKey('cash_account.id'), nullable=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey('cash_account.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    conversion_rate = db.Column(db.Float, nullable=True)

# Bond Model for the Bond Module
class Bond(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    face_value = db.Column(db.Float, nullable=False)
    coupon_rate = db.Column(db.Float, nullable=False)  # e.g., 5 for 5%
    maturity_date = db.Column(db.Date, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    cost_basis = db.Column(db.Float, default=0.0)  # average acquisition price per bond

    @property
    def total_value(self):
        return self.quantity * self.face_value

    @property
    def yield_to_maturity(self):
        years_to_maturity = (self.maturity_date - date.today()).days / 365.25
        if years_to_maturity > 0:
            annual_coupon = self.face_value * (self.coupon_rate / 100)
            return (annual_coupon + ((self.face_value - self.cost_basis) / years_to_maturity)) / ((self.face_value + self.cost_basis)/2) * 100
        return 0

# Dividend Model for stock dividend monitoring
class Dividend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(255), nullable=True)

# Activity Log Model for recording user actions and system events
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)  # May be null for system actions
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)

# -----------------------------
# Centralized Price Data Functions (Mocked)
# -----------------------------
def get_price(symbol):
    # Returns a dummy price based on the symbol hash (for demo purposes)
    return round(50 + (hash(symbol) % 100) * 0.1, 2)

def get_history_price(symbol, start_date, end_date):
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

# Currency Conversion Rates (stub)
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
# Activity Logging Helper
# -----------------------------
def log_activity(action, details=""):
    user_id = current_user.id if current_user.is_authenticated else None
    log = ActivityLog(user_id=user_id, action=action, details=details)
    db.session.add(log)
    db.session.commit()

# -----------------------------
# Routes for Authentication
# -----------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
         username = request.form.get('username')
         password = request.form.get('password')
         if User.query.filter_by(username=username).first():
             flash('Username already exists', 'danger')
             return redirect(url_for('register'))
         user = User(username=username)
         user.set_password(password)
         db.session.add(user)
         db.session.commit()
         flash('Registration successful, please log in.', 'success')
         return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
         username = request.form.get('username')
         password = request.form.get('password')
         user = User.query.filter_by(username=username).first()
         if user and user.check_password(password):
             login_user(user)
             flash('Logged in successfully.', 'success')
             log_activity("User Login", f"User {username} logged in.")
             return redirect(url_for('dashboard'))
         else:
             flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity("User Logout", f"User {current_user.username} logged out.")
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# -----------------------------
# Dashboard & Investment Management
# -----------------------------
@app.route('/')
@login_required
def dashboard():
    investments = Investment.query.all()
    for inv in investments:
        inv.current_price = get_price(inv.symbol)
    # Combined net worth: investments + cash + bonds
    total_investment = sum(inv.total_value for inv in investments)
    cash_accounts = CashAccount.query.all()
    total_cash = sum(cash.balance for cash in cash_accounts)
    bonds = Bond.query.all()
    total_bonds = sum(bond.total_value for bond in bonds)
    net_worth = total_investment + total_cash + total_bonds
    return render_template('dashboard.html', investments=investments,
                           cash_accounts=cash_accounts, bonds=bonds, net_worth=net_worth)

# Investment Transaction Page – record a buy/sell transaction (with optional new investment creation)
@app.route('/transaction', methods=['GET', 'POST'])
@login_required
def transaction():
    investments = Investment.query.all()
    cash_accounts = CashAccount.query.all()
    if request.method == 'POST':
        is_new_investment = request.form.get('is_new_investment')
        if is_new_investment == 'on':
            new_symbol = request.form.get('new_symbol')
            new_description = request.form.get('new_description')
            new_asset_class = request.form.get('new_asset_class')
            new_currency = request.form.get('new_currency')
            new_wallet_address = request.form.get('new_wallet_address')  # For crypto
            new_investment = Investment(
                symbol=new_symbol,
                description=new_description,
                asset_class=new_asset_class,
                currency=new_currency,
                total_equity=0,
                cost_basis=0,
                current_price=get_price(new_symbol),
                wallet_address=new_wallet_address
            )
            db.session.add(new_investment)
            db.session.commit()
            investment_id = new_investment.id
            log_activity("New Investment Added", f"Investment {new_symbol} added.")
        else:
            inv_id = request.form.get('investment_id')
            investment_id = int(inv_id) if inv_id and inv_id != 'None' else None

        transaction_date = request.form.get('date')
        transaction_type = request.form.get('transaction_type')
        transaction_price = float(request.form.get('transaction_price'))
        quantity = float(request.form.get('quantity'))
        broker_note = request.form.get('broker_note')
        cash_account_id = request.form.get('cash_account_id')
        date_obj = datetime.strptime(transaction_date, '%Y-%m-%d').date()

        if investment_id:
            inv = Investment.query.get(investment_id)
            if cash_account_id:
                cash_acc = CashAccount.query.get(int(cash_account_id))
                if cash_acc.currency != inv.currency:
                    flash(f"Error: Investment currency ({inv.currency}) does not match cash account currency ({cash_acc.currency}).", "danger")
                    return redirect(url_for('transaction'))
        new_txn = Transaction(
            investment_id=investment_id,
            date=date_obj,
            transaction_type=transaction_type,
            transaction_price=transaction_price,
            quantity=quantity,
            broker_note=broker_note
        )
        db.session.add(new_txn)

        if investment_id:
            inv = Investment.query.get(investment_id)
            if transaction_type.lower() == 'buy':
                # Update average cost basis on a buy transaction
                if inv.total_equity == 0:
                    inv.cost_basis = transaction_price
                    inv.total_equity = quantity
                else:
                    new_total = inv.total_equity + quantity
                    new_avg = (inv.cost_basis * inv.total_equity + transaction_price * quantity) / new_total
                    inv.cost_basis = new_avg
                    inv.total_equity = new_total
                inv.current_price = get_price(inv.symbol)
            elif transaction_type.lower() == 'sell':
                if inv.total_equity >= quantity:
                    if inv.total_equity == quantity:
                        inv.total_equity = 0
                        inv.cost_basis = 0
                    else:
                        inv.total_equity -= quantity
                    inv.current_price = get_price(inv.symbol)
                else:
                    flash('Not enough equity to sell', 'danger')
                    return redirect(url_for('transaction'))
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
        log_activity("Transaction Recorded", f"Transaction for investment ID {investment_id} recorded.")
        flash('Transaction recorded successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('transaction.html', investments=investments, cash_accounts=cash_accounts)

# Transaction Management – list, search, edit, delete transactions
@app.route('/transactions', methods=['GET'])
@login_required
def transactions():
    search_query = request.args.get('search', '')
    if search_query:
        txns = Transaction.query.join(Investment, isouter=True).filter(
            or_(Investment.symbol.ilike(f"%{search_query}%"),
                Transaction.broker_note.ilike(f"%{search_query}%"))
        ).order_by(Transaction.date.desc()).all()
    else:
        txns = Transaction.query.order_by(Transaction.date.desc()).all()
    return render_template('transactions.html', transactions=txns, search=search_query)

@app.route('/transaction/edit/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    investments = Investment.query.all()
    if request.method == 'POST':
        txn.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        txn.transaction_type = request.form.get('transaction_type')
        txn.transaction_price = float(request.form.get('transaction_price'))
        txn.quantity = float(request.form.get('quantity'))
        txn.broker_note = request.form.get('broker_note')
        inv_id = request.form.get('investment_id')
        txn.investment_id = int(inv_id) if inv_id and inv_id != 'None' else None
        db.session.commit()
        log_activity("Transaction Edited", f"Transaction ID {transaction_id} edited.")
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('transactions'))
    return render_template('edit_transaction.html', transaction=txn, investments=investments)

@app.route('/transaction/delete/<int:transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    db.session.delete(txn)
    db.session.commit()
    log_activity("Transaction Deleted", f"Transaction ID {transaction_id} deleted.")
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('transactions'))

# -----------------------------
# Cash Management Routes
# -----------------------------
@app.route('/cash', methods=['GET'])
@login_required
def cash_list():
    accounts = CashAccount.query.all()
    cash_txns = CashTransaction.query.order_by(CashTransaction.date.desc()).all()
    return render_template('cash.html', cash_accounts=accounts, cash_transactions=cash_txns)

@app.route('/cash/add', methods=['GET', 'POST'])
@login_required
def add_cash():
    if request.method == 'POST':
        account_name = request.form.get('account_name')
        currency = request.form.get('currency')
        balance = float(request.form.get('balance'))
        new_acc = CashAccount(account_name=account_name, currency=currency, balance=balance)
        db.session.add(new_acc)
        db.session.commit()
        # Log initial deposit as cash transaction
        ct = CashTransaction(
            date=datetime.utcnow().date(),
            transaction_type='deposit',
            to_account_id=new_acc.id,
            amount=balance
        )
        db.session.add(ct)
        db.session.commit()
        log_activity("Cash Account Added", f"Cash account {account_name} added.")
        flash('Cash account added successfully!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('add_cash.html')

@app.route('/cash/edit/<int:cash_id>', methods=['GET', 'POST'])
@login_required
def edit_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    if request.method == 'POST':
        acc.account_name = request.form.get('account_name')
        acc.currency = request.form.get('currency')
        acc.balance = float(request.form.get('balance'))
        db.session.commit()
        log_activity("Cash Account Edited", f"Cash account ID {cash_id} edited.")
        flash('Cash account updated successfully!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('edit_cash.html', cash_account=acc)

@app.route('/cash/delete/<int:cash_id>', methods=['POST'])
@login_required
def delete_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    db.session.delete(acc)
    db.session.commit()
    log_activity("Cash Account Deleted", f"Cash account ID {cash_id} deleted.")
    flash('Cash account deleted successfully!', 'success')
    return redirect(url_for('cash_list'))

@app.route('/cash/deposit/<int:cash_id>', methods=['GET', 'POST'])
@login_required
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
        log_activity("Cash Deposit", f"Deposited {amount} into cash account ID {cash_id}.")
        flash('Deposit successful!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('deposit_cash.html', cash_account=acc)

@app.route('/cash/withdraw/<int:cash_id>', methods=['GET', 'POST'])
@login_required
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
            log_activity("Cash Withdrawal", f"Withdrew {amount} from cash account ID {cash_id}.")
            flash('Withdrawal successful!', 'success')
        else:
            flash('Insufficient funds!', 'danger')
        return redirect(url_for('cash_list'))
    return render_template('withdraw_cash.html', cash_account=acc)

@app.route('/cash/convert/<int:from_id>', methods=['GET', 'POST'])
@login_required
def convert_cash(from_id):
    from_acc = CashAccount.query.get_or_404(from_id)
    accounts = CashAccount.query.filter(CashAccount.id != from_id).all()
    if request.method == 'POST':
        to_id = int(request.form.get('to_account_id'))
        amount = float(request.form.get('amount'))
        conversion_rate = float(request.form.get('conversion_rate'))
        to_acc = CashAccount.query.get_or_404(to_id)
        if from_acc.balance < amount:
            flash('Insufficient funds in source account!', 'danger')
            return redirect(url_for('convert_cash', from_id=from_id))
        from_acc.balance -= amount
        converted_amount = amount * conversion_rate
        to_acc.balance += converted_amount
        ct = CashTransaction(
            date=datetime.utcnow().date(),
            transaction_type='conversion',
            from_account_id=from_acc.id,
            to_account_id=to_acc.id,
            amount=amount,
            conversion_rate=conversion_rate
        )
        db.session.add(ct)
        db.session.commit()
        log_activity("Cash Conversion", f"Converted {amount} from account ID {from_id} to account ID {to_id} at rate {conversion_rate}.")
        flash('Conversion successful!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('convert_cash.html', from_account=from_acc, accounts=accounts)

# -----------------------------
# Bond Management Routes
# -----------------------------
@app.route('/bonds', methods=['GET'])
@login_required
def bonds():
    bonds = Bond.query.order_by(Bond.maturity_date).all()
    return render_template('bonds.html', bonds=bonds)

@app.route('/bond/add', methods=['GET', 'POST'])
@login_required
def add_bond():
    if request.method == 'POST':
        name = request.form.get('name')
        face_value = float(request.form.get('face_value'))
        coupon_rate = float(request.form.get('coupon_rate'))
        maturity_date = datetime.strptime(request.form.get('maturity_date'), '%Y-%m-%d').date()
        purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date()
        quantity = float(request.form.get('quantity'))
        transaction_price = float(request.form.get('transaction_price'))
        bond = Bond(
            name=name,
            face_value=face_value,
            coupon_rate=coupon_rate,
            maturity_date=maturity_date,
            purchase_date=purchase_date,
            quantity=quantity,
            cost_basis=transaction_price
        )
        db.session.add(bond)
        db.session.commit()
        log_activity("Bond Added", f"Bond {name} added.")
        flash('Bond added successfully!', 'success')
        return redirect(url_for('bonds'))
    return render_template('add_bond.html')

@app.route('/bond/edit/<int:bond_id>', methods=['GET', 'POST'])
@login_required
def edit_bond(bond_id):
    bond = Bond.query.get_or_404(bond_id)
    if request.method == 'POST':
        bond.name = request.form.get('name')
        bond.face_value = float(request.form.get('face_value'))
        bond.coupon_rate = float(request.form.get('coupon_rate'))
        bond.maturity_date = datetime.strptime(request.form.get('maturity_date'), '%Y-%m-%d').date()
        bond.purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date()
        bond.quantity = float(request.form.get('quantity'))
        bond.cost_basis = float(request.form.get('transaction_price'))
        db.session.commit()
        log_activity("Bond Edited", f"Bond ID {bond_id} edited.")
        flash('Bond updated successfully!', 'success')
        return redirect(url_for('bonds'))
    return render_template('edit_bond.html', bond=bond)

@app.route('/bond/delete/<int:bond_id>', methods=['POST'])
@login_required
def delete_bond(bond_id):
    bond = Bond.query.get_or_404(bond_id)
    db.session.delete(bond)
    db.session.commit()
    log_activity("Bond Deleted", f"Bond ID {bond_id} deleted.")
    flash('Bond deleted successfully!', 'success')
    return redirect(url_for('bonds'))

# -----------------------------
# Dividend Management Routes
# -----------------------------
@app.route('/dividends', methods=['GET'])
@login_required
def dividends():
    dividends = Dividend.query.order_by(Dividend.date.desc()).all()
    # For simplicity, we pass all investments for lookup in the template
    investments = Investment.query.filter(Investment.asset_class=='Stock').all()
    return render_template('dividends.html', dividends=dividends, investments=investments)

@app.route('/dividend/add', methods=['GET', 'POST'])
@login_required
def add_dividend():
    investments = Investment.query.filter(Investment.asset_class=='Stock').all()
    if request.method == 'POST':
        investment_id = int(request.form.get('investment_id'))
        date_div = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        amount = float(request.form.get('amount'))
        note = request.form.get('note')
        dividend = Dividend(investment_id=investment_id, date=date_div, amount=amount, note=note)
        db.session.add(dividend)
        db.session.commit()
        log_activity("Dividend Added", f"Dividend for investment ID {investment_id} added.")
        flash('Dividend recorded successfully!', 'success')
        return redirect(url_for('dividends'))
    return render_template('add_dividend.html', investments=investments)

@app.route('/dividend/edit/<int:dividend_id>', methods=['GET', 'POST'])
@login_required
def edit_dividend(dividend_id):
    dividend = Dividend.query.get_or_404(dividend_id)
    investments = Investment.query.filter(Investment.asset_class=='Stock').all()
    if request.method == 'POST':
        dividend.investment_id = int(request.form.get('investment_id'))
        dividend.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        dividend.amount = float(request.form.get('amount'))
        dividend.note = request.form.get('note')
        db.session.commit()
        log_activity("Dividend Edited", f"Dividend ID {dividend_id} edited.")
        flash('Dividend updated successfully!', 'success')
        return redirect(url_for('dividends'))
    return render_template('edit_dividend.html', dividend=dividend, investments=investments)

@app.route('/dividend/delete/<int:dividend_id>', methods=['POST'])
@login_required
def delete_dividend(dividend_id):
    dividend = Dividend.query.get_or_404(dividend_id)
    db.session.delete(dividend)
    db.session.commit()
    log_activity("Dividend Deleted", f"Dividend ID {dividend_id} deleted.")
    flash('Dividend deleted successfully!', 'success')
    return redirect(url_for('dividends'))

# -----------------------------
# Analytics & Reporting Routes
# -----------------------------
@app.route('/summary')
@login_required
def summary():
    selected_currency = request.args.get('currency', 'USD')
    investments = Investment.query.all()
    for inv in investments:
        inv.current_price = get_price(inv.symbol)
    txns = Transaction.query.order_by(Transaction.date).all()
    if txns:
        first_date = txns[0].date
        start_date = first_date if isinstance(first_date, date) else first_date.date()
    else:
        start_date = datetime.utcnow().date()
    end_date = datetime.utcnow().date()
    
    timeline = []
    current_date = start_date
    while current_date <= end_date:
        timeline.append(current_date)
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year+1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month+1)
    
    monthly_data = []
    for month_start in timeline:
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year+1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month+1)
        total_asset_value = 0
        total_cost_basis = 0
        for inv in investments:
            inv_txns = [t for t in inv.transactions if t.date < next_month]
            if not inv_txns:
                continue
            shares = 0
            avg = 0
            for t in sorted(inv_txns, key=lambda t: t.date):
                if t.transaction_type.lower() == 'buy':
                    if shares == 0:
                        shares = t.quantity
                        avg = t.transaction_price
                    else:
                        new_total = shares + t.quantity
                        new_total_cost = avg * shares + t.transaction_price * t.quantity
                        avg = new_total_cost / new_total
                        shares = new_total
                elif t.transaction_type.lower() == 'sell':
                    if shares >= t.quantity:
                        shares -= t.quantity
                        if shares == 0:
                            avg = 0
                    else:
                        shares = 0
                        avg = 0
            price = get_price(inv.symbol)
            asset_value = shares * price
            cost_basis_total = shares * avg
            asset_value_conv = convert_currency(asset_value, inv.currency, selected_currency)
            cost_conv = convert_currency(cost_basis_total, inv.currency, selected_currency)
            total_asset_value += asset_value_conv
            total_cost_basis += cost_conv
        profit_loss = total_asset_value - total_cost_basis
        monthly_data.append({
            'month': month_start.strftime("%Y-%m"),
            'asset_value': round(total_asset_value, 2),
            'cost_basis': round(total_cost_basis, 2),
            'profit_loss': round(profit_loss, 2)
        })
    
    # Category breakdown
    category_data = {}
    for inv in investments:
        price = get_price(inv.symbol)
        asset_value = inv.total_equity * price
        total_cost = inv.total_equity * inv.cost_basis
        asset_value_conv = convert_currency(asset_value, inv.currency, selected_currency)
        cost_conv = convert_currency(total_cost, inv.currency, selected_currency)
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

@app.route('/report')
@login_required
def report():
    # Export transactions as CSV
    transactions = Transaction.query.order_by(Transaction.date).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Investment', 'Type', 'Price', 'Quantity', 'Broker Note'])
    for t in transactions:
        inv = Investment.query.get(t.investment_id) if t.investment_id else None
        symbol = inv.symbol if inv else 'N/A'
        cw.writerow([t.date, symbol, t.transaction_type, t.transaction_price, t.quantity, t.broker_note])
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=transactions.csv"})

@app.route('/risk')
@login_required
def risk():
    # Basic risk analysis: show diversification by asset class (percentage of total investment)
    investments = Investment.query.all()
    category_totals = {}
    for inv in investments:
        asset_value = inv.total_value
        cat = inv.asset_class
        category_totals[cat] = category_totals.get(cat, 0) + asset_value
    total_investment = sum(category_totals.values())
    risk_data = {cat: round((value/total_investment)*100, 2) for cat, value in category_totals.items()} if total_investment > 0 else {}
    return render_template('risk.html', risk_data=risk_data)

# -----------------------------
# Database Initialization
# -----------------------------
def init_db():
    db.create_all()
    if not CashAccount.query.first():
        default_account = CashAccount(account_name='Main Account', currency='USD', balance=10000)
        db.session.add(default_account)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True , port=8080)
