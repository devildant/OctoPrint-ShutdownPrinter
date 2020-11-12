# coding=utf-8
from __future__ import unicode_literals
from __future__ import absolute_import

try:
	import urllib2
except (ImportError, RuntimeError):
	import urllib.request as urllib2
import ssl
import octoprint.plugin
try:
	from octoprint.access.permissions import Permissions, ADMIN_GROUP, USER_GROUP
except (ImportError, RuntimeError):
	from octoprint.server import current_user, admin_permission, user_permission
from octoprint.util import RepeatedTimer
from octoprint.events import eventManager, Events
from flask import make_response
from flask_babel import gettext
import time
import threading
import traceback
import subprocess

class shutdownprinterPlugin(octoprint.plugin.SettingsPlugin,
							octoprint.plugin.AssetPlugin,
							octoprint.plugin.TemplatePlugin,
							octoprint.plugin.SimpleApiPlugin,
							octoprint.plugin.EventHandlerPlugin,
							octoprint.plugin.StartupPlugin):

	def __init__(self):
		self.url = ""
		self._typeNotifShow = ""
		self._wait_temp = ""
		self.previousEventIsCancel = False
		self._abort_all_for_this_session = False
		self.gcode = "M81"
		self._mode_shutdown_gcode = True
		self._mode_shutdown_api = False
		self._mode_shutdown_api_custom = False
		self.api_custom_GET = False
		self.api_custom_POST = False
		self.api_custom_PUT = False
		self.api_custom_url = ""
		self.api_custom_json_header = ""
		self.api_custom_body = ""
		self.api_key_plugin = ""
		self.api_json_command = ""
		self.api_plugin_name = ""
		self.api_plugin_port = 5000
		self.extraCommand = ""
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

		self.api_custom_PUT = self._settings.get_boolean(["api_custom_PUT"])
		self._logger.debug("api_custom_PUT: %s" % self.api_custom_PUT)
				
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
			
		self.extraCommand = self._settings.get(["extraCommand"])
		self._logger.debug("extraCommand: %s" % self.extraCommand)

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
		self.shutdown_printer = self._plugin_manager.get_hooks("octoprint.plugin.ShutdownPrinter.shutdown")
		self.enclosure_screen_hook = self._plugin_manager.get_hooks("octoprint.plugin.external.event")
		self.hookEnclosureScreenfct()
	
	def on_after_startup(self):
		self.hookEnclosureScreenfct()
		
	def hookEnclosureScreenfct(self, data=dict()):
		self._logger.error("send status off 1")
		if self.enclosure_screen_hook is not None:
			for name, hook in self.enclosure_screen_hook.items():
				# first sd card upload plugin that feels responsible gets the job
				try:
					# hook(self.statusManualStop)
					self._logger.error("send status off 2")
					hook(dict(shutdownPrinter=dict(offAfterPrintEnd=self._shutdown_printer_enabled, data=data)))
				except Exception as e:
					self._logger.error("Failed get hook: %s" % e.message)
		else:
			self._logger.error("hook does not exist")
		
	def hook_event_enclosureScreen(self, data):
		if "shutdownPrinter" in data:
			self._logger.info(str(data["shutdownPrinter"]))
			if "offAfterPrintEnd" in data["shutdownPrinter"]:
				if self._shutdown_printer_enabled:
					self._shutdown_printer_enabled = False
				else:
					self._shutdown_printer_enabled = True
				self.lastCheckBoxValue = self._shutdown_printer_enabled
				if self.rememberCheckBox:
					self._settings.set_boolean(["lastCheckBoxValue"], self.lastCheckBoxValue)
					self._settings.save()
					eventManager().fire(Events.SETTINGS_UPDATED)
				self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type=self._typeNotifShow, timeout_value=self._timeout_value, wait_temp=self._wait_temp, time=time.time()))
			if "abort" in data["shutdownPrinter"]:
				self.forcedAbort = True
				if self._abort_timer is not None:
					self._abort_timer.cancel()
					self._abort_timer = None
				if self._abort_timer_temp is not None:
					self._abort_timer_temp.cancel()
					self._abort_timer_temp = None
				self._timeout_value = None
				self._typeNotifShow = "destroynotif"
				self._timeout_value = -1
				self._wait_temp = ""
				self._logger.info("Shutdown aborted.")
				self._destroyNotif()
				
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

	def get_additional_permissions(self):
		return [
				dict(key="ADMIN",
					name="shutdown printer plugin",
					description=gettext("Allows to access to api of plugin shutdownprinter."),
					default_groups=[ADMIN_GROUP],
					roles=["admin"],
					dangerous=True)
				]
	def on_api_command(self, command, data):
		# if not user_permission.can():
			# return make_response("Insufficient rights", 403)
		try:
			plugin_permission = Permissions.PLUGIN_SHUTDOWNPRINTER_ADMIN.can()
		except:
			plugin_permission = user_permission.can()
		if not plugin_permission:
			return make_response("Insufficient rights", 403)
		# user_id = current_user.get_name()
		# if not user_id or not admin_permission.can():
			# return make_response("Insufficient rights", 403)
		if command == "status":
			return make_response(str(self._shutdown_printer_enabled), 200)
		elif command == "enable":
			self._shutdown_printer_enabled = True
			self.hookEnclosureScreenfct()
		elif command == "disable":
			self._shutdown_printer_enabled = False
			self.hookEnclosureScreenfct()
		elif command == "shutdown":
			def process():
					try:
						self._shutdown_printer_API_CMD( data["mode"]) #mode 1 = gcode, mode 2 = api, mode 3 = custom api
					except:
						# exc_type, exc_obj, exc_tb = sys.exc_info()
						self._logger.error("Failed read tty screen : %s" % str(traceback.format_exc()))
			thread = threading.Thread(target=process)
			thread.daemon = True
			self._logger.info("start thread")
			thread.start()
			
		elif command == "abort":
			self.forcedAbort = True
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
			if self._abort_timer_temp is not None:
				self._abort_timer_temp.cancel()
				self._abort_timer_temp = None
			self._timeout_value = None
			self._typeNotifShow = "destroynotif"
			self._timeout_value = -1
			self._wait_temp = ""
			self._logger.info("Shutdown aborted.")
			self._destroyNotif()
		
		
		if command == "enable" or command == "disable":
			self.lastCheckBoxValue = self._shutdown_printer_enabled
			if self.rememberCheckBox:
				self._settings.set_boolean(["lastCheckBoxValue"], self.lastCheckBoxValue)
				self._settings.save()
				eventManager().fire(Events.SETTINGS_UPDATED)
		self._logger.info("eventView")
		if data["eventView"] == True:
			self.sendNotif(True)
		return make_response("ok", 200)
	
	def sendNotif(self, skipHook = False):
		if self.forcedAbort == False:
			if skipHook == False:
				self.hookEnclosureScreenfct(dict(type=self._typeNotifShow, timeout_value=self._timeout_value, wait_temp=self._wait_temp, time=time.time()))
			self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type=self._typeNotifShow, timeout_value=self._timeout_value, wait_temp=self._wait_temp, time=time.time()))
	
	def on_event(self, event, payload):

		# if event == Events.CLIENT_OPENED:
			# self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type="timeout", timeout_value=self._timeout_value))
			# return
		
		if not self._shutdown_printer_enabled:
			return
		if event == Events.PRINT_STARTED:
			# self._logger.info("Print started")
			self.previousEventIsCancel = False
			self._abort_all_for_this_session = False
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
			if self._abort_timer_temp is not None:
				self._abort_timer_temp.cancel()
				self._abort_timer_temp = None
			self._destroyNotif()
						
		if event not in [Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED]:
			return
		
			return
		if event == Events.PRINT_DONE:
			# self._logger.info("Print done")
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
		
		elif (event == Events.ERROR or event == Events.PRINT_FAILED) and self.printFailed:
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
		self.forcedAbort = False
		if self._abort_timer_temp is not None:
			# self._logger.info("_abort_timer_temp_destroyNotif")
			self._destroyNotif()
			return
		if self._abort_all_for_this_session == True:
			# self._logger.info("_abort_all_for_this_session_destroyNotif")
			if self._abort_timer_temp is not None:
				self._abort_timer_temp.cancel()
			self._abort_timer_temp = None
			self._destroyNotif()
			return
		if self.temperatureTarget:
			self._abort_timer_temp = RepeatedTimer(2, self._temperature_task)
			self._abort_timer_temp.start()
		else:
			self._timer_start()

	
	def _temperature_task(self):
		try:
			if self._abort_all_for_this_session == True:
				if self._abort_timer_temp is not None:
					self._abort_timer_temp.cancel()
				self._abort_timer_temp = None
				self._destroyNotif()
				return
			if self._printer.get_state_id() == "PRINTING" and self._printer.is_printing() == True:
				if self._abort_timer_temp is not None:
					self._abort_timer_temp.cancel()
				self._abort_timer_temp = None
				self._destroyNotif()
				return
			self._temp = self._printer.get_current_temperatures()
			self._logger.info(str(self._temp))
			tester = 0;
			number = 0;
			self._wait_temp = ""
			self._typeNotifShow = "waittemp"
			for tool in self._temp.keys():
				if not tool == "bed" and not tool == "chamber":
					if self._temp[tool]["actual"] is None:
						continue
					if self._temp[tool]["actual"] <= self.temperatureValue:
						tester += 1
					number += 1
					self._wait_temp = " - " + str(tool) + ": " + str(self._temp[tool]["actual"]) + "/" + str(self.temperatureValue) + "°C\n"
			if tester == number:
				if self._abort_timer_temp is not None:
					self._abort_timer_temp.cancel()
				self._abort_timer_temp = None
				self._timer_start()
			else:
				self.sendNotif()
		except:
			self._logger.error("Failed to connect to call api: %s" % str(traceback.format_exc()))
	def _timer_start(self):
		if self._abort_timer is not None:
			self._destroyNotif()
			return
		if self._abort_all_for_this_session == True:
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
			if self._abort_timer_temp is not None:
				self._abort_timer_temp.cancel()
				self._abort_timer_temp = None
			self._destroyNotif()
			return
		self._logger.info("Starting abort shutdown printer timer.")
		
		self._timeout_value = self.abortTimeout
		self._abort_timer = RepeatedTimer(1, self._timer_task)
		self._abort_timer.start()

	def _timer_task(self):
		if self._timeout_value is None:
			self._destroyNotif()
			return
		if self._abort_all_for_this_session == True:
			self._destroyNotif()
			if self._abort_timer is not None:
				self._abort_timer.cancel()
			self._abort_timer = None
			return
		if self._printer.get_state_id() == "PRINTING" and self._printer.is_printing() == True:
			if self._abort_timer is not None:
				self._abort_timer.cancel()
			self._abort_timer = None
			self._destroyNotif()
			return
		self._timeout_value -= 1
		self._typeNotifShow = "timeout"
		self.sendNotif()
		if self._printer.get_state_id() == "PRINTING" and self._printer.is_printing() == True:
			self._timeout_value = 0
			self.sendNotif()
			if self._abort_timer is not None:
				self._abort_timer.cancel()
			self._abort_timer = None
			return
		if self._timeout_value <= 0:
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
			if self.forcedAbort == False:
				self._shutdown_printer()
			
	def _destroyNotif(self):
		self._timeout_value = -1
		self._wait_temp = ""
		self.hookEnclosureScreenfct(dict(type="destroynotif", timeout_value=-1, wait_temp="", time=time.time()))
		self._plugin_manager.send_plugin_message(self._identifier, dict(shutdownprinterEnabled=self._shutdown_printer_enabled, type="destroynotif", timeout_value=-1, wait_temp="", time=time.time()))
			
	def _shutdown_printer(self):
		if self._printer.get_state_id() == "PRINTING" and self._printer.is_printing() == True:
			return
		if self.forcedAbort:
			return
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

	def _extraCommand(self):
		if self.shutdown_printer is not None:
			for name, hook in self.shutdown_printer.items():
				# first sd card upload plugin that feels responsible gets the job
				try:
					hook()
				except Exception as e:
					self._logger.error("Failed get hook: %s" % e.message)
		else:
					self._logger.error("hook does not exist")
		if self.extraCommand != "":
			process = subprocess.Popen(self.extraCommand, shell=True, stdin = None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			stdout, stderr = process.communicate()
			self._logger.info("extraCommand stdout: %s" % stdout.rstrip().strip())
			self._logger.info("extraCommand stderr: %s" % stderr.rstrip().strip())

	def _shutdown_printer_by_API(self):
		if self.forcedAbort:
			return
		url = "http://127.0.0.1:" + str(self.api_plugin_port) + "/api/plugin/" + self.api_plugin_name
		headers = {'Content-Type': 'application/json', 'X-Api-Key' : self.api_key_plugin}
		data = self.api_json_command.encode()
		self._logger.info("Shutting down printer with API")
		try:
			request = urllib2.Request(url, data=data, headers=headers)
			request.get_method = lambda: "POST"
			ctx = ssl.create_default_context()
			ctx.check_hostname = False
			ctx.verify_mode = ssl.CERT_NONE
			contents = urllib2.urlopen(request, timeout=30, context=ctx).read()
			self._logger.debug("call response (POST API octoprint): %s" % contents)
			self._extraCommand()
		except:
			self._logger.error("Failed to connect to call api: %s" % str(traceback.format_exc()))
			return


	def _shutdown_printer_by_API_custom(self):
		if self.forcedAbort:
			return
		headers = {}
		if self.api_custom_json_header != "":
			headers = eval(self.api_custom_json_header)
		if self.api_custom_PUT == True:
			data = self.api_custom_body.encode()
			self._logger.info("Shutting down printer with API custom (PUT)")
			try:
				request = urllib2.Request(self.api_custom_url, data=data, headers=headers)
				request.get_method = lambda: "PUT"
				ctx = ssl.create_default_context()
				ctx.check_hostname = False
				ctx.verify_mode = ssl.CERT_NONE
				contents = urllib2.urlopen(request, timeout=30, context=ctx).read()
				self._logger.debug("call response (PUT): %s" % contents)
				self._extraCommand()
			except Exception as e:
				self._logger.error("Failed to connect to call api: %s" % e.message)
				return
		if self.api_custom_POST == True:
			data = self.api_custom_body
			self._logger.info("Shutting down printer with API custom (POST)")
			try:
				request = urllib2.Request(self.api_custom_url, data=data, headers=headers)
				request.get_method = lambda: "POST"
				ctx = ssl.create_default_context()
				ctx.check_hostname = False
				ctx.verify_mode = ssl.CERT_NONE
				contents = urllib2.urlopen(request, timeout=30, context=ctx).read()
				self._logger.debug("call response (POST): %s" % contents)
				self._extraCommand()
			except Exception as e:
				self._logger.error("Failed to connect to call api: %s" % e.message)
				return
		elif self.api_custom_GET == True:
			self._logger.info("Shutting down printer with API custom (GET)")
			try:
				request = urllib2.Request(self.api_custom_url, headers=headers)
				ctx = ssl.create_default_context()
				ctx.check_hostname = False
				ctx.verify_mode = ssl.CERT_NONE
				contents = urllib2.urlopen(request, timeout=30, context=ctx).read()
				self._logger.debug("call response (GET): %s" % contents)
				self._extraCommand()
			except Exception as e:
				self._logger.error("Failed to connect to call api: %s" % e.message)
				return

	def _shutdown_printer_by_gcode(self):
			if self.forcedAbort:
				return
			self._printer.commands(self.gcode + " " + self.url)
			self._logger.info("Shutting down printer with command: " + self.gcode + " " + self.url)
			self._extraCommand()
	
	def powersupplyCancelAutoShutdown(self, status):
		self._logger.info("Shutdown aborted status " + str(status))
		if status == 0:
			self.forcedAbort = True
			self._abort_all_for_this_session = True
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
			if self._abort_timer_temp is not None:
				self._abort_timer_temp.cancel()
				self._abort_timer_temp = None
			self._timeout_value = None
			self._logger.info("Shutdown aborted.")
			self._destroyNotif()
			
			
	def get_settings_defaults(self):
		return dict(
			gcode = "M81",
			url = "",
			api_key_plugin = "",
			abortTimeout = 30,
			extraCommand = "",
			_mode_shutdown_gcode = True,
			_mode_shutdown_api = False,
			_mode_shutdown_api_custom = False,
			api_custom_POST = False,
			api_custom_GET = False,
			api_custom_PUT = False,
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
		self.api_custom_PUT = self._settings.get_boolean(["api_custom_PUT"])
		self.api_custom_url = self._settings.get(["api_custom_url"])
		self.api_custom_json_header = self._settings.get(["api_custom_json_header"])
		self.api_custom_body = self._settings.get(["api_custom_body"])
		self.api_json_command = self._settings.get(["api_json_command"])
		self.api_plugin_name = self._settings.get(["api_plugin_name"])
		self.api_plugin_port = self._settings.get_int(["api_plugin_port"])
		self.temperatureValue = self._settings.get_int(["temperatureValue"])
		self.temperatureTarget = self._settings.get_int(["temperatureTarget"])
		self.extraCommand = self._settings.get(["extraCommand"])
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
__plugin_pythoncompat__ = ">=2.7,<4"
def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = shutdownprinterPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
		"octoprint.access.permissions": __plugin_implementation__.get_additional_permissions,
		"octoprint.plugin.smartPlugWithSmokeDetector.event.powersupplyoff": __plugin_implementation__.powersupplyCancelAutoShutdown,
		"octoprint.plugin.enclosureScreen.event": __plugin_implementation__.hook_event_enclosureScreen,
	}
