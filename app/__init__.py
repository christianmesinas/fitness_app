# /app/app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_session import Session
from flask_moment import Moment
from authlib.integrations.flask_client import OAuth
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'main.login'
sess = Session()
moment = Moment()
oauth = OAuth()

def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Log configuration for debugging
    logging.info(f"SESSION_TYPE: {app.config.get('SESSION_TYPE')}")
    logging.info(f"AUTH0_CLIENT_ID: {app.config.get('AUTH0_CLIENT_ID')}")
    logging.info(f"AUTH0_CLIENT_SECRET: {app.config.get('AUTH0_CLIENT_SECRET')[:4]}...")
    logging.info(f"AUTH0_DOMAIN: {app.config.get('AUTH0_DOMAIN')}")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    sess.init_app(app)
    moment.init_app(app)
    oauth.init_app(app)

    # Configure Auth0
    try:
        oauth.register(
            name='auth0',
            client_id=app.config['AUTH0_CLIENT_ID'],
            client_secret=app.config['AUTH0_CLIENT_SECRET'],
            api_base_url=f"https://{app.config['AUTH0_DOMAIN']}",
            access_token_url=f"https://{app.config['AUTH0_DOMAIN']}/oauth/token",
            authorize_url=f"https://{app.config['AUTH0_DOMAIN']}/authorize",
            jwks_uri=f"https://{app.config['AUTH0_DOMAIN']}/.well-known/jwks.json",
            client_kwargs={'scope': 'openid profile email'},
        )
        logging.info("Auth0 OAuth client registered successfully")
    except Exception as e:
        logging.error(f"Failed to register Auth0 OAuth client: {str(e)}")
        raise

    # Configure logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/fittrack.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('FitTrack startup')

    # Register Blueprint
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    # Add user loader for Flask-Login
    @login.user_loader
    def load_user(id):
        from app.models import User
        return db.session.get(User, int(id))

    return app