# AGENTS.md

## dashboard/ — KOBIS 박스오피스 대시보드

KOBIS(영화관입장권통합전산망) 박스오피스 데이터로 연도별·영화별 관객수와 한국/외국 영화를 비교하는 단일 HTML 페이지.

### 파일

| 파일 | 역할 |
|---|---|
| `template.html` | 페이지 소스(CSS·JS). 데이터 자리는 `__DATA__` 한 곳. **화면 수정은 여기서** |
| `kobis.json` | 수집한 데이터. 손으로 고치지 말고 스크립트로만 갱신 |
| `index.html` | 운영용 빌드 결과. `daily/`와 함께 웹서버에서 실행하며 직접 고치지 말 것 |
| `preview.html` | `build.py --preview`가 만드는 서버 없는 미리보기. 일별 자료도 압축해 포함하며 Git에는 저장하지 않음 |
| `scrape.py` | 역대 상위 200편 + 연도별 상위 50편 수집 → `kobis.json` 새로 작성 |
| `totals.py` | 연도별 전체 관객수(테마통계) → `totals` 추가 |
| `nation.py` | 국적 필터(K/F)로 영화별 국적 → `nation` 추가 |
| `daily.py` | 일별 박스오피스(엑셀)로 영화별 일별 관객수 → `daily/`에 합침. `python3 daily.py 시작일 종료일`(최대 731일) 또는 `--recent`(최근 7일) |
| `daily/index.json` | 영화 목록(id = 배열 위치, 순서 바꾸지 말 것)과 수집한 기간 `ranges`. 형식은 `daily.py` 맨 위 설명 참고 |
| `daily/YYYY.json` | 연도별 일별 관객수·매출액(숫자 배열). 페이지가 필요한 연도만 불러옴 |
| `build.py` | `template.html` + `kobis.json` → `index.html` |

### 명령 (모두 `dashboard/`에서 실행)

```sh
python3 build.py                    # 화면만 고쳤을 때
python3 build.py --preview          # 파일/앱 미리보기: preview.html을 열기
python3 scrape.py && python3 totals.py && python3 nation.py && python3 build.py   # 데이터 갱신 (순서 지킬 것)
```

표준 라이브러리와 `curl`만 쓴다. 데이터 갱신은 www.kobis.or.kr 접속이 필요하다.

### 자동 갱신·배포 (`.github/workflows/pages.yml`)

- 매일 07:10 KST(수동 실행도 가능)에 수집 → 검증 → 빌드 → `kobis.json`·`daily/`·`index.html` 커밋 → GitHub Pages 배포.
- 예약 실행은 일별 데이터를 최근 7일만 받는다. 수동 실행 때 `daily_from`/`daily_to`를 넣으면 그 기간을 받아 합친다.
- `main`에 `dashboard/**` 변경을 푸시하면 수집 없이 빌드·배포만 한다.
- 수집이나 검증이 실패하면 커밋·배포하지 않는다(이전 사이트 유지). 검증 조건을 느슨하게 바꾸지 말 것.

### 규칙

- 숫자는 KOBIS에서 받은 값만 쓴다. 추정치나 기억에 의존한 값을 넣지 않는다.
- 요청 수는 제한되어 있다(수집 1회에 약 75건). 재시도는 최대 3회이며, 무한 루프를 만들지 않는다.
- 파싱한 행은 검증한다(필수 필드, 관객수는 0 이상의 정수, 연도 안에서 순위 중복 없음). 버린 행은 `rejectedCount`에 센다.
- 진행 중인 연도는 집계 기준일(`asOf`, 수집일 전날)과 함께 표시한다.
- 영화명 같은 데이터 문자열은 `textContent`로만 DOM에 넣는다(`innerHTML` 금지).
- 색은 `:root` 토큰(`--kr` 한국, `--fr` 외국 등)을 쓰고, 라이트/다크 두 테마를 유지한다.
- 외부 스크립트는 쓰지 않는다. 글꼴만 Google Fonts에서 불러온다.
- `template.html`을 고친 뒤에는 `python3 build.py`를 실행해 `index.html`도 함께 커밋한다.
