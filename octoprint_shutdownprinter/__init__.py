# coding=utf-8
from __future__ import absolute_import

import urllib2
import ssl
import octoprint.plugin
from octoprint.server import user_permission
from octoprint.util import RepeatedTimer
from octoprint.events import eventManager, Events
from flask import make_response
import time

class shutdownprinterPlugin(octoprint.plugin.SettingsPlugin,
							  octoprint.plugin.AssetPlugin,
                              octoprint.plugin.TemplatePlugin,
							  octoprint.plugin.SimpleApiPlugin,
							  octoprint.plugin.EventHandlerPlugin,
							  octoprint.plugin.StartupPlugin):

	def __init__(self):
                self.url = ""
                self.previousEventIsCancel = False
                self.gcode = "M81"
                self._mode_shutdown_gcode = True
                self._mode_shutdown_api = False
                self._mode_shutdown_api_custom = False
                self.api_custom_GET = False
                self.api_custom_POST = False
                self.api_custom_url = ""
                self.api_custom_json_header = ""
                self.api_custom_body = ""
                self.api_key_plugin = ""
                self.api_json_command = ""
                self.api_plugin_name = ""
                self.api_plugin_port = 5000
                self.abortTimeout = 0
                self.temperatureValue = 0
                self.temperatureTarget = False
                self.printFailed = False
                self.printCancelled = False
                self.rememberCheckBox = False
                self.lastCheckBoxValue = False
                self._shutdown_printer_enabled = True
                self._timeout_value = None
                self._abort_timer = None
                self._abort_timer_temp = None
                self.ctx = ssl.create_default_context()
                self.ctx.check_hostname = False
                self.ctx.verify_mode = ssl.CERT_NONE

        def initialize(self):
                self.gcode = self._settings.get(["gcode"])
                self._logger.debug("gcode: %s" % self.gcode)

                self.url = self._settings.get(["url"])
                self._logger.debug("url: %s" % self.url)
   
                self.api_key_plugin = self._settings.get(["api_key_plugin"])
                self._logger.debug("api_key_plugin: %s" % self.api_key_plugin)
		
                self._mode_shutdown_gcode = self._settings.get_boolean(["_mode_shutdown_gcode"])
                self._logger.debug("_mode_shutdown_gcode: %s" % self._mode_shutdown_gcode)
		
                self._mode_shutdown_api = self._settings.get_boolean(["_mode_shutdown_api"])
                self._logger.debug("_mode_shutdown_api: %s" % self._mode_shutdown_api)	
				
                self._mode_shutdown_api_custom = self._settings.get_boolean(["_mode_shutdown_api_custom"])
                self._logger.debug("_mode_shutdown_api_custom: %s" % self._mode_shutdown_api_custom)
								
                self.api_custom_POST = self._settings.get_boolean(["api_custom_POST"])
                self._logger.debug("api_custom_POST: %s" % self.api_custom_POST)
								
                self.api_custom_GET = self._settings.get_boolean(["api_custom_GET"])
                self._logger.debug("api_custom_GET: %s" % self.api_custom_GET)
				
                self.api_custom_url = self._settings.get(["api_custom_url"])
                self._logger.debug("api_custom_url: %s" % self.api_custom_url)
								
                self.api_custom_json_header = self._settings.get(["api_custom_json_header"])
                self._logger.debug("api_custom_json_header: %s" % self.api_custom_json_header)
								
                self.api_custom_body = self._settings.get(["api_custom_body"])
                self._logger.debug("api_custom_body: %s" % self.api_custom_body)
								
                self.api_json_command = self._settings.get(["api_json_command"])
                self._logger.debug("api_json_command: %s" % self.api_json_command)
				
                self.api_plugin_name = self._settings.get(["api_plugin_name"])
                self._logger.debug("api_plugin_name: %s" % self.api_plugin_name)
						
                self.api_plugin_port = self._settings.get_int(["api_plugin_port"])
                self._logger.debug("api_plugin_port: %s" % self.api_plugin_port)
				
                self.temperatureValue = self._settings.get_int(["temperatureValue"])
                self._logger.debug("temperatureValue: %s" % self.temperatureValue)
				
                self.temperatureTarget = self._settings.get_boolean(["temperatureTarget"])
                self._logger.debug("temperatureTarget: %s" % self.temperatureTarget)

                self.abortTimeout = self._settings.get_int(["abortTimeout"])
                self._logger.debug("abortTimeout: %s" % self.abortTimeout)

                self.printFailed = self._settings.get_boolean(["printFailed"])
                self._logger.debug("printFailed: %s" % self.printFailed)

                self.printCancelled = self._settings.get_boolean(["printCancelled"])
                self._logger.debug("printCancelled: %s" % self.printCancelled)

                self.rememberCheckBox = self._settings.get_boolean(["rememberCheckBox"])
                self._logger.debug("rememberCheckBox: %s" % self.rememberCheckBox)

                self.lastCheckBoxValue = self._settings.get_boolean(["lastCheckBoxValue"])
                self._logger.debug("lastCheckBoxValue: %s" % self.lastCheckBoxValue)
                if self.rememberCheckBox:
                        self._shutdown_printer_enabled = self.lastCheckBoxValue
                
	def get_assets(self):
		return dict(js=["js/shutdownprinter.js"],css=["css/shutdownprinter.css"])

	def get_template_configs(self):
		return [dict(type="sidebar",
			name="Shutdown Printer",
			custom_bindings=False,
			icon="power-off"),
                        dict(type="settings", custom_bindings=False)]
            

	def get_api_commands(self):
		return dict(enable=["eventView"],
			status=[],
			update=["eventView"],
			disable=["eventView"],
			shutdown=["mode", "eventView"],
			abort=["eventView"])

	def on_api_command(self, command, data):
                if not user_permission.can():
                        return make_response("Insufficient rights", 403)

                if command == "status":
                        return make_response(str(self._shutdown_printer_enabled), 200)
                elif command == "enable":
                        self._shutdown_printer_enabled = True
                elif command == "disable":
                        self._shutdown_printer_enabled = False
                elif command == "shutdown":
                        self._shutdown_printer_API_CMD( data["mode"]) #mode 1 = gcode, mode 2 = api, mode 3 = custom api
                elif command == "abort":
                        if self._abort_timer is not None:
                                self._abort_timer.cancel()
                                self._abort_timer = None
                                if self._abort_timer_temp is not None:
                                        self._abort_timer_temp.cancel()
                                        self._abort_timer_temp = None
                        self._timeout_value = None
                        self._logger.info("Shutdown aborted.")
                
                if command == "enable" or command == "disable":
                        self.lastCheckBoxValue = self._shutdown_printer_enabled
                        if self.rememberCheckBox:
                                self._settings.set_boolean(["lastCheckBoxValue"], self.lastCheckBoxValue)
                                self._settings.save()
                                eventManager().fire(Events.SETTINGS_UPDATED)
                if data["eventView"] == True:      
                        self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type="timeout", timeout_value=self._timeout_value))

        def on_event(self, event, payload):

                # if event == Events.CLIENT_OPENED:
                        # self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type="timeout", timeout_value=self._timeout_value))
                        # return
                
                if not self._shutdown_printer_enabled:
                        return
                
                if event == Events.PRINT_STARTED:
                        # self._logger.info("Print started")
                        self.previousEventIsCancel = False
						
                if event not in [Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED]:
                        return
                
                        return
                if event == Events.PRINT_DONE:
                        self._temperature_target()
                        return
                elif event == Events.PRINT_CANCELLED and self.printCancelled:
                        # self._logger.info("Print cancelled")
                        self.previousEventIsCancel = True
                        self._temperature_target()
                        return
                elif event == Events.PRINT_CANCELLED:
                        # self._logger.info("Print cancelled")
                        self.previousEventIsCancel = True
                        return
                
                elif event == Events.PRINT_FAILED and self.printFailed:
                        if self.previousEventIsCancel == True:
                                self.previousEventIsCancel = False
                                return;
                        # self._logger.info("Print failed")
                        self._temperature_target()
                        return
                else:
                        self.previousEventIsCancel = False
                        return

        def _temperature_target(self):
                if self._abort_timer_temp is not None:
                        return
                if self.temperatureTarget:
                        self._abort_timer_temp = RepeatedTimer(2, self._temperature_task)
                        self._abort_timer_temp.start()
                else:
                        self._timer_start()

        
        def _temperature_task(self):
                if self._printer.get_state_id() == "PRINTING" and self._printer.is_printing() == True:
                        self._abort_timer_temp.cancel()
                        self._abort_timer_temp = None
                        return
                self._temp = self._printer.get_current_temperatures()
                tester = 0;
                number = 0;
                for tool in self._temp.keys():
                        if not tool == "bed":
                                if self._temp[tool]["actual"] <= self.temperatureValue:
                                        tester += 1
                                number += 1
                if tester == number:
                        self._abort_timer_temp.cancel()
                        self._abort_timer_temp = None
                        self._timer_start()

        def _timer_start(self):
                if self._abort_timer is not None:
                        return

                self._logger.info("Starting abort shutdown printer timer.")
                
                self._timeout_value = self.abortTimeout
                self._abort_timer = RepeatedTimer(1, self._timer_task)
                self._abort_timer.start()

        def _timer_task(self):
                if self._timeout_value is None:
                        return

                self._timeout_value -= 1
                self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type="timeout", timeout_value=self._timeout_value))
                if self._printer.get_state_id() == "PRINTING" and self._printer.is_printing() == True:
                        self._timeout_value = 0
                        self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type="timeout", timeout_value=self._timeout_value))
                        self._abort_timer.cancel()
                        self._abort_timer = None
                        return
                if self._timeout_value <= 0:
                        if self._abort_timer is not None:
                                self._abort_timer.cancel()
                                self._abort_timer = None
                        self._shutdown_printer()

        def _shutdown_printer(self):
                if self._mode_shutdown_gcode == True:
                        self._shutdown_printer_by_gcode()
                elif self._mode_shutdown_api == True:
                        self._shutdown_printer_by_API()
                else:
                        self._shutdown_printer_by_API_custom()

        def _shutdown_printer_API_CMD(self, mode):
                if mode == 1:
                        self._shutdown_printer_by_gcode()
                elif mode == 2:
                        self._shutdown_printer_by_API()
                elif mode == 3:
                        self._shutdown_printer_by_API_custom()

        def _shutdown_printer_by_API(self):
                url = "http://127.0.0.1:" + str(self.api_plugin_port) + "/api/plugin/" + self.api_plugin_name
                headers = {'Content-Type': 'application/json', 'X-Api-Key' : self.api_key_plugin}
                data = self.api_json_command
                self._logger.info("Shutting down printer with API")
                try:
                        request = urllib2.Request(url, data=data, headers=headers)
                        request.get_method = lambda: "POST"
                        contents = urllib2.urlopen(request, timeout=30, context=self.ctx).read()
                        self._logger.debug("call response (POST API octoprint): %s" % contents)
                except Exception as e:
                        self._logger.error("Failed to connect to call api: %s" % e.message)
                        return


        def _shutdown_printer_by_API_custom(self):
                headers = {}
                if self.api_custom_json_header != "":
                        headers = eval(self.api_custom_json_header)
                if self.api_custom_POST == True:
                        data = self.api_custom_body
                        self._logger.info("Shutting down printer with API custom (POST)")
                        try:
                                request = urllib2.Request(self.api_custom_url, data=data, headers=headers)
                                request.get_method = lambda: "POST"
                                contents = urllib2.urlopen(request, timeout=30, context=self.ctx).read()
                                self._logger.debug("call response (POST): %s" % contents)
                        except Exception as e:
                                self._logger.error("Failed to connect to call api: %s" % e.message)
                                return
                elif self.api_custom_GET == True:
                        self._logger.info("Shutting down printer with API custom (GET)")
                        try:
                                request = urllib2.Request(self.api_custom_url, headers=headers)
                                contents = urllib2.urlopen(request, timeout=30, context=self.ctx).read()
                                self._logger.debug("call response (GET): %s" % contents)
                        except Exception as e:
                                self._logger.error("Failed to connect to call api: %s" % e.message)
                                return

        def _shutdown_printer_by_gcode(self):
		        self._printer.commands(self.gcode + " " + self.url)
		        self._logger.info("Shutting down printer with command: " + self.gcode + " " + self.url)

        def get_settings_defaults(self):
                return dict(
                        gcode = "M81",
                        url = "",
                        api_key_plugin = "",
                        abortTimeout = 30,
                        _mode_shutdown_gcode = True,
                        _mode_shutdown_api = False,
                        _mode_shutdown_api_custom = False,
                        api_custom_POST = False,
                        api_custom_GET = False,
                        api_custom_url = "",
                        api_custom_json_header = "",
                        api_custom_body = "",
                        api_plugin_port = 5000,
                        temperatureValue = 110,
                        _shutdown_printer_enabled = True,
                        printFailed = False,
                        printCancelled = False,
                        rememberCheckBox = False,
                        lastCheckBoxValue = False
                )

        def on_settings_save(self, data):
                octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

                self.gcode = self._settings.get(["gcode"])
                self.url = self._settings.get(["url"])
                self.api_key_plugin = self._settings.get(["api_key_plugin"])
                self._mode_shutdown_gcode = self._settings.get_boolean(["_mode_shutdown_gcode"])
                self._mode_shutdown_api = self._settings.get_boolean(["_mode_shutdown_api"])
                self._mode_shutdown_api_custom = self._settings.get_boolean(["_mode_shutdown_api_custom"])
                self.api_custom_POST = self._settings.get_boolean(["api_custom_POST"])
                self.api_custom_GET = self._settings.get_boolean(["api_custom_GET"])
                self.api_custom_url = self._settings.get(["api_custom_url"])
                self.api_custom_json_header = self._settings.get(["api_custom_json_header"])
                self.api_custom_body = self._settings.get(["api_custom_body"])
                self.api_json_command = self._settings.get(["api_json_command"])
                self.api_plugin_name = self._settings.get(["api_plugin_name"])
                self.api_plugin_port = self._settings.get_int(["api_plugin_port"])
                self.temperatureValue = self._settings.get_int(["temperatureValue"])
                self.temperatureTarget = self._settings.get_int(["temperatureTarget"])
                self.printFailed = self._settings.get_boolean(["printFailed"])
                self.printCancelled = self._settings.get_boolean(["printCancelled"])
                self.abortTimeout = self._settings.get_int(["abortTimeout"])
                self.rememberCheckBox = self._settings.get_boolean(["rememberCheckBox"])
                self.lastCheckBoxValue = self._settings.get_boolean(["lastCheckBoxValue"])

        def get_update_information(self):
                return dict(
                        shutdownprinter=dict(
                        displayName="Shutdown Printer",
                        displayVersion=self._plugin_version,

                        # version check: github repository
                        type="github_release",
                        user="devildant",
                        repo="OctoPrint-ShutdownPrinter",
                        current=self._plugin_version,

                        # update method: pip w/ dependency links
                        pip="https://github.com/devildant/OctoPrint-ShutdownPrinter/archive/{target_version}.zip"
                )
        )

__plugin_name__ = "Shutdown Printer"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = shutdownprinterPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
