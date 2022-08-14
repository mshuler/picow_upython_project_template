import json
import uasyncio as asyncio
import machine

from uo import UOBase

class RestServer(UOBase):
    """@brief Responsible for providing a REST interface to allow clients to
              collect data but could be extended to send arguments to the Pico W."""

    TCP_PORT = 8080                                          # The TCP port to present the REST server on.
    MAX_CPU_FREQ_HZ = 240000000                              # The MAX CPU freq in Hz.

    SERVER_EXCEPTION_LOG_FILE = '/rest_server_exception.txt' # Rest server exceptions are stored in for debug purposes.
    ERROR_KEY = "ERROR"                                      # The key in the JSON response if an error occurs.
    CMD_KEY = "CMD"                                          # The command from the http request.
    GET_REQ = "GET_REQ"                                      # The full http get request line.

    # HTTP GET request commands
    ADC_REQ = "/adc"                                         # The prefix in the HTTP request when reading the ADC.
    TEMPERATURE_REQ = "/temperature"                         # The text in the HTTP request when reading the picow temperature.
    SETUP_GPIO_REQ = "/set_gpio"                           # The text in the HTTP request when seting a GPIO.
    CPU_FREQ = "/cpu_freq"                                   # The text in the http get request to set/get the CPU frequency.
    SETUP_UART = "/setup_uart"                               # The text in the HTTP request when setting up a UART.
    UART_TX = "/uart_tx"                                     # The text in the HTTP request when sending data out of a uart port.
    UART_RX = "/uart_rx"                                     # The text in the HTTP request when reading data from a uart port.

    def __init__(self, uo=None):
        """@brief Constructor
           @param uo A UO instance for presenting data to the user. If Left as None
                     no data is sent to the user."""
        super().__init__(uo=uo)
        self._gpioDict = {}
        self._uartDict = {}

    def startServer(self):
        asyncio.create_task(asyncio.start_server(self._serve_client, "0.0.0.0", RestServer.TCP_PORT))

    def _ok_json_response(self, writer):
        """@brief Send an HTTP OK response and header to define JSON data following.
           @param writer The writer object used to send data."""
        writer.write('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')

    def _get_return_dict(self, cmd, msg, error):
        """@brief Get a JSON error response.
           @param The http request command.
           @param msg The message to include in the response.
           @param error If True report and error.
           @return The dict containing the error response"""
        return { RestServer.ERROR_KEY: error,
                 cmd: msg}

    async def _serve_client(self, reader, writer):
        """@brief Called to serve a request for data."""
        self._info("Client connected")
        request_line = await reader.readline()
        self._info("Request: %s" % request_line)
        # We are not interested in HTTP request headers, skip them
        while await reader.readline() != b"\r\n":
            pass

        req = request_line.decode()

        # We don't respond with an HTTP 404 error but return a JSON message
        # in the event of an error.
        response_dict = self._get_return_dict("unknown_cmd", "{} is a malformed request.".format(req), True)
        response = json.dumps(response_dict)

        args_dict  = self._get_args_dict(req)
        self._debug("args_dict={}".format(args_dict))
        if RestServer.CMD_KEY in args_dict:
            cmd = args_dict[RestServer.CMD_KEY]
            if cmd == RestServer.ADC_REQ:
                response = self._read_adc(args_dict)

            elif cmd == RestServer.SETUP_GPIO_REQ:
                response = self._setup_gpio(args_dict)

            elif cmd == RestServer.TEMPERATURE_REQ:
                response = self._read_temp()

            elif cmd == RestServer.CPU_FREQ:
                response = self._cpu_freq(args_dict)

            elif cmd == RestServer.SETUP_UART:
                response = self._setup_uart(args_dict)

            elif cmd == RestServer.UART_TX:
                response = self._uart_tx(args_dict)

            elif cmd == RestServer.UART_RX:
                response = self._uart_rx(args_dict)

        # Send the HTTP OK header detailing JSON text to follow.
        self._ok_json_response(writer)

        # Send the response to the request
        writer.write(response)
        await writer.drain()
        await writer.wait_closed()
        self._info("Client disconnected")

    def _get_args_dict(self, http_request):
        """@brief Get a dict containing the arguments detailed in the http request.
           @param http_request The http request line.
           @return A dict containing the arguments passed in the HTTP GET request.
                   This may include the following keys but others may be included
                   if key=value pairs (separated by ? characters) are present in
                   the http request.

                   CMD = The command in the http request. This is the first element
                   of the http request. This is only included if an HTTP get request
                   was found.
                   GET_REQ = The full http request string. This is only included
                   if an HTTP get request was found."""
        return_dict = {}
        pos = http_request.find("GET ")
        if pos >= 0:
            return_dict[RestServer.GET_REQ]=http_request
            sub_str = http_request[pos+4:]
            elems = sub_str.split()
            if len(elems) > 0:
                args_str=elems[0]
                args_list = args_str.split('?')
                if len(args_list) > 0:
                    # Add the command (first arg) to the list of args
                    if len(args_list) > 0:

                        return_dict[RestServer.CMD_KEY]=args_list[0].lower()
                        # Add any subsequent arguments
                        if len(args_list) > 1:
                            for arg_str in args_list[1:]:
                                # Must be key value pairs separated by the = character
                                arg_elems = arg_str.split("=")
                                if len(arg_elems) == 2:
                                    return_dict[arg_elems[0].lower()]=arg_elems[1]

        return return_dict

    def _read_adc(self, args_dict):
        """@brief Read the ADC value.
                   To read an ADC value
                        http://<PICOW ADDRESS>:8080/adc?adc=0
                        http://<PICOW ADDRESS>:8080/adc?adc=1
                        http://<PICOW ADDRESS>:8080/adc?adc=2
                        http://<PICOW ADDRESS>:8080/adc?adc=3
                        http://<PICOW ADDRESS>:8080/adc?adc=4

           @param args_dict A dict containing the elements of the http GET request.
           @return The JSON string containing the ADC value."""
        response_dict = self._get_return_dict(RestServer.ADC_REQ,
                                             "{} is a malformed request to read an ADC.".format(args_dict[RestServer.GET_REQ]),
                                             True)
        if "adc" in args_dict:
            adc_str = args_dict["adc"]
            try:
                adc = int(adc_str)
                if adc >= 0 and adc <= 4:
                    _adc = machine.ADC(adc)
                    adc_value = _adc.read_u16()
                    self._info("Read ADC{}=0x{:04x}".format(adc, adc_value))
                    response_dict = self._get_return_dict(RestServer.ADC_REQ,
                                             str(adc_value),
                                             False)

            except ValueError:
                pass

        response = json.dumps(response_dict)
        return response

    def _read_temp(self):
        """@brief Read the temperature of the picow using the on board temperature sensor.
           To read the picow temperature
                http://<PICOW ADDRESS>:8080/temperature
           @return the JSON response detailing the temperature."""
        sensor_temp = machine.ADC(4)
        conversion_factor = 3.3 / (65535)
        reading = sensor_temp.read_u16() * conversion_factor
        # The temperature sensor measures the Vbe voltage of a biased bipolar diode, connected to the fifth ADC channel
        # Typically, Vbe = 0.706V at 27 degrees C, with a slope of -1.721mV (0.001721) per degree.
        temperature = 27 - (reading - 0.706)/0.001721
        response_dict = self._get_return_dict(RestServer.TEMPERATURE_REQ,
                                 str(temperature),
                                 False)
        response = json.dumps(response_dict)
        return response

    def _setup_gpio(self, args_dict):
        """@brief Setup a GPIO pin.
           To setup a pin as an output and set its state
                http://<PICOW ADDRESS>:8080/set_gpio?pin=16?dir=out?value=1

           To set the state of a pin previously setup as an output pin
                http://<PICOW ADDRESS>:8080/set_gpio?pin=16?value=0

           To setup a pin as an input and get its state
                With internal pull up resistor
                http://<PICOW ADDRESS>:8080/set_gpio?pull=up?pin=22?dir=in
                With internal pull down resistor
                http://<PICOW ADDRESS>:8080/set_gpio?pull=down?pin=22?dir=in
                With no internal pull up/down resistor
                http://<PICOW ADDRESS>:8080/set_gpio?pin=22?dir=in

           To get the state of a pin previously setup as an input pin
                http://<PICOW ADDRESS>:8080/set_gpio?pin=22

           @param args_dict A dict containing the elements of the http GET request.

           @return The JSON string detailing success or failure."""
        response_dict = self._get_return_dict(RestServer.SETUP_GPIO_REQ,
                                             "{} is a malformed request to read/write a gpio pin.".format(args_dict[RestServer.GET_REQ]),
                                             True)
        if "pin" in args_dict:
            try:
                pin = int(args_dict["pin"])
                # If this is a valid picow GPIO pin
                if pin >= 0 and pin <= 28:
                    value = None
                    # If value is defined in the request
                    if 'value' in args_dict:
                        try:
                            value=int(args_dict['value'])
                        except ValueError:
                            pass

                    dir = None
                    # If dir is define the user is setting up the pin
                    if "dir" in args_dict:
                        dir = args_dict['dir']
                        dir=dir.lower()

                    # If setting an output
                    if dir == 'out':
                        # Set the pin state and store in the dict
                        self._gpioDict[pin]=machine.Pin(pin, machine.Pin.OUT, value=value)
                        response_dict = self._get_return_dict(RestServer.SETUP_GPIO_REQ,
                                                              "",
                                                              False)

                    # If setting an input
                    elif dir == 'in':
                        pull = None
                        if "pull" in args_dict:
                            _pull = args_dict["pull"]
                            _pull=_pull.lower()
                            if _pull in ('up', 'down'):
                                pull = _pull
                            if pull and pull == 'up':
                                _pin = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)
                            elif pull and pull == 'down':
                                _pin = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
                        else:
                            _pin = machine.Pin(pin, machine.Pin.IN)
                        # Store pin in the dict
                        self._gpioDict[pin]=_pin
                        response_dict = self._get_return_dict(RestServer.SETUP_GPIO_REQ,
                                 str(_pin.value()),
                                 False)

                    # If we get here the pin should have previously been setup as out or in
                    else:
                        # If pin has been previously setup.
                        if pin in self._gpioDict:
                            # If a value has been defined then set an output
                            if value in (0, 1):
                                self._gpioDict[pin].value(value)
                                response_dict = self._get_return_dict(RestServer.SETUP_GPIO_REQ,
                                 "",
                                 False)

                            # If we get here the pin should have previously been setup as in
                            else:
                                response_dict = self._get_return_dict(RestServer.SETUP_GPIO_REQ,
                                 str(self._gpioDict[pin].value()),
                                 False)

            except Exception as ex:
                response_dict = self._get_return_dict(RestServer.SETUP_GPIO_REQ,
                                                     "GPIO Error: {}".format(ex),
                                                     True)

        response = json.dumps(response_dict)
        return response

    def _cpu_freq(self, args_dict):
        """@brief Get/Set the CPU frequency.
                   To read the CPU frequency
                        http://<PICOW ADDRESS>:8080/cpu_freq

                    To Set the CPU frequency to 240 MHz (240 MHz is the max frequency)
                        http://<PICOW ADDRESS>:8080/cpu_freq?freq=240000000

           @param args_dict A dict containing the elements of the http GET request.
           @return The JSON string detailing success or failure."""
        response_dict = self._get_return_dict(RestServer.CPU_FREQ,
                                             "{} is a malformed request to set/get the CPU frequency.".format(args_dict[RestServer.GET_REQ]),
                                             True)

        try:

            # If Setting the CPU frequency
            if 'freq' in args_dict:
                try:
                    freqHz = int(args_dict['freq'])
                    if freqHz <= RestServer.MAX_CPU_FREQ_HZ:
                        machine.freq(freqHz)
                        response_dict = self._get_return_dict(RestServer.CPU_FREQ,
                                                              "",
                                                              False)

                    else:
                        response_dict = self._get_return_dict(RestServer.CPU_FREQ,
                                                              str(freqHz),
                                                              True)

                except Exception as ex:
                    response_dict = self._get_return_dict(RestServer.CPU_FREQ,
                                                          "Set CPU freq Error: {}".format(ex),
                                                          True)

            else:
                response_dict = self._get_return_dict(RestServer.CPU_FREQ,
                                                      str(machine.freq()),
                                                      False)

        except Exception as ex:
            response_dict = self._get_return_dict(RestServer.CPU_FREQ,
                                                  "Set CPU freq Error: {}".format(ex),
                                                  True)

        response = json.dumps(response_dict)
        return response

    def _setup_uart(self, args_dict):
        """@brief Setup a UART.
                   To setup a uart (8 data bits, 1 parity, 1 stop)
                        http://<PICOW ADDRESS>:8080/setup_uart?uart=0?tx_pin=0?rx_pin=1?baud=115200

           @param args_dict A dict containing the elements of the http GET request.
           @return The JSON string detailing success or failure."""
        response_dict = self._get_return_dict(RestServer.SETUP_UART ,
                                             "{} is a malformed request to setup a UART.".format(args_dict[RestServer.GET_REQ]),
                                             True)

        try:
            if 'uart' in args_dict:
                uart = int(args_dict['uart'])

                if 'tx_pin' in args_dict:
                    tx_pin = int(args_dict['tx_pin'])

                    if 'rx_pin' in args_dict:
                        rx_pin = int(args_dict['rx_pin'])

                        if 'baud' in args_dict:
                            baud_rate = int(args_dict['baud'])

                            uartInstance = machine.UART(uart,
                                                        baudrate=baud_rate,
                                                        tx=machine.Pin(tx_pin),
                                                        rx=machine.Pin(rx_pin))
                            self._uartDict[uart]=uartInstance
                            response_dict = self._get_return_dict(RestServer.SETUP_UART,
                                                                  "",
                                                                  False)

        except Exception as ex:
            response_dict = self._get_return_dict(RestServer.SETUP_UART ,
                                                 "UART setup Error: {}".format(ex),
                                                 True)

        response = json.dumps(response_dict)
        return response

    def _uart_tx(self, args_dict):
        """@brief TX data on a UART.
                   Send Hello World followed by carridge return, line feed
                        http://<PICOW ADDRESS>:8080/uart_tx?uart=0?tx_data=Hello%20World%d%a

                  self._setup_uart() must be called prior to calling this method.
           @param args_dict A dict containing the elements of the http GET request.
           @return The JSON string detailing success or failure."""
        response_dict = self._get_return_dict(RestServer.UART_TX,
                                             "{} is a malformed request to TX UART data.".format(args_dict[RestServer.GET_REQ]),
                                             True)

        try:
            if 'uart' in args_dict:
                uart = int(args_dict['uart'])
                if uart in self._uartDict:
                    if 'tx_data' in args_dict:
                        tx_data = args_dict['tx_data']
                        tx_data = unquote(tx_data)

                        uartInstance = self._uartDict[uart]
                        uartInstance.write(tx_data)
                        response_dict = self._get_return_dict(RestServer.SETUP_UART,
                                                              "",
                                                              False)

                else:
                    raise Exception("Uart {} has not been setup.".format(uart))

        except Exception as ex:
            response_dict = self._get_return_dict(RestServer.UART_TX,
                                                  "UART setup Error: {}".format(ex),
                                                  True)

        response = json.dumps(response_dict)
        return response

    def _uart_rx(self, args_dict):
        """@brief Read data from a UART.
                   To read any data available on the UART
                        http://<PICOW ADDRESS>:8080/uart_rx?uart=0

                  self._setup_uart() must be called prior to calling this method.
           @param args_dict A dict containing the elements of the http GET request.
           @return The JSON string detailing success or failure."""
        response_dict = self._get_return_dict(RestServer.UART_RX,
                                             "{} is a malformed request to RX UART data.".format(args_dict[RestServer.GET_REQ]),
                                             True)

        try:
            if 'uart' in args_dict:
                uart = int(args_dict['uart'])
                if uart in self._uartDict:
                    uartInstance = self._uartDict[uart]
                    rx_data = uartInstance.read()
                    response_dict = self._get_return_dict(RestServer.UART_RX,
                                                          rx_data,
                                                          False)

                else:
                    raise Exception("Uart {} has not been setup.".format(uart))

        except Exception as ex:
            response_dict = self._get_return_dict(RestServer.UART_RX,
                                                  "UART setup Error: {}".format(ex),
                                                  True)

        response = json.dumps(response_dict)
        return response


def unquote(string):
    """unquote('abc%20def') -> b'abc def'.

        Note: if the input is a str instance it is encoded as UTF-8.
        This is only an issue if it contains unescaped non-ASCII characters,
        which URIs should not.

        This was posted in the micropython forum @
        https://forum.micropython.org/viewtopic.php?t=3076&p=54344

    """
    if not string:
        return b''

    if isinstance(string, str):
        string = string.encode('utf-8')

    bits = string.split(b'%')
    if len(bits) == 1:
        return string

    res = bytearray(bits[0])
    append = res.append
    extend = res.extend

    for item in bits[1:]:
        try:
            append(int(item[:2], 16))
            extend(item[2:])
        except KeyError:
            append(b'%')
            extend(item)

    return bytes(res)


#
