$(function() {
    function ShutdownPrinterViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.shutdownprinterEnabled = ko.observable();

        // Hack to remove automatically added Cancel button
        // See https://github.com/sciactive/pnotify/issues/141
        PNotify.prototype.options.confirm.buttons = [];
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
			self.touchUIMoveElement(self, 0);
		};
        
        self.onShutdownPrinterEvent = function() {
            if (self.shutdownprinterEnabled()) {
                $.ajax({
                    url: API_BASEURL + "plugin/shutdownprinter",
                    type: "POST",
                    dataType: "json",
                    data: JSON.stringify({
                        command: "enable"
                    }),
                    contentType: "application/json; charset=UTF-8"
                })
            } else {
                $.ajax({
                    url: API_BASEURL + "plugin/shutdownprinter",
                    type: "POST",
                    dataType: "json",
                    data: JSON.stringify({
                        command: "disable"
                    }),
                    contentType: "application/json; charset=UTF-8"
                })
            }
        }

        self.shutdownprinterEnabled.subscribe(self.onShutdownPrinterEvent, self);

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "shutdownprinter") {
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
                    command: "abort"
                }),
                contentType: "application/json; charset=UTF-8"
            })
        }
    }

    OCTOPRINT_VIEWMODELS.push([
        ShutdownPrinterViewModel,
        ["loginStateViewModel"],
        document.getElementById("sidebar_plugin_shutdownprinter")
    ]);
});
