import py2sqlite
import requests
import sqlite3
import asyncio
import time
import re

db = sqlite3.connect("cold.db")
pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")

class InvalidProxyError(Exception): pass
class InvalidProxyDataError(Exception): pass
class TransparentProxyError(Exception): pass
class ProxyAlreadyExistsError(Exception): pass


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


def getProxyFromAddress(address: str):
    return db.execute(f"SELECT * FROM cold WHERE address={SQLstr(address)}").fetchone()


async def _catFactRequests(proxy):
    """Only intended for internal use."""
    # sends a catfact request using the requests library
    # asyncio does not like this particularly much, but we do like it
    return requests.get("http://catfact.ninja/fact", proxies={"http": proxy})


async def _catFactHTTPX(proxy):
    """Only intended for internal use."""
    # sends a catfact request using the HTTPX library
    # this is supposedly better but it's not built-in
    async with httpx.AsyncClient(proxies={"http://": f"http://{proxy}"}) as client: 
        return await client.get('http://catfact.ninja/fact', follow_redirects=True)


async def checkProxy(proxy: str, requestMethod=_catFactRequests) -> float:
    """Check a proxy and return its latency"""

    # send a request to reliable website
    try: 
        startTime = time.time()
        r = await requestMethod(proxy)
        latency = time.time() - startTime

    # reject these errors, idk what to do about them
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.MissingSchema,
        requests.exceptions.InvalidURL,
        requests.exceptions.ProxyError,
        TypeError
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


async def addProxy(proxy: str, requestMethod=_catFactRequests) -> None:
    """Add a proxy to the database"""

    # make sure the proxy is valid
    if not (pattern.match(proxy)):
        raise InvalidProxyError(f"\"{proxy}\" is not a valid proxy")

    # make sure the proxy does not already exist
    res = db.execute(py2sqlite.select("cold", {"address": f"'{proxy}'"}))

    if len(res.fetchall()):
        raise ProxyAlreadyExistsError(f"Proxy \"{proxy}\" already exists!")

    # make sure the proxy is actually up and running
    latency = await checkProxy(proxy, requestMethod)

    # everything looks good, we add it to the thing
    query = py2sqlite.insert("cold", {"address": proxy, "latency": latency, "working": 1})
    db.execute(query)
    db.commit()


def batch(_list, size):
    """Divides list into batches of given size
    
    Ex: batch([1,2,3,4,5,6,7,8], 3) => [ [1,2,3], [4,5,6], [7,8] ]"""
    return [_list[x*size:x*size+size] for x in range(int(len(_list)/size)+1)]


async def addBulk(proxies: str, batchCount=100):
    """Tries its best to extract all proxies from a given string
    
    Finds any proxy as long as it follows the following pattern:
    [some ip address, ex 0.0.0.0 or 255.255.255.255] [anything (including nothing)] [a 2 to 5 digit number]
    Where [some ip address] can be anything from 0.0.0.0 to 255.255.255.255
    [anything] can be 1 or more of any character (so a ":", " " or "  " would all work)
    [a 2 to 5 digit number] a 2 to 5 digit number, this includes 00 and 99999

    demo: https://pastebin.com/yBYrbVyS

    `batchCount` indicates how many proxies to add in one "batch". This was added after
    an attempt of adding >7000 proxies at once ended up taking over 5GB of memory
    """

    try:
        global httpx
        import httpx
    except ModuleNotFoundError:
        print("You need httpx library to bulk add proxies! do `pip install httpx`")
        return
    
    global batch

    proxyPattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}[\s\S]?\d{2,5}")
    anythingPattern = re.compile(r"[^.\d]")

    rawProxies = re.findall(proxyPattern, proxies)
    validProxies = [":".join(re.split(anythingPattern, rawProxy)) for rawProxy in rawProxies]

    async def addProxyWrapper(proxy):
        try:
            await addProxy(proxy, _catFactRequests)
            print(f"Added {proxy}")
            return 1
        
        except Exception as e:
            return 0

    successes = 0
    batches = batch(validProxies, batchCount)
    print(f"Attempting to add {len(validProxies)} proxies in batches of {batchCount}")
    startTime = time.time()

    for batchNum, batch in enumerate(batches):
        coros = [asyncio.create_task(addProxyWrapper(proxy)) for proxy in batch]
        results = await asyncio.gather(*coros)

        successes+= sum(results)
        print(f"Batch {batchNum+1}/{len(batches)} done.")

    print(f"Added {successes} new proxies from list of {len(validProxies)} proxies in {time.time()-startTime} seconds")


def addBulkFromFile(filename: str, batchCount=100):
    """Load text from file and run addBulk() on the text"""
    
    with open(filename, "r", encoding="UTF-8") as file:
        asyncio.run(addBulk(file.read(), batchCount))


async def recheckProxy(dbProxy: str, instance=None) -> bool:
    """Check if a proxy works and update its values"""

    # set db to be instance or global db
    db = instance or db

    # check proxy
    try:
        latency = await checkProxy(dbProxy[0])
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
            {"retries": dbProxy[4]+1, "fails": dbProxy[6]+1}, 
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
                asyncio.run(recheckProxy(proxy, db))

        db.commit()
        time.sleep(0.5)
        # half a second should be fine.