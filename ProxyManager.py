import ParameterManager as PM
import ProxyChecker as PC
import py2sqlite
import requests
import asyncio
import sqlite3
import time

from typing import Callable

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
        f"SELECT * FROM hot WHERE latency<{PM.latency} AND reliability>{PM.reliability} ORDER BY lastUsed LIMIT 1;"
    ).fetchall()

    try:
        return proxies[0]
    except IndexError:
        PM.increaseLeniency()
        return getProxy()
    

def executeRequest(method: str, URL: str, data=None) -> requests.models.Response:
    return requests.request(method, URL, data=data)



def sendRequest(address, data=None):
    query = "SELECT * FROM hot "