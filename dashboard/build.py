"""template.html의 __DATA__ 자리에 kobis.json을 넣어 페이지를 만든다.

python3 build.py             -> index.html (브라우저에서 바로 여는 독립 페이지)
python3 build.py --artifact  -> artifact.html (Claude 아티팩트 게시용, 문서 뼈대 없음)
"""
import sys

body = open("template.html", encoding="utf-8").read()
data = open("kobis.json", encoding="utf-8").read().replace("</", "<\\/")
assert body.count("__DATA__") == 1
page = body.replace("__DATA__", data)

if "--artifact" in sys.argv:
    open("artifact.html", "w", encoding="utf-8").write(page)
else:
    head = '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
    open("index.html", "w", encoding="utf-8").write(head + page + "\n</body>\n</html>\n")
