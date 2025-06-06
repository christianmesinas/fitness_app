import logging
from app import create_app

# Configureer logging
logger = logging.getLogger(__name__)

app = create_app()
logger.debug("create_app() uitgevoerd, app gemaakt")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)