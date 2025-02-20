from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///investment_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Replace with a secure key

db = SQLAlchemy(app)

# -----------------------------
# Models
# -----------------------------
class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    asset_class = db.Column(db.String(50), nullable=False)  # e.g., Stock, Fixed Income Bond, Crypto, Commodities, Other
    total_equity = db.Column(db.Float, default=0.0)
    cost_basis = db.Column(db.Float, default=0.0)
    current_price = db.Column(db.Float, default=0.0)
    transactions = db.relationship('Transaction', backref='investment', lazy=True)

    @property
    def total_value(self):
        return self.total_equity * self.current_price

    @property
    def profit_loss(self):
        return self.total_value - self.cost_basis

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(10), nullable=False)  # Buy or Sell
    transaction_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)

class CashAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_name = db.Column(db.String(50), nullable=False)
    currency = db.Column(db.String(3), nullable=False)  # USD, THB, SGD
    balance = db.Column(db.Float, default=0.0)

# -----------------------------
# Currency Conversion (stub)
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

# Dashboard: Shows investment positions
@app.route('/')
def dashboard():
    investments = Investment.query.all()
    return render_template('dashboard.html', investments=investments)

# Transaction Page: Record a transaction (and optionally add a new investment)
@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
    investments = Investment.query.all()
    cash_accounts = CashAccount.query.all()
    if request.method == 'POST':
        # Check if new investment details are provided
        is_new_investment = request.form.get('is_new_investment')
        if is_new_investment == 'on':
            new_symbol = request.form.get('new_symbol')
            new_description = request.form.get('new_description')
            new_asset_class = request.form.get('new_asset_class')
            # Create new investment record with default values; use transaction price as initial current_price.
            new_investment = Investment(
                symbol=new_symbol,
                description=new_description,
                asset_class=new_asset_class,
                total_equity=0,
                cost_basis=0,
                current_price=float(request.form.get('transaction_price'))
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

        # Create transaction record
        new_transaction = Transaction(
            investment_id=investment_id,
            date=date_obj,
            transaction_type=transaction_type,
            transaction_price=transaction_price,
            quantity=quantity
        )
        db.session.add(new_transaction)

        # Update Investment if linked
        if investment_id:
            inv = Investment.query.get(investment_id)
            if transaction_type.lower() == 'buy':
                inv.total_equity += quantity
                inv.cost_basis += transaction_price * quantity
                inv.current_price = transaction_price
            elif transaction_type.lower() == 'sell':
                if inv.total_equity >= quantity:
                    avg_cost = inv.cost_basis / inv.total_equity if inv.total_equity != 0 else 0
                    inv.total_equity -= quantity
                    inv.cost_basis -= avg_cost * quantity
                    inv.current_price = transaction_price
                else:
                    flash('Not enough equity to sell', 'danger')
                    return redirect(url_for('transaction'))
        
        # Update CashAccount
        if cash_account_id:
            cash_account = CashAccount.query.get(int(cash_account_id))
            amount = transaction_price * quantity
            if transaction_type.lower() == 'buy':
                cash_account.balance -= amount
            elif transaction_type.lower() == 'sell':
                cash_account.balance += amount
        
        db.session.commit()
        flash('Transaction recorded successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('transaction.html', investments=investments, cash_accounts=cash_accounts)

# Transaction Management: List, search, edit, and delete transactions
@app.route('/transactions', methods=['GET'])
def transactions():
    search = request.args.get('search', '')
    if search:
        transactions = Transaction.query.join(Investment, isouter=True).filter(
            Investment.symbol.ilike(f"%{search}%")
        ).order_by(Transaction.date.desc()).all()
    else:
        transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    return render_template('transactions.html', transactions=transactions, search=search)

@app.route('/transaction/edit/<int:transaction_id>', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    transaction_obj = Transaction.query.get_or_404(transaction_id)
    investments = Investment.query.all()
    cash_accounts = CashAccount.query.all()
    if request.method == 'POST':
        # Note: For simplicity, editing a transaction here does not recalculate previous aggregates.
        transaction_obj.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        transaction_obj.transaction_type = request.form.get('transaction_type')
        transaction_obj.transaction_price = float(request.form.get('transaction_price'))
        transaction_obj.quantity = float(request.form.get('quantity'))
        inv_id = request.form.get('investment_id')
        transaction_obj.investment_id = int(inv_id) if inv_id and inv_id != 'None' else None
        db.session.commit()
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('transactions'))
    return render_template('edit_transaction.html', transaction=transaction_obj, investments=investments, cash_accounts=cash_accounts)

@app.route('/transaction/delete/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    transaction_obj = Transaction.query.get_or_404(transaction_id)
    db.session.delete(transaction_obj)
    db.session.commit()
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('transactions'))

# Cash Management: List cash accounts (with links to add, edit, delete)
@app.route('/cash', methods=['GET'])
def cash_list():
    cash_accounts = CashAccount.query.all()
    return render_template('cash.html', cash_accounts=cash_accounts)

@app.route('/cash/add', methods=['GET', 'POST'])
def add_cash():
    if request.method == 'POST':
        account_name = request.form.get('account_name')
        currency = request.form.get('currency')
        balance = float(request.form.get('balance'))
        new_cash = CashAccount(account_name=account_name, currency=currency, balance=balance)
        db.session.add(new_cash)
        db.session.commit()
        flash('Cash account added successfully!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('add_cash.html')

@app.route('/cash/edit/<int:cash_id>', methods=['GET', 'POST'])
def edit_cash(cash_id):
    cash_account = CashAccount.query.get_or_404(cash_id)
    if request.method == 'POST':
        cash_account.account_name = request.form.get('account_name')
        cash_account.currency = request.form.get('currency')
        cash_account.balance = float(request.form.get('balance'))
        db.session.commit()
        flash('Cash account updated successfully!', 'success')
        return redirect(url_for('cash_list'))
    return render_template('edit_cash.html', cash_account=cash_account)

@app.route('/cash/delete/<int:cash_id>', methods=['POST'])
def delete_cash(cash_id):
    cash_account = CashAccount.query.get_or_404(cash_id)
    db.session.delete(cash_account)
    db.session.commit()
    flash('Cash account deleted successfully!', 'success')
    return redirect(url_for('cash_list'))

# Investment Position Edit: Update investment details
@app.route('/position/edit/<int:investment_id>', methods=['GET', 'POST'])
def edit_position(investment_id):
    investment = Investment.query.get_or_404(investment_id)
    if request.method == 'POST':
        investment.symbol = request.form.get('symbol')
        investment.description = request.form.get('description')
        investment.asset_class = request.form.get('asset_class')
        investment.current_price = float(request.form.get('current_price'))
        db.session.commit()
        flash('Investment updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    asset_classes = ["Stock", "Fixed Income Bond", "Crypto", "Commodities", "Other"]
    return render_template('edit_position.html', investment=investment, asset_classes=asset_classes)

# Summary: Monthly wealth evolution and breakdown by asset category
@app.route('/summary')
def summary():
    currency = request.args.get('currency', 'USD')
    
    investments = Investment.query.all()
    transactions = Transaction.query.order_by(Transaction.date).all()
    
    # Ensure we work with date objects
    if transactions:
        first_date = transactions[0].date
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
        monthly_transactions = Transaction.query.filter(Transaction.date < next_month).all()
        
        total_asset_value = 0
        total_cost_basis = 0
        investment_ids = set(t.investment_id for t in monthly_transactions if t.investment_id)
        for inv_id in investment_ids:
            inv_transactions = [t for t in monthly_transactions if t.investment_id == inv_id]
            total_equity = 0
            cost_basis = 0
            for t in inv_transactions:
                if t.transaction_type.lower() == 'buy':
                    total_equity += t.quantity
                    cost_basis += t.transaction_price * t.quantity
                elif t.transaction_type.lower() == 'sell':
                    avg_cost = (cost_basis / total_equity) if total_equity > 0 else 0
                    total_equity -= t.quantity
                    cost_basis -= avg_cost * t.quantity
            inv = Investment.query.get(inv_id)
            if inv:
                asset_value = total_equity * inv.current_price
                total_asset_value += asset_value
                total_cost_basis += cost_basis
        
        profit_loss = total_asset_value - total_cost_basis
        monthly_data.append({
            'month': month_start.strftime("%Y-%m"),
            'asset_value': total_asset_value,
            'cost_basis': total_cost_basis,
            'profit_loss': profit_loss,
        })
    
    category_data = {}
    for inv in investments:
        category = inv.asset_class
        asset_value = inv.total_equity * inv.current_price
        if category in category_data:
            category_data[category]['asset_value'] += asset_value
            category_data[category]['cost_basis'] += inv.cost_basis
        else:
            category_data[category] = {
                'asset_value': asset_value,
                'cost_basis': inv.cost_basis
            }
    for cat in category_data:
        category_data[cat]['profit_loss'] = category_data[cat]['asset_value'] - category_data[cat]['cost_basis']
    
    if currency != 'USD':
        for data in monthly_data:
            data['asset_value'] = convert_currency(data['asset_value'], 'USD', currency)
            data['cost_basis'] = convert_currency(data['cost_basis'], 'USD', currency)
            data['profit_loss'] = data['asset_value'] - data['cost_basis']
        for cat in category_data:
            category_data[cat]['asset_value'] = convert_currency(category_data[cat]['asset_value'], 'USD', currency)
            category_data[cat]['cost_basis'] = convert_currency(category_data[cat]['cost_basis'], 'USD', currency)
            category_data[cat]['profit_loss'] = category_data[cat]['asset_value'] - category_data[cat]['cost_basis']
    
    return render_template('summary.html', 
                           monthly_data=monthly_data, 
                           category_data=category_data,
                           currency=currency)

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
