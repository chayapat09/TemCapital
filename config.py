# config.py
class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///investment_tracker.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'your_secret_key'  # Replace with a secure key
