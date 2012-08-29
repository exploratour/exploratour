(function($) {
    function MirrorFrame(target, options) {
        var self = this, lastHeight, settings;

        settings = $.extend({
            minHeight: 300,
            margin: 40
        }, options);

        // Autoresize code
        function autoResize(instant) {
	    var framebody = $(self.editor.frame.contentDocument);
	    var children = framebody.find("span");
	    var lastchild = $(children[children.length - 1]);
	    if (lastchild != null) {
	        var newHeight = lastchild.position().top + lastchild.outerHeight() + settings.margin;
	        if (newHeight < settings.minHeight) {
	            newHeight = settings.minHeight;
	        }

	        if (newHeight != lastHeight) {
	            var wrapping = $(self.editor.wrapping);
	            wrapping.stop();
	            if (instant) {
	                wrapping.css({height: newHeight});
	            } else {
	                wrapping.animate({height: newHeight, duration: "fast", queue: false});
	            }
	            lastHeight = newHeight;
	        }
	    }
        };
        $(window).resize(autoResize);

        self.modified = false;
        if (settings.modified_end) {
            settings.modified_end();
        }

        self.editor = CodeMirror.fromTextArea(target, {
	    noScriptCaching: true, // FIXME - remove when not in development
	    parserfile: "parsexml.js",
	    stylesheet: "/static/css/CodeMirror/xmlcolors.css",
	    path: "/static/js/CodeMirror/",
	    content: target.value,
            reindentOnLoad: true,
            textWrapping: false,
            saveFunction: function() {
                if (settings.save) {
                    settings.save();
                }
                if (self.modified) {
                    if (settings.modified_end) {
                        settings.modified_end();
                    }
                    self.modified = false;
                }
            },
            onChange: function() {
                if (!self.modified) {
                    self.modified = true;
                    if (settings.modified_begin) {
                        settings.modified_begin();
                    }
                }
            },
	    initCallback: function(editor) {
	        // Perform an instant autoresize function, and schedule an autoresize
	        // check whenever a highlight change might have happened.
	        autoResize(true);
	        var scheduleHighlight = editor.editor.scheduleHighlight;
	        editor.editor.scheduleHighlight = function() {
	            this.parent.clearTimeout(this.resizeTimeout);
	            this.resizeTimeout = this.parent.setTimeout(autoResize, this.options.passDelay + 10);
	            return scheduleHighlight.apply(this);
	        };
	    }

        });
    }

    MirrorFrame.prototype = {
        add_to_xml: function(text, options) {
            var settings, pos, linecontent, endadjust = 0;
            settings = $.extend({
                'startnewline': true, 
                'endline': true,
                'cursoroffset': 1
            }, options);

            if (settings.startnewline) {
                // If we're at the end of a non-empty line, insert a newline first.
                try {
	            pos = this.editor.cursorPosition();
	            linecontent = this.editor.lineContent(pos.line);
                    if ($.trim(linecontent).length > 0 &&
	                linecontent.length === pos.character) {
	                text = "\n" + text;
	                endadjust += 1;
	            }
	        } catch(InvalidLineHandle) {}
            }
            if (settings.endline) {
                // If we're not at the end of a line, append a newline.
                try {
	            pos = this.editor.cursorPosition();
	            linecontent = this.editor.lineContent(pos.line);
                    if (pos.character !== linecontent.length) {
	                text = text + "\n";
	                endadjust -= 1;
	            }
	        } catch(InvalidLineHandle) {}
            }
            // If we're at the end of the entry, append a newline.
            try {
	        pos = this.editor.cursorPosition();
	        linecontent = this.editor.lineContent(pos.line);
                if (pos.line == this.editor.lastLine()) {
	            text = text + "\n";
	        }
	    } catch(InvalidLineHandle) {}

            this.editor.replaceSelection(text);

            if (settings.cursoroffset !== undefined) {
                endadjust += settings.cursoroffset;
            }
            try {
                while (endadjust < 0) {
                    this.editor.jumpToLine(this.editor.prevLine(this.editor.cursorLine()));
                    endadjust += 1;
                }
                while (endadjust > 0) {
                    this.editor.jumpToLine(this.editor.nextLine(this.editor.cursorLine()));
                    endadjust -= 1;
                }
            } catch(InvalidLineHandle) {}

            try {
                var line = this.editor.cursorLine();
                this.editor.reindent();
                this.editor.jumpToLine(line);
            } catch(InvalidLineHandle) {}
        }
    };

    $.fn.expandXmlArea = function(options) {
        return this.each(function(){
            $(this).data('editor', new MirrorFrame(this, options));
        });
    };
})(jQuery);
