from datetime import datetime, date, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Relationships for user-specific portfolio items
    investments_transactions = db.relationship('Transaction', backref='user', lazy=True)
    cash_accounts = db.relationship('CashAccount', backref='user', lazy=True)
    bonds = db.relationship('Bond', backref='user', lazy=True)
    dividends = db.relationship('Dividend', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    asset_class = db.Column(db.String(50), nullable=False)
    wallet_address = db.Column(db.String(255), nullable=True)
    # No user-specific data – shared globally
    transactions = db.relationship('Transaction', backref='investment', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'Buy' or 'Sell'
    transaction_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    broker_note = db.Column(db.String(255), nullable=True)
    quote_currency = db.Column(db.String(3), nullable=False, default='USD')

class CashAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_name = db.Column(db.String(50), nullable=False)
    currency = db.Column(db.String(3), nullable=False)  # USD, THB, SGD
    balance = db.Column(db.Float, default=0.0)

class CashTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdraw, conversion, investment_buy, investment_sell
    from_account_id = db.Column(db.Integer, db.ForeignKey('cash_account.id'), nullable=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey('cash_account.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    conversion_rate = db.Column(db.Float, nullable=True)

class Bond(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    face_value = db.Column(db.Float, nullable=False)
    coupon_rate = db.Column(db.Float, nullable=False)
    maturity_date = db.Column(db.Date, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    cost_basis = db.Column(db.Float, default=0.0)

    @property
    def total_value(self):
        return self.quantity * self.face_value

    @property
    def yield_to_maturity(self):
        years_to_maturity = (self.maturity_date - date.today()).days / 365.25
        if years_to_maturity > 0:
            annual_coupon = self.face_value * (self.coupon_rate / 100)
            return (annual_coupon + ((self.face_value - self.cost_basis) / years_to_maturity)) / ((self.face_value + self.cost_basis) / 2) * 100
        return 0

class Dividend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(255), nullable=True)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)
