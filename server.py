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
    print(address)

    try: 
        r = requests.get(msg, proxies={"http": address})
        client.send(r.text.encode())
        loop.call_soon(ProxyManager.proxySuccess(address, db))

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.InvalidURL,
        requests.exceptions.ProxyError
        ) as e:
        # any of these (could) indicate proxy error
        try: 
            ProxyManager.PC.checkProxy()
            # ^ if it didn't throw an exception, it was user error
            client.sendall(str(e).encode())

        except Exception:
            # if it did throw an error, it was proxy error and we try again
            loop.call_soon(ProxyManager.proxyError(address, db)) # first we make sure to remove faulty proxy
            interpreter(msg, client, db, loop) # then we call the function again

    except (
        requests.exceptions.MissingSchema,
        TypeError
        ) as e:
        # this indicates user error
        client.sendall(str(e).encode())


ProxyManager.loadProxies(verbose=True)
print("Starting server...")
sock = bind("127.0.0.1", 6969)

start_blocking = False

def main():
    if start_blocking:
        accepter(sock)
    else:
        threading.Thread(target=accepter, args=(sock,)).start()

if __name__ == "__main__":
    main()

print("Done.")