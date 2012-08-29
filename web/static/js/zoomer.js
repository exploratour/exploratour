function init_zoomer(w, h, imgbox, img, endofpage) {
  var curr_size = 'small';
  var vp_height, vp_width, sw, sh;

  function set_box_size() {
    vp_height = $(window).height() - imgbox.offset().top - 4;
    if (endofpage) {
       vp_height -= (endofpage.offset().top - imgbox.offset().top -
                     imgbox.height()) + imgbox.outerHeight();
       if (vp_height < 500) {
           vp_height = 500;
       }
    }
    vp_width = $(window).width() - imgbox.offset().left - 2;
    imgbox.width(vp_width)
          .height(vp_height);
  }

  function getpanpos(evt) {
      var offset = imgbox.offset();
      var imgx = evt.pageX - offset.left;
      var imgy = evt.pageY - offset.top;

      var px = Math.floor(w * (imgx / vp_width) - vp_width / 2);
      var py = Math.floor(h * (imgy / vp_height) - vp_height / 2);
      if (px >= w - vp_width) px = w - vp_width - 1;
      if (py >= h - vp_height) py = h - vp_height - 1;
      if (px < 0) px = 0;
      if (py < 0) py = 0;

      return [-px, -py];
  }

  function autopan(evt) {
      panpos = getpanpos(evt);
      img.css({
         left: panpos[0] + 'px',
         top: panpos[1] + 'px'
      });

      evt.preventDefault();
  }

  function small(evt, immediate) {
      var props = {
          top: '0px',
	  left: '0px',
	  width: sw,
	  height: sh
      };
      img.stop(true,true).css({
          cursor: 'move'
      });
      if (immediate) {
          img.css(props);
          imgbox.unbind('mousemove', autopan);
      } else {
          img.animate(props, 'fast', function() {
              imgbox.unbind('mousemove', autopan);
          });
      }
  }

  function large(evt) {
      if (evt) {
        panpos = getpanpos(evt);
      } else {
        panpos = [0, 0];
      }
      img.stop(true,true).css({
          cursor: 'move'
      }).animate({
          left: panpos[0] + 'px',
	  top: panpos[1] + 'px',
	  width: w,
	  height: h
      }, 'fast', function() {
          imgbox.bind('mousemove', autopan);
      });
  }

  function set_size(evt, immediate) {
      set_box_size();
      sw = w;
      sh = h;
      if (sh > vp_height) {
          sw = sw * (vp_height / sh);
          sh = vp_height;
      }
      if (sw > vp_width) {
          sh = sh * (vp_width / sw);
          sw = vp_width;
      }

      if (curr_size == 'small') {
          small(evt, immediate);
      } else {
          large(evt, immediate);
      }
  }

  function toggle(evt) {
      if (curr_size == 'small') {
          curr_size = 'large';
      } else {
          curr_size = 'small';
      }
      set_size(evt);
  }

  function init() {
      img.css({
        position: 'relative',
        top: '0px',
        left: '0px'
      });
      imgbox.css({
        position: 'relative',
	overflow: 'hidden'
      });
      set_size(null, true);
      $(window).resize(function() { set_size(); });
      img.click(toggle);
  }

  init();
};
