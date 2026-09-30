"""KOBIS 박스오피스 수집: 역대(누적) 1회 + 연도별(2004~2026) 연도당 1회 요청. 재시도 최대 3회."""
import datetime, html, json, re, subprocess, sys, time

BASE = "https://www.kobis.or.kr/kobis/business/stat/boxs/"
CJ = "cj.txt"
MAX_RETRY = 3

def curl(args, marker='id="searchForm"'):
    for attempt in range(1, MAX_RETRY + 1):
        r = subprocess.run(["curl", "-sS", "-b", CJ, "-c", CJ, "--max-time", "60",
                            "-w", "\n%{http_code}"] + args, capture_output=True)
        out = r.stdout.decode("utf-8", "replace")
        body, _, code = out.rpartition("\n")
        if r.returncode == 0 and code == "200" and marker in body:
            return body
        print(f"  retry {attempt}/{MAX_RETRY}: rc={r.returncode} code={code}", file=sys.stderr)
        time.sleep(2 * attempt)
    raise RuntimeError("request failed after retries: " + " ".join(args[-1:]))

def token(page):
    return re.search(r'name="CSRFToken" value="([^"]*)"', page).group(1)

def cell(tr, tid):
    m = re.search(r'<td id="%s"[^>]*>(.*?)</td>' % tid, tr, re.S)
    return None if m is None else html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()

def to_int(s):
    if s is None or not re.fullmatch(r"-?[\d,]+", s):
        return None
    return int(s.replace(",", ""))

def parse(page, rejects, label):
    rows, seen = [], set()
    total = re.search(r'총 <em class="fwb">([\d,]+)</em>건', page)
    for tr in re.findall(r'<tr id="tr_\d+".*?</tr>', page, re.S):
        mv = re.search(r"mstView\('movie','(\d+)'\).*?title=\"([^\"]*)\"", tr, re.S)
        rank, open_dt = to_int(cell(tr, "td_rank")), cell(tr, "td_openDt")
        audi, sales = to_int(cell(tr, "td_audiAcc")), to_int(cell(tr, "td_salesAcc"))
        reason = None
        if mv is None or not html.unescape(mv.group(2)).strip(): reason = "영화명/코드 없음"
        elif rank is None or rank < 1: reason = "순위 이상"
        elif rank in seen: reason = "순위 중복"
        elif audi is None or audi < 0: reason = "관객수 이상"
        elif sales is not None and sales < 0: reason = "매출액 음수"
        elif open_dt and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", open_dt): reason = "개봉일 형식"
        if reason:
            rejects.append({"src": label, "reason": reason, "snippet": re.sub(r"\s+", " ", tr)[:160]})
            continue
        seen.add(rank)
        rows.append({"r": rank, "code": mv.group(1), "t": html.unescape(mv.group(2)).strip(),
                     "o": open_dt or None, "a": audi, "s": sales})
    rows.sort(key=lambda x: x["r"])
    return rows, (to_int(total.group(1)) if total else None)

def main():
    rejects, log = [], []
    fetched_at = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    empty = "sMultiMovieYn=&sRepNationCd=&sWideAreaCd="

    p = curl([BASE + "findYearlyBoxOfficeList.do"])
    years = [int(y) for y in re.findall(r'<option value="(\d{4})"', p)]
    tok = token(p)

    allp = curl(["-X", "POST", BASE + "findFormerBoxOfficeList.do",
                 "--data", f"CSRFToken={tok}&loadEnd=0&searchType=search&{empty}"])
    alltime, n = parse(allp, rejects, "alltime")
    log.append({"src": "alltime", "reported": n, "kept": len(alltime)})

    yearly = {}
    for y in years:
        pg = curl(["-X", "POST", BASE + "findYearlyBoxOfficeList.do",
                   "--data", f"CSRFToken={tok}&loadEnd=0&searchType=search&sSearchYearFrom={y}&{empty}"])
        sel = re.search(r'<option value="(\d{4})"\s+selected', pg)
        if not sel or int(sel.group(1)) != y:
            raise RuntimeError(f"year mismatch for {y}")
        rows, n = parse(pg, rejects, str(y))
        yearly[str(y)] = rows
        log.append({"src": str(y), "reported": n, "kept": len(rows)})
        print(y, n, len(rows), file=sys.stderr)
        time.sleep(0.5)

    out = {"fetchedAt": fetched_at.isoformat(timespec="minutes"),
           "asOf": (fetched_at.date() - datetime.timedelta(days=1)).isoformat(),
           "years": years, "alltime": alltime, "yearly": yearly,
           "rejectedCount": len(rejects), "log": log}
    json.dump(out, open("kobis.json", "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(rejects, open("rejects.json", "w"), ensure_ascii=False, indent=1)
    print("rejected:", len(rejects), file=sys.stderr)

main()
