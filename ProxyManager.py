import ProxyChecker as PC
import requests
import time

db = sqlite3.connect("hot.db")


class 


def createSQLiteTable():
    query = py2sqlite.createTable("hot", {
        "address": "TEXT",
        "latency": "INT",
        "lastUsed": "INT",
    })
    res = db.execute(query) 


# This function is intended to be quite fast. If anything catches your 
# attention about the design of it, here are some things that may seem 
# questionable but that are implemented for the sake of improved 
# performance.
# 
# Have the query be defined as a parameter: https://pastebin.com/3NP4wcW9
def getProxy():
    query = "SELECT * FROM "


def sendRequest(address, data=None):
    query = "SELECT * FROM hot "