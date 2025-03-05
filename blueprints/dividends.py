# blueprints/dividends.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Dividend, Investment
from datetime import datetime
from helpers import log_activity

dividends_bp = Blueprint('dividends', __name__)

@dividends_bp.route('/dividends', methods=['GET'])
@login_required
def dividends():
    dividends = Dividend.query.order_by(Dividend.date.desc()).all()
    investments = Investment.query.filter(Investment.asset_class=='Stock').all()
    return render_template('dividends.html', dividends=dividends, investments=investments)

@dividends_bp.route('/dividend/add', methods=['GET', 'POST'])
@login_required
def add_dividend():
    investments = Investment.query.filter(Investment.asset_class=='Stock').all()
    if request.method == 'POST':
        try:
            investment_id = int(request.form.get('investment_id'))
            amount = float(request.form.get('amount'))
        except ValueError:
            flash("Invalid numeric value in dividend amount", "danger")
            return redirect(url_for('dividends.add_dividend'))
        if amount < 0:
            flash("Dividend amount must be non-negative", "danger")
            return redirect(url_for('dividends.add_dividend'))
        try:
            date_div = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
            return redirect(url_for('dividends.add_dividend'))
        note = request.form.get('note')
        dividend = Dividend(investment_id=investment_id, date=date_div, amount=amount, note=note)
        db.session.add(dividend)
        db.session.commit()
        log_activity("Dividend Added", f"Dividend for investment ID {investment_id} added.")
        flash('Dividend recorded successfully!', 'success')
        return redirect(url_for('dividends.dividends'))
    return render_template('add_dividend.html', investments=investments)

@dividends_bp.route('/dividend/edit/<int:dividend_id>', methods=['GET', 'POST'])
@login_required
def edit_dividend(dividend_id):
    dividend = Dividend.query.get_or_404(dividend_id)
    investments = Investment.query.filter(Investment.asset_class=='Stock').all()
    if request.method == 'POST':
        try:
            dividend.investment_id = int(request.form.get('investment_id'))
            dividend.amount = float(request.form.get('amount'))
        except ValueError:
            flash("Invalid numeric value in dividend amount", "danger")
            return redirect(url_for('dividends.edit_dividend', dividend_id=dividend_id))
        if dividend.amount < 0:
            flash("Dividend amount must be non-negative", "danger")
            return redirect(url_for('dividends.edit_dividend', dividend_id=dividend_id))
        try:
            dividend.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
            return redirect(url_for('dividends.edit_dividend', dividend_id=dividend_id))
        dividend.note = request.form.get('note')
        db.session.commit()
        log_activity("Dividend Edited", f"Dividend ID {dividend_id} edited.")
        flash('Dividend updated successfully!', 'success')
        return redirect(url_for('dividends.dividends'))
    return render_template('edit_dividend.html', dividend=dividend, investments=investments)

@dividends_bp.route('/dividend/delete/<int:dividend_id>', methods=['POST'])
@login_required
def delete_dividend(dividend_id):
    dividend = Dividend.query.get_or_404(dividend_id)
    db.session.delete(dividend)
    db.session.commit()
    log_activity("Dividend Deleted", f"Dividend ID {dividend_id} deleted.")
    flash('Dividend deleted successfully!', 'success')
    return redirect(url_for('dividends.dividends'))
