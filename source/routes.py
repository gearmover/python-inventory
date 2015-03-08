import os
import time
import hashlib
import json

import flask.ext.login as flogin
import vendor.qrtools as qrtools
from elaphe.upc import UpcA
import flask
import rethinkdb as r

from userauth import init, attempt


app = flask.Flask(__name__)
app.secret_key = 'G0AI5jihTfHV9s1ALDqUO6BRCIKn4Nt5'

conn = r.connect('127.0.0.1', 28015)

auth_mgr = init(app, '127.0.0.1', 28015)


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
                        f = open('static/images/' + item['id'] + '.png')
                        f.close()
                    except IOError:
                        qr = qrtools.QR(item['id'])

                        qr.encode('static/images/' + item['id'] + '.png')

                    item['QRUrl'] = '/static/images/' + item['id'] + '.png'

                if 'UPCUrl' not in cache[index]:
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

        view = cache[offset:offset + limit]

        return view

    except RuntimeError as e:
        flask.flash('database error. please try again later. ' + e.message, "error")

        return flask.redirect('/')


@app.route('/assets/<t>/<filename>')
@flogin.login_required
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
@flogin.login_required
def item_count():
    view = update_cache()

    return json.dumps({'status': 200, 'count': len(view)})


@app.route('/items')
@flogin.login_required
def def_list_items():
    return flask.redirect('/items/0/99')


@app.route('/items/<offset>/<limit>', methods=['GET'])
@flogin.login_required
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
@flogin.login_required
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


@app.route('/login', methods=['GET'])
def show_login():

    return flask.render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    form = flask.request.form

    print '[routes::login] -> parameters are : ',dict(form)

    args = {}
    attr = (lambda obj,attr: obj[attr] if attr in obj else None)

    args['username'] = unicode(attr(form,'username'))
    args['password'] = attr(form,'password')
    args['rememberme'] = attr(form,'rememberme') == 'true'

    user = attempt(args['username'], args['password'])

    print '[routes::login] -> login attempt : ', str(user)

    if user is not None:
        print 'id: %d, name: %s, active: %d' % (user.id, user.name, user.active)
        flogin.login_user(user)
        return flask.redirect(flask.request.args.get("next") or '/items')

    return flask.render_template('login.html', form=form)

    # user is not None:
        #flogin.login_user(user, form['rememberme'])



@app.route('/items', methods=['PUT'])
@flogin.login_required
def update_item():
    # try:
    #     pass
    # except KeyError:
    #     # no user data submitted
    #     flask.flash('Invalid Request')
    #     return 403
    #
    # if flogin.current_user is None:
    #     # invalid credentials
    #     flask.flash('Invalid Credentials')
    #     return 401
    #
    # if 'DB_ADMIN' in flogin.current_user.roles:
    #     flask.flash('Yay success')
    #     return 'Success'

    return flask.abort(401)


@app.route('/items', methods=['DELETE'])
@flogin.login_required
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
