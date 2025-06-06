from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

logger.debug("Initialiseren van main blueprint")
bp = Blueprint('main', __name__)

from . import routes
