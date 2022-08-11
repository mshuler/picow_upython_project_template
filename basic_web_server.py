import uasyncio as asyncio
import json
import time
import machine

from wifi import WiFi

class BasicWebServer(object):
    """@brief Responsible for providing a basic web server to serve files from
              flash."""

    WEB_ROOT_FOLDER    = '/webroot/'       # The folder in which all the files served by this server sit.
    GET_REQUEST        = 1                 # An identifier for an HTTP GET.
    POST_REQUEST       = 2                 # An identifier for an HTTP POST.
    GET_REQUEST_STRING = 'GET'             # The String that must be present in an http GET request.
    FAVICON            = '/favicon.ico'    # The favicon file for the server.
    ROOT_FILE          = '/'               # The match for a root folder in an http request where no file is specified.
    INDEX_HTML         = 'index.html'      # The default http file served by the server.
    SETUP_HTML         = 'setup.html'      # The file served by the web server when in WiFi setup mode.
    PRODUCT_HTML       = 'product.html'    # The file served by the web server when not in WiFi setup mode.
    SETUP_WIFI_HTML    = 'setup_wifi.html' # The file served to the user when the WiFi setup is complete.
    WIFI_NETWORKS_STRING = '$WIFINETWORKS' # The text in the setup.html file that is replaced with the WiFi networks found.

    def __init__(self, uo):
        """@brief Constructor"""
        self._uo = uo
        self._setup_wifi_mode = True
        self._wifiNetworkList = []
        self._wifi_networks_string = ""

        #If we have a Wifi config file then the user has already setup the WiFi
        wifiCfgDict = WiFi.GetWifiCfgDict()
        if wifiCfgDict:
            self._setup_wifi_mode = False

    def set_wifi_networks(self, wifi_networks_string):
        """@brief Set the known WiFi networks.
           @param wifi_networks_string The string that details the known WiFi networks as
                  returned by WiFi.Get_Wifi_Networks()"""
        self._wifi_networks_string = wifi_networks_string

    def start(self):
        """@brief start the web server running."""
        asyncio.create_task(asyncio.start_server(self._serve_client, "0.0.0.0", 80))

    def _get_request_element_list(self, request_string):
        """@brief Get a list of request elements.
           @param request_string The string containing the HTTP request.
           @return A list of strings that compose the HTTP request."""
        return request_string.split()

    def is_get_request(self, request_elements):
        """@brief Determine if the request is a get request.
           @param request_elements A list of strings in the HTTP request.
           @return True if the request == HTTP GET."""
        get_request = False
        if len(request_elements) > 0:
            req_type_string = request_elements[0]
            if req_type_string.startswith(BasicWebServer.GET_REQUEST_STRING):
                get_request = True
            return get_request
        else:
            raise Exception('{} is an invalid HTTP request.'.format( str(request_elements) ))

    def get_file(self, request_elements):
        """@brief get the file in the HTTP request.
           @param request_elements A list of strings in the HTTP request.
           @return The file in the HTTP request."""
        if len(request_elements) >= 1:
            return request_elements[1]
        else:
            raise Exception('{} is an invalid HTTP request.'.format( str(request_elements) ))

    def _get_file_contents(self, the_file):
        """@brief Get the contents of a file from flash.
           @param the_file The file to read."""
        fd = open(the_file, 'rb')
        file_contents = fd.read()
        fd.close()
        file_contents = self.process_file_contents(the_file, file_contents)
        return file_contents

    def process_file_contents(self, the_file, file_contents):
        """@brief Process the contents of a file. This method does nothing but return
                  the contents as passed. However it allows BasicWebServer subclasses
                  to change the contents of the file as requried. Typically this involves
                  replacing text in the file to create dynamic web pages.
           @param the_file The absolute path to the file in flash.
           @param file_contents The contents of the file in flash.
           @return The process file contents."""
        try:
            c = file_contents.decode()
            if c.find(BasicWebServer.WIFI_NETWORKS_STRING) >= 0:
                c = c.replace(BasicWebServer.WIFI_NETWORKS_STRING, self._wifi_networks_string)
            return c.encode()
        except:
            return file_contents

    def _serve_file(self, the_file, writer):
        """@brief serve the file to the client from mthe web root folder.
           @param the_file The file to server to the client.
           @param writer The instance to use to send data back to the client."""
        abs_file = '{}{}'.format(BasicWebServer.WEB_ROOT_FOLDER, the_file)
        self._uo.debug("Serve file: {}".format(abs_file))
        try:
            file_contents = self._get_file_contents(abs_file)
            if the_file.endswith('.css'):
                mime_type = "text/css"

            elif the_file.endswith('.js'):
                mime_type = "application/javascript"

            elif the_file.endswith('.ico'):
                mime_type = "image/x-icon"

            elif the_file.endswith('.png'):
                mime_type = "image/png"

            elif the_file.endswith('.jpg'):
                mime_type = "image/jpg"

            else:
                # Default to a text file
                mime_type = "text/html"
            writer.write('HTTP/1.0 200 OK\r\nContent-type: {}\r\n\r\n'.format(mime_type))
            writer.write(file_contents)

        except:
            raise
            writer.write('HTTP/1.0 404 {} file not found.\r\nContent-type: text/html\r\n\r\n'.format(abs_file))

    def _serve_client(self, reader, writer):
        self._uo.debug("Client connected")

        reboot = False

        request_line = await reader.readline()
        # Get a list of the elements in the HTTP request.
        request_elements = self._get_request_element_list(request_line.decode())
        self._uo.debug("request_elements={}".format(request_elements))
        # Read headers
        header_lines= []
        while True:
            header_line = await reader.readline()
            # If the end of the header lines
            if header_line == b"\r\n" or header_line == b"":
                break
            header_line = header_line.decode()
            header_lines.append(header_line)
            self._uo.debug("header_line=<{}>".format(header_line))

        self._uo.debug('http request: {}'.format( str(request_elements) ))

        if request_elements[0] == 'GET':
            if self.is_get_request(request_elements):
                http_file = self.get_file(request_elements)
                # Expand the root folder to the index.html file or if index.html requested
                if http_file == BasicWebServer.ROOT_FILE or http_file == BasicWebServer.INDEX_HTML:
                    # Return the root html file for the current mode.
                    if self._setup_wifi_mode:
                        self._serve_file(BasicWebServer.SETUP_HTML, writer)
                    # If not in WiFi setup mode serve the html file for the product
                    else:
                        self._serve_file(BasicWebServer.PRODUCT_HTML, writer)

                else:
                    self._serve_file(http_file, writer)

        elif request_elements[0] == 'POST':
            readCount=0
            for line in header_lines:
                line=line.strip("\r\n")
                if line.find("Content-Length: ") >= 0:
                    elems = line.split(":")
                    if len(elems) > 1:
                        readCount = int(elems[1].strip())
            self._uo.debug("readCount={}".format( readCount ))
            if readCount > 0:
                data = await reader.read(readCount)
                dataStr = data.decode()
                self._uo.debug("dataStr={}".format( dataStr ))
                elems = dataStr.split("&")
                wifiDict = {}
                if len(elems) == 3:
                    for elem in elems:
                        if elem.startswith('mode='):
                            wifiDict["mode"]=elem.replace('mode=', '')
                        elif elem.startswith('ssid='):
                            wifiDict["ssid"]=elem.replace('ssid=', '')
                        elif elem.startswith('pass='):
                            wifiDict["pass"]=elem.replace('pass=', '')

                    # If we have the WiFi configuration save it to the cfg file.
                    if len( list(wifiDict.keys()) ) == 3 and \
                       "mode" in wifiDict and \
                       "ssid" in wifiDict and \
                       "pass" in wifiDict:
                        fd = open(WiFi.WIFI_CFG_FILE, 'w')
                        fd.write( json.dumps(wifiDict)  )
                        fd.close()
                        reboot = True

            response = 'HTTP/1.1 200 OK\r\n'
            writer.write(response)
            if reboot:
                self._serve_file(BasicWebServer.SETUP_WIFI_HTML, writer)

        await writer.drain()
        await writer.wait_closed()
        self._uo.debug("Client disconnected")

        if reboot:
            self._uo.info("Rebooting to run new WiFi configuration.")
            time.sleep(1)
            machine.reset()
