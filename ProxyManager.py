import ProxyChecker as PC
import py2sqlite
import requests
import asyncio
import sqlite3
import time

db = sqlite3.connect("hot.db")


class ProxyValues:
    # class for managing what proxy values to check for

    latency: float = 9.0 # seconds
    reliability: float = 0.0 # successful requests divided by total amount of requests

    @staticmethod
    def outOfProxies():
        latency /= 0.5 # increase latency leniancy by a factor of 2
        reliability *= 0.5 # decrease reliability leniancy by a factor of 2
        # this is the fastest way of doing these operations
        # don't believe me? -> https://pastebin.com/LjqZqc2d
        




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
    proxies = db.execute(
        f"SELECT * FROM hot WHERE latency<{ProxyValues.latency} AND reliability>{ProxyValues.reliability} ORDER BY lastUsed LIMIT 1;"
    ).fetchall()

    try:
        return proxies[0]
    except Exception:



def sendRequest(address, data=None):
    query = "SELECT * FROM hot "