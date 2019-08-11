$(function() {
    function ShutdownPrinterViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.settings = parameters[1];
        self.printer = parameters[2];
		
		
        self.shutdownprinterEnabled = ko.observable();
		
		self.testButtonChangeStatus = function (stat) {
			$("#tester_shutdownprinter_gcode").prop("disabled", stat);
			$("#tester_shutdownprinter_api").prop("disabled", stat);
			$("#tester_shutdownprinter_api_custom").prop("disabled", stat);
		}
		
		self.eventChangeCheckToRadio =  function (id, listOff) {
				$(id).on("change", function () {
				if ($(this).prop("checked") == true)
				{
					listOff.forEach(function(element) {
						if (id != element.id)
						{
							if ($(element.id).prop("checked") == true)
							{
								$(element.id).unbind("change");
								$(element.id).trigger("click");
								self.eventChangeCheckToRadio(element.id, listOff);
							}
						}
					});
				}
			})
		}
		
		$("#tester_shutdownprinter_gcode").on("click", function () {
			self.settings.saveData();
			$(this).children("i").show();
			setTimeout(function (current) {
			$.ajax({
                url: API_BASEURL + "plugin/shutdownprinter",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "shutdown",
					mode: 1,
					eventView : true
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(function() {
				current.children("i").hide();
			});
			
			}, 1000, $(this));
			 
		});		
		$("#tester_shutdownprinter_api").on("click", function () {
			self.settings.saveData();
			$(this).children("i").show();
			setTimeout(function (current) {
			$.ajax({
                url: API_BASEURL + "plugin/shutdownprinter",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "shutdown",
					mode: 2,
					eventView : true
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(function() {
				current.children("i").hide();
			});
			}, 1000, $(this));
			
		});	
		
		$("#tester_shutdownprinter_api_custom").on("click", function () {
			self.settings.saveData();
			$(this).children("i").show();
			setTimeout(function (current) {
			$.ajax({
                url: API_BASEURL + "plugin/shutdownprinter",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "shutdown",
					mode: 3,
					eventView : true
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(function() {
				current.children("i").hide();
			});
			}, 1000, $(this));
			
		});
		self.listOffMode = [
			{"id" : "#shutdownprinter_mode_shutdown_gcode"},
			{"id" : "#shutdownprinter_mode_shutdown_api"},
			{"id" : "#shutdownprinter_mode_shutdown_api_custom"},
		]
		self.listOffHTTPMethode = [
			{"id" : "#shutdownprinter_api_custom_GET"},
            {"id" : "#shutdownprinter_api_custom_POST"},
            {"id" : "#shutdownprinter_api_custom_PUT"}
		]
		self.eventChangeCheckToRadio("#shutdownprinter_mode_shutdown_gcode", self.listOffMode);
		self.eventChangeCheckToRadio("#shutdownprinter_mode_shutdown_api", self.listOffMode);
		self.eventChangeCheckToRadio("#shutdownprinter_mode_shutdown_api_custom", self.listOffMode);
		
		self.eventChangeCheckToRadio("#shutdownprinter_api_custom_GET", self.listOffHTTPMethode);
        self.eventChangeCheckToRadio("#shutdownprinter_api_custom_POST", self.listOffHTTPMethode);
        self.eventChangeCheckToRadio("#shutdownprinter_api_custom_PUT", self.listOffHTTPMethode);
		
        // Hack to remove automatically added Cancel button
        // See https://github.com/sciactive/pnotify/issues/141
        //PNotify.prototype.options.confirm.buttons = [];
		//another way use, add custom style class for hide cancel button
        self.timeoutPopupText = gettext('Shutting down printer in ');
        self.timeoutPopupOptions = {
            title: gettext('Shutdown Printer'),
            type: 'notice',
            icon: true,
            hide: false,
            confirm: {
                confirm: true,
                buttons: [{
                    text: 'Abort Shutdown Printer',
                    addClass: 'btn-block btn-danger',
                    promptTrigger: true,
                    click: function(notice, value){
                        notice.remove();
                        notice.get().trigger("pnotify.cancel", [notice, value]);
                    }
                }, {
                    addClass: 'shutdownPrinterHideCancelBtnConfirm',
                    promptTrigger: true,
                    click: function(notice, value){
                        notice.remove();
                 
                    }
                }]
            },
            buttons: {
                closer: false,
                sticker: false,
            },
            history: {
                history: false
            }
        };
        
        //for touch ui
		self.touchUIMoveElement = function (self, counter) {
			var hash = window.location.hash;
			if (hash != "" && hash != "#printer" && hash != "#touch")
			{
				return;
			}
			if (counter < 10) {
				if (document.getElementById("touch") != null && document.getElementById("printer") != null && document.getElementById("printer") != null && document.getElementById("touch").querySelector("#printer").querySelector("#files_wrapper")) {
					var newParent = document.getElementById("files_wrapper").parentNode;
					newParent.insertBefore(document.getElementById('sidebar_plugin_shutdownprinter_wrapper'), document.getElementById("files_wrapper"));
				} else {
					setTimeout(self.touchUIMoveElement, 1000, self, ++counter);
				}
			}
		}
		 //add octoprint event for check finish
		self.onStartupComplete = function () {
			//self.touchUIMoveElement(self, 0);
			if (self.printer.isPrinting())
			{
				self.testButtonChangeStatus(true);
			} else {
				self.testButtonChangeStatus(false);
			}
			 
			
		};
		
		self.onUserLoggedIn = function() {
			$.ajax({
                    url: API_BASEURL + "plugin/shutdownprinter",
                    type: "POST",
                    dataType: "json",
                    data: JSON.stringify({
                        command: "update",
						eventView : false
                    }),
                    contentType: "application/json; charset=UTF-8"
            })
			$.ajax({
				url: API_BASEURL + "plugin/shutdownprinter",
				type: "POST",
				data: JSON.stringify({
					command: "status"
				}),
				context:self,
				contentType: "application/json; charset=UTF-8"
			}).done(function(data, textStatus, jqXHR ){
				this.shutdownprinterEnabled(data == "True" ? true : false);
			})	
		}
		
		self.onUserLoggedOut = function() {
		}
        
		self.onEventPrinterStateChanged = function(payload) {
        			if (payload.state_id == "PRINTING" || payload.state_id == "PAUSED"){
        				self.testButtonChangeStatus(true);
        			} else {
        				self.testButtonChangeStatus(false);
        			}
        		}
		
        self.onShutdownPrinterEvent = function() {
            if (self.shutdownprinterEnabled()) {
                $.ajax({
                    url: API_BASEURL + "plugin/shutdownprinter",
                    type: "POST",
                    dataType: "json",
                    data: JSON.stringify({
                        command: "enable",
						eventView : false
                    }),
                    contentType: "application/json; charset=UTF-8"
                })
            } else {
                $.ajax({
                    url: API_BASEURL + "plugin/shutdownprinter",
                    type: "POST",
                    dataType: "json",
                    data: JSON.stringify({
                        command: "disable",
						eventView : false
                    }),
                    contentType: "application/json; charset=UTF-8"
                })
            }
        }

        self.shutdownprinterEnabled.subscribe(self.onShutdownPrinterEvent, self);

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "shutdownprinter" && plugin != "octoprint_shutdownprinter") {
                return;
            }

			 self.shutdownprinterEnabled(data.shutdownprinterEnabled);
            if (data.type == "timeout") {
                if ((data.timeout_value != null) && (data.timeout_value > 0)) {
                    self.timeoutPopupOptions.text = self.timeoutPopupText + data.timeout_value;
                    if (typeof self.timeoutPopup != "undefined") {
                        self.timeoutPopup.update(self.timeoutPopupOptions);
                    } else {
                        self.timeoutPopup = new PNotify(self.timeoutPopupOptions);
                        self.timeoutPopup.get().on('pnotify.cancel', function() {self.abortShutdown(true);});
                    }
                } else {
                    if (typeof self.timeoutPopup != "undefined") {
                        self.timeoutPopup.remove();
                        self.timeoutPopup = undefined;
                    }
                }
            }
        }

        self.abortShutdown = function(abortShutdownValue) {
            self.timeoutPopup.remove();
            self.timeoutPopup = undefined;
            $.ajax({
                url: API_BASEURL + "plugin/shutdownprinter",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "abort",
					eventView : true
                }),
                contentType: "application/json; charset=UTF-8"
            })
        }
    }

    OCTOPRINT_VIEWMODELS.push([
        ShutdownPrinterViewModel,
        ["loginStateViewModel", "settingsViewModel", "printerStateViewModel"],
		$(".sidebar_plugin_shutdownprinter").get(0)
    ]);
});
