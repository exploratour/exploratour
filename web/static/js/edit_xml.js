$(function() {
    var editor = $($(".xmleditarea").expandXmlArea({
        save: function() {
            var form = $(editor.editor.wrapping).parents('form');
        },
        modified_begin: function() {
            return;
            $("button.button_save").attr({disabled: null});
            var imgs = $("button.button_save img"),
                oldsrc = imgs.attr('src'),
                newsrc = oldsrc;
            if (oldsrc.substring(oldsrc.length - 13) == '_disabled.png') {
                newsrc = oldsrc.substring(0, oldsrc.length - 13) + '.png';
            }
            imgs.attr({src: newsrc});
        },
        modified_end: function() {
            return;
            $("button.button_save").attr({disabled: 'disabled'});
            var imgs = $("button.button_save img"),
                oldsrc = imgs.attr('src'),
                newsrc = oldsrc;
            if (oldsrc.substring(oldsrc.length - 13) != '_disabled.png') {
                newsrc = oldsrc.substring(0, oldsrc.length - 4) + '_disabled.png';
            }
            imgs.attr({src: newsrc});
        },
    })).data('editor');

    function escapeXmlAttr(val) {
        return val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    }

    function dialog_insert_group_xml() {
        return dialog_insert_group(function(name) {
            editor.add_to_xml("<group name=\"" + escapeXmlAttr(name) + "\">\n\n</group>", {cursoroffset: -1});
        });
    };
    function dialog_insert_field_title_xml() {
        return dialog_insert_field_title(function(name) {
            editor.add_to_xml("<field name=\"" + escapeXmlAttr(name) + "\" type=\"title\"></field>");
        });
    };
    function dialog_insert_field_date_xml() {
        return dialog_insert_field_date(function(name) {
            editor.add_to_xml("<field name=\"" + escapeXmlAttr(name) + "\" type=\"date\"></field>");
        });
    };
    function dialog_insert_field_location_xml() {
        return dialog_insert_field_location(function(name) {
            editor.add_to_xml("<field name=\"" + escapeXmlAttr(name) + "\" type=\"location\"></field>");
        });
    };
    function dialog_insert_field_text_xml() {
        return dialog_insert_field_text(function(name) {
            editor.add_to_xml("<field name=\"" + escapeXmlAttr(name) + "\" type=\"text\"></field>");
        });
    };
    function dialog_insert_field_tag_xml() {
        return dialog_insert_field_tag(function(name) {
            editor.add_to_xml("<field name=\"" + escapeXmlAttr(name) + "\" type=\"tag\"></field>");
        });
    };
    function dialog_insert_field_number_xml() {
        return dialog_insert_field_number(function(name) {
            editor.add_to_xml("<field name=\"" + escapeXmlAttr(name) + "\" type=\"number\"></field>");
        });
    };
    function dialog_insert_field_file_xml() {
        return dialog_insert_field_file(function(name, display) {
            editor.add_to_xml("<field name=\"" + escapeXmlAttr(name) + "\" " +
                              "type=\"file\" " +
                              "src=\"\" " +
                              "title=\"\" " +
                              "alt=\"\" " +
                              "display=\"" + escapeXmlAttr(display) + "\"" +
                              "></field>");
        });
    };
    function dialog_insert_field_link_xml() {
        return dialog_insert_field_link(function(name, linktype) {
            editor.add_to_xml("<field name=\"" + escapeXmlAttr(name) + "\" " +
                              "linktype=\"" + escapeXmlAttr(linktype) + "\" " +
                              "type=\"link\"></field>");
        });
    };

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
      button.click(action);
      button = button.wrap('<li/>').parent();
      last_button.after(button);
      last_button = button;
    };

    add_button(48, "insert_field_title", "Insert title field", dialog_insert_field_title_xml);
    add_button(48, "insert_field_date", "Insert date field", dialog_insert_field_date_xml);
    add_button(48, "insert_field_location", "Insert location field", dialog_insert_field_location_xml);
    add_button(48, "insert_field_text", "Insert text field", dialog_insert_field_text_xml);
    add_button(48, "insert_field_tag", "Insert tag field", dialog_insert_field_tag_xml);
    add_button(48, "insert_field_number", "Insert number field", dialog_insert_field_number_xml);
    add_button(48, "insert_field_file", "Insert file field", dialog_insert_field_file_xml);
    add_button(48, "insert_field_link", "Insert link field", dialog_insert_field_link_xml);
    add_button(48, "insert_group", "Insert group", dialog_insert_group_xml);

    var form = $(editor.editor.wrapping).parents('form');
    form.submit(function() {
      editor.modified = false;
      return true;
    });
    $(window).bind('beforeunload', function() {
      return; // FIXME - too buggy to enable yet
      if (editor.modified) {
        return 'There are unsaved modifications on this page.  Leaving this page will discard them.';
      }
    });
});
