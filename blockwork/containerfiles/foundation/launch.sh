#!/bin/bash

# If BLOCKWORK_XTOKEN provided, append it to Xauthority
if [[ ! -z "$BLOCKWORK_XTOKEN" ]]; then
    export XAUTHORITY="/tmp/.Xauthority"
    touch $XAUTHORITY
    xauth add $DISPLAY MIT-MAGIC-COOKIE-1 $BLOCKWORK_XTOKEN
fi

# Execute whatever command was passed in
$BLOCKWORK_CMD
