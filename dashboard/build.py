"""template.html의 __DATA__ 자리에 kobis.json을 넣어 페이지를 만든다.

python3 build.py             -> index.html (웹서버에서 daily/와 함께 실행)
python3 build.py --preview   -> preview.html (일별 자료까지 포함, 서버 없이 실행)
python3 build.py --artifact  -> artifact.html (Claude 아티팩트 게시용, 문서 뼈대 없음)
"""
import base64
import gzip
import json
from pathlib import Path
import re
import sys

body = open("template.html", encoding="utf-8").read()
data = open("kobis.json", encoding="utf-8").read().replace("</", "<\\/")
assert body.count("__DATA__") == 1
page = body.replace("__DATA__", data)

if "--preview" in sys.argv:
    # Keep production HTML small. Only the local preview embeds daily data,
    # compressed per year so the browser decodes only the files it needs.
    files = sorted(Path("daily").glob("*.json"))
    if not any(p.name == "index.json" for p in files):
        raise SystemExit("daily/index.json is required for the offline preview")
    bundled = {}
    for path in files:
        raw = path.read_bytes()
        json.loads(raw)  # Do not package malformed source data.
        bundled[path.name] = base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")
    # File preview renderers may discard non-executable JSON script elements.
    # Put preview data directly in the executable script so it needs neither
    # those DOM elements nor relative file requests.
    page, count = re.subn(
        r"// ---- primary data: begin.*?// ---- primary data: end",
        lambda _: "const D = " + data + ";",
        page, flags=re.S,
    )
    assert count == 1, "primary data bootstrap marker missing"
    page, count = re.subn(
        r"// ---- daily bundle: begin.*?// ---- daily bundle: end",
        lambda _: "const dailyBundle = " + json.dumps(bundled, separators=(",", ":")) + ";",
        page, flags=re.S,
    )
    assert count == 1, "daily bundle marker missing"
    data_tag = '<script id="kobis-data" type="application/json">' + data + '</script>'
    assert page.count(data_tag) == 1
    page = page.replace(data_tag, "", 1)
    page = page.replace('<title>한국 박스오피스 관객 비교</title>', '<title>KOBIS 테마별 조회 미리보기</title>', 1)
    page = page.replace('KOBIS 영화관입장권통합전산망 · 박스오피스</div>', 'KOBIS 박스오피스 · 20개 테마 조회 미리보기</div>', 1)

if "--artifact" in sys.argv:
    open("artifact.html", "w", encoding="utf-8").write(page)
else:
    head = '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
    charset = '<meta charset="utf-8">\n'
    if page.startswith(charset):
        page = page[len(charset):]
    target = "preview.html" if "--preview" in sys.argv else "index.html"
    open(target, "w", encoding="utf-8").write(head + page + "\n</body>\n</html>\n")
