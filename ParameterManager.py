# using a module is faster than using a class
# Don't believe me? Check this out -> https://pastebin.com/p7rUYqM7

import time 
import sqlite3

latency: float = 2.25 
# highest acceptable latency in seconds

reliability: float = 0.875
# lowest acceptable reliability (successful requests divided by total amount of requests)

optimalRestTime: float = 5
# the optimal time period (seconds) a proxy should "rest" before being reused

def increaseLeniency() -> None:
    """Increase leniency for acceptable latency/reliability"""
    
    global latency 
    global reliability

    latency /= 0.5 
    # increase latency leniency by a factor of 2

    reliability = round(reliability + (reliability**2)*0.5, 4)
    # decrease reliability leniency by slowly descending towards 0

    # as a side note: it is faster to do x*0.5 than x/2
    # Don't believe me? Check this out -> https://pastebin.com/LjqZqc2d


def decreaseLeniency() -> None:
    """Opposite of increaseLeniency()"""
    # docstring short here on purpose to encourage people to read docs for increaseLatency()

    global latency, reliability

    latency *= 0.5
    reliability = 0.5*reliability + 0.5
    # increase reliability by slowly ascending towards 1


def updateLeniency(db) -> bool:
    """Update leniency values and return True if they're good"""
    # increase leniency if we're running low on proxies (ensure we have proxies ready to used)
    # decrease leniency if we have superfluous proxies (ensure we're using the best proxies possible)

    proxyLastUsed = db.execute(
        f"SELECT lastUsed FROM hot WHERE latency<{latency} AND reliability>{reliability} ORDER BY lastUsed;"
    ).fetchall()[0][0]

    usedSecondsAgo = time.time()-proxyLastUsed
    # how many seconds has passed since it was last used

    if 0 < usedSecondsAgo < optimalRestTime:
        # the oldest acceptable proxy was used less than optimalRestTime seconds ago
        increaseLeniency()
        return False
    
    elif optimalRestTime < usedSecondsAgo < optimalRestTime*1.2:
        # the oldest acceptable proxy was used somewhere between optimalRestTime and optimalRestTime*1.2
        return True 
    
    else:
        # the oldest acceptable proxy was used some time after optimalRestTime*1.2
        return False
    

def updateLeniencyLoop() -> None:
    """Start a loop that modifies leniencies depending on supply/demand of proxies"""

    fallThrough = 10
    # how many leniency updates it should "spam" before resting for a little bit

    db = sqlite3.connect("hot.db")
    # we create our own instance here to allow for multiprocessing

    while True: 
        count = 0

        while not updateLeniency(db) and count!=fallThrough:
            # update leniencies until updateLeniency() is happy or fallthrough is reached
            count+=1

        time.sleep(0.5)
        # rest for half a second, no need to spam it
