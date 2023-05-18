import ProxyChecker as PC
import py2sqlite
import requests
import asyncio
import sqlite3
import time

db = sqlite3.connect("hot.db")


def createSQLiteTable():
    query = py2sqlite.createTable("hot", {
        "address": "TEXT",
        "latency": "INT",
        "lastUsed": "INT",
    })
    res = db.execute(query) 


def getProxy():
    proxies = db.execute(
        f"SELECT * FROM hot WHERE latency<{ProxyValues.latency} AND reliability>{ProxyValues.reliability} ORDER BY lastUsed LIMIT 1;"
    ).fetchall()

    try:
        return proxies[0]
    except IndexError:




def sendRequest(address, data=None):
    query = "SELECT * FROM hot "