# blockwork

## X11 Forwarding under macOS

 * Install XQuartz
 * Tick "Allow connections from network clients" in XQuartz preferences
 * Quit and re-open XQuartz
 * Execute `xhost + 127.0.0.1`
 * `DISPLAY` must be set to `host.containers.internal:0`
