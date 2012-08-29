#!/usr/bin/env python
import os, sys
import config
from apps import bgprocess
import cherrypy
import optparse
import shutil
import subprocess
import threading
import time
import traceback
import webapp
import webbrowser

g_subprocs_lock = threading.Lock()
g_subprocs = []

def parse_args():
    parser = optparse.OptionParser()
    parser.add_option("-p", action="store", dest="mac_proccess_serial")
    parser.add_option("--no-browser", action="store_true", dest="no_browser",
                      help="don't open a browser when starting")
    parser.add_option("--no-restpose", action="store_true", dest="no_restpose",
                      help="don't run restpose server internally")
    parser.add_option("--restpose-url", action="store", dest="restpose_url",
                      help="URL to talk to restpose.  Implies --no-restpose")
    parser.add_option("--restpose-collection", action="store", dest="restpose_collection",
                      help="Collection to store items in restpose in.")

    (options, args) = parser.parse_args()

    socket_host = '127.0.0.1'
    socket_port = 7343

    if len(args) > 0:
        socket_host = args[0]
    if len(args) > 1:
        socket_port = int(args[1])

    if options.restpose_url:
        options.no_restpose = True
        config.search_url = options.restpose_url
    if options.restpose_collection:
        config.search_collection = options.restpose_collection

    options=dict(no_browser = options.no_browser,
                 no_restpose = options.no_restpose,
                 socket_host = socket_host,
                 socket_port = socket_port)
    return options, args

def start_bgprocesses():
    """Setup space for short-running background processes.

    """
    if os.path.exists(config.tmpdir):
        shutil.rmtree(config.tmpdir)
    os.makedirs(config.tmpdir)

def start_restpose():
    restpose_path = os.path.join(config.serversdir, "restpose")
    if sys.platform == 'win32':
        restpose_path += '.exe'

    server = subprocess.Popen([restpose_path, '-d', os.path.join(config.datadir, "rspdbs")])
    g_subprocs.append(server)

def stop_restpose():
    # turn off signal handlers, before sending to subprocess
    engine = cherrypy.engine

    if hasattr(engine, "signal_handler"):
        engine.signal_handler.unsubscribe()
    if hasattr(engine, "console_control_handler"):
        engine.console_control_handler.unsubscribe()

    with g_subprocs_lock:
        for proc in g_subprocs:
            proc.terminate()
        if len(g_subprocs) != 0:
            time.sleep(1)
        for proc in g_subprocs:
            if proc.poll():
                proc.kill()
        for proc in g_subprocs:
            proc.wait()
        g_subproces = []

def start_cherrypy(options):
    webapp.initialise()
    app = webapp.WebApp()
    cherrypy.config.update({
        'environment': 'production',
        'log.error_file': os.path.join(config.logdir, 'site.log'),
        'log.screen': True,
        'engine.autoreload_on': False,
        'server.socket_host': options["socket_host"],
        'server.socket_port': options["socket_port"],
        'server.shutdown_timeout': 0.1,
        'response.headers.Content-Type': 'text/html;charset=UTF-8',
    })
    cherrypy.config.update(app.get_server_config())
    def open_page():
        if not options['no_browser']:
            webbrowser.open("http://127.0.0.1:%d/" % (options["socket_port"], ))
    cherrypy.engine.subscribe('start', open_page)
    cherrypy.quickstart(app, '/', app.get_config())

if __name__ == '__main__':
    options, args = parse_args()
    start_bgprocesses()
    cherrypy.engine.subscribe('stop', bgprocess.pool.close)
    if not options['no_restpose']:
        start_restpose()
        cherrypy.engine.subscribe('stop', stop_restpose)
    try:
        start_cherrypy(options)
    except Exception, e:
        print "Terminating:"
        traceback.print_exc()
        if not options['no_restpose']:
            stop_restpose()
