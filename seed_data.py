from datetime import datetime, date, timedelta
from app import app, db
from models import User, Investment, Transaction, CashAccount, CashTransaction, Bond, Dividend, ActivityLog
from helpers import compute_user_investment

with app.app_context():
    # Start fresh: drop all tables then create them again
    db.drop_all()
    db.create_all()

    # ----------------------------------------------------------
    # Create a test user for authentication testing.
    # ----------------------------------------------------------
    user1 = User(username="testuser")
    user1.set_password("password")
    db.session.add(user1)
    db.session.commit()  # Commit to obtain user1.id

    # ----------------------------------------------------------
    # Create Cash Accounts in different currencies.
    # ----------------------------------------------------------
    cash1 = CashAccount(account_name="Main Account", currency="USD", balance=10000, user_id=user1.id)
    cash2 = CashAccount(account_name="Savings Account", currency="THB", balance=50000, user_id=user1.id)
    cash3 = CashAccount(account_name="Crypto Wallet", currency="SGD", balance=2000, user_id=user1.id)
    db.session.add_all([cash1, cash2, cash3])
    db.session.commit()

    # ----------------------------------------------------------
    # Create Investments (shared across users)
    # ----------------------------------------------------------
    inv1 = Investment(
        symbol="AAPL",
        description="Apple Inc.",
        asset_class="Stock"
    )
    db.session.add(inv1)
    db.session.commit()

    # --- Transactions for AAPL for user1 ---
    t1 = Transaction(
        investment_id=inv1.id,
        user_id=user1.id,
        date=datetime(2022, 1, 10),
        transaction_type="Buy",
        transaction_price=150,
        quantity=10,
        broker_note="Initial buy",
        quote_currency="USD"
    )
    t2 = Transaction(
        investment_id=inv1.id,
        user_id=user1.id,
        date=datetime(2022, 2, 15),
        transaction_type="Buy",
        transaction_price=155,
        quantity=5,
        broker_note="Second buy",
        quote_currency="USD"
    )
    t3 = Transaction(
        investment_id=inv1.id,
        user_id=user1.id,
        date=datetime(2022, 3, 20),
        transaction_type="Sell",
        transaction_price=160,
        quantity=8,
        broker_note="Partial sell",
        quote_currency="USD"
    )
    t4 = Transaction(
        investment_id=inv1.id,
        user_id=user1.id,
        date=datetime(2022, 4, 15),
        transaction_type="Sell",
        transaction_price=158,
        quantity=10,
        broker_note="Oversell test",
        quote_currency="USD"
    )
    db.session.add_all([t1, t2, t3, t4])
    db.session.commit()

    inv2 = Investment(
        symbol="BTC",
        description="Bitcoin",
        asset_class="Crypto"
    )
    db.session.add(inv2)
    db.session.commit()
    t5 = Transaction(
        investment_id=inv2.id,
        user_id=user1.id,
        date=datetime(2022, 4, 1),
        transaction_type="Buy",
        transaction_price=30000,
        quantity=0.1,
        broker_note="Crypto purchase",
        quote_currency="USD"
    )
    db.session.add(t5)
    db.session.commit()

    inv3 = Investment(
        symbol="MSFT",
        description="Microsoft Corp",
        asset_class="Stock"
    )
    db.session.add(inv3)
    db.session.commit()

    t6 = Transaction(
        investment_id=None,
        user_id=user1.id,
        date=datetime(2022, 5, 1),
        transaction_type="Buy",
        transaction_price=200,
        quantity=10,
        broker_note="Unlinked transaction",
        quote_currency="USD"
    )
    db.session.add(t6)
    db.session.commit()

    # ----------------------------------------------------------
    # Create Bonds with different maturity dates and coupon rates.
    # ----------------------------------------------------------
    bond1 = Bond(
        name="Govt Bond 2030",
        face_value=1000,
        coupon_rate=5,
        maturity_date=date(2030, 12, 31),
        purchase_date=date(2022, 1, 1),
        quantity=10,
        cost_basis=950,
        user_id=user1.id
    )
    bond2 = Bond(
        name="Corp Bond 2023",
        face_value=1000,
        coupon_rate=4,
        maturity_date=date(2023, 6, 30),
        purchase_date=date(2022, 6, 1),
        quantity=5,
        cost_basis=980,
        user_id=user1.id
    )
    db.session.add_all([bond1, bond2])
    db.session.commit()

    # ----------------------------------------------------------
    # Create Dividends for investments.
    # ----------------------------------------------------------
    div1 = Dividend(
        investment_id=inv1.id,
        date=date(2022, 3, 25),
        amount=20,
        note="Quarterly dividend",
        user_id=user1.id
    )
    div2 = Dividend(
        investment_id=inv3.id,
        date=date(2022, 5, 15),
        amount=15,
        note="Special dividend",
        user_id=user1.id
    )
    db.session.add_all([div1, div2])
    db.session.commit()

    # ----------------------------------------------------------
    # Create Cash Transactions covering deposit, withdrawal, investment, and conversion.
    # ----------------------------------------------------------
    ct1 = CashTransaction(
        date=datetime(2022, 1, 5),
        transaction_type="deposit",
        to_account_id=cash1.id,
        amount=500
    )
    ct2 = CashTransaction(
        date=datetime(2022, 2, 10),
        transaction_type="withdraw",
        from_account_id=cash1.id,
        amount=300
    )
    ct3 = CashTransaction(
        date=datetime(2022, 1, 10),
        transaction_type="investment_buy",
        from_account_id=cash1.id,
        amount=1500
    )
    ct4 = CashTransaction(
        date=datetime(2022, 3, 20),
        transaction_type="investment_sell",
        to_account_id=cash1.id,
        amount=1280
    )
    ct5 = CashTransaction(
        date=datetime(2022, 4, 10),
        transaction_type="conversion",
        from_account_id=cash2.id,
        to_account_id=cash1.id,
        amount=1000,
        conversion_rate=1 / 34.0
    )
    ct6 = CashTransaction(
        date=datetime(2022, 6, 10),
        transaction_type="conversion",
        from_account_id=cash1.id,
        to_account_id=cash3.id,
        amount=1000,
        conversion_rate=1.35
    )
    ct7 = CashTransaction(
        date=datetime(2022, 7, 1),
        transaction_type="deposit",
        to_account_id=cash3.id,
        amount=500
    )
    ct8 = CashTransaction(
        date=datetime(2022, 7, 5),
        transaction_type="withdraw",
        from_account_id=cash3.id,
        amount=200
    )
    db.session.add_all([ct1, ct2, ct3, ct4, ct5, ct6, ct7, ct8])
    db.session.commit()

    # ----------------------------------------------------------
    # Create an Activity Log entry for auditing.
    # ----------------------------------------------------------
    log1 = ActivityLog(
        user_id=user1.id,
        action="Test Data Creation",
        details="Generated sample data to test all features and edge cases."
    )
    db.session.add(log1)
    db.session.commit()

    print("Sample data generated successfully!")
