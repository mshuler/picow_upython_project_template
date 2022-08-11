import json
import uasyncio as asyncio
from   machine import ADC

from uo import UOBase

class RestServer(UOBase):
    """@brief Responsible for providing a REST interface to allow clients to
              collect data but could be extended to send arguments to the Pico W."""

    TCP_PORT = 8080                                          # The TCP port to present the REST server on.
    SERVER_EXCEPTION_LOG_FILE = '/rest_server_exception.txt' # Rest server exceptions are stored in for debug purposes.

    def __init__(self, uo=None):
        """@brief Constructor
           @param uo A UO instance for presenting data to the user. If Left as None
                     no data is sent to the user."""
        super().__init__(uo=uo)

    def startServer(self):
        asyncio.create_task(asyncio.start_server(self._serve_client, "0.0.0.0", RestServer.TCP_PORT))

    def _getADC(self, req):
        """@brief Get the ADC number to be read or -1 if no ADC read requested.
           @return the ADC to be read or -1 if no ADC read request found."""
        adc = -1
        if req.find("/adc0") != -1:
            adc = 0
        elif req.find("/adc1") != -1:
            adc = 1
        elif req.find("/adc2") != -1:
            adc = 2
        elif req.find("/adc3") != -1:
            adc = 3
        elif req.find("/adc4") != -1:
            adc = 4
        return adc

    async def _serve_client(self, reader, writer):
        """@brief Called to serve a request for data."""
        try:
            self._info("Client connected")
            request_line = await reader.readline()
            self._info("Request: %s" % request_line)
            # We are not interested in HTTP request headers, skip them
            while await reader.readline() != b"\r\n":
                pass

            req = request_line.decode()
            adc = self._getADC(req)

            if adc != -1:
                # Return adc value as JSON
                adcValue = self._read_adc(adc)
                self._info("Read ADC{}=0x{:04x}".format(adc, adcValue))
                data_dict = { "ADC{}".format(adc): adcValue}
                response = json.dumps(data_dict)
                writer.write('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')

            elif req.find("/temp") >= 0:
                temp = self._read_temp()
                # Return temp as JSON
                data_dict = { "TEMPERATURE": temp}
                response = json.dumps(data_dict)
                writer.write('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')

            else:
                response =  'HTTP/1.0 404 file not found.\r\nContent-type: text/html\r\n\r\n'

            writer.write(response)
            await writer.drain()
            await writer.wait_closed()
            self._info("Client disconnected")

        except Exception as ex:
            self._save_msg(RestServer.SERVER_EXCEPTION_LOG_FILE, str(ex))

    def _read_temp(self):
        sensor_temp = ADC(4)
        conversion_factor = 3.3 / (65535)
        reading = sensor_temp.read_u16() * conversion_factor
        # The temperature sensor measures the Vbe voltage of a biased bipolar diode, connected to the fifth ADC channel
        # Typically, Vbe = 0.706V at 27 degrees C, with a slope of -1.721mV (0.001721) per degree.
        temperature = 27 - (reading - 0.706)/0.001721
        return temperature

    def _read_adc(self, adc):
        adc_value = 0x10000
        if adc >= 0 and adc <= 4:
            adc = ADC(adc)
            adc_value = adc.read_u16()
        return adc_value

    def _save_msg(self, the_file, the_message):
        fd = open(the_file, 'w')
        fd.write( the_message )
        fd.close()
