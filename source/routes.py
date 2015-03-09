
__author__ = 'chris'

import os
import time
import hashlib
import json

import traceback

import vendor.qrtools as qrtools
from elaphe.upc import UpcA
import flask
import rethinkdb as r

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, SignatureExpired, BadSignature
from flask import request, session, abort
from static import App

from db import DatabaseMgr

the_app = App()


def setup_db():
    global the_app

    r.db_create('inventory').run(the_app.conn)
    r.db('inventory').table_create('items').run(the_app.conn)
    r.db('inventory').table_create('users').run(the_app.conn)


try:
    db = r.db('inventory')
    items_db = db.table('items')
    users_db = db.table('users')
except:
    setup_db()

    db = r.db('inventory')
    items_db = db.table('items')
    users_db = db.table('users')


class LoginUser:

    def __init__(self, username = '', password = '', active = True):
        global the_app

        self.username = username
        self.passhash = hashlib.sha256(the_app.app.config['SECRET_KEY'] + password).hexdigest()
        self.active = active

        self.uuid = hashlib.sha256(self.username + the_app.app.config['SECRET_KEY'] + self.passhash).hexdigest()

    def generate_token(self, expiration = 600):

        global the_app

        s = Serializer(the_app.app.config['SECRET_KEY'], expires_in = expiration)

        return s.dumps({ 'id': self.uuid })


class LoginMgr:

    @staticmethod
    @the_app.app.route('/users/register', methods=['POST'])
    @the_app.auth.login_required
    def new_user():

        global the_app

        username = request.form.get('username')
        password = request.form.get('password')

        if username is None or password is None:
            return flask.redirect('/400') # missing arguments

        if r.db('inventory').table('users').filter({'username':username}).count().run(the_app.conn):
            print 'existing user'
            return flask.redirect('/400') # existing user

        user = LoginUser(username = username, password = password)

        r.db('inventory').table('users').insert({
            'id':user.uuid,
            'username':user.username,
            'passhash':user.passhash,
            'active':user.active,
            'roles':None,
            'createdAt':time.time()}).run(the_app.conn)

        return json.dumps({ 'username': user.username, 'result': 200, 'id': user.uuid})

    def verify_token(self, token):
        global the_app

        print '[auth::verify_token] -> (%s)' % (token)

        s = Serializer(the_app.app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None
        except BadSignature:
            return None

        user = list(r.db('inventory').table('users').filter({'uuid':data}).run(the_app.conn))

        the_app.user = user

        return user

    @the_app.auth.verify_password
    def verify_pwd(username, password):

        print "[auth::verify_pwd] -> (%s,%s)" % (username,password)

        global the_app

        user = list(r.db('inventory').table('users').filter({'username':username,'passhash':hashlib.sha256(the_app.app.config['SECRET_KEY'] + password).hexdigest()}).run(the_app.conn))

        if not len(user):
            user = list(r.db('inventory').table('users').filter({'uuid':username}).run(the_app.conn))

            if not len(user):
                return False

        the_app.user = user

        return True



def update_cache(offset=0, limit=999):
    global items_db
    global the_app

    try:
        cur_time = int(time.time())

        if cur_time >= the_app.cache_expires:
            all_items = items_db.run(the_app.conn)
            the_app.cache = [i for i in all_items]

            the_app.cache_expires = cur_time + the_app.cache_time

            flask.flash('Cache Updated', "info")

            for index, item in enumerate(the_app.cache):
                if 'ImageUrl' not in item:
                    item['ImageUrl'] = 'http://placehold.it/350x250'
                if 'Status' not in item:
                    item['Status'] = 'In'
                if 'QRUrl' not in item:
                    try:
                        f = open('static/images/' + item['id'] + '.png')
                        f.close()
                    except IOError:
                        qr = qrtools.QR(item['id'])

                        qr.encode('static/images/' + item['id'] + '.png')

                    item['QRUrl'] = '/static/images/' + item['id'] + '.png'

                if 'UPCUrl' not in item:
                    try:
                        upc = ''
                        for a in item['id']:
                            upc += str(ord(a))

                        upc = (str(upc))[-11:]

                        f = open('static/images/' + upc + '.png')
                        f.close()
                    except IOError:
                        qr = UpcA().render(upc, options=dict(includetext=True), scale=2, margine=1)
                        qr.save('static/images/' + upc + '.png')

                    item['UPCUrl'] = '/static/images/' + upc + '.png'

        boff = int(offset)
        blim = int(limit)

        offset = boff
        limit = blim

        view = the_app.cache[offset:offset + limit]

        return view

    except RuntimeError as e:
        flask.flash('database error. please try again later. ' + e.message, "error")

        return flask.redirect('/')


@the_app.app.before_request
def print_headers():

    print the_app.user

@the_app.app.route('/assets/<t>/<filename>')
@the_app.auth.login_required
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


@the_app.app.route('/404')
def not_found():
    return 'Oops!  Looks like we\'ve lost a website!'

@the_app.app.route('/400')
def invalid_request():
    return 'Invalid Request.  Please use your browers back button to return to your previous page.'\

@the_app.app.route('/401')
def unauthorized():
    return 'Unauthorized Access.  If you feel this is in error, please contact the IT support team.'


@the_app.app.route('/items/count', methods=['GET'])
def item_count():
    view = update_cache()

    return json.dumps({'status': 200, 'count': len(view)})


@the_app.app.route('/items')
@the_app.auth.login_required
def def_list_items():
    return flask.redirect('/items/0/99')


@the_app.app.route('/items/<offset>/<limit>', methods=['GET'])
@the_app.auth.login_required
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


@the_app.app.route('/json/items/<offset>/<limit>', methods=['GET'])
@the_app.app.route('/json/items')
@the_app.auth.login_required
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

########################################################################################################################

@the_app.app.route('/users/token')
@the_app.auth.login_required
def get_auth_token():
    global the_app

    token = the_app.auth.generate_token()

    return json.dumps({'result':200, 'token': token.decode('ascii'), 'expiresIn': '600s'})


def find_match(field):

    schema = DatabaseMgr._schema

    for i in schema['fields']:
        if field in schema['fields'][i]['displayName']:
            return i

@the_app.app.route('/items', methods=['PUT'])
@the_app.auth.login_required
def update_item():

    global the_app

    #if 'DB_ADMIN' not in the_app.user['roles']:
    #    return flask.redirect('/401')

    #try:

    form = request.form

    print '[routes::update_item] -> FORM: %s' % json.dumps(form)

    obj = {}

    for field in DatabaseMgr._cols:
        match = find_match(field)
        if match in form:
            obj[field] = form[match]
        elif field in form:
            obj[field] = form[field]
        else:
            obj[field] = ''


    if 'id' in form:
        obj['id'] = form['id']

        result = r.db('inventory').table('items').get(obj['id']).update(obj).run(the_app.conn)
    else:
        obj['id'] = hashlib.md5(str(time.time()) + 'BigBlueSea!').hexdigest()

        result = r.db('inventory').table('items').insert(obj).run(the_app.conn)

    print '[routes::update_item] -> SANITIZED: %s' % json.dumps(obj)

    the_app.cache_expires = 0


    return '[routes::update_item] -> FORM: %s SANI: %s RESULT: %s' % (json.dumps(form), json.dumps(obj), json.dumps(result))


@the_app.app.route('/items', methods=['DELETE'])
@the_app.auth.login_required
def delete_item():
    # try:
    #     current_user = userauth.att(flask.request.form['username'], flask.request.form['password'])
    # except KeyError:
    #     # no user data submitted
    #     flask.flash('Invalid Request')
    #     return 403
    #
    # if current_user is None:
    #     # invalid credentials
    #     flask.flash('Invalid Credentials')
    #     return 401
    #
    # if 'DB_ADMIN' in current_user.roles:
    #     flask.flash('Yay success')
    #     return 'Success'

    return flask.abort(401)


@the_app.app.route('/items/<barcode>', methods=['POST'])
@the_app.auth.login_required
def slice_list_items(barcode):
    view = update_cache()

    for i in view:
        if barcode in str(i['id']):
            return flask.render_template('item_header.html', fields=i)

    return flask.render_template('item_header.html', fields={})


@the_app.app.route('/json/items/<barcode>', methods=['POST'])
@the_app.auth.login_required
def slice_list_json(barcode):
    view = update_cache()

    for i in view:
        if barcode in str(i['id']):
            return json.dumps({'status': 200, 'count': 1, 'items': [i, ]})

    return json.dumps({'status': 404, 'count': 0, 'items': [{}]})


@the_app.app.route('/')
def default():
    return flask.redirect('/items')


if __name__ == "__main__":
    the_app.app.run(debug=True)
