import pymongo

def init_db():

    try:
        client = pymongo.MongoClient('localhost',27017)

        db = client.inventory

        people = db.people

        people.insert([{'name': 'chris', 'age': 27, 'height': '6foot1'},
            {'name': 'heather', 'age': 25, 'height': '5foot10'}])

        for p in people.find({}):
            print p

    except:
        print "error!"


if __name__ == '__main__':
    init_db()