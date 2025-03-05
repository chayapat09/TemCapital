# blueprints/bonds.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Bond
from datetime import datetime
from helpers import log_activity

bonds_bp = Blueprint('bonds', __name__)

@bonds_bp.route('/bonds', methods=['GET'])
@login_required
def bonds():
    bonds = Bond.query.order_by(Bond.maturity_date).all()
    return render_template('bonds.html', bonds=bonds)

@bonds_bp.route('/bond/add', methods=['GET', 'POST'])
@login_required
def add_bond():
    if request.method == 'POST':
        name = request.form.get('name')
        try:
            face_value = float(request.form.get('face_value'))
            coupon_rate = float(request.form.get('coupon_rate'))
            quantity = float(request.form.get('quantity'))
            transaction_price = float(request.form.get('transaction_price'))
        except ValueError:
            flash("Invalid numeric value for bond parameters", "danger")
            return redirect(url_for('bonds.add_bond'))
        if face_value < 0 or coupon_rate < 0 or quantity < 0 or transaction_price < 0:
            flash("Bond parameters must be non-negative", "danger")
            return redirect(url_for('bonds.add_bond'))
        try:
            maturity_date = datetime.strptime(request.form.get('maturity_date'), '%Y-%m-%d').date()
            purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
            return redirect(url_for('bonds.add_bond'))
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
        return redirect(url_for('bonds.bonds'))
    return render_template('add_bond.html')

@bonds_bp.route('/bond/edit/<int:bond_id>', methods=['GET', 'POST'])
@login_required
def edit_bond(bond_id):
    bond = Bond.query.get_or_404(bond_id)
    if request.method == 'POST':
        bond.name = request.form.get('name')
        try:
            bond.face_value = float(request.form.get('face_value'))
            bond.coupon_rate = float(request.form.get('coupon_rate'))
            bond.quantity = float(request.form.get('quantity'))
            bond.cost_basis = float(request.form.get('transaction_price'))
        except ValueError:
            flash("Invalid numeric value for bond parameters", "danger")
            return redirect(url_for('bonds.edit_bond', bond_id=bond_id))
        if bond.face_value < 0 or bond.coupon_rate < 0 or bond.quantity < 0 or bond.cost_basis < 0:
            flash("Bond parameters must be non-negative", "danger")
            return redirect(url_for('bonds.edit_bond', bond_id=bond_id))
        try:
            bond.maturity_date = datetime.strptime(request.form.get('maturity_date'), '%Y-%m-%d').date()
            bond.purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
            return redirect(url_for('bonds.edit_bond', bond_id=bond_id))
        db.session.commit()
        log_activity("Bond Edited", f"Bond ID {bond_id} edited.")
        flash('Bond updated successfully!', 'success')
        return redirect(url_for('bonds.bonds'))
    return render_template('edit_bond.html', bond=bond)

@bonds_bp.route('/bond/delete/<int:bond_id>', methods=['POST'])
@login_required
def delete_bond(bond_id):
    bond = Bond.query.get_or_404(bond_id)
    db.session.delete(bond)
    db.session.commit()
    log_activity("Bond Deleted", f"Bond ID {bond_id} deleted.")
    flash('Bond deleted successfully!', 'success')
    return redirect(url_for('bonds.bonds'))
