import socket
import json
import uasyncio as asyncio

from uo import UOBase

class YDevConfig(object):
    """@brief holds the config for the Yview device."""

    def __init__(self):
        """@brief Constructor."""
        self.unit_name     = 'A_UNIT_NAME'
        self.product_id    = 'A_PRODUCT_NAME'
        self.device_type   = 'PICOW'
        self.service_list  = "WEB:80"
        self.group_name    = ""
        self.os            = "micropython"

class YDev(UOBase):
    """brief A Yview device implementation using micro python.
             See https://github.com/pjaos/yview for more information on the YView IoT architecture."""

    UDP_RX_BUFFER_SIZE       = 2048 # The maximum AYT message size.
    UDP_DEV_DISCOVERY_PORT   = 2934 # The UDP port we expect to receive UDP broadcast
                                    # are you there (AYT) messages on.
    AYT_KEY                  = "AYT" # The key in the received JSON message.
    ID_STRING                = "-!#8[dkG^v\'s!dRznE}6}8sP9}QoIR#?O&pg)Qra" # The AYT key in the RX'ed JSON
                                                                           # message must hold this value in
                                                                           # order to send a response to let the
                                                                           # YView gateway know the device details.

    # These are the attributes for the AYT response message
    IP_ADDRESS_KEY           = "IP_ADDRESS"   # The IP address of this device
    OS_KEY                   = "OS"           # The operating system running on this device
    UNIT_NAME_KEY            = "UNIT_NAME"    # The name of this device.
    DEVICE_TYPE_KEY          = "DEVICE_TYPE"  # The type of this device.
    PRODUCT_ID_KEY           = "PRODUCT_ID"   # The product name for this device.
    SERVICE_LIST_KEY         = "SERVICE_LIST" # Details of the services provided by this device (E.G WEB:80)
    GROUP_NAME_KEY           = "GROUP_NAME"   # The group name for the device. Left unset if not restricted access is needed.

    def __init__(self, yDevConfig, localIPAddress, uo):
        """@brief Constructor.
           @param yDevConfig A YDevConfig instance holding the details to be sent in AYT response messages.
           @param localIPAddress The IP address of this device.s
           @param uo A UO instance or None if no user output messages are needed."""
        super().__init__(uo=uo)
        self._yDevConfig = yDevConfig
        self._localIPAddress = localIPAddress
        self._running = False
        self.listen()

    def _send_response(self, sock, remoteAddressPort):
        """@brief sock The UDP socket to send the response on.
           @param remoteAddressPort A tuple containing the address and port to send the response to."""
        jsonDict = {}
        jsonDict[YDev.IP_ADDRESS_KEY]    = self._localIPAddress
        jsonDict[YDev.OS_KEY]            = self._yDevConfig.os
        jsonDict[YDev.UNIT_NAME_KEY]     = self._yDevConfig.unit_name
        jsonDict[YDev.PRODUCT_ID_KEY]    = self._yDevConfig.product_id
        jsonDict[YDev.DEVICE_TYPE_KEY]   = self._yDevConfig.device_type
        jsonDict[YDev.SERVICE_LIST_KEY]  = self._yDevConfig.service_list
        jsonDict[YDev.GROUP_NAME_KEY]    = self._yDevConfig.group_name

        jsonDictStr = json.dumps( jsonDict )
        self._debug("AYT response message: {}".format(jsonDictStr))
        sock.sendto( jsonDictStr.encode(), remoteAddressPort)
        self._debug("Sent above message to {}:{}".format(remoteAddressPort[0],remoteAddressPort[1]))

    async def listen(self):
        """@brief Listen for YVIEW AYT messages and send responses when received."""
        # Open UDP socket to be used for discovering devices
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', YDev.UDP_DEV_DISCOVERY_PORT))
        sock.setblocking(False)
        self._running = True
        while self._running:
            try:
                rxData, addressPort = sock.recvfrom(YDev.UDP_RX_BUFFER_SIZE)
                rxDict = json.loads(rxData)
                self._debug("rxDict = {}".format(rxDict))
                if YDev.AYT_KEY in rxDict:
                    id_str = rxDict[YDev.AYT_KEY]
                    if id_str == YDev.ID_STRING:
                        self._send_response(sock, addressPort)
            except:
                # We get here primarily when no data is present on the socket
                # when recvfrom is called.
                await asyncio.sleep(0.1)
