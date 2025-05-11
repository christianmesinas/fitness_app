from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

logger.debug("Initialiseren van main blueprint")
bp = Blueprint('main', __name__)
logger.debug("Main blueprint gedefinieerd")

from . import routes
logger.debug("Routes geïmporteerd voor main blueprint")