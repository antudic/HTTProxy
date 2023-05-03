import sqlite3
import py2sqlite
import requests
import re

db = sqlite3.connect("cold.db")
pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")

class InvalidProxyError(BaseException): pass
class InvalidProxyDataError(BaseException): pass
class TransparentProxyError(BaseException): pass
class ProxyAlreadyExistsError(BaseException): pass


def createSQLiteTable():
    query = py2sqlite.createTable("cold", {
        "address": "TEXT",
        "latency": "INT",
        "lastUsed": "INT DEFAULT 0",
        "working": "INT DEFAULT 0",
        "retries": "INT DEFAULT 0"
    })
    res = db.execute(query)
    print(res.fetchall())


def checkProxy(proxy: str):
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
        ( not r.text.find('"', 9)-9 == int(r.text[-(r.text[:-6:-1].find(":")):-1]) )
        and # ^ this catches 99% of all cases and is really fast
        ( len((json := requests.models.complexjson.loads(r.text))["fact"]) == json["length"] )
         # ^ this catches 100% but is ~3.8 times slower
        ):
        raise InvalidProxyDataError(f"Proxy \"{proxy}\" gave faulty data: {r.text}")

    # make sure that the proxy isn't a transparent proxy, we don't like those
    if "Via" in r.headers:
        raise TransparentProxyError(f"Proxy \"{proxy}\" is a transparent proxy")


def addProxy(proxy: str):
    # make sure the proxy is valid
    if not (pattern.match(proxy)):
        raise InvalidProxyError(f"\"{proxy}\" is not a valid proxy")

    # make sure the proxy does not already exist
    res = db.execute(py2sqlite.select("proxies", {"address": f"'{proxy}'"}))

    if len(res.fetchall()):
        raise ProxyAlreadyExistsError(f"Proxy \"{proxy}\" already exists!")

    # make sure the proxy is actually up and running
    checkProxy(proxy)

    # everything looks good, we add it to the thing
    query = py2sqlite.insert("cold", {"address": proxy, "latency": latency})


def checkProxyLoop():
    # create new connection in case it runs threaded
    db = sqlite3.connect("cold.db")

    while True: 
        query = "SELECT * FROM cold WHERE "