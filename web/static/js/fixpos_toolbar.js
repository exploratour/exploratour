$(function() {
    $(".keep_on_screen").each(function(num, item) {
        var origpos, win, proxy;

        function check() {
            var scrolltop = win.scrollTop();
            if (origpos.top < scrolltop) {
                if (!proxy) {
                    proxy = $("<div>").css({height: item.height()});
                    item.after(proxy);
                    item.css({position: "fixed", top: 0, left: proxy.offset().left - $(window).scrollLeft(), width: item.width()});
                    item.addClass("kept_on_screen");
                }
            } else if (origpos.top >= scrolltop) {
                if (proxy) {
                    item.css({position: "static", top: "",
                              width: ""});
                    item.removeClass("kept_on_screen");
                    proxy.remove();
                    proxy = undefined;
                }
            }
        }

        function scroll() {
            check();
            if (proxy) {
                item.css({left: proxy.offset().left - $(window).scrollLeft()});
            }
        }

        function after_layout_change() {
            check();
            if (proxy) {
                origpos = proxy.position()
                item.width(proxy.width());
                proxy.css({height: item.height()});
            } else {
                origpos = item.position()
            }
        }

        item = $(item);
        origpos = item.position();
        win = $(window);
        win.scroll(scroll);
        win.load(after_layout_change);
        win.resize(after_layout_change);
        // Need to re-calculate the position after the menu has been collapsed.
        setTimeout(after_layout_change, 0);
    });
});
