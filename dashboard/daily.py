"""KOBIS 일별 박스오피스(엑셀)로 지정 기간의 영화별 일별 관객수·매출액·스크린수·상영횟수와
영화 정보(배급사·장르·등급·감독)를 받아 daily/에 합친다.

python3 daily.py 2026-01-01 2026-03-31   # 기간 지정 (최대 731일)
python3 daily.py --recent                # 어제까지 최근 7일

- 요청은 7일당 1건(KOBIS 화면의 조회 기간 제한), 1회 실행 최대 105건. 재시도는 최대 3회.
- 같은 날짜를 다시 받으면 그 날짜 값은 새로 받은 값으로 바꾼다.
- 엑셀에 영화 코드가 없어 영화는 '영화명|개봉일'로 식별한다.

저장 형식 (용량을 줄이려고 날짜 문자열 없이 숫자 배열로 저장):
  daily/index.json  {"ranges": [[시작,끝],...], "movies": [[영화명, 개봉일, 국적K/F, 총관객, 첫날, 마지막날], ...]}
                    개봉일·첫날·마지막날은 1970-01-01부터 센 일수(정수, 개봉일 미상은 null)
                    영화 id = movies 배열의 위치. 새 영화는 뒤에 붙이고 순서는 바꾸지 않는다.
  daily/YYYY.json   {"y": YYYY, "m": {"id": [첫날의 연중 일차(0=1월1일), [관객수...], [매출액...], [스크린수...], [상영횟수...]]}}
                    첫날부터 마지막날까지 하루 한 칸. 기록이 없는 날은 0.
  daily/meta.json   {"dist": [배급사명...], "genre": [장르명...], "grade": [등급명...],
                     "m": [[[배급사 번호...], [장르 번호...], 등급 번호(없으면 -1), 감독], ...]}  (영화 id 순서)
                    배급사·장르는 엑셀의 쉼표 구분 값을 나눈 것. 영화마다 가장 최근에 받은 값.
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
HEADER = ["순위", "영화명", "개봉일", "매출액", "매출액점유율", "매출액증감(전일대비)", "매출액증감율(전일대비)", "누적매출액",
          "관객수", "관객수증감(전일대비)", "관객수증감율(전일대비)", "누적관객수", "스크린수", "상영횟수", "대표국적", "국적",
          "제작사", "배급사", "등급", "장르", "감독", "배우"]


def load_db():
    """index.json·meta.json·연도별 파일을 읽어 {키: {t,o,n,meta,d:{날짜:[관객,매출,스크린,상영]}}} 형태로 펼친다."""
    ip = os.path.join(DIR, "index.json")
    if not os.path.exists(ip):
        return {"movies": {}, "order": [], "ranges": [], "rejectedCount": 0}
    idx = json.load(open(ip, encoding="utf-8"))
    for m in idx["movies"]:
        m[1] = None if m[1] is None else str(EPOCH + dt.timedelta(days=m[1]))
    order = [f"{t}|{o or ''}" for t, o, *_ in idx["movies"]]
    movies = {k: {"t": m[0], "o": m[1], "n": m[2], "meta": None, "d": {}} for k, m in zip(order, idx["movies"])}
    mp = os.path.join(DIR, "meta.json")
    if os.path.exists(mp):
        mj = json.load(open(mp, encoding="utf-8"))
        for k, (dist, genre, grade, dirr) in zip(order, mj["m"]):
            movies[k]["meta"] = {"dist": [mj["dist"][i] for i in dist], "genre": [mj["genre"][i] for i in genre],
                                 "grade": mj["grade"][grade] if grade >= 0 else "", "dir": dirr}
    for fn in sorted(os.listdir(DIR)):
        if not re.fullmatch(r"\d{4}\.json", fn):
            continue
        yf = json.load(open(os.path.join(DIR, fn), encoding="utf-8"))
        jan1 = dt.date(yf["y"], 1, 1)
        for mid, e in yf["m"].items():
            if len(e) != 5:
                fail(f"{fn}: 스크린수·상영횟수가 없는 옛 형식입니다. daily/를 비우고 전체 기간을 다시 받아야 합니다")
            off, *cols = e
            dd = movies[order[int(mid)]]["d"]
            for i, v in enumerate(zip(*cols)):
                if any(v):
                    dd[str(jan1 + dt.timedelta(days=off + i))] = list(v)
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
            cols = [[0] * n for _ in range(4)]  # 관객, 매출, 스크린, 상영
            for day in days:
                i = (dt.date.fromisoformat(day) - jan1).days - first
                for c, v in zip(cols, db["movies"][order[mid]]["d"][day]):
                    c[i] = v
            out[str(mid)] = [first, *cols]
        json.dump({"y": y, "m": out}, open(os.path.join(DIR, f"{y}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
    metas = [db["movies"][k]["meta"] or {"dist": [], "genre": [], "grade": "", "dir": ""} for k in order]
    dic = {f: sorted({x for m in metas for x in (m[f] if f != "grade" else [m[f]]) if x}) for f in ("dist", "genre", "grade")}
    pos = {f: {x: i for i, x in enumerate(v)} for f, v in dic.items()}
    json.dump({**dic, "m": [[[pos["dist"][x] for x in m["dist"]], [pos["genre"][x] for x in m["genre"]],
                             pos["grade"].get(m["grade"], -1), m["dir"]] for m in metas]},
              open(os.path.join(DIR, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
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
        day_sum, day_total, header_ok = 0, None, False
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
            c = [cell(x) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if c and c[0] == "순위":  # 머리글: 열 순서가 바뀌면 잘못 읽지 않도록 멈춘다
                header_ok = [re.sub(r"\s+", "", x) for x in c[:22]] == HEADER
                if not header_ok:
                    fail(f"{day} 엑셀 열 구성이 예상과 다릅니다: {c[:22]}")
                continue
            if not c:
                continue
            if c[0] == "합계":  # 그날 전체 합계 행: 검증에만 사용
                day_total = to_int(c[8]) if len(c) > 8 else None
                continue
            # 열: 순위 영화명 개봉일 매출액 점유율 매출증감 증감율 누적매출 관객수 관객증감 증감율 누적관객 스크린 상영횟수 대표국적 ...
            ok = (len(c) >= 21 and to_int(c[0]) and c[1] and re.fullmatch(r"\d{4}-\d{2}-\d{2}|", c[2])
                  and to_int(c[8]) is not None and to_int(c[8]) >= 0 and to_int(c[3]) is not None
                  and (to_int(c[12]) or 0) >= 0 and to_int(c[12]) is not None
                  and (to_int(c[13]) or 0) >= 0 and to_int(c[13]) is not None)
            if not ok:  # 영화를 알 수 없는 행 등: 버리고 기록. 관객수를 읽을 수 있으면 합계 검증에는 넣는다
                rejects.append({"day": day, "row": c[:9]})
                day_sum += to_int(c[8]) if len(c) > 8 and to_int(c[8]) is not None else 0
                continue
            key = f"{c[1]}|{c[2]}"
            mv = movies.setdefault(key, {"t": c[1], "o": c[2] or None, "n": "K" if c[14] == "한국" else "F", "meta": None, "d": {}})
            mv["d"][day] = [to_int(c[8]), to_int(c[3]), to_int(c[12]), to_int(c[13])]  # 관객, 매출, 스크린, 상영
            if day >= mv.get("metaDay", ""):  # 영화 정보는 가장 최근 날짜 값
                split = lambda s: [x.strip() for x in s.split(",") if x.strip()]
                mv["meta"], mv["metaDay"] = {"dist": split(c[17]), "genre": split(c[19]), "grade": c[18], "dir": c[20]}, day
            written.add((key, day))
            day_sum += to_int(c[8])
        if not header_ok:
            fail(f"{day} 엑셀 머리글을 찾지 못했습니다")
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
