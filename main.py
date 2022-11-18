import uasyncio as asyncio

from uo import UO
from basic_web_server import BasicWebServer
from wifi import WiFi
from rest_server import RestServer
from ydev import YDevConfig, YDev

WIFI_SETUP_BUTTON_PIN = 19              # The GPIO pin that the WiFi setup
                                        # button is connected to GND through.

# Program entry point
async def main():

    uo = UO(enabled=True, debug_enabled=True)
    wn = WiFi.Get_Wifi_Networks()

    # Init the WiFi interface
    wifi = WiFi(uo, WIFI_SETUP_BUTTON_PIN)
    wifi.setup()

    # Start a web server using uasyncio.
    # This provides the WiFi setup interface and once the WiFi is setup
    # the product.html file is served which may be customised as required for your project.
    # This can be customised for your project by changing the files in /webroot
    # and the GET/POST handling in basic_web_server.py
    basicWebServer = BasicWebServer(uo)
    basicWebServer.set_wifi_networks(wn)
    basicWebServer.start()

    # Block at this point if in WiFi setup mode.
    # We enter WiFi setup mode if the user holds down the WiFi button
    # for > 5 seconds.
    # Once in WiFi setup mode the WiFi LED flashes and the user can configure
    # the WiFi by connecting to the PICOWXXYYZZ WiFi network (password 12345678)
    # and the opening a browser connection to 192.168.4.1.
    # A web page is then presented that allows the user to configure the WiFi.
    if wifi.isSetupModeActive():
        while True:
            wifi.toggleWiFiLED()
            await asyncio.sleep(0.1)

    # Start a server to provide a REST interface.
    # The example code allows the ADC's and temperature to be read.
    # Update reset_server.py to add features for your project.
    restServer = RestServer(uo)
    restServer.startServer()

    # Read the IP address we have on the WiFi network.
    ip_address = wifi.getIPAddress()
    # Define the YView config that defines the capabilities of the device.
    # These can be updated in ydev.py.
    yDevConfig = YDevConfig()
    # start Yview device listener using uasyncio
    yDev = YDev(yDevConfig, ip_address, None)
    asyncio.create_task(yDev.listen())

    # Main loop
    while True:
        # Periodically we need to check if the user is holding down the WiFi
        # button to move to WiFi setup mode.
        # This should be called at least once a second.
        wifi.checkWiFiSetupMode()

        # Add code here to do stuff for your project as this is the main loop.

        await asyncio.sleep(.1)

try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
