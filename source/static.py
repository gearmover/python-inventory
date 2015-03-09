__author__ = 'chris'


import flask
import rethinkdb as r
from flask.ext.httpauth import HTTPBasicAuth

class App:

    def __init__(self):

        # manager objects
        #
        self.app = None
        self.conn = None
        self.user = None
        self.auth = None
        self.user = None

        # the items cache, prevents us from hitting the database with each request
        #
        self.cache = []
        self.cache_expires = 0
        self.cache_time = 60  # 60 second cache time

        # program initialization
        #
        self.app = flask.Flask(__name__)
        self.app.config['SECRET_KEY'] = 'G0AI5jihTfHV9s1ALDqUO6BRCIKn4Nt5'
        self.conn = r.connect('127.0.0.1', 28015)
        self.auth = HTTPBasicAuth()
