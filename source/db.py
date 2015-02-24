""" DB.py
This module encapsulates all internal database logic. If we ever needed to change databases,
this is the only file that should need major revision.
"""

__author__ = 'Chris Pergrossi'

import rethinkdb as r
import pymongo
import uuid
import json



class DatabaseMgr:
    """ Handles the database start up, shut down and initial addition of items.
    """

    _schema = {
        'version': '0.0.1',
        'fields': {
            'essieqr': {'displayName': 'ESSIE QR Code', 'summary': True, 'style': 'width:50px;height:50px;', 'hide': False, 'description': 'The ESSIE QR image and the plaintext data encoded in it'},           #
            'uf_inventory': {'displayName': 'UF Inventory Number', 'summary': False, 'style': 'width:10%;', 'hide': False, 'description': 'University of Florida assigned inventory ID'},            #
            'type': {'displayName':'Type', 'summary': False, 'style': 'width:10%;', 'hide': False, 'description': 'One of four broad categories of ESSIE inventory'},
            'manufacturer': {'displayName':'Manufacturer', 'summary': False, 'style': 'width:10%;', 'hide': False, 'description': 'The items parent company, or a representative brand'},
            'model': {'displayName': 'Model', 'summary': False, 'style': 'width:10%;', 'hide': False, 'description': 'The product line or version'},                                 #
            'description': {'displayName': 'description', 'summary': False, 'style': 'width:10%', 'hide': False, 'description': 'A short description of the item from the vendors marketing material'},                      # Approx a paragraph describing the item
            'serial': {'displayName': 'Serial Number', 'summary': False, 'style': 'width:10%', 'hide': False, 'description': 'Any unique serial the item might have from the manufacturer'},                         #
            'location': {'displayName': 'Location', 'summary': False, 'style': 'width:10%', 'hide': False, 'description': 'The main storage facility of this item.'},
            'gps': {'displayName': 'Last GPS', 'summary': True, 'style': 'width:10%;', 'hide': False, 'description': 'The GPS coordinates of the previous location this item was scanned'},
            'lastcheck': {'displayName': 'Last Calibration', 'summary': False, 'style': 'width:10%;', 'hide': False, 'description': 'The most recent instrument calibration, if applicable'},
            'nextcheck': {'displayName': 'Next Calibration', 'summary': False, 'style': 'width:10%;', 'hide': False, 'description': 'The next scheduled instrument calibration, if applicable'},
            'rangeUnits': {'displayName': 'Units of Range', 'summary': True, 'style': 'width:10%;', 'hide': True, 'description': 'The units measured throughout the items range'},
            'rangeMin': {'displayName': 'Range Min', 'summary': True, 'style': 'width:10%;', 'hide': False, 'description': 'The minimum value expected to not cause permanent damage'},
            'rangeMax': {'displayName': 'Range Max', 'summary': True, 'style': 'width:10%;', 'hide': False, 'description': 'The maximum value expected to not cause permanent damage'},
            'measureUnits': {'displayName': 'Units of Measurement', 'summary': True, 'style': 'width:10%;', 'hide': True, 'description': 'The units used by the instrument for measurements'},
            'measureMin': {'displayName': 'Min Measurement', 'summary': True, 'style': 'width:10%;', 'hide': False, 'description': 'The minimum value expected to provide repeatable, reliable results'},
            'measureMax': {'displayName': 'Max Measurement', 'summary': True, 'style': 'width:10%;', 'hide': False, 'description': 'The maximum value expected to provide repeatable, reliable results'},
            'room': {'displayName':'Room', 'summary': False, 'style': 'width:10%', 'hide': False, 'description': 'The room number where this item is typically stored'},
            'manual': {'displayName':'Manual', 'summary': False, 'style': 'width:10%', 'hide': False, 'description': 'A link to a local digital copy of the product manual, if available'},
            'ocodecal': {'displayName':'OCO Decal No.', 'summary': False, 'style': 'width:10%;', 'hide': False, 'description': 'Another external tracking decal (?)'},
            'sourcegrant': {'displayName': 'Source Grant', 'summary': False, 'style': 'width:10%', 'hide': False, 'description': 'The grant funding the purchase and maintenance of this item'}
        }
    }

    _DefaultConfig = {
        'rethinkDB': {
            'dbType': 'rethinkdb',
            'host': 'localhost',
            'port': 28015,
            'database': 'inventory',
            'tables': ['control','sensing','data','vision'],
            'username': '',
            'password': '',
            'authkey': '',
            'fatalIfNotFound': True,
            'authenticated': False,
            'adminParty': True
        },
        'mongoDB': {
            'dbType': 'mongodb',
            'host': 'localhost',
            'port': 27017,
            'database': 'inventory',
            'tables': ['control','sensing','data','vision'],
            'username': '',
            'password': '',
            'authkey': '',
            'fatalIfNotFound': True,
            'authenticated': False,
            'adminParty': True
        }
    }

    def __init__(self):
        self._config = self._DefaultConfig['rethinkDB']

    def setActiveDB(self,which):
        which = which.lower()

        if 'rethinkdb' in which:
            self._config = self._DefaultConfig['rethinkDB']

        elif 'mongodb' in which:

            raise NotImplementedError("MongoDB is not supported yet.")

    def connect(self,host = None,port = None):

        try:
            if 'rethinkdb' in self._config['dbType']:
                return r.connect(host or self._config['host'], port or self._config['port'])
        except:
            return None

        raise RuntimeError("[%s:%s]: Attempting to connect with invalid DB configuration." % (__file__,__name__))

    def prepCSV(self, filename, category = None):

        print "Converting '%s' to JSON for use with rethinkdb import" % filename

        try:
            f = open(filename, "rt")

            filename += 'new'

            data = f.readlines()

            print "Read %d records." % (len(data)-1)

            f.close()
        except IOError as e:
            print("[%s:%s]: IOError - %s" % (__file__, __name__, e.message))
            raise e


        needsConverting = data[0].split(',')

        print "Converting %d fields in file of %d fields in _schema (v%s)" % (len(needsConverting), len(self._schema['fields']), self._schema['version'])
        print "Empty fields will be filled with a single '_'"

        document = []

        for line in data[1:]:
            try:
                fields = line.split(',')
                headers = [m for m,n in self._schema['fields'] if n.displayName in needsConverting]

                obj = {}

                for i,header in enumerate(headers):
                    if i > len(fields):
                        break
                    obj[header] = fields[i]

                for header in self._schema['fields']:
                    if header not in obj:
                        obj[header] = '_'

                # here we prepend a category if passed one, causing all items in the same category to
                # automatically be sorted next to each other - and after adding a slice of randomness, serve
                # it up as the object ID

                obj['id'] = str(category or 'essie')[:5] + hex(uuid.uuid4().bytes)[:12]

                document.append(obj)

            except:
                pass

        itemCount = len(document)

        try:
            newname = ''.join(filename.split('.')[:-1])

            f = open(filename+'.hdr', "wt")
            print "Printing %d header descriptors to %s.hdr" % (len(self._schema['fields']), filename)

            f.write(json.dumps(self._schema['fields']))
            f.close()
        except IOError as e:
            print "[%s:%s]: IOError - %s" % (__file__,__name__,e.message)

        try:
            f = open(filename, "wt")
            print "Printing %d records to '%s'" % (itemCount, newname)
            f.write(json.dumps(document))


            f.close()
        except IOError as e:
            print "[%s:%s]: IOError - %s" % (__file__,__name__,e.message)

        print "[I]: CSV Conversion Complete"

if __name__ == "__main__":
    mgr = DatabaseMgr()

    mgr.setActiveDB('rethinkdb')
    mgr.prepCSV('/home/chris/src/python/backend/data.csv','data')