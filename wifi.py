import os
import network
import time
import binascii
import json
from   machine import Pin
import machine

class WiFi(object):
    """@brief Responsible for accessing the WiFi interface."""

    AP_IP_ADDRESS               = '192.168.4.1'   # The IP address to access the unit when configuring the WiFi from the web server interface.
    AP_SUBNET_MASK              = '255.255.255.0' # The netmask of the above interface.
    AP_DEFAULT_SSID             = 'PICOW'         # The prefix of the WiFi of the AP SSID when configuring the WiFi. This will be followed by the AP MAC address to make each SSID unique.
    AP_DEFAULT_PASSWORD         = '12345678'      # The password to access the PICOWXXYYZZ network when setting up the WiFi from the web interface.
    WIFI_SETUP_BUTTON_HOLD_SECS = 5               # The number of seconds the WiFi button must be held down by the user to move to WiFi setup mode.
    WIFI_CFG_FILE               = "/wifi.cfg"     # The config file to hold to WiFi configuration (E.G SSID, password etc).
    AP_CHANNEL                  = 3               # The WiFi channel used in setup mode.

    @staticmethod
    def Get_Wifi_Networks():
        """@brief Get details of all the detectable WiFi networks.
           @return A list of Wifi networks as a string as detailed below
                   Each WiFi network string is deliniated by a ',' character
                   Each Parameter in each WiFi network is deliniated by a : character
                   Each network contains the following parameters
                   ssid:bssid:channel:RSSI:security:hidden

                   The bssid is returned as a string of 6 hex characters each one separated by a '0x' characters
        """
        wifi_network_list = []
        wlan = network.WLAN(network.STA_IF)
        wlan.active(False)
        wlan.active(True)
        # Returns a tuple each element of which contains
        # (ssid, bssid, channel, RSSI, security, hidden)
        # bssid = MAC address of AP
        # There are five values for security:
        # 0 – open
        # 1 – WEP
        # 2 – WPA-PSK
        # 3 – WPA2-PSK
        # 4 – WPA/WPA2-PSK
        # and two for hidden:
        # 0 – visible
        # 1 – hidden
        networks = wlan.scan()
        for n in networks:
            if n[0] != b'\x00\x00\x00\x00\x00\x00\x00\x00\x00':
                ssid      = n[0].decode()
                bssid     = binascii.hexlify(n[1],'0x').decode()
                channel   = n[2]
                rssi      = n[3]
                security  = n[4]
                hidden    = n[5]
            wifi_network_str = "{}:{}:{}:{}:{}:{}".format(ssid, bssid, channel, rssi, security, hidden)
            wifi_network_list.append(wifi_network_str)

        return ",".join(wifi_network_list)

    @staticmethod
    def GetWifiCfgDict():
        """@brief Get the the WiFi config dict fromm from the Wifi configuration file.
           @return The WiFi configuration dict or None if not found."""
        wiFiCfgDict = None
        try:
            with open(WiFi.WIFI_CFG_FILE, "r") as read_file:
                wiFiCfgDict = json.load(read_file)
        except:
            pass

        return wiFiCfgDict

    def __init__(self, uo, wifiButtonGPIO, useOnBoardLED=True, wifiLEDPin=-1):
        """@brief Constructor
           @param uo A UO instance.
           @param wifiButtonGPIO The GPIO pin with a button to GND that is used to setup the WiFi.
           @param useOnBoardLED Use the picow on board LED to indicate the WiFi state.
           @param wifiLEDPin If an external LED is connected to indicate WiFi state
                             this should be set to the GPIO pin number with the LED connected."""
        self._uo = uo
        self._useOnBoardLED = useOnBoardLED
        self._setup_mode = True
        self._wifiButtonPressedTime = None
        # Define the pin that the button is connected to.
        self._wifiButton = Pin(wifiButtonGPIO, Pin.IN, Pin.PULL_UP)

        #Set Pico W board LED, connected to WiFi chip over SPI bus
        self._picowLED = Pin("LED", Pin.OUT, value=0)
        if wifiLEDPin >= 0:
            self._wifiLed = Pin(wifiLEDPin, Pin.OUT, value=0)
        else:
            self._wifiLed = None

        self._wifiConnected = False
        self._staMode = False
        self._wlan = None

        self._nextCheckSetupTime = time.time() + 1

    def _loadWifiCfg(self):
        """@brief Load the WiFi config from the Wifi configuration file.
           @return The WiFi configuration dict or None if not set"""
        wiFiCfgDict = None
        try:
            with open(WiFi.WIFI_CFG_FILE, "r") as read_file:
                wiFiCfgDict = json.load(read_file)
        except:
            pass

        return wiFiCfgDict

    def _configAP(self, ssid, password, add_mac=False, powerSaveMode=False):
        """@brief configure the WiFi in AP mode.
           @paraam ssid The AP's SSID.
           @param password The password for the network.
           @param add_mac If True add part of the AP MAC address to the SSID.
           @param powerSaveMode If True then run the wiFi in power save mode.
           @return A WLAN instance."""
        # When in AP mode we set a fixed AP address
        ap = network.WLAN(network.AP_IF)
        if not powerSaveMode:
            ap.config(pm = 0xa11140) # Disable power-save mode
        ap.ifconfig((WiFi.AP_IP_ADDRESS, WiFi.AP_SUBNET_MASK, '', ''))
        if add_mac:
            ap_mac = ap.config('mac')
            full_ssid = "{}{:02x}{:02x}{:02x}".format(ssid, ap_mac[0], ap_mac[1], ap_mac[2])
        else:
            full_ssid = ssid
        ap.config(essid=full_ssid, channel=WiFi.AP_CHANNEL, password=password)
        ap.active('up')
        self._uo.info("Set AP mode ({}/{}).".format(WiFi.AP_IP_ADDRESS, WiFi.AP_SUBNET_MASK))
        self._setWiFiLED(True)
        self._wifiConnected = True
        self._staMode = False
        return ap

    def _configSTA(self, ssid, password, powerSaveMode=False):
        """@brief Configure the WiFi in STA mode.
           @paraam ssid The AP's SSID.
           @param password The password for the network.
           @param powerSaveMode If True then run the wiFi in power save mode.
           @return A WLAN instance."""
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if not powerSaveMode:
            sta.config(pm = 0xa11140) # Disable power-save mode
        sta.connect(ssid, password)
        max_wait = 30 # The maximum time (seconds) to wait to register on
                      # the WiFi network.
        while max_wait > 0:
            wifi_status = sta.status()
            self._uo.debug("wifi_status={}".format(wifi_status))
            if wifi_status < 0 or wifi_status >= 3:
                break
            max_wait -= 1
            self._uo.info('waiting for connection...')
            time.sleep(1)

        if wifi_status != 3:
            self._uo.info("Failed to connect to {}.".format(ssid))

        else:
            self._uo.info('connected')
            status = sta.ifconfig()
            self._uo.info('ip = ' + status[0])
            self._setWiFiLED(True)
            self._wifiConnected = True
            self._staMode = True
        return sta

    def _configWifi(self, wifiCfgDict):
        """@brief Setup the Wifi as per the configuration.
           @param wifiCfgDict A Dict containing in the WiFi configuration.
           @return An instance of network.WLAN."""
        mode = wifiCfgDict['mode']
        ssid = wifiCfgDict['ssid']
        password = wifiCfgDict['pass']

        if mode == 'AP':
            wlan = self._configAP(ssid, password)

        elif mode == 'STA':
            wlan = self._configSTA(ssid, password)

        else:
            raise Exception("{} is an invalid WiFi mode.".format(mode))

        self._wlan = wlan
        return wlan

    def setup(self):
        """@brief Setup the WiFi networking.
           @return An instance of network.WLAN."""
        wifiCfgDict = WiFi.GetWifiCfgDict()
        if wifiCfgDict:
            wlan = self._configWifi(wifiCfgDict)
            self._setup_mode = False
        else:
            # The WiFi has not been setup therefore we set AP mode
            # and allow the user to configure the WiFi settings via the web interface.
            wlan = self._configAP(WiFi.AP_DEFAULT_SSID, WiFi.AP_DEFAULT_PASSWORD, add_mac=True)

        return wlan

    def isSetupModeActive(self):
        """@brief Determine if the Wifi setting are currently being setup.
           @return True if setup mode is active."""
        return self._setup_mode

    def checkWiFiSetupMode(self):
        """@brief Check for WiFi setup mode.
                  This must be called periodically to see if the user is holding down the WiFi setup button."""
        if time.time() < self._nextCheckSetupTime:
            return

        if self._wifiButtonPressedTime is None:
            if self._wifiButton.value() == 0:
                self._wifiButtonPressedTime = time.time()
        else:
            if self._wifiButton.value() == 1:
                self._wifiButtonPressedTime = None
                # If user has held WiFi button then the WiFi button should be set back on if currently connected.
                if self._wifiConnected:
                    self._setWiFiLED(True)
            elif self._wifiButton.value() == 0:
                # Toggle the WiFi LED slowly to indicate the button is pressed
                self.toggleWiFiLED()
                eleapseSeconds = time.time() - self._wifiButtonPressedTime
                self._uo.debug('Button pressed for {} of {} seconds.'.format(eleapseSeconds, WiFi.WIFI_SETUP_BUTTON_HOLD_SECS))
                if eleapseSeconds >= WiFi.WIFI_SETUP_BUTTON_HOLD_SECS:
                    try:
                        os.remove(WiFi.WIFI_CFG_FILE)
                        self._uo.info("Removed {}".format(WiFi.WIFI_CFG_FILE))
                    except:
                        pass
                    self._uo.debug("Rebooting into AP mode to allow the Wifi to be setup.")
                    time.sleep(1)
                    machine.reset()

        # Define the next time we should check the wifi setup
        self._nextCheckSetupTime = time.time() + 1

    def toggleWiFiLED(self):
        """@brief Change the state of the WiFi LED."""
        if self._useOnBoardLED:
            self._picowLED.toggle()
        if self._wifiLed:
            self._wifiLed.toggle()

    def _setWiFiLED(self, on):
        """@brief Set the LED state to indicate the WiFi is connected (LED on).
           @param on If True the WiFi LED is on."""
        if self._useOnBoardLED:
            self._picowLED.value(on)

        if self._wifiLed:
            self._wifiLed.value(on)

    def getIPAddress(self):
        """@brief Read the IP address we have on the WiFi network.
           @return The IP address of None if WiFi is not setup."""
        ip_address = None
        if self._wifiConnected:
            if self._staMode:
                if self._wlan:
                    status = self._wlan.ifconfig()
                    ip_address = status[0]
            else:
                ip_address = WiFi.AP_IP_ADDRESS

        return ip_address
