import logging

from CTFd import CTFdFlask

from . import views
from . import scaffoldmgr

logger = logging.getLogger("masterthesis")
logger.setLevel(logging.INFO)

# TODO check how we should deal with in-memory data (redis / global variables). also e.g. state of scaffold

def load(app: CTFdFlask):
    logger.info("Initializing masterthesis plugin")
    views.load(app)
    
    scaffoldmgr.load()
