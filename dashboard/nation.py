"""국적 필터(K/F)로 연도별·역대 목록을 다시 받아 영화 코드별 국적을 매긴다. 요청 48건, 재시도 최대 3회."""
import json, re, sys, time
sys.argv = [sys.argv[0]]
exec(open("scrape.py").read().split("def main():")[0])  # curl, token, parse 재사용

d = json.load(open("kobis.json"))
p = curl([BASE + "findYearlyBoxOfficeList.do"])
tok = token(p)
nat, conflicts, rejects = {}, [], []

def fetch(url, extra, cd, label):
    pg = curl(["-X", "POST", BASE + url, "--data",
               f"CSRFToken={tok}&loadEnd=0&searchType=search&sMultiMovieYn=&sRepNationCd={cd}&sWideAreaCd={extra}"])
    sel = re.search(r'<option value="%s"\s+selected' % cd, pg) if cd else True
    if not sel:
        raise RuntimeError(f"nation filter not applied: {label}")
    rows, _ = parse(pg, rejects, label)
    for r in rows:
        if nat.get(r["code"], cd) != cd:
            conflicts.append(r["code"])
        nat[r["code"]] = cd

for cd in ("K", "F"):
    fetch("findFormerBoxOfficeList.do", "", cd, f"alltime-{cd}")
    for y in d["years"]:
        fetch("findYearlyBoxOfficeList.do", f"&sSearchYearFrom={y}", cd, f"{y}-{cd}")
        time.sleep(0.4)
    print(cd, "done", file=sys.stderr)

codes = {r["code"] for r in d["alltime"]} | {r["code"] for v in d["yearly"].values() for r in v}
missing = sorted(codes - nat.keys())
print("conflicts", len(conflicts), "missing", len(missing), "rejects", len(rejects), file=sys.stderr)
d["nation"] = {c: nat[c] for c in codes if c in nat}
d["nationMissing"] = len(missing)
json.dump(d, open("kobis.json", "w"), ensure_ascii=False, separators=(",", ":"))
