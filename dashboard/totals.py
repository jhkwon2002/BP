"""KOBIS 테마통계 '총 관객수 및 매출액'(연도별 전체 관객수)을 받아 kobis.json의 totals에 넣는다. 요청 2건, 재시도 최대 3회."""
import html, json, re, sys
sys.argv = [sys.argv[0]]
exec(open("scrape.py").read().split("def main():")[0])  # curl, token, to_int 재사용

URL = "https://www.kobis.or.kr/kobis/business/stat/them/findYearlyTotalList.do"
tok = token(curl([URL]))
page = curl(["-X", "POST", URL, "--data", f"CSRFToken={tok}&loadVal=0&searchType=search"])
tbody = re.search(r"<tbody>(.*?)</tbody>", page, re.S).group(1)

d = json.load(open("kobis.json"))
rows, rejects = [], []
for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.S):
    c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
    if c and c[0] == "합계":  # 표 맨 아래 요약행 (연도 행 아님)
        continue
    # 열: 연도 | 한국 개봉·상영·매출·관객·점유율 | 외국 (같은 5열) | 전체 개봉·상영·매출·관객
    if len(c) != 15 or not re.fullmatch(r"\d{4}", c[0]) or None in (to_int(c[4]), to_int(c[9]), to_int(c[13]), to_int(c[14])):
        rejects.append(c)
        continue
    r = {"y": int(c[0]), "a": to_int(c[14]), "s": to_int(c[13]), "ak": to_int(c[4]), "af": to_int(c[9])}
    if r["ak"] + r["af"] != r["a"] or r["y"] in {x["y"] for x in rows}:
        rejects.append(c)
        continue
    rows.append(r)

print("totals", len(rows), "rejected", len(rejects), file=sys.stderr)
d["totals"] = rows
d["rejectedCount"] += len(rejects)
d["log"].append({"src": "totals", "kept": len(rows), "rejected": len(rejects)})
json.dump(d, open("kobis.json", "w"), ensure_ascii=False, separators=(",", ":"))
