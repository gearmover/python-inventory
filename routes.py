import flask
import pymongo
import os
import time

from flask.ext.stormpath import (
    StormpathError,
    StormpathManager,
    User,
    login_required,
    login_user,
    logout_user,
    user,
)

app = flask.Flask(__name__)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'xU3kyh3mPKtVw1ya8Lywn07WCPT3q8xRoDHB90mtjqAnce0pJS'
app.config['STORMPATH_API_KEY_FILE'] = '/home/chris/.stormpath/apiKey.properties'
app.config['STORMPATH_APPLICATION'] = 'My Application'

stormpath_manager = StormpathManager(app)

client = pymongo.MongoClient('localhost', 27017)
db = client.inventory
items = db.items

cache = []
cache_expires = 0
cache_time = 60                     # 60 second cache time

def update_cache(offset=0, limit=999):
    global cache
    global cache_expires
    global cache_time

    try:
        cur_time = int(time.time())

        if cur_time >= cache_expires:
            all_items = items.find({})
            cache = [i for i in all_items]

            cache_expires = cur_time + cache_time

            flask.flash('Cache Updated', "info")

            index=0
            for item in cache:
                if 'ImageUrl' not in cache[index]:
                    cache[index]['ImageUrl'] = 'http://placehold.it/350x250'
                if 'Status' not in cache[index]:
                    cache[index]['Status'] = 'In'
                if 'IntBarcode' not in cache[index]:
                    cache[index]['IntBarcode'] = 1941491841

                index+=1

        boff = int(offset)
        blim = int(limit)

        offset = boff
        limit = blim

        view = cache[offset:offset+limit]

        return view
    except RuntimeError as e:
        flask.flash('database error. please try again later. ' + e.message, "error")

        return flask.redirect('/')

    return None

@app.route('/assets/<t>/<filename>')
def assets(filename, t):

    try:
        if '..' in filename or filename[0] == '/':
            flask.abort(401)

        if '.js' in filename:
            f = open(os.path.dirname(__file__) + '/static/js/' + filename, "r")
            return flask.send_file(f,'text/javascript')
        elif '.css' in filename:
            f = open(os.path.dirname(__file__) + '/static/css/' + filename, "r")
            return flask.send_file(f,'text/css')
        else:
            flask.abort(401)
    except IOError as e:
        out = open('log.out','a')
        out.write('[!] IOError: %s: "%s", "%s"\n' % (e.strerror, e.filename, e.filename2))
        out.close()

        flask.flash("File not found. Please try your request again later.", "error")

        return flask.redirect('/')

@app.route('/404')
def notfound():
    return 'Oops!  Looks like we\'ve lost a website!'

@app.route('/items/count')
def item_count():
    return str(items.count())

@app.route('/items/p/<offset>/<limit>', methods=['GET'])
@app.route('/items')
def list_items(offset=0, limit=20):

    view = update_cache(offset, limit)

    summary_headers = ["Model", "Manufacturer", "Serial Number", "Location"]

    display = {'Model': 'model',
               'Manufacturer': 'manufacturer',
                'Serial Number': 'serial',
               'Location': 'location'}

    return flask.render_template('list_item.html', items=view, display=display, headers=summary_headers)

@app.route('/items/p/<offset>/<limit>', methods=['POST'])
def slice_list_items(offset=0, limit=20):
    view = update_cache(offset, limit)

    summary_headers = ["Model", "Manufacturer", "Serial Number", "Location"]

    display = {'Model': 'model',
               'Manufacturer': 'manufacturer',
                'Serial Number': 'serial',
               'Location': 'location'}

    return flask.render_template('item_table.html', items=view, display=display, headers=summary_headers)

@app.route('/details/<name>')
def detailed_item(name):

    view = update_cache()

    for i in view:
        if name in str(i['_id']):
            return flask.render_template('item_header.html', fields=i)

    return 'oops :( ' + name

@app.route('/items/p/<offset>/<limit>/json')
@app.route('/items/json')
def list_items_json(offset=0, limit=20):
    view = update_cache(offset, limit)

    summary_headers = ["Model", "Manufacturer", "Serial Number", "Location"]

    display = {'Model': 'model',
               'Manufacturer': 'manufacturer',
                'Serial Number': 'serial',
               'Location': 'location'}

    json = {'headers': summary_headers, 'display': display, 'items': view}

    return str(json)


@app.route('/')
def hello():
    return flask.redirect('/items')


if __name__ == "__main__":
    app.run(debug=True)
