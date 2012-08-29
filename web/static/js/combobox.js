(function( $ ) {
	$.widget( "ui.combobox", {
		_create: function() {
			var self = this,
				select = this.element.hide(),
				selected = select.children( ":selected" ),
				value = selected.val() ? selected.text() : "",
				emptyval = select.children( ":first" ).text() || "";
			var input = this.input = $( "<input>" )
				.insertAfter( select )
				.val( value )
				.focus( function(ev) {
					var self = $(this);
					if (self.val() == emptyval) {
                        self.val('');
					}
					ev.preventDefault();

					input.autocomplete( "search", "" );
				})
                .blur( function(ev) {
					var self = $(this);
                    if (self.val() == '') {
                        self.val(emptyval);
                    }
                })
				.autocomplete({
					delay: 0,
                    minLength: 0,
                    maxHeight: "10px",
					source: function( request, response ) {
						var matcher = new RegExp( $.ui.autocomplete.escapeRegex(request.term), "i" );
						response( select.children( "option" ).map(function() {
							var text = $( this ).text();
							if ( this.value && ( !request.term || matcher.test(text) ) )
								return {
									label: text.replace(
										new RegExp(
											"(?![^&;]+;)(?!<[^<>]*)(" +
											$.ui.autocomplete.escapeRegex(request.term) +
											")(?![^<>]*>)(?![^&;]+;)", "gi"
										), "<strong>$1</strong>" ),
									value: text,
									option: this
								};
						}) );
					},
					select: function( event, ui ) {
						ui.item.option.selected = true;
						self._trigger( "selected", event, {
							item: ui.item.option
						});
						select.trigger("change", event);
					},
					change: function( event, ui ) {
						var inputbox = $(this);
						if ( !ui.item ) {
							var entered = inputbox.val(),
							    matcher = new RegExp( "^\\s*" + $.ui.autocomplete.escapeRegex(entered) + "$", "i" ),
								valid = false,
								changed = false;
							select.children( "option" ).each(function() {
								if ( $( this ).text().match( matcher ) ) {
									if (!this.selected) {
										changed = true;
									}
									this.selected = valid = true;
                                    inputbox.val($(this).text());
									return false;
								}
							});
							if ( !valid ) {
								// Invalid value (didn't match anything).
								// Select first child, as a placeholder
								select.children("option:first").each(function() {
								    this.selected = true;
								    inputbox.val($(this).text());
								});

								return false;
							}
						}
					}
				})
				.addClass( "ui-widget ui-widget-content ui-corner-left" );

			input.data( "autocomplete" )._renderItem = function( ul, item ) {
				return $( "<li></li>" )
					.data( "item.autocomplete", item )
					.append( "<a>" + item.label + "</a>" )
					.appendTo( ul );
			};

			this.button = $( "<button type='button'>&nbsp;</button>" )
				.attr( "tabIndex", -1 )
				.attr( "title", "Show All Items" )
				.insertAfter( input )
				.button({
					icons: {
						primary: "ui-icon-triangle-1-s"
					},
					text: false
				})
				.removeClass( "ui-corner-all" )
				.addClass( "ui-corner-right ui-button-icon ui-combobox" )
				.click(function() {
					// close if already visible
					if ( input.autocomplete( "widget" ).is( ":visible" ) ) {
						input.autocomplete( "close" );
						return;
					}

					// work around a bug (likely same cause as #5265)
					$( this ).blur();

					// pass empty string as value to search for, displaying all results
					input.autocomplete( "search", "" );
					input.focus();
				});
		},

		destroy: function() {
			this.input.remove();
			this.button.remove();
			this.element.show();
			$.Widget.prototype.destroy.call( this );
		}
	});
})( jQuery );
