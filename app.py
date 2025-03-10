from flask import Flask
from config import Config
from models import db, User
from flask_login import LoginManager
from blueprints import register_blueprints

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

register_blueprints(app)

def init_db():
    with app.app_context():
        db.create_all()
        from models import CashAccount
        # For testing purposes only. In production, each user creates their own account.
        if not CashAccount.query.first():
            default_account = CashAccount(account_name='Main Account', currency='USD', balance=10000, user_id=1)
            db.session.add(default_account)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=8080)
