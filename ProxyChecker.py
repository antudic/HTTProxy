import sqlite3
import py2sqlite
import re

db = sqlite3.connect("proxies.db")
pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")

class InvalidProxyError(BaseException): pass
class ProxyAlreadyExistsError(BaseException): pass

def createSQLiteTable():
    query = py2sqlite.createTable("proxies", {
        "address": "TEXT", 
        "latency": "INT", 
        "lastUsed": "INT DEFAULT 0", 
        "lock": "INT DEFAULT 0", 
        "working": "INT DEFAULT 0", 
        "retries": "INT DEFAULT 0"
        })
    res = db.execute(query)
    print(res.fetchall())


def addProxy(proxy: str, commit=True):
    if not (pattern.match(proxy)):
        raise InvalidProxyError(f"\"{proxy}\" is not a valid proxy")
    res = db.execute(py2sqlite.select("proxies", {"address": f"'{proxy}'"}))
    
    if len(res.fetchall()):
        raise ProxyAlreadyExistsError(f"Proxy \"{proxy}\" already exists!")
