# inspect_map_cache.py
import json
from pathlib import Path

p = Path("api_cache/city_map.json")
if not p.exists():
    print("No existe api_cache/city_map.json — revisa ruta y nombre")
else:
    raw = json.load(p.open(encoding="utf-8"))
    print("Top-level type:", type(raw))
    if isinstance(raw, dict):
        print("Top-level keys:", list(raw.keys()))
    # print a compact preview (first 500 chars)
    print("\nPreview (compact):")
    s = json.dumps(raw, ensure_ascii=False)[:800]
    print(s + ("..." if len(s) > 800 else ""))

    # Buscamos posibles candidates que sean matriz de filas
    def looks_like_matrix(obj):
        if not isinstance(obj, list):
            return False
        if len(obj) == 0:
            return False
        # check first row: list[str] or str
        r0 = obj[0]
        return isinstance(r0, list) or isinstance(r0, str)

    # Examinar todo el dict por valores que parezcan matriz
    candidates = []
    def scan(node, path="root"):
        if looks_like_matrix(node):
            candidates.append((path, node if len(node)<=5 else node[:5]))
        if isinstance(node, dict):
            for k, v in node.items():
                scan(v, path + "/" + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node[:20]):
                scan(v, path + f"[{i}]")

    scan(raw)
    print("\nCandidates (paths that look like a matrix):")
    for pth, sample in candidates:
        print(" -", pth, " sample_first_rows:", sample)
