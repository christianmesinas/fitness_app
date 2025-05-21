import logging
from app import create_app, db

# Configureer logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Start van fittrack.py")
app = create_app()
logger.debug("create_app() uitgevoerd, app gemaakt")

if __name__ == '__main__':
    logger.debug("Start Flask server")
    app.run(host='0.0.0.0', port=5000, debug=True)