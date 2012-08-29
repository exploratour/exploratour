$(function() {
    $('.nojs').hide();
    var options = {
        minWidth: 120,
        arrowSrc: 'arrow_right.gif',
        onClick: function(e, menuItem) {
            $.MenuPlugin.closeAll();
        }
    };
    $('#globalmenu > ul').MenuPlugin(options);
    $('.tabarea').tabs();
    $('img[usemap]').maphilight({ alwaysOn: true });

    $("[data-ac]").each(function() {
        var input = $(this);
        input.autocomplete({
            source: input.data('ac')
        });
    });

    $(".submitonchange").bind("change", function() {
                                $(this).parents("form").submit(); });

    $(".queryentry").each(function() {
        var input = $(this);
        var name = input.attr('name');
        name = name.substr(0, name.length - 1) + "f";
        var finput = $("select[name=" + name + "]");
        var colls = [];
	$("select[name=collid]").each(function(index, item) {
	    colls.push($(item).val());
	});
	input.autocomplete({
	    source: function(request, response) {
	    console.log(request,response);
		$.getJSON("/ac", {
		    term: request.term,
		    field: finput.val(),
		    colls: colls.join(',')
                }, response);
            }
        });
    });

    $(".combobox").combobox();

    // Expand pointed to thing when expand buttons are pressed.
    $("a[data-expand]").live("click", function (ev) {
        var expander = $(this),
            expandid = expander.data('expand'),
            expandblk = $('[id="tree_' + expandid + '"]'),
            shrinker = $('a[data-shrink="' + expandid + '"]');
        ev.preventDefault();
        expander.hide();
        expandblk.show();
        shrinker.show();
    });
    $("a[data-shrink]").live("click", function (ev) {
        var shrinker = $(this),
            expandid = shrinker.data('shrink'),
            expandblk = $('[id="tree_' + expandid + '"]'),
            expander = $('a[data-expand="' + expandid + '"]');
        ev.preventDefault();
        expander.show();
        shrinker.hide();
        expandblk.hide();
    });
    $('.collapsible').each(function () {
        var self = $(this),
            idstr = self.attr('id').substr(5);
        if (self.data('shrunk')) {
            $('a[data-expand="' + idstr + '"]').show();
            $('a[data-shrink="' + idstr + '"]').hide();
            $('[id="tree_' + idstr + '"]').hide();
        } else {
            $('a[data-expand="' + idstr + '"]').hide();
            $('a[data-shrink="' + idstr + '"]').show();
            $('[id="tree_' + idstr + '"]').show();
        }
    });
    $('.selectsidebyside').multiselect2side({
        autoSortAvailable: true,
	minSize: 20
    });
    $('.collapse_box .header').click(function() {
	$(this).next().toggle('fast');
	return false;
    }).next().hide();

});
