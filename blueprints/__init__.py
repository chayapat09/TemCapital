# blueprints/__init__.py
from .auth import auth_bp
from .investments import investments_bp
from .cash import cash_bp
from .bonds import bonds_bp
from .dividends import dividends_bp
from .financials import financials_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(investments_bp)
    app.register_blueprint(cash_bp)
    app.register_blueprint(bonds_bp)
    app.register_blueprint(dividends_bp)
    app.register_blueprint(financials_bp)
