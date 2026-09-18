# AGENTS.md — 원시인 형님 2 프로토타입

> 이 파일은 저장소 루트에 `AGENTS.md`로 배치한다. 코딩 에이전트는 **작업 시작 전에 이 파일 전체를 읽는다.**

## 문서 경로 (코드보다 문서가 우선이다)

| 문서 | 경로 | 내용 |
|---|---|---|
| 기획 | **`docs/GDD.md`** | 게임 디자인 문서 v0.1. 시스템 규칙·테이블 스키마·분석 이벤트·MVP 범위 |
| 밸런스 | **`docs/BALANCE.md`** | `bal_v1` 수식·파라미터·목표 진행 벽 표·검산·시뮬레이터 구현 계약 |
| 빌드 플랜 | **`docs/BUILD_PLAN.md`** | 아키텍처·데이터 스키마·Phase별 태스크 카드(T0.1~T6.5)·회귀 명세·실행 가이드 |
| 가정 기록 | **`docs/ASSUMPTIONS.md`** | 결정·가정·보류 목록. **에이전트가 직접 추가하는 유일한 문서** |

문서와 코드가 다르면 **문서를 고치지 말고** 코드를 문서에 맞춘다. 문서 자체가 틀렸다고 판단되면 고치지 말고 `docs/ASSUMPTIONS.md`에 관측 사실을 한 줄 추가하고 보고한다.

## 이 저장소는

「원시인 형님 2」(방치형 RPG + 부족 경영 메타)의 **웹 프로토타입**이다. 목적은 하나다 — **`docs/BALANCE.md`의 목표 진행 벽 표를 화면 없이 재현하고, 그 결과를 사람이 눈으로 볼 수 있게 하는 것.** 그래서 순서가 정해져 있다: 결정적 코어 → 헤드리스 시뮬레이터 → 렌더러. 렌더러를 먼저 만들면 검증할 대상이 없다.

## 구조

- `packages/core` — 순수 게임 룰. **외부 런타임 의존성 0.** DOM·타이머·네트워크·파일 I/O·`Math.random`·`Date.now` 금지.
- `packages/data` — 테이블 로더. ajv(JSON Schema draft 2020-12) 검증, `_manifest.json` 체크섬, 참조 무결성. 파일 I/O는 여기서만 한다.
- `packages/sim` — 헤드리스 시뮬레이터 CLI. `core`·`data`만 의존. 봇 3종·회귀·확률 검증·곡선 diff.
- `apps/web` — 렌더러(PixiJS, PWA). `core`·`data`만 의존. **룰을 여기서 구현하지 않는다.** 화면은 코어 상태를 읽기만 한다.
- `data/*.json` — 모든 콘텐츠·밸런스 테이블. **코드에 수치를 하드코딩하지 않는다.**
- `data/schema/*.schema.json` — 테이블별 JSON Schema. 스키마 위반 = 기동 실패.
- `assets/source/` 사람 원화 · `assets/gen/` AI 변형 · `assets/_index.json` 메타.
- `tools/` — 검증·생성 스크립트. `reports/` — 시뮬레이터 산출물(커밋하지 않는다).

## 명령

```bash
npm ci                                              # 설치 (Node 22 LTS 고정, .nvmrc)
npm test                                            # 전체 테스트 (pretest에서 validate:assets + check:deps)
npm test -w packages/core                           # 코어만
npm test -w packages/core -- combat                 # 특정 스위트만
npm run build                                       # 전 패키지 빌드 (prebuild에서 validate:assets)

npm run sim -- --days 7 --bot balanced --seed 42    # 시뮬레이터 1회
npm run sim:regress                                 # 목표 벽 표 10 체크포인트 ±10% + 첫 벽 + 격차 + D1 프레스티지
npm run sim:prob                                    # 확률 표기 검증 + 천장 단언
npm run sim:determinism                             # 동일 시드 2회 바이트 동일
npm run sim:diff -- --base bal_v1 --head bal_v2     # 곡선 diff 리포트
npm run sim:long -- --all                           # 60·90일 장기 프로파일 (리포트 전용, 게이트 아님)

npm run dev -w apps/web                             # 렌더러 개발 서버
npm run e2e                                         # Playwright 스크린샷 + 콘솔 에러 검사

npm run validate:assets                             # 에셋 거버넌스 게이트
npm run check:deps                                  # 의존 방향·금지 식별자 검사
```

## 규칙

### 결정성 (가장 중요)

1. **난수는 `packages/core/src/rng.ts`의 시드 RNG(`xoshiro128**`)만 사용한다.** `Math.random()` 금지. 드랍·합성·뼈 갈기·몬스터 선택은 각각 `rng.fork(streamId)`로 스트림을 분리한다.
2. **시간은 정수 틱(100ms)으로만 흐른다.** 코어 상태에 실수 시간 변수를 두지 않는다. 시뮬레이터도 해석적으로 구한 시간을 `ceil(t_sec × 10)` 틱으로 올려 렌더러와 **같은 함수**를 호출한다.
3. **`Math.pow` 금지.** `g^n`은 로드 시 1회 생성한 사전 계산 테이블(반복 곱)에서 읽는다. 범위를 벗어나면 `RangeError`를 던지고 조용히 폴백하지 않는다. 유일한 예외는 `prestige.ts`의 비정수 지수 `Q = ember_c · s^ember_p` 1줄이며 `// ALLOW_POW:` 주석과 `check:deps` 화이트리스트에 등록되어 있다.
4. **`Date.now()`·`performance.now()`는 코어에 넣지 않는다.** 경과 시간은 어댑터가 계산해 초 단위 정수로 주입한다.
5. 부동소수점 덧셈·곱셈의 **순서를 바꾸지 않는다.** 배수 곱셈 순서는 `DPS_MULT_ORDER` 상수로 고정되어 있다.

### 데이터

6. **`data/balance.json`의 값을 수정하지 않는다.** 이 파일은 기획 담당(game-design-director)의 결정 사항이다. 회귀 테스트가 실패해도, 목표표를 못 맞춰도, 60일 시뮬레이션이 이상해도 **고치지 않고 보고한다.**
7. 수치를 코드에 하드코딩하지 않는다. 전부 `data/*.json`에서 읽는다. 확률 표기값을 테스트나 UI에 타이핑하면 검증 의미가 사라진다 — 반드시 `balance.drop_rates`에서 읽는다.
8. 새 콘텐츠는 **테이블 행 추가로만** 만든다. 몬스터 1종 추가에 코드 변경이 1줄이라도 필요하면 설계가 잘못된 것이다.
9. 타입·스키마 변경은 `data/schema/*.json` 갱신 + 테스트 동반. 스키마 위반 시 경고가 아니라 **기동 실패**여야 한다.

### 저장

10. 저장 데이터에는 `schemaVersion` 필드가 있다. **마이그레이션 함수 없이 `GameState`의 필드를 추가·제거·개명하지 않는다.** 구조 잠금 테스트가 이를 막는다.
11. 프레스티지는 `state.run`만 새로 만들고 `state.account`는 건드리지 않는다. GDD 4.1 「유지」 12항목 보존은 구조로 보장한다.
12. 사용자 설정(`account.settings`)은 로드 시 코드 기본값으로 덮어쓰지 않는다. 기본값 주입은 마이그레이션에서만 한다.

### 에셋 거버넌스

13. `assets/_index.json`에서 **`origin:"ai"`인 항목은 `source_id`와 `reviewed_by`가 필수**다. 비어 있으면 `npm run build`와 `npm test`가 실패한다. 게이트를 우회하지 않는다(`--ignore-scripts` 금지).
14. 사람 원화는 `assets/source/`, AI 변형은 `assets/gen/`에만 둔다. AI 변형의 `source_id`는 반드시 `origin:"human"` 항목이어야 한다(AI의 AI 변형 금지).
15. 애니메이션 프레임(`fx_anim_*`)은 사람 생산물만 허용한다.
16. 테이블에 에셋 **파일 경로를 쓰지 않는다.** `asset_id`만 쓰고 경로 해석은 `assets/_index.json`이 담당한다.

### 커밋

17. **커밋 1개 = 태스크 카드 1개.** 메시지 첫머리에 태스크 id를 붙인다: `T1.3: 전투 틱 루프와 벽 판정`.
18. 중간 상태를 커밋하지 않는다. 태스크가 1세션에 안 끝나면 카드를 2개로 쪼개는 제안을 보고하고 사람의 승인을 받는다.
19. `reports/`와 `node_modules/`는 커밋하지 않는다. `package-lock.json`은 커밋한다.

## 완료 정의

1. 태스크 카드의 **수용 기준 명령이 전부 통과**하고, 각 명령의 실제 출력을 보고에 붙였다.
2. `npm test` 전체 통과, `npm run check:deps`·`npm run validate:assets` 통과.
3. 밸런스에 영향을 주는 변경이면 `npm run sim:regress` 통과.
4. 변경 요약 3줄 + 새로 생긴 가정은 `docs/ASSUMPTIONS.md`에 추가.

**수용 기준을 약화시켜 통과시키는 것은 완료가 아니라 실패다.** 기대값 변경, 단언 삭제, `skip`/`todo` 추가, 테스트 개수 축소는 전부 금지다. 카드에 "14 passed"라고 적혀 있으면 14개가 실제로 통과해야 한다.

## 막히면

**규칙이 GDD에 없으면 임의로 정하지 않는다.** 순서는 이렇다.

1. 가장 **보수적인** 선택을 한다 — 유저에게 불리하지 않고, 성장 곡선을 빠르게 만들지 않는 쪽.
2. `docs/ASSUMPTIONS.md`에 한 행을 추가한다: `가정: {내용} / 근거: {왜 이 선택} / 영향: {어느 태스크·곡선}`.
3. 보고에 명시한다.

**단, `data/balance.json` 값 변경은 가정으로 처리할 수 없다.** 그건 항상 기획 담당 회신 대상이다.

### 상황별 대응

| 상황 | 행동 |
|---|---|
| 유닛 테스트 실패 | 스스로 고친다. 3회 시도 후에도 실패하면 중단하고 원인·시도 내역을 보고한다. 테스트를 약화시키지 않는다 |
| `sim:regress` 실패 | **`balance.json`을 건드리지 않는다.** ① 최근 diff에서 곡선 영향 변경을 찾는다 ② `npm run sim:diff`로 이전 통과 시점과 비교한다 ③ 구현 버그면 고친다 ④ 모델 가정 차이면 `ASSUMPTIONS.md`에 관측값과 함께 기록하고 기획 담당에게 회신한다 |
| `sim:determinism` 실패 | **최우선.** 점검 순서: `Math.random`/`Date.now` 유입 → 실수 시간 누적 → `Math.pow` 사용 → 객체 키 순회 순서 의존 → 부동소수점 연산 순서 변경. 고칠 때까지 다음 태스크로 넘어가지 않는다 |
| Playwright 스크린샷 차이 | 의도한 UI 변경이면 스크린샷을 갱신하고 커밋에 명시한다. 아니면 회귀다. **콘솔 에러 0건 기준은 어떤 경우에도 완화하지 않는다** |
| `validate:assets` 실패 | 우회하지 않는다. 메타를 채우거나, 감수 전이면 해당 에셋을 커밋에서 제외한다 |
| 선행 태스크 미완료 | 착수하지 않고 보고한다 |
