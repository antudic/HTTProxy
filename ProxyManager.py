import ParameterManager as PM
import ProxyChecker as PC
import py2sqlite
import asyncio
import sqlite3
import time

db = sqlite3.connect("hot.db")


def createSQLiteTable():
    query = py2sqlite.createTable("hot", {
        "address": "TEXT",
        "latency": "INT",
        "lastUsed": "INT",
        "successes": "INT",
        "fails": "INT",
        "reliability": "INT"
    })
    res = db.execute(query)


def reloadProxies() -> int:
    """\
    Empty database and refill it with working proxies from cold
    return total working proxy count"""

    db.execute("DELETE FROM hot;")
    db.commit()

    columns = ("address", "latency", "lastUsed", "successes", "fails", "reliability")
    query = py2sqlite.select("cold", {"working": 1}, columns)

    proxies = PC.db.execute(query).fetchall()

    db.executemany("INSERT INTO hot VALUES(?,?,?,?,?,?)", proxies)
    db.commit()

    return len(proxies)


def loadProxies(verbose=False) -> None:
    if verbose: print("Loading proxies...")
    proxyCount = reloadProxies()
    if verbose: print(f"Successfully loaded {proxyCount} proxies")
    # this is faster than trying to find some sort of intercept between hot and cold (I think)


def getProxy(instance=None, loop=None) -> str:
    db = instance or db

    proxies = db.execute(
        f"SELECT * FROM hot WHERE latency<{PM.latency} AND reliability>{PM.reliability} ORDER BY lastUsed LIMIT 1;"
    ).fetchall()

    try:
        loop.call_soon(updateProxyLastUsed(proxies[0], db))
        return proxies[0]
    
    except IndexError:
        PM.increaseLeniency()
        return getProxy()


async def proxyError(address: str, instance=None):
    """Run logic for if a "working" proxy failed"""

    db = instance or db

    # remove from hot
    db.execute(f"DELETE FROM hot WHERE address={address}")
    db.commit()

    # set working to 0 in cold db
    PC.db.execute(py2sqlite.update("cold", {"working": 0}, {"address": PC.SQLstr(address)}))

    # we intentionally don't update the proxy's "fails" thingy since we don't actually 
    # know if it was user error or proxy error. We leave that to ProxyChecker.


async def proxySuccess(address: str, instance=None):
    # get proxy data from cold db
    db = instance or db

    coldProxy = PC.getProxyFromAddress(address)

    # update successes (and therefore also reliability) for both hot and cold
    values = {"successes": coldProxy[5]+1}
    conditions = {"address": f"'${address}'"}

    db.execute(py2sqlite.update("hot", values, conditions))
    PC.db.execute(py2sqlite.update("cold", values, conditions))

    db.commit()
    PC.db.commit()


async def updateProxyLastUsed(address: str, instance=None):
    # this is done separately from proxySuccess/proxyError because we want to do it ASAP

    db = instance or db

    db.execute(f"UPDATE hot SET lastUsed={time.time()} WHERE address='{address}'")
    db.commit()