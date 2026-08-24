#!/usr/bin/env python3
import json
import sys


args = sys.argv[1:]
if args == ["--version"]:
    print("codewiki 0.6.5")
elif args[:2] == ["repos", "add"]:
    print(json.dumps({"repository": {"id": "probe-repo", "path": args[2]}}))
elif args and args[0] == "analyze":
    print(json.dumps({"status": "completed", "repository_id": "probe-repo"}))
elif args[:2] == ["repos", "scan"]:
    print(json.dumps({"files": [
        {"path": "src/shop/checkout.py", "language": "python"},
        {"path": "src/shop/inventory.py", "language": "python"},
    ]}))
elif args[:2] == ["graph", "search"]:
    print(json.dumps({"nodes": [{
        "name": "CheckoutService",
        "path": "src/shop/checkout.py",
        "start_line": 4,
        "end_line": 11,
    }]}))
elif args[:2] == ["graph", "explore"]:
    print(json.dumps({
        "nodes": ["CheckoutService.checkout", "Inventory.reserve"],
        "edges": [{
            "source": "CheckoutService.checkout",
            "predicate": "calls",
            "target": "Inventory.reserve",
        }],
        "sources": [{"path": "src/shop/checkout.py", "start_line": 8, "end_line": 11}],
    }))
elif args[:2] == ["graph", "affected"]:
    print(json.dumps({"affected": ["CheckoutService.checkout"]}))
elif args and args[0] == "update":
    print(json.dumps({"status": "completed"}))
else:
    print(json.dumps({"error": "unsupported", "args": args}))
    raise SystemExit(2)

