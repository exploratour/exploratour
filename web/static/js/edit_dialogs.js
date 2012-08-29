var current_dialog = null;

function close_dialog() {
    if (current_dialog) {
        current_dialog.dialog("close");
        current_dialog.dialog("destroy");
        current_dialog = null;
    }
};

var display_opts_names = {
    full: "Full size",
    inline: "Inline",
    thumb: "Thumbnail",
    icon: "Icon",
    icontext: "Icon and text",
    text: "Text link"
};

// Append a file display-type picker to the dialog supplied.
function dialog_append_file_display_picker(dialog, display_opts, display) {
    var displayinput;
    if (display_opts.length == 1) {
        displayinput = $("<input type='hidden'>");
        displayinput.val(display_opts[0]);
        dialog.append(displayinput);
    } else {
        dialog.append($("<label>").text("Display style:"));
        displayinput = $("<select class='display'/>");
        $.each(display_opts, function(i, v) {
            displayinput.append($("<option value='" + v + "'>" +
                                  display_opts_names[v] + "</option>"));
        });
        displayinput.find('option[value=' + display + ']').attr({selected: 'selected'})
        dialog.append(displayinput);
        dialog.append("<br>");
    }

    return displayinput;
}

// A dialog for picking the display type and associated parameters for a file.
function dialog_pick_file_display(obj, success) {
    var dialog, displayinput, altinput, titleinput, display_opts;
    dialog = $("<div title='File display options'>");
    dialog.append($("<label>").text("Source:"));
    dialog.append($("<span>").text(obj.src));
    dialog.append("<br>");
    dialog.append($("<label>").text("Mimetype:"));
    dialog.append($("<span>").text(obj.mimetype));
    dialog.append("<br>");

    display_opts = obj.display_opts;
    if (obj.display_opts_fn) {
        display_opts = obj.display_opts_fn(obj.mimetype);
    }

    displayinput = dialog_append_file_display_picker(dialog, display_opts,
                                                     obj.display);
    dialog.append($("<label>").text("Alt text:"));
    dialog.append($("<input class='alt' type='text' style='width: 300px'>").attr({value: obj.alt}));
    dialog.append("<br>");
    dialog.append($("<label>").text("Title:"));
    dialog.append($("<input class='title' type='text' style='width: 300px'>").attr({value: obj.title}));
    dialog.append("<br>");

    altinput = $(dialog.find('input.alt'));
    titleinput = $(dialog.find('input.title'));

    function submit() {
        obj.display = displayinput.val();
        obj.alt = altinput.val();
        obj.title = titleinput.val();
        success(obj);
        close_dialog();
    }
    close_dialog();
    current_dialog = dialog;
    current_dialog.dialog({
        buttons: {
            "Insert": submit,
            "Cancel": close_dialog
        },
        width: 600,
        closeOnEscape: true
    });
    titleinput.focus();
    displayinput.onEnter(submit);
    return false;
}

// A dialog for embedding a link in text
function dialog_embedded_link_type(obj, success) {
    var dialog, display_input, linktype_input;
    dialog = $("<div title='Pick link type'>");

    linktype_input = $("<select class='linktype'/>");
    linktype_input.append($("<option value='file'>File</option>"));
    linktype_input.append($("<option value='record'>Record</option>"));
    linktype_input.append($("<option value='collection'>Collection</option>"));
    linktype_input.append($("<option value='search'>Search</option>"));
    linktype_input.append($("<option value='url'>URL</option>"));
    $("option[value=" + obj.linktype + "]", linktype_input).attr("selected", "selected");
    dialog.append(linktype_input);
    dialog.append("<br>");

    display_input = dialog_append_file_display_picker(dialog,
        ['icon', 'text'], obj.display);
    dialog.append("<br>");

    dialog.append($("<label>").text("Display text:"));
    text_input = $("<input type='text' style='width: 300px'>").attr({value: obj.text});
    dialog.append(text_input);
    dialog.append("<br>");

    dialog.append($("<label>").text("Link target:"));
    target_input = $("<input type='text' style='width: 300px'>").attr({value: obj.target});
    error_elt = $("<span class='error'>");
    dialog.append(target_input);
    dialog.append(error_elt);


    function submit() {
        obj.target = target_input.val();
        if (!obj.target) {
            error_elt.text("(Required)");
            return;
        }

        obj.linktype = linktype_input.val();
        obj.display = display_input.val();
        obj.text = text_input.val();
        if (!(obj.text) && obj.display == 'text') {
            obj.text = '[link]';
        };
        success(obj);
        close_dialog();
    }
    close_dialog();
    current_dialog = dialog;
    current_dialog.dialog({
        buttons: {
            "Insert": submit,
            "Cancel": close_dialog
        },
        width: 600,
        closeOnEscape: true
    });
    linktype_input.focus();
    display_input.onEnter(submit);
    return false;
};

// A dialog with a single text input.
function dialog_single_input(title, label, defval, success) {
    var dialog, label_elt, error_elt, nameinput;
    dialog = $("<div>").attr({title: title});
    label_elt = $("<label>");
    nameinput = $("<input type='text' style='width: 95%'>").attr({value: defval});
    error_elt = $("<div class='error'>");
    dialog.append(label_elt.text(label));
    dialog.append(nameinput);
    dialog.append(error_elt);
    function submit() {
        var val = nameinput.val();
        if (val) {
            success(val); 
            close_dialog();
        } else {
            error_elt.text("(Required)");
        }
    }
    close_dialog();
    current_dialog = dialog;
    current_dialog.dialog({
        buttons: {
            "Insert": submit,
            "Cancel": close_dialog
        },
        width: 600,
    });
    nameinput.focus();
    nameinput.select();
    nameinput.onEnter(submit);
    return false;
};

function dialog_insert_group(success) {
    return dialog_single_input("Insert a group", "Group name", "", function(name) {
        if (name !== '') {
            success(name);
        }
    });
};

function dialog_insert_field_date(success) {
    return dialog_single_input("Insert a date field", "Field name", "Date", function(name) {
        if (name !== '') {
            success(name);
        }
    });
};

function dialog_insert_field_file(success) {
    var dialog, nameinput, displayinput;
    dialog = $("<div title='Insert a file field'>" +
               "<label>Field name:</label>" +
               "<input type='text' class='name' style='width: 400px'><br/>" +
               "<div class='error'/>" +
               "</div>");
    displayinput = dialog_append_file_display_picker(dialog,
        ['full', 'inline', 'thumb', 'icon', 'text'], 'inline');
    nameinput = $(dialog.find('input.name'));
    error_elt = $(dialog.find('div.error'));
    function submit() {
        var name, display;
        name = nameinput.val();
        display = displayinput.val();
        if (name) {
            success(name, display);
            close_dialog();
        } else {
            error_elt.text("(field name is required)")
        }
    }
    close_dialog();
    current_dialog = dialog;
    current_dialog.dialog({
        buttons: {
            "Insert": submit,
            "Cancel": close_dialog
        },
        width: 600,
    });
    nameinput.focus();
    nameinput.onEnter(submit);
    return false;
};

function dialog_insert_field_location(success) {
    return dialog_single_input("Insert a location field", "Field name", "Location", function(name) {
        if (name !== '') {
            success(name);
        }
    });
};

function dialog_insert_field_link(success) {
    var dialog, nameinput, displayinput;
    dialog = $("<div title='Insert a link field'>" +
               "<label>Field name:</label>" +
               "<input type='text' class='name' style='width: 400px'><br/>" +
               "<div class='error'/>" +
               "<label>Link type:</label>" +
               "<select class='linktype'>" +
               "<option value='record'>Record</option>" +
               "<option value='collection'>Collection</option>" +
               "<option value='search'>Search</option>" +
               "<option value='url'>Url</option>" +
               "</select>" +
               "</div>");
    nameinput = $(dialog.find('input.name'));
    error_elt = $(dialog.find('div.error'));
    linktypeinput = $(dialog.find('select.linktype'));
    function submit() {
        var name, linktype;
        name = nameinput.val();
        linktype = linktypeinput.val();
        if (name) {
            success(name, linktype);
            close_dialog();
        } else {
            error_elt.text("(field name is required)")
        }
    }
    close_dialog();
    current_dialog = dialog;
    current_dialog.dialog({
        buttons: {
            "Insert": submit,
            "Cancel": close_dialog
        },
        width: 600,
    });
    nameinput.focus();
    nameinput.onEnter(submit);
    return false;
};

function dialog_insert_field_number(success) {
    return dialog_single_input("Insert a numeric field", "Field name", "", function(name) {
        if (name !== '') {
            success(name);
        }
    });
};

function dialog_insert_field_text(success) {
    return dialog_single_input("Insert an text field", "Field name", "", function(name) {
        if (name !== '') {
            success(name);
        }
    });
};

function dialog_insert_field_tag(success) {
    return dialog_single_input("Insert a tag field", "Field name", "", function(name) {
        if (name !== '') {
            success(name);
        }
    });
};

function dialog_insert_field_title(success) {
    return dialog_single_input("Insert a title field", "Field name", "Record Title", function(name) {
        if (name !== '') {
            success(name);
        }
    });
};
