"""按 tag 分组展示线上 schema 的所有操作（包括无 summary 的操作，定位多余分组）。"""
import os
import urllib.request
from collections import defaultdict

import yaml

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "devops.settings")

data = urllib.request.urlopen(
    "http://10.0.0.40:8001/api/schema/", timeout=10
).read()
schema = yaml.safe_load(data)

by_tag = defaultdict(list)
for path, item in schema.get("paths", {}).items():
    for method, op in item.items():
        if not isinstance(op, dict):
            continue
        for tag in op.get("tags", ["(无tag)"]):
            by_tag[tag].append(
                (method.upper(), path, op.get("summary") or "(无summary)")
            )

for tag in sorted(by_tag):
    print(f"\n### {tag} ({len(by_tag[tag])} 个操作)")
    for method, path, summary in sorted(by_tag[tag], key=lambda x: (x[1], x[0])):
        print(f"  {method:7} {path:55} {summary}")
