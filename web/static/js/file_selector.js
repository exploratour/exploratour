(function($) {
    $.fn.onEnter = function(cb) {
        return this.each(function()
        {
            $(this).keypress(function(e)
            {
                var key = e.which;
                switch (key) {
                    case 13:
                        $(this).trigger('keyEnter', e);
                };
            });
            $(this).bind('keyEnter', cb);
        })
    };
})(jQuery);


function FileSelector(initialpath, mimepattern, pick_file) {
    var pathinput, hidden_toggle,
        loadingmsg, filelist, currently_displayed_path = null, last_requested_path = null, last_request = null, parent = null,
        dialog;

    // Get the url to request the current file details
    function file_details_url() {
        var url = "/mediainfo?path=" + encodeURIComponent(pathinput.val());
        if (hidden_toggle.checked) {
            url += "&hidden=1";
        }
        if (mimepattern) {
            url += "&mimepattern=" + encodeURIComponent(mimepattern);
        }
        return url;
    }

    function error(request, status, error) {
        last_request = null;
        if (status == "error" && request.status == 404) {
            // Not found.
            hide_loading();
            return;
        }
        if (status == "timeout") {
            defer_update_filelist(5000, "Timeout connecting to server - retrying...");
            return;
        }
        defer_update_filelist(5000, "An error occurred - retrying...");
    }

    function get_filedetails(complete) {
	var url = file_details_url() + "&exactpath=1";
	if (last_request != null) {
	    last_request.abort();
            last_request = null;
	}

	last_requested_path = null;
	last_request = $.ajax({
	    url: url, success: function(data, status, request) {
                if (data === null) {
                    cancel_deferred_update();
                    last_request = null;
                    defer_update_filelist(5000, "Couldn't connect to server - retrying...");
                    return;
                }
                if (data.path != pathinput.val()) {
                    // Probably an old request which we didn't manage to cancel in
                    // time.
                    return;
                }
                // Cancel any deferred updates, because we've got a response for
                // the right path.
                cancel_deferred_update();
	        last_request = null;
	        hide_loading();

                complete(data);
            }, error: error, dataType: 'json'
	});
    }

    function update_filelist() {
        function success(data, status, request) {
            if (data === null) {
                cancel_deferred_update();
                last_request = null;
                defer_update_filelist(5000, "Couldn't connect to server - retrying...");
                return;
            }
            if (data.path != pathinput.val()) {
                // Probably an old request which we didn't manage to cancel in
                // time.
                return;
            }
            // Cancel any deferred updates, because we've got a response for
            // the right path.
            cancel_deferred_update();
	    last_request = null;
	    currently_displayed_path = data.path;
	    hide_loading();

	    update_display(data);
	    if (data.path == data.dirpath) {
		parent = data.parent;
	    } else {
		parent = data.dirpath;
	    }
	    pathinput.focus();
	}

	function update_display(data) {
	    filelist.html("");
	    for (var dir in data.dirs) {
		dir = data.dirs[dir];
		item = $('<div class="chooser_item"></div>').text(dir.name).
			click(function() {
			      pathinput.val($(this).data('fullpath'));
			      immediate_update_filelist();
			      }).data('fullpath', data.dirpath + dir.name + data.sep);
		filelist.append(item);
	    }
	    filelist.append($('<hr>'));
	    filelist.append($('<table>'));
	    for (var file in data.files) {
		file = data.files[file];
		item = $('<tr class="chooser_item"></tr>');
		item.append($('<td></td>').text(file.name));
		item.append($('<td></td>').append($('<img></img>').attr({src: file.thumburl})));
                if (file.summary) {
                    item.append($('<td class="file_summary"></td>').text(file.summary));
                }
		item.click(function() {
			   pathinput.val($(this).data('fullpath'));
                           picked_file();
			   }).data('fullpath', data.dirpath + file.name);
		filelist.append(item);
	    }
	}

	var path = pathinput.val();
	if (path == currently_displayed_path) {
	    cancel_deferred_update();
	    hide_loading();
	    return;
	}
	if (last_request != null) {
	    if (path == last_requested_path) {
		return;
	    }
	    last_request.abort();
            last_request = null;
	}
	last_requested_path = path;
	show_loading();

	var url = file_details_url();
	last_request = $.ajax({
	    url: url, success: success, error: error, dataType: 'json'
	});
    }

    var update_timer = null;

    // Set a timer to cause the file details to be updated, unless they're
    // already correct.  `delay` is the number of milliseconds to wait
    // (default 100), `msg` is the message to display (default "Loading..."),
    // and `force` is true if a new update should be scheduled even if the
    // last update was for the current path (this is used when the new value
    // might not yet have been written).
    function defer_update_filelist(delay, msg, force) {
	var path = pathinput.val();

	if (!force && last_request != null && path == last_requested_path) {
	    return;
	}

	if (delay == undefined) {
	    delay = 100;
	}
	if (msg == undefined) {
	    msg = "Loading...";
	}
	cancel_deferred_update();
	if (!force && path == currently_displayed_path) {
	    hide_loading();
	} else {
	    show_loading(msg);
	    update_timer = setTimeout(update_filelist, delay);
	}
    }

    // Update the filelist immediately.
    function immediate_update_filelist() {
	cancel_deferred_update();
	update_filelist();
    }

    // Cancel any updates in progress.
    function cancel_deferred_update() {
	if (update_timer != null) {
	    clearTimeout(update_timer);
	    update_timer = null;
	}
	if (last_request != null) {
	    last_request.abort();
	    last_request = null;
	}
    }

    // Show the loading message.
    function show_loading(msg) {
	if (msg != undefined) {
	    loadingmsg.text(msg);
	}
	loadingmsg.show();
    }

    // Hide the loading message.
    function hide_loading() {
	loadingmsg.hide();
    }

    // Called when a file has been picked
    function picked_file() {
        get_filedetails(function(data) {
            var result;
            if (data.files.length != 1) {
                // Path chosen is not a single file.
                // FIXME - display an error somewhere
            } else {
                result = data.files[0];
                result.dirpath = data.dirpath;
                pick_file(result);
            }
        });
        close_dialog();
    }

    function close_dialog() {
        dialog.dialog("close");
        dialog.dialog("destroy");
        dialog = null;
    }

    // Create the dialog box and open it.
    function open_dialog() {
        var displayarea;
	dialog = $("<div title='Choose a file'/>");
	pathinput = $("<input type='text' style='width: 100%' class='filepath'/>");
	pathinput.val(initialpath);
	dialog.append(pathinput);
	dialog.append($("<span class='button'>UP</span>").click(function() {
            if (parent != null) {
                pathinput.val(parent);
                immediate_update_filelist();
                pathinput.focus();
            }
        }));
	hidden_toggle = $("<input type='checkbox' id='hidden_toggle'><label for='hidden_toggle'>Show hidden files</label>");
	dialog.append(hidden_toggle.click(function() {
					  defer_update_filelist();
					  }));
	displayarea = $("<div class='filelist_display'></div>");
	loadingmsg = $("<div class='loading_message'>Loading...</div>");
	displayarea.append(loadingmsg);
	filelist = $("<div class='filelist'></div>").height(400);
	show_loading();
	displayarea.append(filelist);
	dialog.append(displayarea);

	dialog.dialog({
	    buttons: {
		"Pick file": picked_file,
		"Cancel": close_dialog
	    },
	    width: 800,
	    position: [350, 100]
	});

	pathinput.change(immediate_update_filelist);
	pathinput.keyup(function() {defer_update_filelist();});
	pathinput.mouseup(function() {defer_update_filelist();});
	pathinput.bind('paste', function() {defer_update_filelist(null, null, true);});
	pathinput.bind('cut', function() {defer_update_filelist(null, null, true);});

	pathinput.focus();
    }

    open_dialog();
    update_filelist();

    this.close = close_dialog;
};
