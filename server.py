import socket
import time
import sqlite3
import asyncio 
import requests
import threading
import ProxyManager


def bind(ip: str, port: int, retry=True) -> socket.socket:
    """Bind to ip:addr and retry if fail"""

    counter = 0
    
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((ip, port))
            sock.listen(5) 
            # ^ https://docs.python.org/3/library/socket.html#socket.socket.listen

            print("Connected.\n") # redundant new line for thread safer printing
            return sock

        except OSError as error:
            if retry:

                if not counter%5:
                    print(f"Address already in use... {int(counter/5)}")
                    # only print every 5 connection attempts
                
                time.sleep(1)
                counter+= 1
                
            else:
                raise error # propagate 


def accepter(sock: socket.socket):
    # loop to continuously accept new incoming connections

    while True:
        try:
            client, address = sock.accept()
            threading.Thread(target=recver, args=(client,)).start()
            
        except OSError: 
            # from previous testing, "self.socket.accept()" throws an OSError when the socket is shut down, so we want to exit quietly.
            pass


def recver(sock: socket.socket):
    db = sqlite3.connect("hot.db")
    # ^ this is unfortunately needed but should realistically be not that bad

    loop = asyncio.new_event_loop()

    while True:
        try:
            msg = sock.recv(8192).decode()
        except Exception:
            return 

        interpreter(msg, sock, db, loop)
    

def interpreter(msg, client: socket.socket, db, loop: asyncio.AbstractEventLoop) -> None:

    address = ProxyManager.getProxy(db, loop)

    try: 
        r = requests.get(msg, proxies={"http": address})
        print("1")
        client.sendall(r.text.encode())
        loop.call_soon(ProxyManager.proxySuccess(address, db))
        print("6")

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.InvalidURL,
        requests.exceptions.ProxyError
        ) as e:
        print("2")
        # any of these (could) indicate proxy error
        loop.call_soon(ProxyManager.proxyError(address, db))
        client.sendall(str(e).encode())
        print("5")

    except requests.exceptions.MissingSchema:
        print("3")
        # this indicates user error
        client.sendall(str(e).encode())
        print("4")


ProxyManager.loadProxies(verbose=True)
print("Starting server...")
sock = bind("127.0.0.1", 6969)
accepter(sock)
print("Done.")