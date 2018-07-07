# OctoPrint Shutdown Printer

This OctoPrint plugin enables the system to be automatically shut down printer after a print is finished (works with tplink plugs and OctoPrint-TPLinkSmartplug plugins).

The user can enable shutdown print for each print by using a checkbox in the sidebar.

This plugin was inspired by the work of "Nicanor Romero Venier" on the plugin: AutomaticShutdown (https://plugins.octoprint.org/plugins/automaticshutdown/)

![Sidebar](https://i.imgur.com/VAGQUA2.jpg)

![Settings](https://i.imgur.com/gC6dINZ.jpg)
![Settings](https://i.imgur.com/qjxYu9f.jpg)
![Settings](https://i.imgur.com/JeQ4knS.jpg)

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/devildant/OctoPrint-ShutdownPrinter/archive/master.zip

## Configuration

For the plugin to work, the OctoPrint-TPLinkSmartplug and OctoPrint-Tasmota plugin must be installed
https://plugins.octoprint.org/plugins/tplinksmartplug/

https://plugins.octoprint.org/plugins/tasmota/

## Compatibility
this plugin is compatible with any plugin monitoring the GCODE M81, an API options has been added to allow compatibility with other plugins via their API

## Mode GCODE
the plugin will send a gcode after print finish with specifique parameter
exemple : M81 192.168.1.2

## Mode API
the plugin will call specifique API (octoprint plugin) after print finish
exemple for tplink : 
```api key (key octoprint) : AAAAAAAAAAAAAAAA
Plugin ID : tplinksmartplug
Port : 5000
JSON : {"command": "turnOff", "ip": "192.168.1.43" }
```


## Mode API Custom
the plugin will call specifique API (external) after print finish
exemple for tplink : 
```POST : enable
URL : http://127.0.0.1:5000/api/plugin/tplinksmartplug
header (json format) : {"Content-Type": "application/json", "X-Api-Key" : "AAAAAAAAAAAAAAAA"}
body : {"command": "turnOff", "ip": "192.168.1.43" }
```

NB : do not forget to put the API key (octoprint / settings / API)


