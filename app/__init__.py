import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_moment import Moment
from authlib.integrations.flask_client import OAuth
from config import Config

logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
moment = Moment()
oauth = OAuth()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    moment.init_app(app)
    oauth.init_app(app)

    login.login_view = 'main.login'

    auth0_domain = app.config['AUTH0_DOMAIN']
    oauth.register(
        name='auth0',
        client_id=app.config['AUTH0_CLIENT_ID'],
        client_secret=app.config['AUTH0_CLIENT_SECRET'],
        server_metadata_url=f'https://{auth0_domain}/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid profile email',
        },
    )

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    return app

@login.user_loader
def load_user(id):
    from app.models import User
    logger.debug(f"Laden van gebruiker met id: {id}")
    try:
        user = db.session.get(User, int(id))
        if user:
            logger.debug(f"Gebruiker geladen: {user.username}")
            return user
        logger.debug("Geen gebruiker gevonden voor id")
        return None
    except Exception as e:
        logger.error(f"Fout bij laden van gebruiker met id {id}: {str(e)}")
        return None