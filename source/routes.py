import os
import time
import hashlib
import json

import vendor.qrtools as qrtools
from elaphe.upc import UpcA
import flask
import rethinkdb as r


app = flask.Flask(__name__)
app.secret_key = 'EFAWEFBEEWOINAEWBNAWEF:OIEBNAWDA'

conn = r.connect('127.0.0.1', 28015)


def setup_db():
    global conn
    r.db_create('inventory').run(conn)
    r.db('inventory').table_create('items').run(conn)
    r.db('inventory').table_create('users').run(conn)


try:
    db = r.db('inventory')
    items_db = db.table('items')
    users_db = db.table('users')
except:
    setup_db()

    db = r.db('inventory')
    items_db = db.table('items')
    users_db = db.table('users')


# the items cache, prevents us from hitting the database with each request
#
cache = []
cache_expires = 0
cache_time = 60  # 60 second cache time


class UserMgr:
    _conn = None

    def __init__(self, dconn):

        self._conn = dconn

        self._db = r.db('inventory').table('users')
        self._cache = self._db.run(dconn)
        self._cacheExpires = time.time() + 60

    def check_cache(self, force=False):

        if time.time() < self._cacheExpires and not force:
            return

        try:
            self._cache = list(self._db.run(self._conn))
            self._cacheExpires = time.time() + 60

        except r.RqlError as e:
            print "[ERROR] User Database Error: %s" % e.message

            raise e

    def register_user(self, user):

        self.check_cache()

        try:
            dup = [i for i in self._cache if i.username == user.username]

            if len(dup) > 0:
                print "[WARNING]: Attempted to register duplicate user"

                return dup

            safe = {'roles': user.roles,
                    'username': user.username,
                    'password': user.password,
                    'lastSeen': time.time(),
                    'itemList': user.itemList,
                    'locked': user.locked}

            result = self._db.insert(safe).run(self._conn)

            print "[INFO]: Registered new user %s.  DB Result: %s" % (safe['username'], json.dumps(result))

        except:

            return None

        return result

    def check_user(self, username, password):

        hashed = hashlib.sha256(password)

        self.check_cache()

        matched = [user for user in self._cache if user.username == username and user.password == hashed]

        if len(matched) > 0:
            return matched[0]

        return None


class User:
    def __init__(self):
        self.roles = ['']
        self.username = ''
        self.password = '!'
        self.lastSeen = 'NEVER'
        self.itemList = [{}]
        self.locked = False

    def to_string(self):

        serial = json.dumps({'roles': self.roles,
                             'username': self.username,
                             'password': self.password,
                             'lastSeen': time.time(),
                             'itemList': self.itemList,
                             'locked': self.locked})

        return serial

    def from_string(self, string):

        checker = lambda i, attr: i['roles'] if attr in i else None

        try:
            item = json.loads(string)

            self.roles = checker(item, 'roles')
            self.username = checker(item, 'username')
            self.password = checker(item, 'password')
            self.lastSeen = checker(item, 'lastSeen')
            self.itemList = checker(item, 'itemList')
            self.locked = checker(item, 'locked')

        except:

            self.__init__()


# attempts to log a user in
#
def user_login(username, password):
    global users_db

    item = users_db.find_one(r.row('username', username)).run()

    if item:
        hashed_pw = hashlib.sha256('MONTESSORI' + password)
        if item.password == hashed_pw:
            return item

    return None


def update_cache(offset=0, limit=999):
    global cache
    global cache_expires
    global cache_time
    global items_db
    global conn

    try:
        cur_time = int(time.time())

        if cur_time >= cache_expires:
            all_items = items_db.run(conn)
            cache = [i for i in all_items]

            cache_expires = cur_time + cache_time

            flask.flash('Cache Updated', "info")

            for index, item in enumerate(cache):
                if 'ImageUrl' not in item:
                    item['ImageUrl'] = 'http://placehold.it/350x250'
                if 'Status' not in item:
                    item['Status'] = 'In'
                if 'QRUrl' not in item:
                    try:
                        f = open(os.path.dirname(__file__) + '/static/images/' + item['id'] + '.png')
                        f.close()
                    except IOError:
                        qr = qrtools.QR(item['id'])

                        qr.encode(os.path.dirname(__file__) + '/static/images/' + item['id'] + '.png')

                    item['QRUrl'] = '/static/images/' + item['id'] + '.png'

                if 'UPCUrl' not in cache[index]:
                    try:
                        upc = ''
                        for a in item['id']:
                            upc += str(ord(a))

                        upc = (str(upc))[-11:]

                        print 'upc: %s\n' % upc

                        f = open(os.path.dirname(__file__) + '/static/images/' + upc + '.png')
                        f.close()
                    except IOError:
                        qr = UpcA().render(upc, options=dict(includetext=True), scale=2, margine=1)
                        qr.save(os.path.dirname(__file__) + '/static/images/' + upc + '.png')

                    item['UPCUrl'] = '/static/images/' + upc + '.png'

        boff = int(offset)
        blim = int(limit)

        offset = boff
        limit = blim

        view = cache[offset:offset + limit]

        return view

    except RuntimeError as e:
        flask.flash('database error. please try again later. ' + e.message, "error")

        return flask.redirect('/')


@app.route('/assets/<t>/<filename>')
def assets(filename, t):
    try:
        if '..' in filename or filename[0] == '/':
            flask.abort(401)

        if '.js' in filename:
            f = open(os.path.dirname(__file__) + '/static/js/' + filename, "r")
            return flask.send_file(f, 'text/javascript')
        elif '.css' in filename:
            f = open(os.path.dirname(__file__) + '/static/css/' + filename, "r")
            return flask.send_file(f, 'text/css')
        else:
            flask.abort(401)
    except IOError as e:
        out = open('log.out', 'a')
        out.write('[!] IOError: %s: "%s"\n' % (e.strerror, e.filename))
        out.close()

        flask.flash("File not found. Please try your request again later.", "error")

        return flask.redirect('/')


@app.route('/404')
def not_found():
    return 'Oops!  Looks like we\'ve lost a website!'


@app.route('/items/count', methods=['GET'])
def item_count():
    view = update_cache()

    return json.dumps({'status': 200, 'count': len(view)})


@app.route('/items')
def def_list_items():
    return flask.redirect('/items/0/99')


@app.route('/items/<offset>/<limit>', methods=['GET'])
def list_items(offset, limit):
    offset = offset or 0
    limit = limit or 100

    view = update_cache(offset, limit)

    summary_headers = ["Model", "Manufacturer", "Serial Number", "Location"]

    display = {'Model': 'model',
               'Manufacturer': 'manufacturer',
               'Serial Number': 'serial',
               'Location': 'location',
               'id': 'id'}

    final = []

    for item in view:
        tmp = {}
        for field in display:
            try:
                tmp[field] = item[field]
            except:
                pass

        final.append(tmp)

    return flask.render_template('list_item.html', items=final, display=display, headers=summary_headers)


@app.route('/json/items/<offset>/<limit>', methods=['GET'])
@app.route('/json/items')
def list_items_json(offset=0, limit=99):
    offset = offset or 0
    limit = limit or 100

    view = update_cache(offset, limit)

    summary_headers = ["Model", "Manufacturer", "Serial Number", "Location"]

    display = {'Model': 'model',
               'Manufacturer': 'manufacturer',
               'Serial Number': 'serial',
               'Location': 'location',
               'id': 'id'}

    final = []

    for item in view:
        tmp = {}
        for field in display:
            try:
                tmp[field] = item[field]
            except:
                pass

        final.append(tmp)

    return json.dumps({'status': 200,
                       'offset': offset,
                       'limit': limit,
                       'count': len(final),
                       'items': final,
                       'display': display,
                       'headers': summary_headers})


@app.route('/items', methods=['PUT'])
def update_item():
    try:
        current_user = user_login(flask.request.form['username'], flask.request.form['password'])
    except KeyError:
        # no user data submitted
        flask.flash('Invalid Request')
        return 403

    if current_user is None:
        # invalid credentials
        flask.flash('Invalid Credentials')
        return 401

    if 'DB_ADMIN' in current_user.roles:
        flask.flash('Yay success')
        return 'Success'

    return 401


@app.route('/items', methods=['DELETE'])
def delete_item():
    try:
        current_user = user_login(flask.request.form['username'], flask.request.form['password'])
    except KeyError:
        # no user data submitted
        flask.flash('Invalid Request')
        return 403

    if current_user is None:
        # invalid credentials
        flask.flash('Invalid Credentials')
        return 401

    if 'DB_ADMIN' in current_user.roles:
        flask.flash('Yay success')
        return 'Success'

    return 401


@app.route('/items/<barcode>', methods=['POST'])
def slice_list_items(barcode):
    view = update_cache()

    for i in view:
        if barcode in str(i['id']):
            return flask.render_template('item_header.html', fields=i)

    return flask.render_template('item_header.html', fields={})


@app.route('/json/items/<barcode>', methods=['POST'])
def slice_list_json(barcode):
    view = update_cache()

    for i in view:
        if barcode in str(i['id']):
            return json.dumps({'status': 200, 'count': 1, 'items': [i, ]})

    return json.dumps({'status': 404, 'count': 0, 'items': [{}]})


@app.route('/')
def default():
    return flask.redirect('/items')


if __name__ == "__main__":
    app.run(debug=True)
