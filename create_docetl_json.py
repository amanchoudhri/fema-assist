import json

from pathlib import Path

with open(Path.home() / 'Downloads' / 'DocETL April 7 2025.json') as f:
    res = json.load(f)

prefix = 'converted_2025-04-07T18-30-58-028Z'
for doc in res:
    doc['filename'] = prefix + '/' + doc['filename']

with open(Path.home() / 'Downloads' / 'updated.json', 'w+') as f:
    json.dump(res, f)
