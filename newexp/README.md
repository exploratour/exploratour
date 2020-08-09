Exporting data

../web/generate_json.sh

Importing data

PYTHONPATH=. python import_export/load_json.py ../web/collections.jsonl ../web/records.jsonl 1

To run

FLASK_APP=exploratour FLASK_ENV=development flask run -h 0.0.0.0



# Design for files

Need a db that can say:

 - For each path
   - what is the hash of the file there now
   - what are the hashes of the files that have been there
 - For each hash
   - what are the paths that that hash is at now
   - what are the paths that have held that hash


