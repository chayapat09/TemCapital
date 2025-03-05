# blueprints/investments.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from models import db, Investment, Transaction, CashAccount, CashTransaction, Bond, Dividend
from helpers import get_price, recalc_investment, log_activity, convert_currency
from datetime import datetime
from sqlalchemy import or_

investments_bp = Blueprint('investments', __name__)

@investments_bp.route('/')
@login_required
def dashboard():
    investments = Investment.query.all()
    for inv in investments:
        inv.current_price = get_price(inv.symbol)
    total_investment = sum(inv.total_value for inv in investments)
    cash_accounts = CashAccount.query.all()
    total_cash = sum(cash.balance for cash in cash_accounts)
    bonds = Bond.query.all()
    total_bonds = sum(bond.total_value for bond in bonds)
    net_worth = total_investment + total_cash + total_bonds
    return render_template('dashboard.html', investments=investments,
                           cash_accounts=cash_accounts, bonds=bonds, net_worth=net_worth)

@investments_bp.route('/transaction', methods=['GET', 'POST'])
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
            log_activity("New Investment Added", f"Investment {new_symbol} added.")
            investment_id = new_investment.id
        else:
            inv_id = request.form.get('investment_id')
            investment_id = int(inv_id) if inv_id and inv_id != 'None' else None

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

        if investment_id:
            inv = Investment.query.get(investment_id)
            if cash_account_id:
                cash_acc = CashAccount.query.get(int(cash_account_id))
                if cash_acc.currency != inv.currency:
                    flash(f"Error: Investment currency ({inv.currency}) does not match cash account currency ({cash_acc.currency}).", "danger")
                    return redirect(url_for('investments.transaction'))
        new_txn = Transaction(
            investment_id=investment_id,
            date=date_obj,
            transaction_type=transaction_type,
            transaction_price=transaction_price,
            quantity=quantity,
            broker_note=broker_note
        )
        db.session.add(new_txn)
        db.session.flush()

        if investment_id:
            inv = Investment.query.get(investment_id)
            recalc_investment(inv)

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
        return redirect(url_for('investments.dashboard'))
    return render_template('transaction.html', investments=investments, cash_accounts=cash_accounts)

@investments_bp.route('/transactions', methods=['GET'])
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

@investments_bp.route('/transaction/edit/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    investments = Investment.query.all()
    old_investment_id = txn.investment_id
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

        if old_investment_id:
            old_inv = Investment.query.get(old_investment_id)
            if old_inv:
                recalc_investment(old_inv)
        if txn.investment_id:
            new_inv = Investment.query.get(txn.investment_id)
            if new_inv:
                recalc_investment(new_inv)

        log_activity("Transaction Edited", f"Transaction ID {transaction_id} edited.")
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('investments.transactions'))
    return render_template('edit_transaction.html', transaction=txn, investments=investments)

@investments_bp.route('/transaction/delete/<int:transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    investment_id = txn.investment_id
    db.session.delete(txn)
    db.session.commit()
    if investment_id:
        inv = Investment.query.get(investment_id)
        if inv:
            recalc_investment(inv)
    log_activity("Transaction Deleted", f"Transaction ID {transaction_id} deleted.")
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('investments.transactions'))

@investments_bp.route('/report')
@login_required
def report():
    transactions = Transaction.query.order_by(Transaction.date).all()
    import csv, io
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Investment', 'Type', 'Price', 'Quantity', 'Broker Note'])
    for t in transactions:
        inv = Investment.query.get(t.investment_id) if t.investment_id else None
        symbol = inv.symbol if inv else 'N/A'
        cw.writerow([t.date, symbol, t.transaction_type, t.transaction_price, t.quantity, t.broker_note])
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=transactions.csv"})

@investments_bp.route('/risk')
@login_required
def risk():
    investments = Investment.query.all()
    category_totals = {}
    for inv in investments:
        asset_value = inv.total_value
        cat = inv.asset_class
        category_totals[cat] = category_totals.get(cat, 0) + asset_value
    total_investment = sum(category_totals.values())
    risk_data = {cat: round((value / total_investment) * 100, 2) for cat, value in category_totals.items()} if total_investment > 0 else {}
    return render_template('risk.html', risk_data=risk_data)
