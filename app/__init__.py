from flask import Flask
import os

def create_app():
    app = Flask(__name__)
    
    # Set a secure secret key for sessions
    app.secret_key = os.urandom(24)
    
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    return app