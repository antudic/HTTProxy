import sqlite3
import py2sqlite
import requests
import time
import re

db = sqlite3.connect("cold.db")
pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")

class InvalidProxyError(BaseException): pass
class InvalidProxyDataError(BaseException): pass
class TransparentProxyError(BaseException): pass
class ProxyAlreadyExistsError(BaseException): pass


def SQLstr(value) -> str:
    """Convert from input "value" to "'value'" """
    return "'" + value + "'"
    # doing this is faster than using an f-string
    # Don't believe me? Check this out -> https://pastebin.com/yM62Hprv


def createSQLiteTable() -> sqlite3.Cursor:
    """Initialize the "cold" table"""
    query = py2sqlite.createTable("cold", {
        "address": "TEXT",
        "latency": "INT",
        "lastUsed": "INT DEFAULT 0",
        "working": "INT DEFAULT 0",
        "retries": "INT DEFAULT 0",
        "successes": "INT DEFAULT 0",
        "fails": "INT DEFAULT 0",
        "reliability": "INT DEFAULT 1"
    })
    return db.execute(query)


def createReliabilityTrigger() -> None:
    """Create a trigger to automatically update the reliability parameter"""

    query = (
        """\
        CREATE TRIGGER update_reliability
        AFTER UPDATE OF successes, fails ON cold
        FOR EACH ROW
        BEGIN
            UPDATE cold
            SET reliability = NEW.successes / (NEW.successes + NEW.fails)
            WHERE address = NEW.address;
        END;
        """
    ) # credit: ChatGPT

    db.execute(query)
    db.commit()


def checkProxy(proxy: str) -> float:
    """Check a proxy and return its latency"""

    # send a request to reliable website
    try: 
        startTime = time.time()
        r = requests.get("https://catfact.ninja/fact", proxies={"http": proxy})
        latency = time.time() - startTime

    # reject these errors, idk what to do about them
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.MissingSchema,
        requests.exceptions.InvalidURL,
        requests.exceptions.ProxyError
        ) as e:
        raise InvalidProxyError(e)
    
    # make sure it actually got correct data
    if (
        ( r.text.find('"', 9)-9 == int(r.text[-(r.text[:-6:-1].find(":")):-1]) )
        or # ^ this catches 99% of all cases and is really fast
        ( len((json := requests.models.complexjson.loads(r.text))["fact"]) == json["length"] )
         # ^ this catches 100% but is ~3.8 times slower
        ): pass

    else: # we got invalid data
        raise InvalidProxyDataError(f"Proxy \"{proxy}\" gave faulty data: {r.text}")
        

    # make sure that the proxy isn't a transparent proxy, we don't like those
    if "Via" in r.headers:
        raise TransparentProxyError(f"Proxy \"{proxy}\" is a transparent proxy")

    return latency


def addProxy(proxy: str) -> None:
    """Add a proxy to the database"""

    # make sure the proxy is valid
    if not (pattern.match(proxy)):
        raise InvalidProxyError(f"\"{proxy}\" is not a valid proxy")

    # make sure the proxy does not already exist
    res = db.execute(py2sqlite.select("cold", {"address": f"'{proxy}'"}))

    if len(res.fetchall()):
        raise ProxyAlreadyExistsError(f"Proxy \"{proxy}\" already exists!")

    # make sure the proxy is actually up and running
    latency = checkProxy(proxy)

    # everything looks good, we add it to the thing
    query = py2sqlite.insert("cold", {"address": proxy, "latency": latency, "working": 1})
    db.execute(query)
    db.commit()


def recheckProxy(dbProxy, instance=None) -> None:
    """Check if a proxy works and update its values"""

    # set db to be instance or global db
    db = instance or db

    # check proxy
    try:
        latency = checkProxy(dbProxy)
        # ^ if we get past this, it works.
        
        lastUsed = int(time.time())
        query = py2sqlite.update(
            "cold", 
            {"latency": latency, "lastUsed": lastUsed, "working": 1, "retries": 0, "successes": dbProxy[5]+1}, 
            {"address": SQLstr(dbProxy[0])}
            )
        db.execute(query)
        # we intentionally don't call db.commit here
        print("Recommissioned proxy", dbProxy[0])

    except Exception:
        # the proxy does not work
        query = py2sqlite.update(
            "cold", 
            {"retries": dbProxy[4]+1, "fails": dbProxy[5]+1}, 
            {"address": SQLstr(dbProxy[0])}
            )
            
        db.execute(query)
        # we intentionally don't call db.commit here


def checkProxyLoop() -> None:
    # create new connection in case it runs threaded
    db = sqlite3.connect("cold.db")

    # define default queries
    now = int(time.time())

    retryQueries = [
        f"SELECT * FROM cold WHERE working=0 AND retries=0 AND {now}-lastUsed >= 30",
        # ^ for 0 retries, retry after 30 seconds
        f"SELECT * FROM cold WHERE working=0 AND retries=1 AND {now}-lastUsed >= 120",
        # ^ for 1 retry, retry after 2 minutes
        f"SELECT * FROM cold WHERE working=0 AND retries=2 AND {now}-lastUsed >= 300",
        # ^ for 2 retries, retry after 5 minutes
        f"SELECT * FROM cold WHERE working=0 AND retries=3 AND {now}-lastUsed >= 600",
        # ^ for 3 retries, retry after 10 minutes
        f"SELECT * FROM cold WHERE working=0 AND retries=4 AND {now}-lastUsed >= 1800",
        # ^ for 4 retries, retry after 30 minutes 
        f"SELECT * FROM cold WHERE working=0 AND retries=5 AND {now}-lastUsed >= 3600",
        # ^ for 5 retries, retry after 1 hour
        f"SELECT * FROM cold WHERE working=0 AND retries=6 AND {now}-lastUsed >= 18000",
        # ^ for 6 retries, retry after 5 hours
        f"SELECT * FROM cold WHERE working=0 AND retries=7 AND {now}-lastUsed >= 86400",
        # ^ for 7 retries, retry after 24 hours
        f"SELECT * FROM cold WHERE working=0 AND retries=8 AND {now}-lastUsed >= 259200",
        # ^ for 8 retries, retry after 3 days
        f"SELECT * FROM cold WHERE working=0 AND retries>8 AND {now}-lastUsed >= (retries-8)*604800",
        # ^ for more than 8 retries, retry once a week
    ]

    # run the loop

    while True:
        for query in retryQueries:

            # get proxies to retry
            proxies = db.execute(query).fetchall()

            for proxy in proxies:
                recheckProxy(proxy, db)

        db.commit()
        time.sleep(0.5)
        # half a second should be fine.