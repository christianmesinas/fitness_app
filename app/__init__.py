import logging
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_moment import Moment
from flask_session import Session
from authlib.integrations.flask_client import OAuth
from flask_wtf import CSRFProtect
from config import Config

logger = logging.getLogger(__name__)

# Initialiseer extensies globaal voor gebruik in de applicatiefactory
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
moment = Moment()
oauth = OAuth()
csrf = CSRFProtect()


@login.user_loader
def load_user(user_id):
    # Laad een gebruikersobject op basis van de user_id voor Flask-Login.
    from app.models import User # Import hier om circulaire imports te vermijden
    try:
        user = db.session.get(User, int(user_id))
        if not user:
            session.clear()  # forceer nieuwe login
            logger.debug("Geen gebruiker gevonden voor id, sessie gecleared")
        else:
            logger.debug(f"Gebruiker geladen: {user.name}")
        return user
    except Exception as e:
        logger.error(f"Fout bij laden van gebruiker met id {user_id}: {str(e)}")
        return None


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configureer sessie-opslag op bestandssysteem
    app.config['SESSION_TYPE'] = 'filesystem'  # Persistente sessies
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'  # Map voor sessiebestanden

    # Initialiseer Flask-Session voor server-side sessiebeheer
    Session(app)

    # Initialiseer CSRF-bescherming voor formulieren
    csrf.init_app(app)

    # Initialiseer extensies met de app
    db.init_app(app)  # Database-ORM
    migrate.init_app(app, db)  # Database-migraties
    login.init_app(app)  # Gebruikersauthenticatie
    moment.init_app(app)  # Tijdformattering
    oauth.init_app(app)  # OAuth voor Auth0

    # Stel login-view in voor Flask-Login
    login.login_view = 'main.login'

    auth0_domain = app.config['AUTH0_DOMAIN']
    oauth.register(
        name='auth0',
        client_id=app.config['AUTH0_CLIENT_ID'],
        client_secret=app.config['AUTH0_CLIENT_SECRET'],
        server_metadata_url=f'https://{auth0_domain}/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid profile email',  # Vraag toegang tot profiel en e-mail
        },
    )
    # Registreer blueprints voor routes en errorhandling

    from app.errors import bp as errors_bp
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(errors_bp)

    # Importeer modellen om database-tabellen te registreren
    from app import models

    return app
