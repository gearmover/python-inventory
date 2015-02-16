from flask import Flask, render_template, abort, redirect
import pymongo
import os

from flask.ext.triangle import Triangle

app = Flask(__name__)
Triangle(app)

client = pymongo.MongoClient('localhost', 27017)
db = client.inventory
items = db.items


@app.route('/assets/<type>/<path>')
def assets(type, path):
    try:
        logfile = open('log.out', 'w')
        print >> logfile, "%s/templates/%s/%s" % (os.path.dirname(os.path.realpath(__file__)), type, path)
        logfile.close()

        path = path.replace('..', '')
        asset = open(os.path.dirname(os.path.realpath(__file__)) + '/templates/' + "%s/%s" % (str(type), str(path)))

        asset = asset.readlines()

        return '\n'.join(asset)

    except IOError as e:

        abort(404)


@app.route('/404')
def notfound():
    return 'Oops!  Looks like we\'ve lost a website!'

@app.route('/items/p/<offset>/<limit>', methods=['GET'])
@app.route('/items')
def list_items(offset=0, limit=20):
    all_items = items.find({}).limit(int(limit)).skip(int(offset))

    headers = items.find_one({}).keys()

    for f in headers:
        if '_id' in f:
            headers.remove(f)
        elif 'OCO Decal' in f:
            headers.remove(f)
        elif 'alib' in f:
            headers.remove(f)

    itemList = []
    index = 0

    for i in all_items:
        itemList.append({})
        for k in i:
            try:
                field = k.replace('&','').replace('"','')
                itemList[index][field] = i[k].replace('u&#39;','').replace('"','')
            except:
                pass

        index = index+1

    return render_template('list_item.html', items=itemList, headers=headers)

@app.route('/items/p/<offset>/<limit>/json')
@app.route('/items/json')
def list_items_json(offset=0, limit=20):
    all_items = items.find({}).limit(int(limit)).skip(int(offset))

    headers = items.find_one({}).keys()

    for f in headers:
        if '_id' in f:
            headers.remove(f)
        elif 'OCO Decal' in f:
            headers.remove(f)
        elif 'alib' in f:
            headers.remove(f)

    for i in all_items:
        for k in i:
            k = k.replace('&','').replace('"','')
            i[k] = i[k].replace('&','').replace('"','')

    json = {'headers': headers, 'items': [i for i in all_items] }

    return str(json)


@app.route('/')
def hello():
    return redirect('/items')


if __name__ == "__main__":
    app.run(debug=True)