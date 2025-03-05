

# Tem Capital



## Setup Instructions

### 1. Clone the Repository

```
git clone <repository-url>
cd TemCapital
```

### 2. Create and Activate a Virtual Environment
On UNIX/Linux/MacOS:

```
python3 -m venv venv
source venv/bin/activate
```

On Windows:
```
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```
pip install -r requirements.txt
```

### 4. Run the Application
```
python app.py
```

The app will start on http://127.0.0.1:8080.

## Optional: Running via Provided Scripts
For UNIX-like systems, you can run:
```
./run.sh
```
For Windows, double-click or run run.bat from the command prompt.

```
investment_tracker/
├── app.py
├── config.py
├── models.py
├── helpers.py
├── blueprints/
│   ├── __init__.py
│   ├── auth.py
│   ├── investments.py
│   ├── cash.py
│   ├── bonds.py
│   ├── dividends.py
│   ├── reports.py
│   └── financials.py
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── login.html
│   ├── register.html
│   ├── transaction.html
│   ├── edit_transaction.html
│   ├── cash.html
│   ├── add_cash.html
│   ├── edit_cash.html
│   ├── deposit_cash.html
│   ├── withdraw_cash.html
│   ├── convert_cash.html
│   ├── bonds.html
│   ├── add_bond.html
│   ├── edit_bond.html
│   ├── dividends.html
│   ├── add_dividend.html
│   ├── edit_dividend.html
│   ├── summary.html
│   ├── transactions.html
│   ├── cash_flow_statement.html
│   ├── risk.html
│   ├── financial_overview.html
│   ├── income_statement.html
│   └── balance_sheet.html
└── static/
    ├── css/
    ├── js/
    └── images/

```

TODO : 
- For prices , We will implament price feed that run with python code one code can output multiple price outputs. and each symbol can subscribe feeds.
Historical Prices feed also mandatory
- Quarterly Financial Statement from given data
- Add Mobile support.