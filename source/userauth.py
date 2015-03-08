__author__ = 'chris'


import base64
import flask.ext.login as login
import rethinkdb as r
import hashlib
import uuid
import time
from flask import request, session


_conn = None

salt = 'G0AI5jihTfHV9s1ALDqUO6BRCIKn4Nt5'

class UserLite(login.UserMixin):
    def __init__(self, name, id, active=True):
        self.id = id
        self.name = name
        self.active = active

    def get_id(self):
        return self.id

    def is_active(self):
        return self.active

    def get_auth_token(self):
        return login.make_secure_token(self.name, key='deterministic')

def attempt(username, password):

    global salt
    global _conn

    print "[userauth::attempt] -> parameters (%s,%s)" % (username,password)

    if username is None or password is None:
        return None

    passhash = hashlib.sha256(salt + password).hexdigest()

    print '[userauth::attempt] -> passhash is ',passhash

    #try:
    user = list(r.db('inventory').table('users').filter({'username':username, 'passhash':passhash}).run(_conn) or None,)[0]

    print '[userauth::attempt] -> db lookup result ', user is not None

    l = UserLite( user['username'], sum([ord(k) for k in user['id']]) )

    print 'object: ', str(l)

    return l

    #except:
    #    return None


def db_connect(host,port):
    """
    Connects to a user database backend for authorization
    :param host: the ip or hostname of the backend
    :param port: port to connect to
    :return: none
    """

    global _conn

    _conn = r.connect(host,port)

    try:
        r.db_create('inventory').run(_conn)
    except:
        pass

    try:
        r.db('inventory').table_create('users').run(_conn)
    except:
        pass


def init(app, host, port):

    global _conn

    _conn = None
    login_manager = login.LoginManager()

    login_manager.init_app(app)
    login_manager.user_callback = lambda id: list(UserLite(r.db('inventory').table('users').filter({'id':id}).run(_conn)))

    db_connect(host,port)

    @login_manager.request_loader
    def load_user_from_request(request):

        global _conn

        # first, try to login with credentials
        username = request.form.get('username')
        password = request.form.get('password')

        if username and password:
            creds = attempt(username, password)

            if creds:
                return creds

        # second, try to login using the api_key url arg
        api_key = request.args.get('api_key')
        if api_key:
            user = User.load_one(_conn, {'apiKey': api_key})
            if user:
                return user

        # next, try to login using Basic Auth
        api_key = request.headers.get('Authorization')
        if api_key:
            api_key = api_key.replace('Basic ', '', 1)
            try:
                api_key = base64.b64decode(api_key)
            except TypeError:
                pass
            user = User.load_one(_conn, {'apiKey': api_key})
            if user:
                return user

        # finally, return None if both methods did not login the user
        return None


    class AuthMethods:

        def __init__(self,app):

            global _conn

            self.app = app
            self.app.config['SECRET_KEY'] = 'deterministic'
            self.app.config['SESSION_PROTECTION'] = None
            self.app.config['TESTING'] = True
            self.remember_cookie_name = 'remember'
            self.app.config['REMEMBER_COOKIE_NAME'] = self.remember_cookie_name
            self.login_manager = login.LoginManager()
            self.login_manager.init_app(self.app)
            self.login_manager._login_disabled = False
            self.conn = _conn


            @self.app.route('/')
            def index():
                return u'Welcome!'


            @self.app.route('/secret')
            def secret():
                return self.login_manager.unauthorized()


            @self.app.route('/needs-refresh')
            def needs_refresh():
                return self.login_manager.needs_refresh()


            @self.app.route('/confirm-login')
            def _confirm_login():
                login.confirm_login()

                return u''


            @self.app.route('/username')
            def username():
                if login.current_user.is_authenticated:
                    return login.current_user.name

                return u'Anonymous'


            @self.app.route('/is-fresh')
            def is_fresh():
                return unicode(login.login_fresh())


            @self.app.route('/logout')
            def logout():
                return unicode(login.logout_user())


            @self.login_manager.user_loader
            def load_user(user_id):
                u = list(r.db('inventory').table('users').filter({'id':user_id}).run(self.conn),)[0]
                if u:
                    return UserLite(u.id, u.username)


            # @self.login_manager.header_loader
            # def load_user_from_header(header_value):
            #     if header_value.startswith('Basic '):
            #         header_value = header_value.replace('Basic ', '', 1)
            #     try:
            #         user_id = base64.b64decode(header_value)
            #     except TypeError:
            #         pass
            #
            #     return USERS.get(int(user_id))


            @self.login_manager.request_loader
            def load_user_from_request(request):
                user_id = request.args.get('username')

                u = list(r.db('inventory').table('users').filter({'username':user_id}).run(self.conn))

                if len(u):
                    u = u[0]
                    return UserLite(u.id, u.username)


            @self.app.route('/empty_session')
            def empty_session():
                return unicode(u'modified=%s' % session.modified)


            @self.app.errorhandler(404)
            def handle_404(e):
                raise e


        def _get_remember_cookie(self, test_client):
            our_cookies = test_client.cookie_jar._cookies['localhost']['/']

            return our_cookies[self.remember_cookie_name]


        def _delete_session(self, c):
            # Helper method to cause the session to be deleted
            # as if the browser was closed. This will remove
            # the session regardless of the permament flag
            # on the session!
            with c.session_transaction() as sess:
                sess.clear()


    am = AuthMethods(app)

class User:
    def __init__(self):

        self.username = ''
        self.passhash = ''
        self.firstName = ''
        self.lastName = ''
        self.UFID = ''
        self.roles = ''
        self.api_key = ''
        self.id = uuid.uuid4()
        self.lastSeen = time.time()


    def update_seen_time(self):
        """
        an explicit method to update a user's 'last seen' timestamp
        :return: None
        """

        self.lastSeen = time.time()



    def save(self, conn):
        """
        saves this User instance in the passed RethinkDB database

        :param conn:
        :return:
        """

        try:
            return r.db('inventory').table('users').get(self.id).update(self.toJSON()).run(conn)
        except:
            try:
                return r.db('inventory').table('users').insert(self.toJSON()).run(conn)
            except:
                return None

    @staticmethod
    def load(conn, filter):
        """
        loads a particular user or set of users from the passed RethinkDB database.  it does NOT modify
        the object.

        :param conn: an active RDB connection
        :param filter: either a lambda function that returns True/False or r.row('<fieldname>') == '<value>'
        :return: the record(s) matching the filter
        """
        try:
            return list(r.db('inventory').table('users').filter(filter).run(conn))
        except:
            return None

    @staticmethod
    def load_one(conn, filter):

        return (User.load(conn,filter) or [None])[0]


    def toJSON(self):
        """
        reformat this user object into a serializable JSON object

        :return:  JSON document describing this User() instance
        """

        return {'username': self.username,
               'passhash': self.passhash,
               'firstName': self.firstName,
               'lastName': self.lastName,
               'UFID': self.UFID,
               'roles': self.roles,
               'apiKey': self.api_key,
               'lastSeen': self.lastSeen,
               'id': self.id}


    @staticmethod
    def fromJSON(json):
        """
        converts from a string-JSON object back into a User instance

        :param json: the json object describing the user
        :return: a new instance of User() describing the data
        """

        if json is None:
            return None

        attr = lambda obj, param, default=None: obj[param] if param in obj else default

        that = User()

        that.username = attr(json,'username')
        that.passhash = attr(json,'password')
        that.firstName = attr(json, 'firstName')
        that.lastName = attr(json, 'lastName')
        that.UFID = attr(json, 'UFID')
        that.roles = attr(json, 'roles')
        that.api_key = attr(json, 'apiKey', hashlib.sha256(that.username + salt + that.passhash).hexdigest())
        that.lastSeen = attr(json, 'lastSeen', time.time())
        that.id = attr(json,'id',uuid.uuid4())

        return that


    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)