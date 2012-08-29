$(function() {
    function init_datepicker(item) {
    item.datepicker({
        autoSize: true,
        changeMonth: true,
        changeYear: true,
        constrainInput: false,
        showButtonPanel: true,
        yearRange: '100:c',
        showOn: 'button',
        dateFormat: 'dd/mm/yy',
        defaultDate: user_lastdate || null,
        onSelect: function(dateText, inst) {
            $.post("/user/lastdate", {lastdate: dateText});
            $(".fieldentry_date").datepicker("option", "defaultDate", dateText);
        }
    })};
    init_datepicker($(".fieldentry_date"));

    /* Open a dialog to pick a file, followed by picking its display
       attributes. Call completed when user completes picking, with
       src, mimetype */
    function select_file(obj, completed) {
        var initialpath = obj.src;
        if (initialpath == "") {
            initialpath = last_dir;
        } else {
            var idx = initialpath.lastIndexOf("/");
            if (idx != -1) {
                initialpath = initialpath.substring(0, idx + 1);
            }
        }

        new FileSelector(initialpath, obj.mimepattern, function(data) {
            if (data.dirpath != "") {
                last_dir = data.dirpath;
            }
            obj.src = data.src;
            obj.mimetype = data.mimetype;
            dialog_pick_file_display(obj, completed);
        });
    }

    function setup_file_buttons(_, elt) {
        elt = $(elt);
        var input_src = elt.find("input[type=text].src"),
            input_num = input_src.attr('id').substr(4),
            input_mimetype = elt.find("input[type=text].mimetype"),
            input_display = elt.find("input[type=text].display"),
            input_alt = elt.find("input[type=text].alt"),
            input_title = elt.find("input[type=text].title"),
            thumbholder = elt.find("span.thumbnail"),
            pickfile_button = elt.find("button.pickfile"),
            displayopt_button = elt.find("button.displayopt"),
            setval_request = null,
            params;


        elt.find(".nojsinputs").hide();
        pickfile_button.show().click(open_file_selector);
        displayopt_button.click(open_displayopt_selector);
        set_value({src: input_src.val(),
                   mimetype: input_mimetype.val(),
                   display: input_display.val(),
                   alt: input_alt.val(),
                   title: input_title.val()});

        function set_value(obj) {
            if (obj.src == "") {
                pickfile_button.text("Insert file");
                thumbholder.hide();
                displayopt_button.hide();
            } else {
                pickfile_button.text("Change file");
                thumbholder.show();
                displayopt_button.show();
            }
            if (input_src.val() == obj.src &&
                input_mimetype.val() == obj.mimetype &&
                input_display.val() == obj.display &&
                input_alt.val() == obj.alt &&
                input_title.val() == obj.title) {
                return;
            }

            // Set the params to new values.
            input_src.val(obj.src);
            input_mimetype.val(obj.mimetype);
            input_display.val(obj.display);
            input_alt.val(obj.alt);
            input_title.val(obj.title);

            // Fetch new element over ajax to update preview display.
            if (setval_request != null) {
                setval_request.abort();
                setval_request = null;
            }
            params = $(':input', elt.parent()).serializeArray();
            params.push({name: "ordering", value: input_num});
            params.push({name: "start_count", value: input_num});
            setval_request = $.ajax({
                url: '/record_edit_fragment',
                data: params,
                success: function(data, status, request) {
                    var p = elt.parent();
                    p.before(data);
                    $(".fieldentry_file", p.prev()).each(setup_file_buttons);
                    p.remove();
                }
            });
        }

        function display_opts_from_mimetype(mimetype) {
            if (mimetype.substr(0, 6) == 'image/') {
                return ['full', 'inline', 'thumb', 'icon', 'icontext', 'text']
            } else {
                return ['inline', 'icon', 'icontext', 'text']
            }
        }

        function open_file_selector(ev) {
            var obj = {
                src: input_src.val(),
                mimetype: input_mimetype.val(),
                display: input_display.val(),
                display_opts_fn: display_opts_from_mimetype,
                alt: input_alt.val(),
                title: input_title.val(),
                mimepattern: ''
            };
            ev.preventDefault();
            select_file(obj, set_value);
        }

        function open_displayopt_selector(ev) {
            ev.preventDefault();
            var obj = {
                src: input_src.val(),
                mimetype: input_mimetype.val(),
                display: input_display.val(),
                display_opts_fn: display_opts_from_mimetype,
                alt: input_alt.val(),
                title: input_title.val()
            };
            dialog_pick_file_display(obj, set_value);
        }
    }

    var last_dir = media_lastdir;
    $(".fieldentry_file").each(setup_file_buttons);

    function init_textfield(item) {
        var wysiwyg = item.wysiwyg({
            autoGrow: true,
            initialContent: "<p></p>",
            initialMinHeight: 100,
            css: STATIC_ASSETS_URL + "jwysiwyg/editor.css",
            controls: {
                h1: { groupIndex: 7.1 },
                h2: { groupIndex: 7.1 },
                h3: { groupIndex: 7.1 },
                h4: {
                    groupIndex: 7.1,
                    visible: true,
                    className: "h4",
                    command: ($.browser.msie || $.browser.safari) ? "FormatBlock" : "heading",
                    "arguments": ($.browser.msie || $.browser.safari) ? "<h4>" : "h4",
                    tags: ["h4"],
                    tooltip: "Header 4"
                },

                code: {
                    visible: false
                },

/* These buttons don't currently work.
                copy: {
                    visible: true
                },
                cut: {
                    visible: true
                },
                paste: {
                    visible: true
                },
 */

                increaseFontSize: {
                    visible: true,
                    exec: function() {
                        $.wysiwyg.textsize.run(this, "big", "small");
                    }
                },
                decreaseFontSize: {
                    visible: true,
                    exec: function() {
                        $.wysiwyg.textsize.run(this, "small", "big");
                    }
                },

                foreColor: {
                    groupIndex: 11,
                    visible: true,
                    css: {
                        "color": function(cssValue, Wysiwyg) {
                            var defaultTextareaColor = Wysiwyg.editor.css("color");

                            if (cssValue !== defaultTextareaColor) {
                                return true;
                            }

                            return false;
                        }
                    },
                    exec: function() {
                        if ($.wysiwyg.controls.colorpicker) {
                            $.wysiwyg.controls.colorpicker.init(this, "fore");
                        }
                    },
                    tooltip: "Set text colour"
                },
                backColor: {
                    groupIndex: 11,
                    visible: true,
                    exec: function() {
                        if ($.wysiwyg.controls.colorpicker) {
                            $.wysiwyg.controls.colorpicker.init(this, "back");
                        }
                    },
                    tooltip: "Set background colour"
                },

                html: {
                    visible: true
                },

                pre: {
                    groupIndex: 7,
                    visible: true,
                    tooltip: "Preformatted text",
		    exec: function () {
		        var wysiwyg = this, command, arguments,
			    selection, doc = wysiwyg.innerDocument();
			if ($.browser.msie || $.browser.safari) {
			    command = "FormatBlock";
			    arguments = "<pre>";
			} else {
			    command = "heading";
			    arguments = "pre";
			}

			function GetNextLeaf (node) {
			    while (!node.nextSibling) {
				node = node.parentNode;
				if (!node) {
				    return node;
				}
			    }
			    var leaf = node.nextSibling;
			    while (leaf.firstChild) {
				leaf = leaf.firstChild;
			    }
			    return leaf;
			}

			selection = wysiwyg.getInternalSelection();
			for (var i = 0; i < selection.rangeCount; i++) {
			    // For each range in the selection, remove any newlines.
			    var sel_range = selection.getRangeAt(i);
			    var node = sel_range.commonAncestorContainer;
			    while (node.firstChild) {
				node = node.firstChild;
			    }
			    while (node) {
				var item_range = doc.createRange();
				item_range.selectNode(node);
				//item_range.setStart(node, 0);
				//item_range.setEnd(node, 0);

				// Check if item_range intersects sel_range.
				if (sel_range.compareBoundaryPoints(sel_range.END_TO_START, item_range) <= 0 &&
				    sel_range.compareBoundaryPoints(sel_range.START_TO_END, item_range) >= 0) {
				    node.textContent = node.textContent.replace(/\s+/gm, ' ');
				}

				if (node.nodeType === 3) {
				    node = node.parentNode;
				}
				node = GetNextLeaf(node);
			    }
			}

			{
			    this.ui.focus();
			    this.ui.withoutCss();
			    this.editorDoc.execCommand(command, !1, arguments)
			}
		    }
                },

                customInsertImage: {
                    groupIndex: 6,
                    visible: true,
                    exec: function () {
                        var wysiwyg = this,
                            fileobj = false, selection, doc = wysiwyg.innerDocument();

                        // Set fileobj to be the first img with a data-type=file
                        // attribute in the selection; or false if no such node.
                        selection = wysiwyg.getInternalSelection();
                        for (var i = 0; i < selection.rangeCount; i++) {
                            var r = selection.getRangeAt(i);

                            var node = r.commonAncestorContainer;
                            if (node.nodeType === 3) {
                                node = node.parentNode;
                            }

                            var elements = doc.getElementsByTagName('img');
                            for (var j = 0; j < elements.length; j++) {
                                var element = elements[j];
                                if (element.getAttribute('data-type') == "file") {
                                    var sourceRange = doc.createRange();
                                    sourceRange.setStart(element, 0);
                                    sourceRange.setEnd(element, 0);

                                    // Check if sourceRange is inside r.
                                    if (r.compareBoundaryPoints(r.START_TO_START, sourceRange) <= 0 &&
                                        r.compareBoundaryPoints(r.END_TO_END, sourceRange) >= 0) {
                                        fileobj = $(element);
                                        break;
                                    }
                                }
                            }

                            if (fileobj) break;
                        }
                        
                        choose_embedded_file(wysiwyg, fileobj);
                    },
                    tooltip: "Insert image"
                },

                customCreateLink: {
                    groupIndex: 6,
                    visible: true,
                    exec: function () {
                        var wysiwyg = this,
                            linkobj = false, selection, doc = wysiwyg.innerDocument();

                        // Set linkobj to be the first <a> with a data-type=link
                        // attribute in the selection; or false if no such node.
                        selection = wysiwyg.getInternalSelection();
                        for (var i = 0; i < selection.rangeCount; i++) {
                            var r = selection.getRangeAt(i);

                            var node = r.commonAncestorContainer;
                            if (node.nodeType === 3) {
                                node = node.parentNode;
                            }

                            var elements = doc.getElementsByTagName('a');
                            for (var j = 0; j < elements.length; j++) {
                                var element = elements[j];
                                if (element.getAttribute('data-type') == "link") {
                                    var sourceRange = doc.createRange();
                                    sourceRange.setStart(element, 0);
                                    sourceRange.setEnd(element, 0);

                                    // Check if sourceRange is inside r.
                                    if (r.compareBoundaryPoints(r.START_TO_START, sourceRange) <= 0 &&
                                        r.compareBoundaryPoints(r.END_TO_END, sourceRange) >= 0) {
                                        linkobj = $(element);
                                        break;
                                    }
                                }
                            }

                            if (linkobj) break;
                        }
 
                        choose_embedded_link(wysiwyg, linkobj);
                    },
                    tags: ["a"],
                    tooltip: "Insert link"
                },

                insertImage: { visible: false },
                createLink: { visible: false },
                insertTable: { visible: false }
            }
        });

        wysiwyg.each(function() {
            var wysiwyg = $(this).data('wysiwyg');
            var editorDoc = $(wysiwyg.editorDoc);

            /* Set the sources of any embedded media files. */
            editorDoc.find("img[data-type=file]").each(function() {
                display_embedded_file(wysiwyg, $(this));
            });

            editorDoc.find("a[data-type=link]").each(function() {
                display_embedded_link(wysiwyg, $(this));
            });
            editorDoc.bind("mouseup paste", function() {
                // Do a grow after a short delay.  If we grow immediately, it
                // happens before the paste.
                // FIXME - find a way to change after the paste has happened,
                // and any images involved in the paste have been loaded.
                setTimeout(function() {wysiwyg.ui.grow()}, 100);
            });

            // Resize as appropriate.
            setTimeout(function() {
                editorDoc.trigger("editorRefresh.wysiwyg");
            }, 100);

            $("img[data-type=file]", editorDoc).live("click", function(ev) {
                choose_embedded_file(wysiwyg, $(this));
            });
            $("img[data-type=link]", editorDoc).live("click", function(ev) {
                choose_embedded_link(wysiwyg, $(this));
            });
        });

    }
    init_textfield($(".fieldentry_text"));

    function display_embedded_file(wysiwyg, elem) {
        var src = elem.attr('data-src');
        elem.empty();
        if (src && elem.attr('data-mimetype').substr(0, 6) == 'image/') {
            var displaytype = elem.attr('data-display');
            switch (displaytype) {
                case 'full':
                    elem.attr('src', MEDIA_BASE_URL + src);
                    break;
                case 'inline':
                    elem.attr('src', '/thumbnail?path=' + encodeURIComponent(src) + '&width=800&height=600');
                    break;
                default:
                    elem.attr('src', '/thumbnail?path=' + encodeURIComponent(src) + '&width=256&height=256');
                    break;
            }
        } else {
            // Non-image files shouldn't be embedded, so display a complaint icon.
            elem.attr('src', STATIC_ASSETS_URL + "icons/thumbs/unknown.png");
        }
        elem.load(function() {
            $(wysiwyg.editorDoc).trigger("editorRefresh.wysiwyg");
        });
    }

    function display_embedded_link(wysiwyg, elem) {
        var linktype = elem.attr('data-linktype'),
            displaytype = elem.attr('data-display'),
            major_mimetype, icontype;
        elem.removeClass('exp_linkicon exp_linktext exp_image exp_audio ' +
                         'exp_video exp_search exp_url exp_collection ' +
                         'exp_record exp_unknown');
        if (displaytype == 'icon') {
            switch (linktype) {
                case 'file':
                    major_mimetype = (elem.attr('data-mimetype') || '')
                        .split('/')[0];
                    if (major_mimetype == 'image' ||
                        major_mimetype == 'audio' ||
                        major_mimetype == 'video'
                       ) {
                        icontype = major_mimetype;
                    } else {
                        icontype = 'unknown';
                    }
                    break;
                case 'search':
                    icontype = linktype;
                    break;
                case 'url':
                    icontype = linktype;
                    break;
                case 'record':
                    icontype = linktype;
                    break;
                case 'collection':
                    icontype = linktype;
                    break;
            }
            elem.addClass('exp_linkicon');
            elem.addClass('exp_' + icontype);
        } else {
            elem.addClass('exp_linktext');
        }
        elem.attr('contenteditable', "false");
        elem.unbind('click');
        elem.click(function(ev) {
            choose_embedded_link(wysiwyg, elem);
        });
    }


    function insert_file_in_text(obj) {
        var elem;
        if (!obj.elem) {
            obj.wysiwyg.insertHtml('<img data-type="#jwysiwyg_temp#"></img>');
            elem = $(obj.wysiwyg.getElementByAttributeValue(
                "img", "data-type", "#jwysiwyg_temp#"));
        } else {
            elem = obj.elem;
        }
        elem.attr('data-type', 'file');
        elem.attr('data-src', obj.src);
        elem.attr('data-display', obj.display);
        elem.attr('data-mimetype', obj.mimetype);
        elem.attr('data-alt', obj.alt);
        elem.attr('data-title', obj.title);
        display_embedded_file(obj.wysiwyg, elem);
    };

    function insert_link_in_text(obj) {
        var elem, selection;
        if (!obj.elem) {
            obj.wysiwyg.insertHtml('<a data-type="#jwysiwyg_temp#"></a>');
            elem = $(obj.wysiwyg.getElementByAttributeValue(
                "a", "data-type", "#jwysiwyg_temp#"));
        } else {
            elem = obj.elem;
        }
        elem.empty();
        elem.attr('data-type', 'link');
        elem.attr('data-linktype', obj.linktype);
        elem.attr('data-target', obj.target);
        elem.attr('data-display', obj.display);
        if (obj.mimetype) {
            elem.attr('data-mimetype', obj.mimetype);
        }
        elem.text(obj.text);

        display_embedded_link(obj.wysiwyg, elem);
        $(obj.wysiwyg.editorDoc).trigger("editorRefresh.wysiwyg");
    };


    function choose_embedded_file(wysiwyg, fileobj) {
        obj = { wysiwyg: wysiwyg };
        if (fileobj) {
            obj.elem = fileobj;
            obj.src = fileobj.attr('data-src') || '';
            obj.mimetype = fileobj.attr('data-mimetype') || '';
            obj.display = fileobj.attr('data-display') || '';
            obj.alt = fileobj.attr('data-alt') || '';
            obj.title = fileobj.attr('data-title') || '';
        } else {
            obj.elem = false;
            obj.src = '';
            obj.mimetype = '';
            obj.display = 'inline';
            obj.alt = '';
            obj.title = '';
        }
        obj.display_opts = ['full', 'inline', 'thumb'];
        obj.mimepattern = 'image/*';

        select_file(obj, insert_file_in_text);
    };

    function choose_embedded_link(wysiwyg, linkobj) {
        var obj = { wysiwyg: wysiwyg };
        if (linkobj) {
            obj.elem = linkobj;
            obj.display = linkobj.attr('data-display') || '';
            obj.linktype = linkobj.attr('data-linktype') || '';
            obj.target = linkobj.attr('data-target') || '';
            obj.mimetype = linkobj.attr('data-mimetype') || '';
            obj.text = linkobj.text();
        } else {
            obj.elem = false;
            obj.display = '';
            obj.linktype = '';
            obj.target = '';
            obj.mimetype = '';
            obj.text = '';
        }
        obj.display_opts = ['text', 'icon'];
        obj.mimepattern = '';

        dialog_embedded_link_type(obj, insert_link_in_text);
    };

    $.wysiwyg.rmFormat.enabled = true;

    /// Add new field buttons.
    function add_buttons() {
        var addfield_request = null;

        function insert_field(params) {
            var ordering_elt = $("input[name='ordering']"),
                ordering = ordering_elt.val().split(','),
                maxidx = 0, newidx, params, lastnum = 0;
            $.each(ordering, function() {
                var idx;
                if (this == '') return;
                idx = parseInt(this);
                if (idx > maxidx) {
                    maxidx = idx;
                }
                lastnum = idx;
            });
            if (!(params.after)) {
                params.after = lastnum;
            }
            newidx = maxidx + 1;

            /* Fetch new field over ajax. */
            if (addfield_request != null) {
                addfield_request.abort();
                addfield_request = null;
            }
            reqdata = [];
            reqdata.push({name: "ordering", value: newidx});
            reqdata.push({name: "start_count", value: newidx});
            reqdata.push({name: "t_" + newidx, value: "field"});
            reqdata.push({name: "f_" + newidx, value: params.value});
            reqdata.push({name: "ft_" + newidx, value: params.type});
            reqdata.push({name: "fl_" + newidx, value: params.level});
            reqdata.push({name: "fn_" + newidx, value: params.name});
            reqdata.push({name: "display_" + newidx, value: params.display});
            addfield_request = $.ajax({
                url: '/record_edit_fragment',
                data: reqdata,
                success: function(data, status, request) {
                    var ordering, previous, i;

                    // Insert into the right place in ordering.
                    ordering = ordering_elt.val().split(','),
                    i = ordering.lastIndexOf(params.after.toString());
                    ordering.splice(i + 1, 0, newidx);
                    ordering_elt.val(ordering.join(","));

                    // Insert new element.
                    previous = $("#item_" + params.after);
                    if (previous.length == 0) {
                        // No previous element found - should only happen when
                        // there are no fields.
                        previous = $("table.simple_record_entry");
                        previous.append(data);
                        init_field(previous.children());
                    } else {
                        previous.after(data);
                        init_field(previous.next());
                    }
                }
                // FIXME - error handling
            });
        }
        function insert_copy_of_field(oldidx) {
            var oldelt = $("input[name='t_" + oldidx + "']").parent();
            insert_field({
                value: "",
                type: $("input[name='ft_" + oldidx + "']").val(),
                level: $("input[name='fl_" + oldidx + "']").val(),
                name: $("input[name='fn_" + oldidx + "']").val(),
                display: $("input[name='display_" + oldidx + "']").val(),
                after: oldidx
            });
        }

        function init_field(item) {
            init_datepicker($(".fieldentry_date", item));
            init_textfield($(".fieldentry_text", item));
            $(".fieldentry_file", item).each(setup_file_buttons);
        }
        function append_field_title_simple(ev) {
            insert_field({ type: 'title', level: 0, name: '', value: '' });
        }
        function append_field_date_simple(ev) {
            insert_field({ type: 'date', level: 0, name: '', value: '' });
        }
        function append_field_location_simple(ev) {
            insert_field({ type: 'location', level: 0, name: '', value: '' });
        }
        function append_field_text_simple(ev) {
            insert_field({ type: 'text', level: 0, name: '', value: '' });
        }
        function append_field_tag_simple(ev) {
            insert_field({ type: 'tag', level: 0, name: '', value: '' });
        }
        function append_field_number_simple(ev) {
            insert_field({ type: 'number', level: 0, name: '', value: '' });
        }
        function append_field_file_simple(ev) {
            insert_field({ type: 'file', level: 0, name: '', value: '',
                           display: 'inline' });
        }
        function append_field_link_simple(ev) {
            insert_field({ type: 'link', level: 0, name: '', value: '' });
        }

        var last_button = $(".edit_toolbar_start");
        function add_button(size, name, title, action) {
            var button = $('<button>')
                .attr({
                      'class': 'button button_' + name
                      })
                .append($('<img>')
                    .attr({
                          'src': '/static/icons/buttons/' + size + '/' + name + '.png',
                          'title': title,
                          'alt': title
                          })
                );
            button.click(function(ev) { ev.preventDefault(); action(ev); });
            button = button.wrap('<li/>').parent();
            last_button.after(button);
            last_button = button;
        };

        add_button(48, "insert_field_title", "Insert title field", append_field_title_simple);
        add_button(48, "insert_field_date", "Insert date field", append_field_date_simple);
        add_button(48, "insert_field_location", "Insert location field", append_field_location_simple);
        add_button(48, "insert_field_text", "Insert text field", append_field_text_simple);
        add_button(48, "insert_field_tag", "Insert tag field", append_field_tag_simple);
        add_button(48, "insert_field_number", "Insert number field", append_field_number_simple);
        add_button(48, "insert_field_file", "Insert file field", append_field_file_simple);
        add_button(48, "insert_field_link", "Insert link field", append_field_link_simple);
        $('input.repeat_field').live("click", function(ev) {
            var idx = this.name.substr(7),
                type = $("input[name='t_" + idx + "']").val();
            if (type == 'field') {
                ev.preventDefault();
                insert_copy_of_field(idx);
            }
        });
    }

    add_buttons();
});
