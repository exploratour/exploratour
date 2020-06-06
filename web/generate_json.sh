#!/bin/sh

rsync -a richard@server1:code/exploratour/exploratour/data/store/ /home/richard/code/exploratour/exploratour/data/store

. ENV2/bin/activate
ENV2/bin/python iterate_db.py
