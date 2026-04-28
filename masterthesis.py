from CTFd import CTFdFlask

from . import views
from . import scaffoldmgr

# TODO check how we should deal with in-memory data (redis / global variables). also e.g. state of scaffold
# TODO set up logging

def load(app: CTFdFlask):
    views.load(app)
    
    scaffoldmgr.load()
