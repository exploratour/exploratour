(function ($) {
    var console = window.console || {
        log: function () {},
        error: function () {}
    },
    methods = {
        // Initialise the player.
        //
        // The jplayer widgets will be created inside each element that this is
        // called on.  Usually, this should be a single element.  If called on
        // multiple elements, multiple players will be created.
        init: function (options) {
            var settings = {
                jplayer_settings: {
                    swfPath: STATIC_ASSETS_URL + "jplayer",
                    errorAlerts: false,
                    warningAlerts: false
                }
            };
            if (options) {
                $.extend(settings, options);
            }

            return this.each(function () {
                var $this = $(this),
                    data = $this.data('jPlayerPlaylist');

                if (!data) {
                    $this.data('jPlayerPlaylist', {
                        // The object which the player is attached to.
                        playerobj: $this,

                        // An ordered list of the tracks to be played.
                        audiolist: [],

                        // Index of the currently selected track, -1 for none.
                        current_index: -1,

                        // True if we're currently playing all.
                        play_all: false,

                        // The tracks, keyed by track type.
                        track_types: {},

                        // The players which have started being initialised,
                        // keyed by track type.
                        players: {},

                        // Tracks which have not been notified that the player
                        // is ready, keyed by track type.
                        unnotified_tracks: {},

                        // The players which are ready.
                        players_ready: {},

                        // Settings to pass to jplayer, when starting a player.
                        // (The media, supplied and ready properties will be
                        // overwritten, and thus ignored.)
                        jplayer_settings: settings.jplayer_settings
                    });
                }
            });
        },

        // Add tracks to the playlist.
        //
        // The tracks should have mimetype and audiourl data properties.
        //
        // If supplied, readyfn will be called for each of the tracks, if and
        // when the player is ready to play it (ie, when the player for that
        // media type has been successfully initialised).
        // readyfn will be passed two arguments - the object the player was
        // initialised on, and the object associated with the track.
        add_tracks: function (elements, readyfn) {
            var players = this;
            elements.each(function () {
                var trackobj = $(this),
                    url = trackobj.data('audiourl'),
                    mimetype = trackobj.data('mimetype'),
                    media, track_type;

                switch (mimetype) {
                    case 'audio/mpeg':
                        media = { mp3: url };
                        track_type = 'mp3';
                        break;
                    case 'audio/ogg':
                        media = { oga: url };
                        track_type = 'oga';
                        break;
                    case 'audio/x-wav':
                        media = { wav: url };
                        track_type = 'wav';
                        break;
                    case 'audio/webm':
                        media = { webma: url };
                        track_type = 'webma';
                        break;
                }

                if (media) {
                    players.each(function () {
                        add_track($(this), trackobj, url, media, track_type, readyfn);
                    });
                } else {
                    console.log("Didn't recognise media type", mimetype);
                }
            });

            players.each(function() {
                setup_players($(this));
            });
            return this;
        },

        play: function (trackobj) {
            this.each(function() {
                if (trackobj) {
                    play($(this).data('jPlayerPlaylist'),
                         trackobj.data('jPlayerPlaylistTrack'));
                } else {
                    play_all($(this).data('jPlayerPlaylist'));
                }
            });
            return this;
        },

        pause: function () {
            this.each(function() {
                pause($(this).data('jPlayerPlaylist'));
            });
            return this;
        },

        stop: function () {
            return this.each(function() {
                stop($(this).data('jPlayerPlaylist'));
            });
        },

        prev: function () {
            return this.each(function() {
                prev($(this).data('jPlayerPlaylist'));
            });
        },

        next: function () {
            return this.each(function() {
                next($(this).data('jPlayerPlaylist'));
            });
        }
    };

    // Add a track to a player.
    function add_track(playerobj, trackobj, url, media, track_type, readyfn) {
        var data = playerobj.data('jPlayerPlaylist'),
            trackinfo,
            tracks_of_this_type;
        if (!data) {
            console.error("Must initialise player first");
        }

        trackinfo = {
            trackobj: trackobj, // The original element.
            url: url, // The URL of the track.
            media: media, // The media to supply to jplayer
            track_type: track_type, // The track type being supplied to jplayer.
            player: null, // The player for this track; set when ready.
            readyfn: readyfn // Callback called when player becomes ready.
        };
        trackobj.data('jPlayerPlaylistTrack', trackinfo)

        // Append the track to the audiolist.
        data.audiolist[data.audiolist.length] = trackinfo;

        // Append the track to the list of tracks of its type.
        if (!data.track_types[track_type]) {
            data.track_types[track_type] = [];
            data.unnotified_tracks[track_type] = [];
        }
        tracks_of_this_type = data.track_types[track_type];
        tracks_of_this_type[tracks_of_this_type.length] = trackinfo;
        tracks_of_this_type = data.unnotified_tracks[track_type];
        tracks_of_this_type[tracks_of_this_type.length] = trackinfo;
    }

    // Set up the necessary players.
    function setup_players(playerobj) {
        var playerinfo = playerobj.data('jPlayerPlaylist'),
            players = playerinfo.players;

        // Create the player for any track type which doesn't have a player.
        $.each(playerinfo.track_types, function(track_type, value) {
            var playerelem, params;
            if (!players[track_type]) {
                playerelem = $('<div/>').css({width: "0px", height: "0px"});
                playerobj.after(playerelem);
                params = $.extend({}, playerinfo.jplayer_settings, {
                    ready: function() {
                        playerinfo.players_ready[track_type] = playerelem;
                        notify_ready(playerelem, playerobj,
                                     playerinfo.unnotified_tracks[track_type]);
                    },
                    ended: function() {
                        notify_ended(playerinfo);
                    },
                    supplied: track_type
                });
                players[track_type] = playerelem.jPlayer(params);
            }
        });

        // Notify any tracks for players which are already ready.
        $.each(playerinfo.players_ready, function(track_type, playerelem) {
            notify_ready(playerelem, playerobj,
                         playerinfo.unnotified_tracks[track_type]);
        });
    };

    // Send all the notifications about a player being ready to play a list of
    // unnotified tracks.
    function notify_ready(playerelem, playerobj, unnotified_tracks) {
        $.each(unnotified_tracks,
               function (index, trackinfo) {
            if (!trackinfo.player) {
                trackinfo.player = playerelem;
                trackinfo.readyfn(playerobj, trackinfo.trackobj);
            }
        });
        unnotified_tracks.length = 0;
    }

    // Notify that a player has finished its current track.
    function notify_ended(playerinfo) {
        var trackinfo;
        if (playerinfo.current_index >= 0) {
            trackinfo = playerinfo.audiolist[playerinfo.current_index];
            if (playerinfo.play_all) {
                if (playerinfo.current_index + 1 < playerinfo.audiolist.length) {
                    playerinfo.current_index += 1;
                    play(playerinfo, 
                         playerinfo.audiolist[playerinfo.current_index]);
                } else {
                    notify_track_pause(playerinfo, trackinfo);
                    playerinfo.current_index = -1;
                    playerinfo.playerobj.trigger('setcurrent');
                }
            } else {
                notify_track_pause(playerinfo, trackinfo);
            }
        }
    }

    // Notify that a track has started being played.
    function notify_track_play(playerinfo, trackinfo) {
        trackinfo.trackobj.trigger('play');
        playerinfo.playerobj.trigger('play', trackinfo.trackobj);
    }

    // Notify that a track has stopped being played.
    function notify_track_pause(playerinfo, trackinfo) {
        trackinfo.trackobj.trigger('pause');
        playerinfo.playerobj.trigger('pause', trackinfo.trackobj);
    }

    // Notify that a track is now the current track.
    function notify_track_current(playerinfo, trackinfo) {
        trackinfo.trackobj.trigger('setcurrent');
        playerinfo.playerobj.trigger('setcurrent', trackinfo.trackobj);
    }

    // Start playing the track associated with the given object.
    function play(playerinfo, trackinfo) {
        if (!trackinfo) return;
        var player = playerinfo.players_ready[trackinfo.track_type],
            newindex = -1;

        if (playerinfo.current_index >= 0) {
            pause(playerinfo);
        }

        $.each(playerinfo.audiolist, function(index, item) {
            if (item == trackinfo) {
                newindex = index;
                return false;
            }
        });

        if (player && newindex >= 0) {
            playerinfo.current_index = newindex;
            player.jPlayer("setMedia", trackinfo.media).jPlayer("play");
            notify_track_current(playerinfo, trackinfo);
            notify_track_play(playerinfo, trackinfo);
        }
    }

    function play_all(playerinfo) {
        playerinfo.play_all = true;
        if (playerinfo.current_index < 0) {
            playerinfo.current_index = 0;
        }
        play(playerinfo, playerinfo.audiolist[playerinfo.current_index]);
    }

    // Pause whatever track is currently playing.
    function pause(playerinfo) {
        var trackinfo, player;
        if (playerinfo.current_index >= 0) {
            trackinfo = playerinfo.audiolist[playerinfo.current_index];
            player = trackinfo.player;
            player.jPlayer("pause");
            notify_track_pause(playerinfo, trackinfo);
        }
    }

    function stop(playerinfo) {
        var trackinfo, player;
        playerinfo.play_all = false;
        if (playerinfo.current_index >= 0) {
            trackinfo = playerinfo.audiolist[playerinfo.current_index];
            player = trackinfo.player;
            player.jPlayer("pause", 0);
            notify_track_pause(playerinfo, trackinfo);
        }
    }

    // Start playing the previous track.
    function prev(playerinfo) {
        var trackinfo;
        pause(playerinfo);
        if (playerinfo.current_index >= 0) {
            playerinfo.current_index -= 1;
            trackinfo = playerinfo.audiolist[playerinfo.current_index];
            play(playerinfo, trackinfo);
        }
    }

    // Start playing the next track.
    function next(playerinfo) {
        var trackinfo, player;
        if (playerinfo.current_index >= 0) {
            pause(playerinfo);

            if (playerinfo.current_index + 1 < playerinfo.audiolist.length) {
                playerinfo.current_index += 1;
            } else {
                playerinfo.current_index = -1;
            }
        } else {
            playerinfo.current_index = 0;
        }
        if (playerinfo.current_index >= 0) {
            trackinfo = playerinfo.audiolist[playerinfo.current_index];
            play(playerinfo, trackinfo);
        }
    }

    $.fn.jPlayerPlaylist = function (method) {
        if (methods[method]) {
            return methods[method].apply(this, Array.prototype.slice.call(arguments, 1));
        } else if (typeof method === 'object' || ! method) {
            return methods.init.apply(this, arguments);
        } else {
            $.error('Method ' +  method + ' does not exist on jQuery.jPlayerPlaylist');
        }    
    };
})(jQuery);

$(function() {
    var controls = {
        play: $('.jpl-controls .jpl-play'),
        pause: $('.jpl-controls .jpl-pause'),
        stop: $('.jpl-controls .jpl-stop'),
        next: $('.jpl-controls .jpl-next'),
        prev: $('.jpl-controls .jpl-prev')
    }, playerobj;

    controls.play.click(function() {
        playerobj.jPlayerPlaylist("play");
    });
    controls.pause.click(function() {
        playerobj.jPlayerPlaylist("pause");
    });
    controls.stop.click(function() {
        playerobj.jPlayerPlaylist("stop");
    });
    controls.next.click(function() {
        playerobj.jPlayerPlaylist("next");
    });
    controls.prev.click(function() {
        playerobj.jPlayerPlaylist("prev");
    });

   function track_ready(playerobj, trackobj) {
        var play = $('<a class="jpl-play"></a>'),
            pause = $('<a class="jpl-pause"></a>');
        pause.hide();
        trackobj.append(play).append(pause);

        trackobj.bind("play", function(e) {
            play.hide();
            pause.show();
        });
        trackobj.bind("pause", function(e) {
            play.show();
            pause.hide();
        });
        trackobj.bind("setcurrent", function(e) {
            trackobj.addClass('current');
        });

        play.click(function() {
            playerobj.jPlayerPlaylist("play", trackobj);
        });
        pause.click(function() {
            playerobj.jPlayerPlaylist("pause");
        });
    };

    playerobj = $('#jpAudioPlayer').jPlayerPlaylist()
        .jPlayerPlaylist('add_tracks', $("span.audio-track[data-audiourl]"), track_ready)
        .jPlayerPlaylist('add_tracks', $("span.single-audio-track[data-audiourl]"))

        .bind("play", function() {
            controls.play.hide();
            controls.pause.show();
        })
        .bind("pause", function() {
            controls.play.show();
            controls.pause.hide();
        });
 
});
