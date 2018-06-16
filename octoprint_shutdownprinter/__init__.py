# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.server import user_permission
from octoprint.util import RepeatedTimer
from octoprint.events import eventManager, Events
from flask import make_response
import time

class shutdownprinterPlugin(octoprint.plugin.TemplatePlugin,
							  octoprint.plugin.AssetPlugin,
							  octoprint.plugin.SimpleApiPlugin,
							  octoprint.plugin.EventHandlerPlugin,
							  octoprint.plugin.SettingsPlugin,
							  octoprint.plugin.StartupPlugin):

	def __init__(self):
                self.url = ""
                self.abortTimeout = 0
                self.printFailed = False
                self.printCancelled = False
                self.rememberCheckBox = False
                self.lastCheckBoxValue = False
                self._shutdown_printer_enabled = False
                self._timeout_value = None
		self._abort_timer = None

        def initialize(self):
                self.url = self._settings.get(["url"])
                self._logger.debug("Shutdown Printer url: %s" % self.url)
				
                self.abortTimeout = self._settings.get_int(["abortTimeout"])
                self._logger.debug("Shutdown Printer abortTimeout: %s" % self.abortTimeout)

                self.printFailed = self._settings.get_boolean(["printFailed"])
                self._logger.debug("Shutdown Printer printFailed: %s" % self.printFailed)

                self.printCancelled = self._settings.get_boolean(["printCancelled"])
                self._logger.debug("Shutdown Printer printCancelled: %s" % self.printCancelled)

                self.rememberCheckBox = self._settings.get_boolean(["rememberCheckBox"])
                self._logger.debug("Shutdown Printer rememberCheckBox: %s" % self.rememberCheckBox)

                self.lastCheckBoxValue = self._settings.get_boolean(["lastCheckBoxValue"])
                self._logger.debug("Shutdown Printer lastCheckBoxValue: %s" % self.lastCheckBoxValue)
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
                        self._timeout_value = None
                        self._logger.info("Shutdown Printer aborted.")
                
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
                        self._timer_start()
                        return
                
                elif event == Events.PRINT_CANCELLED and self.printCancelled:
                        self._timer_start()
                        return
                
                elif event == Events.PRINT_FAILED and self.printFailed:
                        self._timer_start()
                        return
                else:
                        return

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
		self._printer.commands("M81 " + self.url)
		self._logger.info("Shutting down printer with command: M81 " + self.url)

        def get_settings_defaults(self):
                return dict(
                        abortTimeout = 30,
                        printFailed = False,
                        printCancelled = False,
                        rememberCheckBox = False,
                        lastCheckBoxValue = False
                )

        def on_settings_save(self, data):
                octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

                self.url = self._settings.get(["url"])
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
                        user="OctoPrint",
                        repo="OctoPrint-ShutdownPrinter",
                        current=self._plugin_version,

                        # update method: pip w/ dependency links
                        pip="https://github.com/OctoPrint/OctoPrint-ShutdownPrinter/archive/{target_version}.zip"
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
