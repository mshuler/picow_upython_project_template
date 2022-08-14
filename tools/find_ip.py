#!/usr/bin/env python

import socket
import sys
from   time import sleep
from   optparse import OptionParser
from   threading import Thread
import json

UDP_SERVER_PORT = 2934

def find_ydev_devices():
    """Send broadcast UDP messages (are you there/AYT) messages on the local LAN to find YDev devices."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(('', UDP_SERVER_PORT))

    print('Sending AYT messages.')
    areYouThereThread = AreYouThereThread(sock)
    areYouThereThread.start()

    print("Listening on UDP port %d" % (UDP_SERVER_PORT) )
    while True:
        data = sock.recv(10240)
        #Ignore the messaage we sent
        if data != AreYouThereThread.AreYouThereMessage:
            try:
                dataStr = data.decode()
                rx_dict = json.loads(dataStr)
                print("-"*30+ "DEVICE FOUND" + "-"*30)
                for key in rx_dict:
                    print("{: <25}={}".format(key, rx_dict[key]))

            except:
                pass

class AreYouThereThread(Thread):
    """Class to are you there messages to devices"""

    AreYouThereMessage = "{\"AYT\":\"-!#8[dkG^v's!dRznE}6}8sP9}QoIR#?O&pg)Qra\"}"
    PERIODICITY_SECONDS = 2.0
    MULTICAST_ADDRESS   = "255.255.255.255"

    def __init__(self, sock):
        Thread.__init__(self)
        self._running = None
        self.setDaemon(True)

        self._sock = sock

    def run(self):
        self._running = True
        while self._running:
            self._sock.sendto(AreYouThereThread.AreYouThereMessage, (AreYouThereThread.MULTICAST_ADDRESS, UDP_SERVER_PORT))
            sleep(AreYouThereThread.PERIODICITY_SECONDS)

if __name__ == "__main__":
    opts=OptionParser(usage='Find YDev device connected to the local network.')
    opts.add_option("--debug",      help="Enable debugging", action="store_true", default=False)

    try:
        (options, args) = opts.parse_args()

        find_ydev_devices()

    #If the program throws a system exit exception
    except SystemExit:
      pass
    #Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
      pass
    except:
     if options.debug:
       raise

     else:
       print(str(sys.exc_value))
