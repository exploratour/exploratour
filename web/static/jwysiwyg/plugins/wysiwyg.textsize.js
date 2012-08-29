/**
 * textsize plugin
 * 
 * Depends on jWYSIWYG
 */
(function($) {
if (undefined === $.wysiwyg) {
	throw "wysiwyg.textsize.js depends on $.wysiwyg";
}

/*
 * Wysiwyg namespace: public properties and methods
 */
var textsize = {
	name: "textsize",
	version: "1",

	run: function(Wysiwyg, name, revname) {
		var r = Wysiwyg.getInternalRange();
                if (r === null) return;

                var selection = Wysiwyg.getInternalSelection();
                var newranges = [];
                function addRange(start, end) {
                        var doc = Wysiwyg.innerDocument();
                        var newRange = doc.createRange();
                        newRange.setStart(start, 0);
                        newRange.setEndAfter(end, 0);
                        newranges.push(newRange);
                }
                for (var i = 0; i < selection.rangeCount; i++) {
                        var r = selection.getRangeAt(i);

                        var node = r.commonAncestorContainer;
                        if (node.nodeType === 3) {
                            node = node.parentNode;
                        }

                        if (node.nodeName.toLowerCase().match(revname)) {
                            // The "opposite" node to the one we want to insert
                            // is wrapping all our content - we just want to
                            // remove it.
                            var newnode = $(node).contents();
                            $(node).replaceWith(newnode);
                            addRange(newnode[0], newnode[newnode.length - 1]);
                        } else {
                            // Pull the content out, insert it into a new node
                            // with the appropriate tag, and then insert it
                            // again.  Chromium loses the selection when you do
                            // this (and firefox appears to set the selection
                            // incorrectly in some cases), so we then need to
                            // set the selection again.
                            var doc = Wysiwyg.innerDocument();
                            var newNode = doc.createElement(name);
                            var newChild = r.extractContents();
                            newNode.appendChild(newChild);
                            r.insertNode(newNode);

                            addRange(newNode, newNode);
                        }
                }
                selection.removeAllRanges();
                for (var i = 0; i < newranges.length; i++) {
                        selection.addRange(newranges[i]);
                }
	}
};

$.wysiwyg.plugin.register(textsize);

})(jQuery);
