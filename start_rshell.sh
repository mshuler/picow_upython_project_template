#!/bin/sh
# Requires rshell is installed (pip install rshell)
# Requires a single argument. This is the USB port number.
# E.G for /dev/ttyUSB0 you should pass an argument of 0.
# This command gives access to the rshell that allows you to manually inspect
# the contents of the picow flash in the cd /pyboard/ folder.
# Once running you can copy files to the /pyboard folder and
# these will then be present in the picow flash folder.
rshell -p /dev/ttyACM$1 --buffer-size 512
