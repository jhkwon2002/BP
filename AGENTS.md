# AGENTS.md

## dashboard/ — KOBIS 박스오피스 대시보드

KOBIS(영화관입장권통합전산망) 박스오피스 데이터로 연도별·영화별 관객수와 한국/외국 영화를 비교하는 단일 HTML 페이지.

### 파일

| 파일 | 역할 |
|---|---|
| `template.html` | 페이지 소스(CSS·JS). 데이터 자리는 `__DATA__` 한 곳. **화면 수정은 여기서** |
| `kobis.json` | 수집한 데이터. 손으로 고치지 말고 스크립트로만 갱신 |
| `index.html` | 빌드 결과(독립 페이지). 직접 고치지 말 것 |
| `scrape.py` | 역대 상위 200편 + 연도별 상위 50편 수집 → `kobis.json` 새로 작성 |
| `totals.py` | 연도별 전체 관객수(테마통계) → `totals` 추가 |
| `nation.py` | 국적 필터(K/F)로 영화별 국적 → `nation` 추가 |
| `build.py` | `template.html` + `kobis.json` → `index.html` |

### 명령 (모두 `dashboard/`에서 실행)

```sh
python3 build.py                    # 화면만 고쳤을 때
python3 scrape.py && python3 totals.py && python3 nation.py && python3 build.py   # 데이터 갱신 (순서 지킬 것)
```

표준 라이브러리와 `curl`만 쓴다. 데이터 갱신은 www.kobis.or.kr 접속이 필요하다.

### 규칙

- 숫자는 KOBIS에서 받은 값만 쓴다. 추정치나 기억에 의존한 값을 넣지 않는다.
- 요청 수는 제한되어 있다(수집 1회에 약 75건). 재시도는 최대 3회이며, 무한 루프를 만들지 않는다.
- 파싱한 행은 검증한다(필수 필드, 관객수는 0 이상의 정수, 연도 안에서 순위 중복 없음). 버린 행은 `rejectedCount`에 센다.
- 진행 중인 연도는 집계 기준일(`asOf`, 수집일 전날)과 함께 표시한다.
- 영화명 같은 데이터 문자열은 `textContent`로만 DOM에 넣는다(`innerHTML` 금지).
- 색은 `:root` 토큰(`--kr` 한국, `--fr` 외국 등)을 쓰고, 라이트/다크 두 테마를 유지한다.
- 외부 스크립트는 쓰지 않는다. 글꼴만 Google Fonts에서 불러온다.
- `template.html`을 고친 뒤에는 `python3 build.py`를 실행해 `index.html`도 함께 커밋한다.
