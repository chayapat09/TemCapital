from flask import Blueprint, render_template, request, flash, session
from flask_login import login_required, current_user
from models import db, Investment, Transaction, CashAccount, CashTransaction, Bond, Dividend
from datetime import datetime, date
from helpers import (
    convert_currency, 
    get_price, 
    calculate_cash_balance_as_of, 
    get_periods,
    log_activity, 
    get_investment_quote_currency, 
    compute_user_investment, 
    compute_realized_gain
)

financials_bp = Blueprint('financials', __name__)

@financials_bp.route('/summary')
@login_required
def summary():
    selected_currency = request.args.get('currency', 'USD')
    investments = Investment.query.all()
    
    # Determine timeline based on user transactions
    txns = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date).all()
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
            shares, avg_cost = compute_user_investment(inv, current_user.id)
            if shares == 0:
                continue
            price = get_price(inv.symbol)
            asset_value = shares * price
            cost_basis_total = shares * avg_cost
            inv_currency = get_investment_quote_currency(inv, current_user.id)
            asset_value_conv = convert_currency(asset_value, inv_currency, selected_currency)
            cost_conv = convert_currency(cost_basis_total, inv_currency, selected_currency)
            total_asset_value += asset_value_conv
            total_cost_basis += cost_conv
        profit_loss = total_asset_value - total_cost_basis
        monthly_data.append({
            'month': month_start.strftime("%Y-%m"),
            'asset_value': round(total_asset_value, 2),
            'cost_basis': round(total_cost_basis, 2),
            'profit_loss': round(profit_loss, 2)
        })
    
    category_data = {}
    for inv in investments:
        shares, avg_cost = compute_user_investment(inv, current_user.id)
        if shares == 0:
            continue
        price = get_price(inv.symbol)
        asset_value = shares * price
        total_cost = shares * avg_cost
        inv_currency = get_investment_quote_currency(inv, current_user.id)
        asset_value_conv = convert_currency(asset_value, inv_currency, selected_currency)
        cost_conv = convert_currency(total_cost, inv_currency, selected_currency)
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

@financials_bp.route('/balance_sheet')
@login_required
def balance_sheet():
    period_type = request.args.get('period_type', 'yearly')
    today = date.today()
    allowed_years = list(range(today.year - 10, today.year + 1))
    periods = get_periods(period_type, request)
    period_labels = [label for (label, s, e) in periods]

    cash_values = []
    investment_values = []
    bond_values = []
    total_assets = []
    liabilities_values = []
    equity_values = []

    for label, start_date, end_date in periods:
        cash = sum(calculate_cash_balance_as_of(acc, end_date) for acc in CashAccount.query.filter_by(user_id=current_user.id).all())
        inv_val = 0
        for inv in Investment.query.all():
            shares, avg = compute_user_investment(inv, current_user.id)
            price = get_price(inv.symbol)
            asset_value = shares * price
            inv_val += convert_currency(asset_value, get_investment_quote_currency(inv, current_user.id), 'USD')
        bonds_list = Bond.query.filter(Bond.purchase_date <= end_date, Bond.user_id==current_user.id).all()
        bond_val = sum(bond.quantity * bond.face_value for bond in bonds_list)
        total = cash + inv_val + bond_val
        
        cash_values.append(round(cash, 2))
        investment_values.append(round(inv_val, 2))
        bond_values.append(round(bond_val, 2))
        total_assets.append(round(total, 2))
        liabilities_values.append(0)
        equity_values.append(round(total, 2))
    
    return render_template('balance_sheet.html', period_type=period_type,
                           period_labels=period_labels, cash_values=cash_values,
                           investment_values=investment_values, bond_values=bond_values,
                           total_assets=total_assets, liabilities_values=liabilities_values,
                           equity_values=equity_values, allowed_years=allowed_years, today=today)

@financials_bp.route('/income_statement')
@login_required
def income_statement():
    period_type = request.args.get('period_type', 'yearly')
    today = date.today()
    allowed_years = list(range(today.year - 10, today.year + 1))
    periods = get_periods(period_type, request)
    period_labels = [label for (label, s, e) in periods]

    total_dividends_list = []
    realized_gain_list = []
    total_revenue_list = []
    total_expenses_list = []
    net_income_list = []

    for label, start_date, end_date in periods:
        dividends = Dividend.query.filter(Dividend.date >= start_date, Dividend.date <= end_date, Dividend.user_id==current_user.id).all()
        total_dividends = sum(d.amount for d in dividends)
        
        realized_gain = 0
        for inv in Investment.query.all():
            realized_gain += compute_realized_gain(inv, current_user.id, start_date, end_date)
        
        total_revenue = total_dividends + realized_gain
        total_expenses = 0
        net_income = total_revenue - total_expenses

        total_dividends_list.append(round(total_dividends, 2))
        realized_gain_list.append(round(realized_gain, 2))
        total_revenue_list.append(round(total_revenue, 2))
        total_expenses_list.append(round(total_expenses, 2))
        net_income_list.append(round(net_income, 2))

    return render_template('income_statement.html', period_type=period_type,
                           period_labels=period_labels, total_dividends_list=total_dividends_list,
                           realized_gain_list=realized_gain_list, total_revenue_list=total_revenue_list,
                           total_expenses_list=total_expenses_list, net_income_list=net_income_list,
                           allowed_years=allowed_years, today=today)

@financials_bp.route('/cash_flow')
@login_required
def cash_flow_statement():
    period_type = request.args.get('period_type', 'yearly')
    today = date.today()
    allowed_years = list(range(today.year - 10, today.year + 1))
    periods = get_periods(period_type, request)
    period_labels = [label for (label, s, e) in periods]

    operating_list = []
    investing_list = []
    net_cash_flow_list = []

    for label, start_date, end_date in periods:
        txns = CashTransaction.query.filter(CashTransaction.date >= start_date, CashTransaction.date <= end_date).all()
        operating = 0
        investing = 0
        for txn in txns:
            if txn.transaction_type in ['deposit', 'withdraw']:
                if txn.transaction_type == 'deposit':
                    operating += txn.amount
                else:
                    operating -= txn.amount
            elif txn.transaction_type in ['investment_buy', 'investment_sell']:
                if txn.transaction_type == 'investment_buy':
                    investing -= txn.amount
                else:
                    investing += txn.amount
        net_cash_flow = operating + investing
        operating_list.append(round(operating, 2))
        investing_list.append(round(investing, 2))
        net_cash_flow_list.append(round(net_cash_flow, 2))

    return render_template('cash_flow_statement.html', period_type=period_type,
                           period_labels=period_labels, operating_list=operating_list,
                           investing_list=investing_list, net_cash_flow_list=net_cash_flow_list,
                           allowed_years=allowed_years, today=today)

@financials_bp.route('/financial_overview')
@login_required
def financial_overview():
    period_type = request.args.get('period_type', 'yearly')
    today = date.today()
    allowed_years = list(range(today.year - 10, today.year + 1))
    overview_data = []
    if period_type == 'yearly':
        current_year = today.year
        try:
            start_year = int(request.args.get('start_year', current_year))
            end_year = int(request.args.get('end_year', current_year))
        except ValueError:
            start_year = current_year
            end_year = current_year
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        if end_year > current_year:
            end_year = current_year
        if end_year - start_year + 1 > 5:
            end_year = start_year + 4
        for year in range(start_year, end_year + 1):
            comp_total_asset = 0
            comp_total_cost = 0
            for inv in Investment.query.all():
                txns = Transaction.query.filter(
                    Transaction.investment_id == inv.id,
                    Transaction.user_id == current_user.id,
                    Transaction.date <= datetime(year, 12, 31)
                ).order_by(Transaction.date).all()
                shares = 0
                avg = 0
                for t in txns:
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
                        shares -= t.quantity
                        if shares <= 0:
                            shares = 0
                            avg = 0
                price = get_price(inv.symbol)
                comp_total_asset += convert_currency(shares * price, get_investment_quote_currency(inv, current_user.id), 'USD')
                comp_total_cost += convert_currency(shares * avg, get_investment_quote_currency(inv, current_user.id), 'USD')
            profit_loss = comp_total_asset - comp_total_cost
            overview_data.append({
                'period': str(year),
                'asset_value': round(comp_total_asset, 2),
                'cost_basis': round(comp_total_cost, 2),
                'profit_loss': round(profit_loss, 2)
            })
    elif period_type == 'quarterly':
        selected_year = int(request.args.get('year', today.year))
        if selected_year > today.year:
            selected_year = today.year
        quarters = ['Q1', 'Q2', 'Q3', 'Q4']
        for q in quarters:
            if q == 'Q1':
                comp_end = date(selected_year, 3, 31)
            elif q == 'Q2':
                comp_end = date(selected_year, 6, 30)
            elif q == 'Q3':
                comp_end = date(selected_year, 9, 30)
            elif q == 'Q4':
                comp_end = date(selected_year, 12, 31)
            comp_total_asset = 0
            comp_total_cost = 0
            for inv in Investment.query.all():
                txns = Transaction.query.filter(
                    Transaction.investment_id == inv.id,
                    Transaction.user_id == current_user.id,
                    Transaction.date <= datetime(selected_year, comp_end.month, comp_end.day)
                ).order_by(Transaction.date).all()
                shares = 0
                avg = 0
                for t in txns:
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
                        shares -= t.quantity
                        if shares <= 0:
                            shares = 0
                            avg = 0
                price = get_price(inv.symbol)
                comp_total_asset += convert_currency(shares * price, get_investment_quote_currency(inv, current_user.id), 'USD')
                comp_total_cost += convert_currency(shares * avg, get_investment_quote_currency(inv, current_user.id), 'USD')
            profit_loss = comp_total_asset - comp_total_cost
            overview_data.append({
                'period': f"{selected_year}-{q}",
                'asset_value': round(comp_total_asset, 2),
                'cost_basis': round(comp_total_cost, 2),
                'profit_loss': round(profit_loss, 2)
            })

    labels = [d['period'] for d in overview_data]
    asset_values = [d['asset_value'] for d in overview_data]
    cost_basis_list = [d['cost_basis'] for d in overview_data]
    profit_losses = [d['profit_loss'] for d in overview_data]
    
    return render_template('financial_overview.html',
                           period_type=period_type,
                           overview_data=overview_data,
                           labels=labels,
                           asset_values=asset_values,
                           cost_basis_list=cost_basis_list,
                           profit_losses=profit_losses,
                           allowed_years=allowed_years, today=today)
