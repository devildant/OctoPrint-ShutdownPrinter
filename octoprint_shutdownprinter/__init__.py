# coding=utf-8
from __future__ import absolute_import

import requests
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
                self._mode_shutdown_gcode = True
                self._mode_shutdown_api = False
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

        def initialize(self):
                self.url = self._settings.get(["url"])
                self._logger.debug("url: %s" % self.url)
				
                self.api_key_plugin = self._settings.get(["api_key_plugin"])
                self._logger.debug("api_key_plugin: %s" % self.api_key_plugin)
		
                self._mode_shutdown_gcode = self._settings.get_boolean(["_mode_shutdown_gcode"])
                self._logger.debug("_mode_shutdown_gcode: %s" % self._mode_shutdown_gcode)
		
                self._mode_shutdown_api = self._settings.get_boolean(["_mode_shutdown_api"])
                self._logger.debug("_mode_shutdown_api: %s" % self._mode_shutdown_api)
				
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
		return dict(enable=[],
			disable=[],
			abort=[])

	def on_api_command(self, command, data):
                if not user_permission.can():
                        return make_response("Insufficient rights", 403)

                if command == "enable":
                        self._shutdown_printer_enabled = True
                elif command == "disable":
                        self._shutdown_printer_enabled = False
                elif command == "abort":
                        if self._abort_timer is not None:
                                self._abort_timer.cancel()
                                self._abort_timer = None
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
                        
                self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type="timeout", timeout_value=self._timeout_value))

        def on_event(self, event, payload):

                if event == Events.CLIENT_OPENED:
                        self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type="timeout", timeout_value=self._timeout_value))
                        return
                
                if not self._shutdown_printer_enabled:
                        return
                
                
                if event not in [Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED]:
                        return
                
                if event == Events.PRINT_DONE:
                        self._temperature_target()
                        return
                
                elif event == Events.PRINT_CANCELLED and self.printCancelled:
                        self._temperature_target()
                        return
                
                elif event == Events.PRINT_FAILED and self.printFailed:
                        self._temperature_target()
                        return
                else:
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
                if self._timeout_value <= 0:
                        if self._abort_timer is not None:
                                self._abort_timer.cancel()
                                self._abort_timer = None
                        self._shutdown_printer()

        def _shutdown_printer(self):
                self._logger.info("_mode_shutdown_gcode: %s" % self._mode_shutdown_gcode)
                if self._mode_shutdown_gcode == True:
                        self._shutdown_printer_by_gcode()
                else:
                        self._shutdown_printer_by_API()

        def _shutdown_printer_by_API(self):
                url = "http://127.0.0.1:" + str(self.api_plugin_port) + "/api/plugin/" + self.api_plugin_name
                headers = {'Content-Type': 'application/json', 'X-Api-Key' : self.api_key_plugin}
                data = self.api_json_command
                response = requests.post(url, headers=headers, data=data, timeout=0.001)
                self._logger.info("Shutting down printer with API")

        def _shutdown_printer_by_gcode(self):
		        self._printer.commands("M81 " + self.url)
		        self._logger.info("Shutting down printer with command: M81 " + self.url)

        def get_settings_defaults(self):
                return dict(
                        url = "",
                        api_key_plugin = "",
                        abortTimeout = 30,
                        _mode_shutdown_gcode = True,
                        _mode_shutdown_api = False,
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

                self.url = self._settings.get(["url"])
                self.api_key_plugin = self._settings.get(["api_key_plugin"])
                self._mode_shutdown_gcode = self._settings.get_boolean(["_mode_shutdown_gcode"])
                self._logger.info("_mode_shutdown_gcode1: %s" % self._mode_shutdown_gcode)
                self._mode_shutdown_api = self._settings.get_boolean(["_mode_shutdown_api"])
                self._logger.info("_mode_shutdown_gcode2: %s" % self._mode_shutdown_gcode)
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
