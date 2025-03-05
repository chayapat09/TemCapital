# blueprints/cash.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, CashAccount, CashTransaction
from datetime import datetime
from helpers import log_activity

cash_bp = Blueprint('cash', __name__)

@cash_bp.route('/cash', methods=['GET'])
@login_required
def cash_list():
    accounts = CashAccount.query.all()
    cash_txns = CashTransaction.query.order_by(CashTransaction.date.desc()).all()
    return render_template('cash.html', cash_accounts=accounts, cash_transactions=cash_txns)

@cash_bp.route('/cash/add', methods=['GET', 'POST'])
@login_required
def add_cash():
    if request.method == 'POST':
        account_name = request.form.get('account_name')
        currency = request.form.get('currency')
        try:
            balance = float(request.form.get('balance'))
        except ValueError:
            flash("Invalid balance value", "danger")
            return redirect(url_for('cash.add_cash'))
        if balance < 0:
            flash("Balance cannot be negative", "danger")
            return redirect(url_for('cash.add_cash'))
        new_acc = CashAccount(account_name=account_name, currency=currency, balance=balance)
        db.session.add(new_acc)
        db.session.commit()
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
        return redirect(url_for('cash.cash_list'))
    return render_template('add_cash.html')

@cash_bp.route('/cash/edit/<int:cash_id>', methods=['GET', 'POST'])
@login_required
def edit_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    if request.method == 'POST':
        acc.account_name = request.form.get('account_name')
        acc.currency = request.form.get('currency')
        try:
            new_balance = float(request.form.get('balance'))
        except ValueError:
            flash("Invalid balance value", "danger")
            return redirect(url_for('cash.edit_cash', cash_id=cash_id))
        if new_balance < 0:
            flash("Balance cannot be negative", "danger")
            return redirect(url_for('cash.edit_cash', cash_id=cash_id))
        acc.balance = new_balance
        db.session.commit()
        log_activity("Cash Account Edited", f"Cash account ID {cash_id} edited.")
        flash('Cash account updated successfully!', 'success')
        return redirect(url_for('cash.cash_list'))
    return render_template('edit_cash.html', cash_account=acc)

@cash_bp.route('/cash/delete/<int:cash_id>', methods=['POST'])
@login_required
def delete_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    db.session.delete(acc)
    db.session.commit()
    log_activity("Cash Account Deleted", f"Cash account ID {cash_id} deleted.")
    flash('Cash account deleted successfully!', 'success')
    return redirect(url_for('cash.cash_list'))

@cash_bp.route('/cash/deposit/<int:cash_id>', methods=['GET', 'POST'])
@login_required
def deposit_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
        except ValueError:
            flash("Invalid deposit amount", "danger")
            return redirect(url_for('cash.deposit_cash', cash_id=cash_id))
        if amount < 0:
            flash("Deposit amount must be non-negative", "danger")
            return redirect(url_for('cash.deposit_cash', cash_id=cash_id))
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
        return redirect(url_for('cash.cash_list'))
    return render_template('deposit_cash.html', cash_account=acc)

@cash_bp.route('/cash/withdraw/<int:cash_id>', methods=['GET', 'POST'])
@login_required
def withdraw_cash(cash_id):
    acc = CashAccount.query.get_or_404(cash_id)
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
        except ValueError:
            flash("Invalid withdrawal amount", "danger")
            return redirect(url_for('cash.withdraw_cash', cash_id=cash_id))
        if amount < 0:
            flash("Withdrawal amount must be non-negative", "danger")
            return redirect(url_for('cash.withdraw_cash', cash_id=cash_id))
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
        return redirect(url_for('cash.cash_list'))
    return render_template('withdraw_cash.html', cash_account=acc)

@cash_bp.route('/cash/convert/<int:from_id>', methods=['GET', 'POST'])
@login_required
def convert_cash(from_id):
    from_acc = CashAccount.query.get_or_404(from_id)
    accounts = CashAccount.query.filter(CashAccount.id != from_id).all()
    if request.method == 'POST':
        try:
            to_id = int(request.form.get('to_account_id'))
            amount = float(request.form.get('amount'))
            conversion_rate = float(request.form.get('conversion_rate'))
        except ValueError:
            flash("Invalid conversion parameters", "danger")
            return redirect(url_for('cash.convert_cash', from_id=from_id))
        if amount < 0 or conversion_rate < 0:
            flash("Amount and conversion rate must be non-negative", "danger")
            return redirect(url_for('cash.convert_cash', from_id=from_id))
        to_acc = CashAccount.query.get_or_404(to_id)
        if from_acc.balance < amount:
            flash('Insufficient funds in source account!', 'danger')
            return redirect(url_for('cash.convert_cash', from_id=from_id))
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
        return redirect(url_for('cash.cash_list'))
    return render_template('convert_cash.html', from_account=from_acc, accounts=accounts)
