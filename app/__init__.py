import os
from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_moment import Moment
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

# Initialiseer extensies zonder app
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
moment = Moment()
oauth = OAuth()

load_dotenv()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static')
    app.config.from_object(config_class)
    app.secret_key = os.getenv('APP_SECRET_KEY')

    # Stel Redis-configuratie in
    app.config['REDIS_URL'] = config_class.REDIS_URL
    app.config['POSTS_PER_PAGE'] = 10
    app.config['SESSION_COOKIE_SECURE'] = False  # Zet op True in productie
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600
    app.config['SESSION_COOKIE_NAME'] = 'fittrack_session'

    app.logger.debug(f"Session config: {app.config.get_namespace('SESSION_')}")

    # Initialiseer extensies met app
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    moment.init_app(app)
    oauth.init_app(app)

    # Initialiseer Auth0
    oauth.register(
        'auth0',
        client_id=app.config['AUTH0_CLIENT_ID'],
        client_secret=app.config['AUTH0_CLIENT_SECRET'],
        server_metadata_url=f"https://{app.config['AUTH0_DOMAIN']}/.well-known/openid-configuration",
        client_kwargs={
            'scope': 'openid profile email',
            'prompt': 'login',
        },
    )

    # Importeer Blueprints
    from app.api import bp as api_bp
    from app.errors import bp as errors_bp
    from app.main import bp as main_bp

    # Importeer routes en handlers expliciet om ze te laden
    from app.api import errors
    from app.api import routes
    from app.errors import handlers
    from app.main import routes

    # Registreer Blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(errors_bp)
    app.register_blueprint(main_bp)


    return app