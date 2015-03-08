""" DB.py
This module encapsulates all internal database logic. If we ever needed to change databases,
this is the only file that should need major revision.
"""

__author__ = 'Chris Pergrossi'

import rethinkdb as r
import pymongo as mongo
import time
import csv
import json
import hashlib
import os

conn = r.connect('localhost', 28015)

try:
    r.db('inventory').run(conn)
except:
    try:
        r.db_create('inventory').run(conn)
    except:
        pass

time.sleep(1)

try:
    r.db('inventory').table('items').run(conn)
except:
    try:
        r.db('inventory').table_create('items').run(conn)
    except:
        pass

class DatabaseMgr:

    _schema = {
        'version': '0.0.1',
        'fields': {
            'essieqr': {'displayName': 'ESSIE QR Code', 'summary': True, 'style': 'width:50px;height:50px;',
                        'hide': False, 'description': 'The ESSIE QR image and the plaintext data encoded in it'},  #
            'uf_inventory': {'displayName': 'UF Inventory Number', 'summary': False, 'style': 'width:10%;',
                             'hide': False, 'description': 'University of Florida assigned inventory ID'},  #
            'type': {'displayName': 'Type', 'summary': False, 'style': 'width:10%;', 'hide': False,
                     'description': 'One of four broad categories of ESSIE inventory'},
            'manufacturer': {'displayName': 'Manufacturer', 'summary': False, 'style': 'width:10%;', 'hide': False,
                             'description': 'The items parent company, or a representative brand'},
            'model': {'displayName': 'Model', 'summary': False, 'style': 'width:10%;', 'hide': False,
                      'description': 'The product line or version'},  #
            'description': {'displayName': 'description', 'summary': False, 'style': 'width:10%', 'hide': False,
                            'description': 'A short description of the item from the vendors marketing material'},
            # Approx a paragraph describing the item
            'serial': {'displayName': 'Serial Number', 'summary': False, 'style': 'width:10%', 'hide': False,
                       'description': 'Any unique serial the item might have from the manufacturer'},  #
            'location': {'displayName': 'Location', 'summary': False, 'style': 'width:10%', 'hide': False,
                         'description': 'The main storage facility of this item.'},
            'gps': {'displayName': 'Last GPS', 'summary': True, 'style': 'width:10%;', 'hide': False,
                    'description': 'The GPS coordinates of the previous location this item was scanned'},
            'lastcheck': {'displayName': 'Last Calibration', 'summary': False, 'style': 'width:10%;', 'hide': False,
                          'description': 'The most recent instrument calibration, if applicable'},
            'nextcheck': {'displayName': 'Next Calibration', 'summary': False, 'style': 'width:10%;', 'hide': False,
                          'description': 'The next scheduled instrument calibration, if applicable'},
            'rangeUnits': {'displayName': 'Units of Range', 'summary': True, 'style': 'width:10%;', 'hide': True,
                           'description': 'The units measured throughout the items range'},
            'rangeMin': {'displayName': 'Range Min', 'summary': True, 'style': 'width:10%;', 'hide': False,
                         'description': 'The minimum value expected to not cause permanent damage'},
            'rangeMax': {'displayName': 'Range Max', 'summary': True, 'style': 'width:10%;', 'hide': False,
                         'description': 'The maximum value expected to not cause permanent damage'},
            'measureUnits': {'displayName': 'Units of Measurement', 'summary': True, 'style': 'width:10%;',
                             'hide': True, 'description': 'The units used by the instrument for measurements'},
            'measureMin': {'displayName': 'Min Measurement', 'summary': True, 'style': 'width:10%;', 'hide': False,
                           'description': 'The minimum value expected to provide repeatable, reliable results'},
            'measureMax': {'displayName': 'Max Measurement', 'summary': True, 'style': 'width:10%;', 'hide': False,
                           'description': 'The maximum value expected to provide repeatable, reliable results'},
            'room': {'displayName': 'Room', 'summary': False, 'style': 'width:10%', 'hide': False,
                     'description': 'The room number where this item is typically stored'},
            'manual': {'displayName': 'Manual', 'summary': False, 'style': 'width:10%', 'hide': False,
                       'description': 'A link to a local digital copy of the product manual, if available'},
            'ocodecal': {'displayName': 'OCO Decal No.', 'summary': False, 'style': 'width:10%;', 'hide': False,
                         'description': 'Another external tracking decal (?)'},
            'sourcegrant': {'displayName': 'Source Grant', 'summary': False, 'style': 'width:10%', 'hide': False,
                            'description': 'The grant funding the purchase and maintenance of this item'}
            }
        }

    _DefaultConfig = {
        'rethinkDB': {
            'dbType': 'rethinkdb',
            'host': 'localhost',
            'port': 28015,
            'database': 'inventory',
            'tables': ['control', 'sensing', 'data', 'vision'],
            'username': '',
            'password': '',
            'authkey': '',
            'fatalIfNotFound': True,
            'authenticated': False,
            'adminParty': True
        }
    }

    def __init__(self):
        pass

    def connect(self, host=None, port=None):
        print "[warning]: function call to pure virtual DatabaseMgr::connect method"

    def dump_table(self, output='database.dump'):
        print "[warning]: function call to pure virtual DatabaseMgr::dump_table method"

    def load_csv(self, filename, category=None):

        data = list(csv.DictReader(open(filename, 'rb')))

        if len(data) == 0:
            print "[warning]: CSV file %s empty or not found. no data loaded." % os.path.basename(filename)

        print "Converting %d fields in file with schema v%s" % (len(data), self._schema['version'])

        document = []

        for i in xrange(len(data)):
            data[i]['Category'] = category
            data[i]['id'] = hashlib.md5(str(data[i])).hexdigest()

            document.append(data[i])

           # print '%d: %s' % (i, data[i])

        item_count = len(document)

        return {'row_count': item_count, 'rows': document}


class RDatabaseMgr(DatabaseMgr):
    """ Handles the database start up, shut down and initial addition of items.
    """


    def __init__(self):
        DatabaseMgr.__init__(self)

        self._config = self._DefaultConfig['rethinkDB']

    def connect(self, host=None, port=None):

        try:
            return r.connect(host or self._config['host'], port or self._config['port'])
        except:
            return None

    def dump_table(self, output='database.dump'):

        conn = r.connect('localhost', 28015)

        table = r.db('inventory').table('items').run(conn)

        f = open('dump.bak', 'wt')

        for i in table:
            f.writelines(json.dumps(i) + '\n')

        f.close()

    def load_csv(self, filename, category=None):

        global conn

        records = DatabaseMgr.load_csv(self, filename, category)

        result = r.db('inventory').table('items').insert(records['rows'], conflict='replace').run(conn)

        print result


csv_files = [('/home/chris/src/python-inventory/db/data.csv', 'data'),
             ('/home/chris/src/python-inventory/db/vision.csv', 'vision'),
             ('/home/chris/src/python-inventory/db/control.csv', 'control'),
             ('/home/chris/src/python-inventory/db/sensing.csv', 'sensing')]

if __name__ == "__main__":

    mgr = RDatabaseMgr()

    #mgr.dumpTable()

    index = 0

    for index in xrange(len(csv_files)):
        mgr.load_csv(csv_files[index][0], csv_files[index][1])
        time.sleep(1)
