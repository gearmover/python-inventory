import pymongo

client = pymongo.MongoClient('localhost',27017)

db = client.inventory

items = db.items

def interpretLine(line, headers):

    line = line.replace('\n','')
    line = line.replace('.','')
    line = line.replace('\r','')

    fields = line.split(",")
    index = 0
    output = {}

    print "[D] Output Values"

    for col in headers:
        output[col] = fields[index]

        print "%s : %s" % (col,output[col])
        index += 1

    return output

def pretty_print(obj):

    output = ''
    output += "{\n"

    for key in obj.keys():
        obj[key].replace("\n","")
        key.replace("\n","")
        output += "\"" + key + "\""
        output += ': '
        output += "\"" + obj[key] + "\""
        output += ',\n';

    output += "},\n"

    return output


def main():

    db = open("db.csv", "rt")
    out = open('out.db', 'wt')

    line = db.readline()

    line = line.replace('\n','')
    line = line.replace('\r','')
    line = line.replace('.','')

    headers = line.split(",")

    for line in db:
        obj = interpretLine(line, headers)

        items.insert(obj)

    out.close()
    db.close()

    all = items.find({})
    for i in all:
        print i

if __name__ == "__main__":
    main()