from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from models import db, Investment, Transaction, CashAccount, CashTransaction, Bond, Dividend
from helpers import get_price, compute_user_investment, log_activity, convert_currency, get_investment_quote_currency
from datetime import datetime
from sqlalchemy import or_

investments_bp = Blueprint('investments', __name__)

@investments_bp.route('/')
@login_required
def dashboard():
    # Get all global investments
    investments = Investment.query.all()
    # For each investment, compute user's holdings
    for inv in investments:
        shares, avg_cost = compute_user_investment(inv, current_user.id)
        inv.user_shares = shares
        inv.user_avg_cost = avg_cost
        inv.current_price = get_price(inv.symbol)
        inv.user_total_value = shares * inv.current_price
        inv.user_profit_loss = (inv.current_price - avg_cost) * shares
    total_investment = sum(inv.user_total_value for inv in investments)
    cash_accounts = CashAccount.query.filter_by(user_id=current_user.id).all()
    total_cash = sum(cash.balance for cash in cash_accounts)
    bonds = Bond.query.filter_by(user_id=current_user.id).all()
    total_bonds = sum(bond.total_value for bond in bonds)
    net_worth = total_investment + total_cash + total_bonds
    return render_template('dashboard.html', investments=investments,
                           cash_accounts=cash_accounts, bonds=bonds, net_worth=net_worth)

@investments_bp.route('/transaction', methods=['GET', 'POST'])
@login_required
def transaction():
    investments = Investment.query.all()  # global investments
    cash_accounts = CashAccount.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        is_new_investment = request.form.get('is_new_investment')
        if is_new_investment == 'on':
            new_symbol = request.form.get('new_symbol')
            new_description = request.form.get('new_description')
            new_asset_class = request.form.get('new_asset_class')
            new_currency = request.form.get('new_currency')  # used for quote_currency in transaction
            new_wallet_address = request.form.get('new_wallet_address')
            new_investment = Investment(
                symbol=new_symbol,
                description=new_description,
                asset_class=new_asset_class,
                wallet_address=new_wallet_address
            )
            db.session.add(new_investment)
            db.session.commit()
            log_activity("New Investment Added", f"Investment {new_symbol} added.")
            investment_id = new_investment.id
            quote_currency = new_currency
        else:
            inv_id = request.form.get('investment_id')
            investment_id = int(inv_id) if inv_id and inv_id != 'None' else None
            quote_currency = None
        transaction_date = request.form.get('date')
        transaction_type = request.form.get('transaction_type')
        try:
            transaction_price = float(request.form.get('transaction_price'))
            quantity = float(request.form.get('quantity'))
        except ValueError:
            flash("Invalid numeric value in transaction price or quantity", "danger")
            return redirect(url_for('investments.transaction'))
        if transaction_price < 0 or quantity < 0:
            flash("Transaction price and quantity must be non-negative", "danger")
            return redirect(url_for('investments.transaction'))

        broker_note = request.form.get('broker_note')
        cash_account_id = request.form.get('cash_account_id')
        try:
            date_obj = datetime.strptime(transaction_date, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
            return redirect(url_for('investments.transaction'))

        new_txn = Transaction(
            investment_id=investment_id,
            user_id=current_user.id,
            date=date_obj,
            transaction_type=transaction_type,
            transaction_price=transaction_price,
            quantity=quantity,
            broker_note=broker_note
        )
        if cash_account_id:
            cash_acc = CashAccount.query.filter_by(id=int(cash_account_id), user_id=current_user.id).first()
            if not quote_currency:
                quote_currency = cash_acc.currency
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
        new_txn.quote_currency = quote_currency if quote_currency else 'USD'
        db.session.add(new_txn)
        db.session.commit()
        log_activity("Transaction Recorded", f"Transaction for investment ID {investment_id} recorded.")
        flash('Transaction recorded successfully!', 'success')
        return redirect(url_for('investments.dashboard'))
    return render_template('transaction.html', investments=investments, cash_accounts=cash_accounts)

@investments_bp.route('/transactions', methods=['GET'])
@login_required
def transactions():
    search_query = request.args.get('search', '')
    if search_query:
        txns = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            or_(Investment.symbol.ilike(f"%{search_query}%"),
                Transaction.broker_note.ilike(f"%{search_query}%"))
        ).order_by(Transaction.date.desc()).all()
    else:
        txns = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    return render_template('transactions.html', transactions=txns, search=search_query)

@investments_bp.route('/transaction/edit/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    if txn.user_id != current_user.id:
        flash("Unauthorized access", "danger")
        return redirect(url_for('investments.dashboard'))
    investments = Investment.query.all()
    if request.method == 'POST':
        try:
            txn_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
            return redirect(url_for('investments.edit_transaction', transaction_id=transaction_id))
        txn.date = txn_date
        txn.transaction_type = request.form.get('transaction_type')
        try:
            new_price = float(request.form.get('transaction_price'))
            new_quantity = float(request.form.get('quantity'))
        except ValueError:
            flash("Invalid numeric value in transaction price or quantity", "danger")
            return redirect(url_for('investments.edit_transaction', transaction_id=transaction_id))
        if new_price < 0 or new_quantity < 0:
            flash("Transaction price and quantity must be non-negative", "danger")
            return redirect(url_for('investments.edit_transaction', transaction_id=transaction_id))
        txn.transaction_price = new_price
        txn.quantity = new_quantity
        txn.broker_note = request.form.get('broker_note')
        inv_id = request.form.get('investment_id')
        txn.investment_id = int(inv_id) if inv_id and inv_id != 'None' else None
        db.session.commit()
        log_activity("Transaction Edited", f"Transaction ID {transaction_id} edited.")
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('investments.transactions'))
    return render_template('edit_transaction.html', transaction=txn, investments=investments)

@investments_bp.route('/transaction/delete/<int:transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    if txn.user_id != current_user.id:
        flash("Unauthorized access", "danger")
        return redirect(url_for('investments.dashboard'))
    db.session.delete(txn)
    db.session.commit()
    log_activity("Transaction Deleted", f"Transaction ID {transaction_id} deleted.")
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('investments.transactions'))

@investments_bp.route('/report')
@login_required
def report():
    txns = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date).all()
    import csv, io
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Investment', 'Type', 'Price', 'Quantity', 'Broker Note', 'Quote Currency'])
    for t in txns:
        inv = Investment.query.filter_by(id=t.investment_id).first() if t.investment_id else None
        symbol = inv.symbol if inv else 'N/A'
        cw.writerow([t.date, symbol, t.transaction_type, t.transaction_price, t.quantity, t.broker_note, t.quote_currency])
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=transactions.csv"})

@investments_bp.route('/risk')
@login_required
def risk():
    investments = Investment.query.all()
    category_totals = {}
    for inv in investments:
        shares, _ = compute_user_investment(inv, current_user.id)
        price = get_price(inv.symbol)
        asset_value = shares * price
        cat = inv.asset_class
        category_totals[cat] = category_totals.get(cat, 0) + asset_value
    total_investment = sum(category_totals.values())
    risk_data = {cat: round((value / total_investment) * 100, 2) for cat, value in category_totals.items()} if total_investment > 0 else {}
    return render_template('risk.html', risk_data=risk_data)
