"""KOBIS 일별 박스오피스(엑셀)로 지정 기간의 영화별 일별 관객수를 받아 daily.json에 합친다.

python3 daily.py 2026-01-01 2026-03-31   # 기간 지정 (최대 731일)
python3 daily.py --recent                # 어제까지 최근 7일

- 요청은 7일당 1건(KOBIS 화면의 조회 기간 제한), 1회 실행 최대 105건. 재시도는 최대 3회.
- 같은 날짜를 다시 받으면 그 날짜 값은 새로 받은 값으로 바꾼다.
- 엑셀에 영화 코드가 없어 영화는 '영화명|개봉일'로 식별한다.

저장 형식 (용량을 줄이려고 날짜 문자열 없이 숫자 배열로 저장):
  daily/index.json  {"ranges": [[시작,끝],...], "movies": [[영화명, 개봉일, 국적K/F, 총관객, 첫날, 마지막날], ...]}
                    개봉일·첫날·마지막날은 1970-01-01부터 센 일수(정수, 개봉일 미상은 null)
                    영화 id = movies 배열의 위치. 새 영화는 뒤에 붙이고 순서는 바꾸지 않는다.
  daily/YYYY.json   {"y": YYYY, "m": {"id": [첫날의 연중 일차(0=1월1일), [관객수...], [매출액...]]}}
                    첫날부터 마지막날까지 하루 한 칸. 기록이 없는 날은 0.
"""
import datetime as dt, html, json, os, re, sys
sys_argv = sys.argv[1:]
sys.argv = [sys.argv[0]]
exec(open("scrape.py").read().split("def main():")[0])  # curl, token, to_int 재사용

URL = BASE + "findDailyBoxOfficeList.do"
MAX_DAYS, MAX_REQ, DIR = 731, 105, "daily"
KST = dt.timezone(dt.timedelta(hours=9))


def fail(msg):
    print("error:", msg, file=sys.stderr)
    sys.exit(1)


today = dt.datetime.now(KST).date()
yesterday = today - dt.timedelta(days=1)
if sys_argv == ["--recent"]:
    start, end = yesterday - dt.timedelta(days=6), yesterday
elif len(sys_argv) == 2:
    try:
        start, end = (dt.date.fromisoformat(s) for s in sys_argv)
    except ValueError:
        fail("날짜는 YYYY-MM-DD 형식이어야 합니다")
else:
    fail("사용법: python3 daily.py 시작일 종료일  |  python3 daily.py --recent")
if start > end:
    start, end = end, start
if start < dt.date(2004, 1, 1):
    fail("2004-01-01 이후만 수집할 수 있습니다")
if end > yesterday:
    fail(f"종료일은 어제({yesterday}) 이전이어야 합니다")
if (end - start).days + 1 > MAX_DAYS:
    fail(f"한 번에 최대 {MAX_DAYS}일까지 수집할 수 있습니다")

EPOCH = dt.date(1970, 1, 1)


def load_db():
    """index.json과 연도별 파일을 읽어 {키: {t,o,n,d:{날짜:[관객,매출]}}} 형태로 펼친다."""
    ip = os.path.join(DIR, "index.json")
    if not os.path.exists(ip):
        return {"movies": {}, "order": [], "ranges": [], "rejectedCount": 0}
    idx = json.load(open(ip, encoding="utf-8"))
    for m in idx["movies"]:
        m[1] = None if m[1] is None else str(EPOCH + dt.timedelta(days=m[1]))
    order = [f"{t}|{o or ''}" for t, o, *_ in idx["movies"]]
    movies = {k: {"t": m[0], "o": m[1], "n": m[2], "d": {}} for k, m in zip(order, idx["movies"])}
    for fn in sorted(os.listdir(DIR)):
        if not re.fullmatch(r"\d{4}\.json", fn):
            continue
        yf = json.load(open(os.path.join(DIR, fn), encoding="utf-8"))
        jan1 = dt.date(yf["y"], 1, 1)
        for mid, (off, aud, sal) in yf["m"].items():
            dd = movies[order[int(mid)]]["d"]
            for i, (a, s) in enumerate(zip(aud, sal)):
                if a or s:
                    dd[str(jan1 + dt.timedelta(days=off + i))] = [a, s]
    return {"movies": movies, "order": order, "ranges": idx["ranges"], "rejectedCount": idx.get("rejectedCount", 0)}


def save_db(db):
    os.makedirs(DIR, exist_ok=True)
    order = db["order"] + sorted(k for k in db["movies"] if k not in set(db["order"]))
    years = {}
    rows = []
    for mid, k in enumerate(order):
        m = db["movies"][k]
        days = sorted(m["d"])
        num = lambda s: None if not s else (dt.date.fromisoformat(s) - EPOCH).days
        rows.append([m["t"], num(m["o"]), m["n"], sum(v[0] for v in m["d"].values()),
                     num(days[0] if days else None), num(days[-1] if days else None)])
        for day in days:
            years.setdefault(int(day[:4]), {}).setdefault(mid, []).append(day)
    for y, per in years.items():
        jan1, out = dt.date(y, 1, 1), {}
        for mid, days in per.items():
            first = (dt.date.fromisoformat(days[0]) - jan1).days
            n = (dt.date.fromisoformat(days[-1]) - jan1).days - first + 1
            aud, sal = [0] * n, [0] * n
            for day in days:
                i = (dt.date.fromisoformat(day) - jan1).days - first
                aud[i], sal[i] = db["movies"][order[mid]]["d"][day]
            out[str(mid)] = [first, aud, sal]
        json.dump({"y": y, "m": out}, open(os.path.join(DIR, f"{y}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
    json.dump({"fetchedAt": db["fetchedAt"], "ranges": db["ranges"], "rejectedCount": db["rejectedCount"], "movies": rows},
              open(os.path.join(DIR, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


db = load_db()
movies = db["movies"]
written = set()
tok = token(curl([URL]))
rejects, got_days, reqs = [], set(), 0
empty = "sMultiMovieYn=&sRepNationCd=&sWideAreaCd="
cell = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()

d = start
while d <= end:
    e = min(d + dt.timedelta(days=6), end)
    reqs += 1
    if reqs > MAX_REQ:
        fail(f"요청 수 한도 {MAX_REQ}건 초과")
    page = curl(["-X", "POST", URL, "--data",
                 f"CSRFToken={tok}&loadEnd=0&searchType=excel&sSearchFrom={d}&sSearchTo={e}&{empty}"],
                marker="board_tit")
    for block in page.split('<div class="board_tit">')[1:]:
        m = re.search(r"(\d{4})년 (\d{2})월 (\d{2})일", block)
        if not m:
            continue
        day = "-".join(m.groups())
        got_days.add(day)
        day_sum, day_total = 0, None
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
            c = [cell(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if not c or c[0] == "순위":
                continue
            if c[0] == "합계":  # 그날 전체 합계 행: 검증에만 사용
                day_total = to_int(c[8]) if len(c) > 8 else None
                continue
            # 열: 순위 영화명 개봉일 매출액 점유율 매출증감 증감율 누적매출 관객수 관객증감 증감율 누적관객 스크린 상영횟수 대표국적 ...
            ok = (len(c) >= 15 and to_int(c[0]) and c[1] and re.fullmatch(r"\d{4}-\d{2}-\d{2}|", c[2])
                  and to_int(c[8]) is not None and to_int(c[8]) >= 0 and to_int(c[3]) is not None)
            if not ok:  # 영화를 알 수 없는 행 등: 버리고 기록. 관객수를 읽을 수 있으면 합계 검증에는 넣는다
                rejects.append({"day": day, "row": c[:9]})
                day_sum += to_int(c[8]) if len(c) > 8 and to_int(c[8]) is not None else 0
                continue
            key = f"{c[1]}|{c[2]}"
            mv = movies.setdefault(key, {"t": c[1], "o": c[2] or None, "n": "K" if c[14] == "한국" else "F", "d": {}})
            mv["d"][day] = [to_int(c[8]), to_int(c[3])]  # [관객수, 매출액]
            written.add((key, day))
            day_sum += to_int(c[8])
        if day_total is None or day_total != day_sum:
            fail(f"{day} 영화별 관객수 합({day_sum})이 합계 행({day_total})과 다릅니다")
    print(d, e, file=sys.stderr)
    d = e + dt.timedelta(days=1)

want = {str(start + dt.timedelta(days=i)) for i in range((end - start).days + 1)}
if got_days != want:
    fail(f"받은 날짜가 요청과 다릅니다: 누락 {sorted(want - got_days)[:5]}")

for key, mv in movies.items():  # 다시 받은 날짜에 이번에 나오지 않은 영화의 옛 값은 지운다
    for day in [x for x in mv["d"] if x in got_days and (key, x) not in written]:
        del mv["d"][day]

ranges = db["ranges"] + [[str(start), str(end)]]
ranges.sort()
merged = []
for a, b in ranges:  # 겹치거나 이어지는 기간 합치기
    if merged and dt.date.fromisoformat(a) <= dt.date.fromisoformat(merged[-1][1]) + dt.timedelta(days=1):
        merged[-1][1] = max(merged[-1][1], b)
    else:
        merged.append([a, b])
db.update(ranges=merged, fetchedAt=dt.datetime.now(KST).isoformat(timespec="minutes"),
          rejectedCount=db["rejectedCount"] + len(rejects))
save_db(db)
for r in rejects:
    print("rejected:", json.dumps(r, ensure_ascii=False), file=sys.stderr)
print(f"requests {reqs}, days {len(got_days)}, movies {len(movies)}, rejected {len(rejects)}", file=sys.stderr)
