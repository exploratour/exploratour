import sys
from cx_Freeze import setup, Executable

base = None
exeext = ''


packages = ["lxml",
        "PIL",
        "cherrypy",
        "jinja2",
        "routes",
        "restpose",
        #"repoze",
]

includes = []

if sys.platform == "win32":
    exeext = '.exe'
    #base = "Win32Service"
    includes.append("socketpool.backend_thread")

build_exe_options = {
    "packages": packages,
    "includes": includes,
    "excludes": ["email",
                 "Tkinter",
                 "PyQt4",
                 "OpenSSL",
                 "__pypy__",
                 "_grabscreen",
                 "_systemrestart",
                 "memcache",
                 "distutils",
                 ],
    "include_files": [
                 ["templates", "web/templates"],
                 ["static", "web/static"],
                 ["servers/restpose" + exeext, "servers/restpose" + exeext],
                 ],
}

bdist_msi_options = {
    "upgrade_code": "exploratour_main_98n92cb",
}

setup( name = "exploratour",
       version = "0.9.1",
       description = "Exploratour",
       options = {
           "build_exe": build_exe_options,
           "bdist_msi": bdist_msi_options,
       },
       executables = [
           Executable("start.py",
               base=base,
               shortcutName="exploratour",
               shortcutDir="ProgramMenuFolder"),
       ]
)

