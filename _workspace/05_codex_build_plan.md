# 원시인 형님 2 — Codex 빌드 플랜 v1

> 작성: codex-build-planner · 2026-09-18 · 썬더게임즈(부산) 신작 트랙
> 입력: `04_gdd_primitive_brothers_2.md` (GDD v0.1), `04b_balance_model.md` (bal_v1), `02_diagnostician_studio_diagnosis.md` (팀원 전달 메모 3)
> 출력 대상: OpenAI Codex(에이전틱 코딩 도구)의 자율 구현 세션
> 동반 산출물: `05b_AGENTS.md` (저장소 루트 `AGENTS.md`로 배치)

---

## 0. 이 문서를 읽는 법

| 읽는 사람 | 읽어야 할 절 |
|---|---|
| Codex 세션 1개(태스크 1개 수행) | `AGENTS.md` 전체 + 본 문서 1·2·3절 + 자기 태스크 카드 1장 |
| 사람 검토자(Phase 종료 시) | 5절(대응표) + 6절(회귀 기준) + 7.4(검토 포인트) |
| 기획 담당(game-design-director) | 8절(가정·미결) — **회신 요청 4건에 대한 리더 결정이 여기 있다** |

**설계 전제 3줄.** 코딩 에이전트는 모호함에 약하고 테스트로 완료를 증명할 수 있는 작업에 강하다. 그래서 (1) 렌더링 없는 결정적 코어를 먼저 만들어 모든 규칙을 유닛 테스트로 못 박고, (2) 그 코어를 그대로 돌리는 헤드리스 시뮬레이터로 밸런스를 회귀 테스트하고, (3) 마지막에 렌더러를 붙인다. 이 순서는 진단자 전달 메모의 "로직 추출 → 결정론적 실행 환경 → 회귀 시나리오 → 곡선 리포트" 권고와 동일하며, 신작에서는 리팩터링 없이 처음부터 이 형태로 짓는다.

**총 태스크 40개** (P0:4 / P1:10 / P2:8 / P3:4 / P4:5 / P5:4 / P6:5). 각 태스크 = Codex 1세션(S: 30분 미만 / M: 60분 미만).

---

## 1. 아키텍처

### 1.1 패키지 경계와 의존 방향

```
                       ┌───────────────────────────────┐
                       │   data/*.json  +  data/schema │
                       │   assets/_index.json          │
                       └───────────────┬───────────────┘
                                       │ (파일 읽기 + 스키마 검증)
                                       v
   ┌───────────────┐          ┌──────────────────┐
   │ packages/core │ <────────│  packages/data   │   ajv 2020-12
   │  의존성 0     │  주입     │  로더·검증·매니페스트 │
   │  순수 TS      │──────────>└──────────────────┘
   └───┬───────┬───┘   (타입만 역참조 없음: core는 plain object를 받는다)
       │       │
       │       └───────────────────────────┐
       v                                   v
 ┌──────────────┐                   ┌──────────────┐
 │ packages/sim │  헤드리스 CLI      │  apps/web    │  PixiJS PWA
 │  tsx 실행    │  CSV·MD 리포트     │  렌더러 전용  │  읽기 전용 셀렉터
 └──────┬───────┘                   └──────┬───────┘
        │                                  │
        └──────────> reports/ <────────────┘ (e2e 스크린샷: tests/e2e/__screenshots__)
```

**의존 규칙 (CI에서 강제)**

| 패키지 | 허용 의존 | 금지 |
|---|---|---|
| `packages/core` | **없음** (devDependencies의 vitest만) | DOM, `window`, `document`, `setTimeout`, `Date.now()`, `Math.random()`, `fs`, `process`, npm 런타임 의존성 전부 |
| `packages/data` | `ajv`, `ajv-formats`, `node:fs`, `node:crypto` | core 내부 구현 import (공개 타입만) |
| `packages/sim` | `core`, `data`, `node:*` | DOM, PixiJS |
| `apps/web` | `core`, `data`, `pixi.js` | 게임 규칙 구현(계산식을 여기 쓰면 태스크 실패) |

강제 방법: `tools/check-deps.ts`가 각 패키지 `package.json`의 `dependencies`와 소스의 import 목록을 대조하고, `packages/core/src/**`에 대해 금지 식별자(`Math.random`, `Date.now`, `document`, `window`, `setTimeout`, `performance`)를 정규식으로 검사한다. `npm run check:deps`가 CI 필수 게이트다.

### 1.2 결정성 계약 (가장 중요한 절)

프로토타입 성공 판정 기준 13.3-2 "동일 시드 2회 실행 결과가 바이트 단위로 동일"을 만족시키기 위한 4개 규칙이다. **이 4개가 깨지면 밸런스 회귀 전체가 무의미하다.**

**(D-1) 시간은 정수 틱으로만 흐른다.**
- `TICK_MS = 100` 고정. 코어 상태의 시간 필드는 `tick: number`(정수, 100ms 단위)뿐이다. 초 단위 실수 누적 변수를 상태에 두지 않는다.
- 렌더러는 실시간 경과를 `floor(elapsedMs / 100)`틱으로 환산해 `stepTicks(n)`을 호출한다. 배속 ×10/×100/×1000은 한 프레임에 `stepTicks(n × 배속)`을 호출하는 것일 뿐, 별도 코드 경로가 아니다.
- 시뮬레이터는 "다음 이벤트까지 걸리는 시간"을 해석적으로 구한 뒤 **`ceil(t_required_sec × 10)` 틱으로 올림**해서 `stepTicks()`에 넘긴다. 즉 시뮬레이터와 렌더러는 **같은 함수, 같은 양자화**를 쓴다. 이것이 "렌더러를 제거해도 헤드리스 시뮬레이터가 동일 결과를 낸다"(GDD 12.3)의 구현이다.
- 부작용: 밸런스 모델 9.2의 의사코드는 연속 시간을 쓴다. 100ms 양자화로 미세 편차가 생기며 이는 ±10% 회귀 밴드가 흡수한다(8절 U-3에 리스크로 등록).

**(D-2) 난수는 `xoshiro128**` 한 곳에서만 나온다.**
- 상태 = `Uint32Array(4)`. 연산은 `Math.imul`·`>>>`·`^`·`<<`만 사용 → 전부 32비트 정수 연산이라 엔진·플랫폼 간 결과가 정의상 동일하다.
- `next()`는 `uint32`를 반환하고, `nextFloat()`는 `next() / 2**32`(정확한 f64)만 제공한다. `Math.random()` 사용은 `check:deps`에서 실패 처리한다.
- 스트림 분리: 드랍/합성/뼈 갈기/몬스터 선택은 각각 **독립 RNG 인스턴스**를 쓴다(`rng.fork(streamId)`가 seed를 `splitmix32`로 파생). 한 스트림의 소비 횟수가 바뀌어도 다른 스트림의 시퀀스가 밀리지 않는다 → 기능 추가 시 회귀 곡선이 통째로 흔들리는 사고를 막는다.
- RNG 상태는 저장 포맷에 그대로 직렬화된다(`rng: {main:[u32×4], drop:[...], craft:[...]}`).
- **GDD 13.1 M1은 `xorshift128+`를 적었다.** xorshift128+는 64비트 상태라 JS에서 BigInt(느림) 또는 분할 구현(엔진 간 차이 위험)이 필요하다. 32비트 정수만 쓰는 `xoshiro128**`로 대체한다 → 가정 A-D5로 기록.

**(D-3) 거듭제곱은 `Math.pow`를 쓰지 않는다.** (리더 결정 ①)
- `g^n` 형태(`1.058^(s-1)`, `1.052^(s-1)`, `1.075^L`, `1.05^A`, `1.20^k`)는 전부 **로드 시 1회 생성하는 사전 계산 테이블**에서 읽는다. 테이블은 `pow[0]=1; pow[i]=pow[i-1]*g` 반복 곱으로 만든다.
- 사전 계산 범위: 스테이지 `1..STAGE_TABLE_MAX(=2000)`, 강화 레벨 `0..LEVEL_TABLE_MAX(=4000)`, 노드 `0..NODE_TABLE_MAX(=4000)`, 장비 등급 `0..40`.
- 범위를 벗어나면 **예외를 던진다**(조용한 `Math.pow` 폴백 금지). 범위 확장은 balance.json이 아니라 `core/constants.ts`의 상수 변경 + 회귀 재실행으로 처리한다.
- 대수 표현은 IEEE754 f64. bal_v1의 D30 값(HP≈1.07e26, M≈3.02e12, D30 소과금 s=1150에서 HP≈1.2e32)은 f64 범위(≈1.8e308) 안이다. 1e300 초과 대비 로그 공간/`{mantissa,exponent}` 전환은 **확장 태스크 P6.5**로만 명시하고 MVP에서는 하지 않는다.

**(D-4) 결정성 테스트의 범위를 좁게 정의한다.** (리더 결정 ①)
- 판정: **동일 Node LTS 버전(22.x, `.nvmrc` 고정) · 동일 시드 → 출력 바이트 동일.** 다른 엔진(브라우저 JS, 향후 C#)과의 바이트 동일성은 요구하지 않는다.
- 측정: `sim` 실행 결과 디렉터리 전체의 SHA-256을 찍어 두 번 실행분을 비교한다(`npm run sim:determinism`).
- 브라우저와 Node 사이는 "동일 시드 → 동일 최종 스테이지·골드(상대오차 0)"를 Playwright 테스트로 별도 확인한다(P4.5). 여기서 차이가 나면 (D-1)~(D-3) 중 하나가 깨진 것이다.

### 1.3 코어 상태 모델

```ts
// packages/core/src/state.ts  (전부 plain data. 클래스 메서드에 상태를 숨기지 않는다)
type GameState = {
  schemaVersion: number;        // 저장 포맷 버전 (1.5절)
  dataVersion: number;          // balance.json의 version. 분석 이벤트 data_version과 동일 값
  tick: number;                 // 100ms 단위 정수 경과 시간 (D-1)
  rng: RngBundle;               // 스트림별 uint32 상태 (D-2)
  run: {                        // 세대 교체로 리셋되는 것 (GDD 4.1 리셋 열)
    stage: number; runBest: number; gold: number;
    levels: number[];           // 형님별 L_i (index = brothers.slot)
    unlocked: boolean[];
    equip: { tier: number; owned: number[] };   // owned[k] = k등급 보유 수
    campLevels: Record<string, number>;
    startedAtTick: number;
  };
  account: {                    // 절대 리셋되지 않는 것 (GDD 4.1 유지 열 12종)
    bestEver: number; ember: number; nodes: Record<Branch, number>;
    codexKills: Record<string, number>; cards: string[];
    skins: string[]; equippedSkin: Record<string, string|null>;
    mounts: string[]; campUnlocked: string[];
    seasonPass: { level: number; xp: number; premium: boolean };
    achievements: Record<string, number>; stats: Record<string, number>;
    mailbox: MailItem[];        // 미수령 상품 (11.3-2)
    pity: { grind: number };    // 천장 카운터. 세대 교체로 리셋되지 않음 (GDD 7.3)
    prestigeCount: number; purchases: string[];
    settings: Record<string, unknown>;  // 보스 원정 설정 등 (11.3-3)
  };
  wallWindow: { samples: Array<[tick:number, best:number]> };  // 30분 이동창
};
```

**불변식 (테스트로 단언)**
- `run` 밖의 필드는 `prestige()`가 절대 건드리지 않는다. `prestige()`는 `state.run`을 통째로 새로 만들고 `state.account`는 얕은 복사조차 하지 않는다(참조 유지). → GDD 4.1 유지 자산 12종 보존이 구조로 보장된다.
- `GameState`는 JSON 직렬화 가능(함수·Map·Set·undefined 금지). 저장·복원·비교가 전부 `JSON.stringify`로 끝난다.

### 1.4 틱 파이프라인 (GDD 3.2 표의 구현)

```
stepTicks(state, n, tables):
  for each "구간"(다음 이벤트까지 정수 틱 수):
    1. dps  = computeDps(state, tables)            // 3.1 모든 배수의 곱
    2. 전투 해상도:
         일반: t_req = max(n_mob*HP(s)/dps, t_min_kill*n_mob)
         보스: t_req = max(m_boss*HP(s)/dps, t_min_kill*1)
         ticksNeeded = ceil(t_req * 10)
    3. ticksNeeded가 보스 타이머(300틱)를 넘으면 → wall_hit 발행 + f* 파밍 모드
    4. 처치 처리: gold += G(s)*배수, codexKills++, 드랍 롤(drop 스트림)
    5. 웨이브 소진 → s += 1, runBest 갱신
    6. autoUpgrade가 켜져 있으면 buyGreedy() (1.4의 그리디)
    7. wallWindow 갱신 → 정체 감지 → 프레스티지 힌트/자동 프레스티지
```

- 보스 타임아웃 판정은 **틱 단위 정수 비교**(`ticksNeeded > boss_timer_sec*10`)로 한다. 실수 비교(`t_req > 30.0`)를 쓰면 경계에서 플랫폼 차이가 난다.
- f* 파밍 모드에서는 스테이지가 오르지 않고 `rate(f*) = G(f*)/t_min_kill`로 골드만 누적한다(밸런스 모델 4.3).

### 1.5 저장 포맷과 마이그레이션

```jsonc
{
  "schemaVersion": 1,          // 저장 포맷 버전 (코드가 소유)
  "dataVersion": 1,            // balance.json version (데이터가 소유)
  "savedAtMs": 1789500000000,  // 벽시계. 오프라인 계산에만 쓰고 룰에는 쓰지 않는다
  "state": { /* GameState */ }
}
```

- `packages/core/src/save/migrations.ts`에 `Record<number, (save) => save>` 레지스트리. `load()`는 `schemaVersion`이 현재보다 낮으면 등록된 마이그레이션을 순서대로 적용하고, 높으면 **로드를 거부**한다(미래 세이브 손상 방지).
- 마이그레이션 없이 필드를 추가·제거·개명하면 P3.2의 테스트가 실패한다(`SCHEMA_VERSION`과 마이그레이션 개수가 일치해야 한다).
- 오프라인 경과 시간은 `Date.now() - savedAtMs`로 **어댑터(`apps/web`, `packages/sim`)에서만** 계산해 `applyOffline(state, elapsedSec, opts)`에 초 단위 정수로 넘긴다. 코어는 벽시계를 모른다.

### 1.6 테이블 로딩과 스키마 검증

1. `packages/data/src/load.ts`가 `data/*.json`을 읽는다.
2. **ajv(draft 2020-12, `strict: true`, `allErrors: true`)** 로 `data/schema/{table}.schema.json`을 컴파일해 검증한다. 자체 검증기가 아니라 ajv를 쓴다 — 스키마가 문서이자 테스트가 되고, 신규 테이블 추가 시 코드 변경이 0줄이기 때문이다.
3. `data/_manifest.json`의 `checksum`(파일 내용 SHA-256, 개행 정규화 후)을 대조한다. 불일치 시 **기동 실패**.
4. 참조 무결성 검사(스키마로는 못 잡는 것): `brothers.skin_ids ⊆ skins.id`, `monsters.codex_id ∈ collection.id`, `equipment.merge_from ∈ equipment.id`, `stages.monster_pool ⊆ monsters.id`, `*.asset_id ∈ assets/_index.json`.
5. 파생 테이블 생성(1회): 스테이지 HP/골드 테이블, 강화 비용 테이블, 노드 비용 누적 테이블 (D-3).
6. 결과를 `Tables` 불변 객체로 얼려(`Object.freeze` 재귀) 코어에 주입한다.

**스키마 위반 = 기동 실패**(GDD 13.1 M2). 경고 후 진행하는 경로를 만들지 않는다.

### 1.7 에셋 거버넌스 게이트 (빌드 실패 규칙)

GDD 8.1을 코드로 강제한다. `tools/validate-assets.ts`:

| 검사 | 실패 조건 |
|---|---|
| `origin` 필수 | `"human"` \| `"ai"` 이외 값 |
| **AI 산출물 추적** | `origin==="ai"`인데 `source_id`가 비었거나 `_index.json`에 없음 |
| **사람 감수** | `origin==="ai"`인데 `reviewed_by`가 비었거나 `reviewed_at`이 ISO8601이 아님 |
| 디렉터리 분리 | `origin==="human"`인데 경로가 `assets/source/`로 시작하지 않음 / `origin==="ai"`인데 `assets/gen/`로 시작하지 않음 |
| id 규칙 | `{kind}_{family}_{index}[_{variant}]` 정규식 불일치 (`^(bro\|mon\|eqp\|skn\|mnt\|tot\|bg\|ui\|fx\|card)_[a-z0-9_]+_\d{3}(_[a-z]\d{2}\|_icon\|_silh)?$`) |
| 변형 일관성 | variant가 있는데 `source_id`가 없음 / `source_id`의 `origin`이 `"ai"`임(AI의 AI 변형 금지) |
| 고아 참조 | 테이블이 참조하는 `asset_id`가 인덱스에 없음 |

- 실행 지점: `npm run validate:assets` — **`prebuild` 스크립트와 `pretest` 스크립트에 연결**해서 `npm run build`/`npm test`가 자동으로 통과해야만 진행되게 한다. CI에서도 독립 잡으로 돈다.
- 스프라이트 애니메이션 프레임(`kind=fx` 중 `anim_` 접두)은 `origin==="human"`만 허용한다(GDD 9.2: 프레임 간 일관성은 현 시점 AI 한계).

### 1.8 분석 이벤트 배출 경로

- 코어는 `EventSink` 인터페이스(`emit(name, payload)`)만 안다. I/O는 하지 않는다.
- 공통 필드(GDD 11.1) 14개는 코어의 `withCommon()`이 주입하며, **`data_version`은 `state.dataVersion`에서 자동으로 채운다**(누락 시 타입 에러가 나도록 필수 필드로 선언). GDD 모호 지점 10번의 대응이다.
- 싱크 구현: `sim` → `reports/{runId}/events.jsonl`, `web` → IndexedDB 버퍼 + 다운로드 버튼, 향후 서버 → HTTP 배치.

### 1.9 2차 트랙 — Unity/C# 포팅 (1절)

진단자 전달 메모의 추정 스택은 Unity/C#이고 **U-06(전투 로직이 화면 갱신 코드와 분리되어 있는가)이 미확인**이다. 본 빌드 플랜은 그 값과 무관하게 진행할 수 있도록 설계했다: 웹 프로토타입의 `packages/core`가 **신작의 규칙 원본**이 되고, Unity 클라이언트는 이 원본을 1:1 포팅한 `PrimitiveCore` C# 클래스 라이브러리(MonoBehaviour 상속 금지, `UnityEngine` using 금지)를 참조한다. 포팅 시 지켜야 할 4가지는 (a) 같은 `data/*.json`을 그대로 로드(파서만 교체), (b) `xoshiro128**`을 `uint` 연산으로 동일 구현(C#의 `uint`는 JS의 `Math.imul` 결과와 정의상 일치), (c) 시간은 `long tick`(100ms), (d) 사전 계산 테이블을 `double[]`로 동일 절차 생성. 검증은 **교차 골든 테스트** — TS 시뮬레이터가 시드별 최종 상태를 `golden/{seed}.json`으로 뽑고, C# 테스트가 같은 시드로 같은 JSON을 만들어 비교한다(허용 오차: 스테이지·레벨·노드 수는 완전 일치, 골드는 상대오차 1e-9). 진단 결과 전작 전투 로직이 "혼재됨"으로 나오면 이 라이브러리가 **추출 대상이 아니라 교체 대상**이 되므로, 리팩터링 견적이 아니라 신규 작성 견적으로 바뀐다는 점을 경영진 보고에 반영해야 한다. 포팅 태스크 카드는 프로토타입 성공 판정(GDD 13.3) 통과 후에 별도 문서로 분해한다.

---

## 2. 저장소 구조와 데이터 파일

```
primitive-brothers-2/
├─ AGENTS.md                     ← 05b_AGENTS.md를 그대로 배치
├─ .nvmrc                        ← "22"
├─ package.json                  ← npm workspaces 루트
├─ tsconfig.base.json
├─ vitest.workspace.ts
├─ playwright.config.ts
├─ .github/workflows/ci.yml
├─ docs/
│   ├─ GDD.md                    ← 04_gdd_primitive_brothers_2.md 복사본
│   ├─ BALANCE.md                ← 04b_balance_model.md 복사본
│   ├─ BUILD_PLAN.md             ← 본 문서 복사본
│   └─ ASSUMPTIONS.md            ← 8절을 초기 내용으로. Codex가 추가한다
├─ data/
│   ├─ brothers.json  upgrades.json  equipment.json  totems.json
│   ├─ stages.json    monsters.json  skins.json      mounts.json
│   ├─ collection.json events.json   shop_products.json  balance.json
│   ├─ _manifest.json
│   └─ schema/{같은 이름}.schema.json  (+ 확장 전용 5종)
├─ assets/
│   ├─ source/                   ← 사람 원화만
│   ├─ gen/                      ← AI 변형만
│   └─ _index.json
├─ packages/
│   ├─ core/   src/{rng,state,tables,combat,upgrade,equip,offline,prestige,codex,save,format,events}.ts
│   ├─ data/   src/{load,validate,manifest,integrity}.ts
│   └─ sim/    src/{cli,profiles,bots,schedule,report,regress,diff}.ts
├─ apps/web/   src/{main,render/*,ui/*,bind/*}.ts  + index.html + manifest.webmanifest
├─ tools/      validate-assets.ts  gen-manifest.ts  gen-equipment.ts  check-deps.ts
├─ tests/e2e/  *.spec.ts  __screenshots__/
└─ reports/    {runId}/{summary.json,gold_curve.csv,stage_curve.csv,walls.csv,report.md,events.jsonl}
```

**npm 스크립트 (루트 `package.json`)**

| 스크립트 | 내용 |
|---|---|
| `npm ci` | 설치 (Node 22.x 고정) |
| `npm test` | `vitest run` 전 워크스페이스 (pretest에서 `validate:assets`, `check:deps`) |
| `npm test -w packages/core` | 코어 유닛 테스트만 |
| `npm run sim -- --days 7 --bot balanced --seed 42` | 시뮬레이터 1회 실행 |
| `npm run sim:regress` | 목표 벽 표 10 체크포인트 + 첫 벽 + 확률 + 천장 회귀 |
| `npm run sim:diff -- --base bal_v1 --head bal_v2` | 곡선 diff 마크다운 리포트 |
| `npm run sim:determinism` | 동일 시드 2회 실행 SHA-256 비교 |
| `npm run sim:long -- --days 90` | 60/90일 장기 프로파일 (리포트 전용) |
| `npm run dev -w apps/web` | 렌더러 개발 서버 |
| `npm run e2e` | Playwright 스크린샷 + 콘솔 에러 검사 |
| `npm run validate:assets` | 에셋 거버넌스 게이트 (1.7) |
| `npm run check:deps` | 의존 방향·금지 식별자 검사 (1.1) |
| `npm run build` | 전 패키지 빌드 (prebuild에서 validate:assets) |

**도구 버전 고정**: Node 22 LTS(`.nvmrc`=`22`, `package.json engines.node=">=22 <23"`), TypeScript 5.x, vitest, tsx, Playwright, ajv 8.x, pixi.js 8.x. 패키지 매니저는 npm(워크스페이스). `package-lock.json`을 커밋한다.

---

## 3. 데이터 테이블 스키마

### 3.1 공통 규칙

- JSON 배열 1테이블 1파일(`balance.json`만 단일 객체). 첫 필드 `id`(string, snake_case, 전역 유일).
- JSON Schema draft 2020-12. 모든 스키마에 `"additionalProperties": false`, `"required"` 전량 명시, 수치에 `minimum`/`maximum` 명시.
- 확률은 `number` 0~1, 시간은 초, 배수는 `number`.
- **`data/balance.json`이 모든 튜닝 파라미터의 유일한 원본이다.** `stages.json`/`upgrades.json`의 곡선 필드(`hp0`, `hp_growth`, `cost_growth` 등)는 **선택 필드**이며, 생략하면 로더가 balance 값을 상속한다(`resolveStageParams()`). MVP 테이블은 전부 생략한다. GDD 8.3/8.6 예시 JSON에는 값이 박혀 있으나 그것은 문서용 예시이고 구현은 상속 규칙을 따른다 → 가정 A-D6.

### 3.2 MVP 초기 행 수

| 파일 | MVP 행 수 | 내용 | 확장 시 |
|---|---|---|---|
| `brothers.json` | **4** | `bro_thak`(slot0) `bro_urg`(1) `bro_gom`(2) `bro_ddol`(3). `unlock_stage` 1/12/35/75 | +2행 (150, 280) |
| `upgrades.json` | **4** | 형님별 `atk` 트랙 1개씩 | 전역·캠프 트랙 추가 |
| `equipment.json` | **13** | `eqp_bone_club_t0..t12` (weapon 1계열). `tools/gen-equipment.ts`가 생성 | 계열 추가 = 13행씩 |
| `totems.json` | **4** | 계열 1행씩(`fire`/`hunt`/`step`/`hide`). **MVP 로더는 `fire`만 활성** | 로더 플래그만 해제 |
| `stages.json` | **1** | `stg_w1_main` (1~1000, type=normal) | `stg_w2_main`, tower/raid 행 |
| `monsters.json` | **6** | 툰드라 팔레트 6종 | 월드당 6종 |
| `skins.json` | **2** | `skn_thak_basic`(free, bonus 0), `skn_thak_ice`(pass, +0.05) | 형님×3종 |
| `mounts.json` | **1** | `mnt_sabertooth` (MVP 미지급, 스키마 검증용) | |
| `collection.json` | **6** | monsters와 1:1 | |
| `events.json` | **1** | 샘플 `evt_glacier_boss_s1` (MVP 로더는 읽기만) | |
| `shop_products.json` | **9** | GDD 7.2 표 전량 | |
| `balance.json` | **1** (객체) | 3.4의 전 키 | |
| `_manifest.json` | 12 항목 | `{table, version, checksum}` | |
| `assets/_index.json` | **약 34** | 형님4 + 몬스터6 + 장비1+팔레트12 + UI·배경 약 10 + 카드 1 | |

**MVP 총 행 수 약 60.** "신규 몬스터 1종 = 코드 0줄 + 테이블 1행"(GDD 13.3-4)을 P1.1 태스크의 수용 기준으로 검증한다.

### 3.3 테이블별 필드 제약 (JSON Schema 요약)

GDD 8.2~8.12를 그대로 옮기되, 스키마로 강제해야 하는 제약을 **굵게** 표시한다.

| 테이블 | 필수 필드 | 스키마 강제 제약 |
|---|---|---|
| `brothers` | id, name_ko, slot, atk0, cost0, unlock_stage, passive_id, asset_id, skin_ids | `slot` 0~5 **유일**, `name_ko` 1~16자, `atk0>0`, `cost0>0`, `unlock_stage≥1`, `passive_id` null 허용 |
| `upgrades` | id, target_type, target_id, stat, curve, base_value, cost0 | `target_type` enum, `stat` enum, `curve` enum, `lin_coeff` 0~1, `step_every≥1`, `step_mult` 1~3, `cost_growth` 1.0~1.2, `max_level` null 허용 |
| `equipment` | id, name_ko, slot, tier, mult, merge_count, drop_stage_min, drop_weight, asset_id | `tier` 0~40, **`mult == equip_tier_mult^tier` (로더 파생 검사, 오차 1e-12)**, `merge_count == 4`, `drop_weight` 0~1, `merge_from` null 또는 tier-1 항목 |
| `totems` | id, branch, order, cost_base, cost_slope, effect_stat, effect_value, effect_kind, requires | `branch` enum 4종 **유일**, **`order == 0` (계열 1행 규칙 — 589행 금지)**, `cost_slope > 0`, `effect_kind` enum |
| `stages` | id, type, range_from, world_id, monster_pool | `range_to` null 허용, `range_from ≤ range_to`, **구간 중첩 금지(로더 검사)**, `monster_pool` minItems 1 |
| `monsters` | id, name_ko, family, rank, hp_mult, gold_mult, codex_id, asset_id | `hp_mult` 0.8~1.3, `gold_mult` 0.8~1.3, `rank` enum |
| `skins` | id, brother_id, name_ko, rarity, stat_bonus, acquire, asset_id, source_asset_id | **`stat_bonus.value ≤ 0.05` (GDD 5.8 상한, 스키마 `maximum`)**, `product_id` null 허용 |
| `mounts` | id, name_ko, offline_cap_add_sec, start_stage_add, atk_mult, acquire, asset_id | `offline_cap_add_sec` 0~14400, `start_stage_add` 0~50, **`atk_mult` 1.00~1.05** |
| `collection` | id, monster_id, tiers, rewards, card_asset_id, persist_on_prestige | `tiers` = `[10,100,1000]` 고정 길이 3 오름차순, `rewards` 길이 == tiers 길이, **`persist_on_prestige` const true** |
| `events` | id, type, start_at, end_at, reward_hours, repeat | `start_at`/`end_at` `format: date-time`, **`reward_hours` 0.5~10 (절대 수치 금지 — GDD 6.3)**, `end_at > start_at` |
| `shop_products` | id, name_ko, price_krw, store_sku, kind, grants, is_probabilistic | `price_krw ≥ 0`, **`is_probabilistic` const false** (뼈 갈기는 상품이 아니라 게임 내 시행이므로 상점 테이블에 확률형 상품이 존재할 수 없다) |

**확장 전용 스키마(로더 무시, 파일만 존재)**: `camp_buildings`, `guilds`, `pass_tracks`, `drop_tables`, `passives` — P0.3에서 스키마만 작성하고 `_manifest.json`에 `"loaded": false`로 등록한다.

### 3.4 `data/balance.json` (단일 원본, 전체 키)

밸런스 모델 10절 + GDD 8.13을 합친 최종 키 목록이다. **이 파일의 값은 Codex가 절대 수정하지 않는다**(AGENTS.md 금지 규칙).

```json
{
  "id": "bal_v1", "version": 1,
  "hp0": 25.0, "hp_growth": 1.058, "hp_step_coeff": 0.25, "hp_step_every": 10,
  "mob_count": 4, "boss_every": 10, "boss_mult": 7.0, "boss_timer_sec": 30,
  "gold0": 8.0, "gold_growth": 1.052, "boss_gold_mult": 10.0,
  "t_min_kill_sec": 0.5, "t_wall_sec": 30,
  "atk0": 6.0, "atk_lin_coeff": 0.12, "atk_step_mult": 1.75, "atk_step_every": 25,
  "brother_atk_ratio": 4.0, "brother_cost_ratio": 4.0,
  "brother_unlock_stages": [1, 12, 35, 75, 150, 280],
  "cost0": 25.0, "cost_growth": 1.075,
  "equip_tier_mult": 1.20, "equip_tier_span": 60, "equip_tier_cap": 40, "merge_count": 4,
  "equip_recovery_mode": "drop_wait",
  "offline_cap_sec": 28800, "offline_rate": 0.60, "ad_offline_mult": 2.0,
  "pass_offline_cap_sec": 43200,
  "ember_c": 0.35, "ember_p": 1.45,
  "node_cost_base": 5.0, "node_cost_slope": 0.7, "node_effect": 1.05,
  "prestige_min_stage": 120, "prestige_ratio_hint": 1.15, "start_stage_ratio": 0.5,
  "wall_window_sec": 1800, "wall_window_gain": 5,
  "rng_seed_default": 20260918,
  "drop_rates": { "bone_grind": { "legend": 0.005, "hero": 0.03, "rare": 0.15, "common": 0.815 } },
  "pity_hero": 20, "pity_legend": 40
}
```

스키마 강제 제약: `drop_rates.bone_grind`의 4개 값 **합이 1.0 ± 1e-9**(로더 검사), `node_cost_slope > 0`(등차 보장), `equip_recovery_mode` enum `["instant","drop_wait"]`, `version` integer ≥ 1.

`equip_recovery_mode`는 GDD·밸런스 모델에 없는 **신설 키**다. 리더 결정 ③(드랍 대기 가정 채택)과 밸런스 모델의 즉시 반영 근사를 둘 다 실행 가능하게 만들어, 회귀 기준(`instant`)과 실제 게임 동작(`drop_wait`)의 격차를 리포트로 산출하기 위한 것이다(8절 D3·U-2 참조).

---

## 4. Phase별 태스크 카드

**읽는 규칙**: 태스크 1개 = Codex 1세션 = 커밋 1개. 수용 기준은 전부 `실행 명령 → 기대 결과` 형식이며, "동작해야 한다" 같은 서술은 기준이 아니다. 의존 태스크가 끝나지 않았으면 착수하지 않는다.

**Phase 순서가 스킬 기본형과 다른 점**: 스킬 템플릿은 Phase 3을 "저장·오프라인·프레스티지"로 두지만, 본 플랜은 **오프라인·프레스티지를 Phase 1(코어)로 올리고 Phase 3을 "저장·영속성·회귀 시나리오"로 재정의**했다. 밸런스 회귀(Phase 2)가 프레스티지와 오프라인 없이는 목표 벽 표를 재현할 수 없고, 디렉터 우선순위표도 오프라인(5위)·프레스티지(6위)를 시뮬레이터(8위)보다 앞에 두었기 때문이다.

---

### Phase 0 — 스캐폴드 (4태스크)

#### T0.1 모노레포 스캐폴드와 CI 게이트
- 목표: Node 22 고정 npm workspaces 모노레포를 만들고 빈 패키지 4개가 빌드·테스트·린트를 통과하게 한다.
- 의존: 없음
- 입력: 본 문서 1.1, 2절. `AGENTS.md`
- 산출: `package.json`, `.nvmrc`, `tsconfig.base.json`, `vitest.workspace.ts`, `packages/{core,data,sim}/package.json`+`tsconfig.json`+`src/index.ts`, `apps/web/package.json`, `tools/check-deps.ts`, `.github/workflows/ci.yml`, `.gitignore`, `docs/ASSUMPTIONS.md`(빈 템플릿)
- 규칙: `packages/core`의 `dependencies`는 **빈 객체**여야 한다. `check-deps.ts`는 `packages/core/src/**`에서 금지 식별자(`Math.random`, `Date.now`, `document`, `window`, `setTimeout`, `setInterval`, `performance`, `require(`, `process.`)를 정규식으로 찾아 1건이라도 있으면 exit 1.
- 수용 기준:
  1. `node -v` → `v22.` 로 시작
  2. `npm ci` → 종료 코드 0, `package-lock.json` 존재
  3. `npm run build` → 4개 패키지 전부 `tsc` 성공, 종료 코드 0
  4. `npm test` → vitest 0 failed (스모크 테스트 1개 통과: `expect(1).toBe(1)`)
  5. `npm run check:deps` → `OK: core has 0 runtime deps, 0 forbidden identifiers` 출력, 종료 코드 0
  6. `packages/core/src/index.ts`에 `Math.random()` 한 줄을 임시로 넣고 `npm run check:deps` → **종료 코드 1**, 파일·라인 번호가 출력됨 (넣은 줄은 되돌린다)
- 크기: M
- 참고: `vitest.workspace.ts`를 빼먹으면 `npm test -w packages/core` 형태의 부분 실행이 안 된다. Playwright는 T4.5에서 설치하므로 여기서 devDependency에 넣지 않는다.

#### T0.2 시드 RNG (`xoshiro128**`)와 스트림 분리
- 목표: 코어 전역의 유일한 난수원을 구현하고 결정성·분포를 테스트로 고정한다.
- 의존: T0.1
- 입력: 본 문서 1.2 (D-2), GDD 13.1 M1
- 산출: `packages/core/src/rng.ts`, `packages/core/src/rng.test.ts`
- 규칙: 상태 `Uint32Array(4)`. `Math.imul`·시프트·XOR만 사용. `nextFloat() = next() / 2**32`. `fork(streamId: string)`은 `splitmix32(hash(streamId) ^ seed)`로 새 인스턴스를 만든다. 상태 직렬화 `toJSON(): number[4]` / `fromJSON()`.
- 수용 기준:
  1. `npm test -w packages/core -- rng` → **14 passed, 0 failed**
  2. 테스트 목록에 다음 케이스가 모두 포함: ① 동일 시드 2개 인스턴스가 10,000회 동일 시퀀스 ② `toJSON→fromJSON` 후 이후 1,000개 시퀀스 동일 ③ `nextFloat()` 결과가 전부 `[0,1)` ④ 100,000회 평균이 `0.5 ± 0.005` ⑤ `nextInt(0,1)` 1,000,000회에서 각 값 빈도 `0.5 ± 0.003` ⑥ 서로 다른 `fork("drop")`/`fork("craft")`의 첫 1,000개가 1개도 겹치지 않음 ⑦ **경계**: seed=0에서도 상태가 전부 0이 되지 않음(all-zero 상태 금지) ⑧ seed=`2**32-1`에서 정상 동작
  3. `grep -rn "Math.random" packages/` → 출력 0줄
- 크기: S
- 참고: `next() / 2**32`를 `next() / 0xFFFFFFFF`로 쓰면 1.0이 나올 수 있다. 반드시 `2**32`로 나눈다.

#### T0.3 데이터 스키마·로더·매니페스트
- 목표: `data/*.json` 12종과 JSON Schema 12종(+확장 5종)을 작성하고, ajv 검증·체크섬·참조 무결성을 통과하는 로더를 만든다.
- 의존: T0.1
- 입력: 본 문서 3절 전체, GDD 8.1~8.14, 밸런스 모델 10절
- 산출: `data/*.json`(12), `data/schema/*.schema.json`(17), `data/_manifest.json`, `packages/data/src/{load,validate,manifest,integrity}.ts` + 테스트, `tools/gen-manifest.ts`, `tools/gen-equipment.ts`
- 규칙: 3.2의 MVP 행 수를 그대로 채운다. 3.3의 굵은 제약을 스키마에 반영한다. `balance.json`은 3.4를 **한 글자도 바꾸지 않고** 그대로 쓴다. `totems.json`은 계열 1행 + `order:0` (589행 금지).
- 수용 기준:
  1. `npm test -w packages/data` → **22 passed, 0 failed**
  2. 테스트에 다음 실패 케이스가 포함되고 각각 기동 실패를 단언: ① `skins[0].stat_bonus.value = 0.06` → 스키마 오류 ② `totems[0].order = 5` → 스키마 오류 ③ `equipment[3].mult` 임의 변경 → 파생 검사 오류 ④ `monsters[0].codex_id = "cdx_none"` → 참조 무결성 오류 ⑤ `_manifest.json` 체크섬 1자 변경 → 체크섬 오류 ⑥ `drop_rates` 합 ≠ 1 → 합계 오류 ⑦ `stages` 구간 중첩 → 구간 오류 ⑧ **경계**: `brothers`가 빈 배열 → minItems 오류
  3. `npx tsx packages/data/src/load.ts --print-summary` → `tables loaded: 12, rows: 60, checksum OK, integrity OK` 형태 출력, 종료 코드 0
  4. `npx tsx tools/gen-equipment.ts --check` → 13행 재생성 결과가 `data/equipment.json`과 **완전 일치**(diff 0줄)
- 크기: M
- 참고: ajv `strict: true`에서는 `"$schema"`와 `"additionalProperties": false` 누락이 에러가 된다. `format: date-time`은 `ajv-formats` 등록이 필요하다.

#### T0.4 에셋 거버넌스 게이트
- 목표: `origin:"ai"` 에셋의 추적·감수 메타가 비면 **빌드가 실패**하도록 만든다.
- 의존: T0.3
- 입력: 본 문서 1.7, GDD 8.1, 9.2
- 산출: `tools/validate-assets.ts` + 테스트, `assets/_index.json`(약 34항목), `assets/source/.gitkeep`, `assets/gen/.gitkeep`, 루트 `package.json`의 `prebuild`/`pretest` 훅
- 규칙: 1.7 표의 7개 검사를 전부 구현. 애니메이션 프레임(`fx_anim_*`)은 `origin:"human"`만 허용. 실패 시 위반 항목 id·사유를 한 줄씩 출력하고 exit 1.
- 수용 기준:
  1. `npm run validate:assets` → `assets OK: 34 entries (human 11, ai 23)`, 종료 코드 0
  2. `npm test -w tools -- validate-assets` → **9 passed** (7개 실패 케이스 + 정상 케이스 + 고아 참조 케이스)
  3. `_index.json`에서 임의의 `origin:"ai"` 항목의 `reviewed_by`를 `""`로 바꾸고 `npm run build` → **종료 코드 1**, stderr에 해당 `asset_id`와 `reviewed_by is required for origin=ai` 출력 (변경은 되돌린다)
  4. `origin:"ai"` 항목의 `source_id`를 다른 AI 항목 id로 바꾸고 `npm run validate:assets` → 종료 코드 1, `source of an ai asset must be human-origin` 출력
- 크기: S
- 참고: `prebuild`/`pretest`는 npm이 자동 실행한다. CI에도 독립 잡으로 넣어서, 누군가 `--ignore-scripts`로 우회해도 머지가 막히게 한다.

---

### Phase 1 — 결정적 코어 룰 (10태스크)

#### T1.1 스테이지·몬스터 곡선과 사전 계산 테이블
- 목표: `HP(s)`·`G(s)`·보스 변형을 구현하고, 모든 거듭제곱을 로드 시 1회 생성 테이블로 고정한다(리더 결정 ①).
- 의존: T0.3
- 입력: 밸런스 모델 2.1·2.3, 본 문서 1.2 (D-3)
- 산출: `packages/core/src/tables.ts`(사전 계산), `packages/core/src/stage.ts` + 테스트
- 규칙:
  - `HP(s) = hp0 · g_hp^(s-1) · (1 + a_step · floor(s/10))`, `HP_boss(s) = HP(s) · m_boss` (`s % 10 == 0`)
  - `G(s) = gold0 · g_gold^(s-1)`, 보스는 `× boss_gold_mult`
  - `powTable(g, n)`은 `t[0]=1; t[i]=t[i-1]*g` 반복 곱. `Math.pow` 사용 금지(`check:deps`에 `Math.pow` 금지 식별자 추가).
  - 테이블 범위 초과 호출은 `RangeError`를 던진다. 조용한 폴백 금지.
- 수용 기준:
  1. `npm test -w packages/core -- stage` → **18 passed, 0 failed**
  2. 밸런스 모델 2.3 표의 12개 행(s = 1, 10, 25, 50, 100, 138, 200, 360, 450, 700, 950, 1200)이 각각 `HP(s)`·`G(s)`·웨이브 총 HP에 대해 **상대오차 1e-3 이내**로 단언됨
  3. **경계 케이스** 테스트 포함: `s=1`(지수 0), `s=10`(첫 보스, 계단 항 첫 적용), `s=9→10` 계단 불연속, `s=2000`(테이블 상한 정상), `s=2001` → `RangeError`, `s=0` → `RangeError`
  4. `grep -rn "Math.pow\|\*\*" packages/core/src/stage.ts packages/core/src/tables.ts` → 지수 연산자 사용 0건(테이블 생성 루프의 곱셈만 존재)
  5. `monsters.json`에 `mon_icebear` 1행을 추가하고 `stg_w1_main.monster_pool`에 추가 → `npm test -w packages/core` 통과 + `npm run sim -- --days 1 --bot balanced --seed 42`가 **코드 변경 0줄로** 실행(GDD 13.3-4 검증, T2.1 완료 후 재확인)
- 크기: M
- 참고: `floor(s/10)` 계단 항은 s=10에서 처음 1이 된다(s=9는 0). 보스 골드는 `G(s) × 10`이며 `n_mob`을 곱하지 않는다.

#### T1.2 형님 전투력과 DPS 합성
- 목표: `ATK_i(L)`·해금·`DPS_total`의 모든 배수 곱을 구현한다.
- 의존: T1.1
- 입력: 밸런스 모델 3.1·3.2·3.3, GDD 5.1
- 산출: `packages/core/src/brother.ts`, `packages/core/src/dps.ts` + 테스트
- 규칙:
  - `ATK_i(L) = atk0_i · (1 + b·L) · g_atk^floor(L/25)`, `atk0_i = ATK0 · 4^i`
  - `DPS_base = Σ_{i ∈ 해금} ATK_i(L_i)`, `DPS_total = DPS_base · E(s) · M · (1 + Σcard%) · 패키지배수 · 스킨배수`
  - 해금 판정은 **`run_best ≥ unlock_stage`** (GDD 모호 지점 4의 결정: 프레스티지 시작 스테이지가 높으면 즉시 해금. 시작 시 `run_best = start_stage`)
  - 배수 곱셈 순서를 `DPS_MULT_ORDER` 상수 배열로 고정한다(부동소수점 결합법칙이 성립하지 않으므로 순서가 결정성의 일부다).
- 수용 기준:
  1. `npm test -w packages/core -- brother dps` → **16 passed, 0 failed**
  2. 밸런스 모델 3.3 표 9행(L = 1, 10, 25, 50, 75, 100, 150, 200, 300)의 `ATK(L)`·`C(L)`이 상대오차 1e-3 이내로 단언됨
  3. **경계 케이스**: `L=0`(배수 점프 0회, `ATK=atk0`), `L=24→25`(첫 ×1.75 점프), `L=4000`(테이블 상한), 해금되지 않은 형님의 기여 = 0, 형님 4명 전부 `L=0`일 때 `DPS_base = 6+24+96+384 = 510`
  4. 배수 순서 테스트: `DPS_MULT_ORDER`를 뒤집으면 스냅샷 테스트가 **실패**함을 단언(순서 고정이 의도적임을 증명)
- 크기: M
- 참고: `4^i`도 사전 계산 테이블(i=0..5)에서 읽는다. 스킨 배수는 MVP에서 `skn_thak_basic`(0)만 장착되므로 1.0이지만 경로는 구현한다.

#### T1.3 전투 틱 루프와 벽 판정
- 목표: 고정 100ms 정수 틱으로 웨이브·보스·벽을 처리하는 코어 루프를 만든다.
- 의존: T1.2
- 입력: GDD 3.2·3.3, 본 문서 1.2 (D-1), 1.4
- 산출: `packages/core/src/combat.ts`, `packages/core/src/step.ts` + 테스트
- 규칙:
  - `stepTicks(state, n)`만이 공개 진입점. 상태의 `tick`은 정수만 증가한다.
  - `t_min_kill_sec = 0.5`는 **몬스터 1마리당**(GDD 모호 지점 7의 결정) → 일반 웨이브 최소 `4 × 0.5 = 2.0초`(20틱), 보스 최소 `0.5초`(5틱)
  - 보스 타임아웃: `ticksNeeded > boss_timer_sec × 10` (300틱) → `wall_hit` 이벤트(`wall_type:"boss"`) 발행 후 f* 파밍 모드
  - 일반 웨이브 벽: `ticksNeeded > 300` → `wall_type:"wave"`
  - 체감 벽: 30분(18,000틱) 이동창에서 `run_best` 증가 < 5 → `wall_type:"window"`
- 수용 기준:
  1. `npm test -w packages/core -- combat step` → **20 passed, 0 failed**
  2. **경계 케이스** 전량 포함: ① `L=0` 4명, `s=1` → 웨이브 클리어에 정확히 20틱(최소 처치 시간 지배) ② DPS가 극단적으로 클 때도 20틱 미만으로 내려가지 않음 ③ 보스에서 `ticksNeeded == 300` → 클리어(경계 포함), `301` → 벽 ④ `s=9`(일반) → `s=10`(보스) 전환 시 몬스터 수 4→1 ⑤ 벽 진입 후 f* 파밍 중에는 `stage`가 증가하지 않음 ⑥ 30분 이동창이 오프라인 주입 후에도 리셋되지 않음
  3. 결정성: `stepTicks(state, 36000)` 1회와 `stepTicks(state, 100)` 360회의 최종 `JSON.stringify(state)`가 **완전 일치**
  4. `npm test -w packages/core -- step` 실행 중 `state.tick`이 정수가 아닌 순간이 없음(`Number.isInteger` 단언이 매 스텝 수행)
- 크기: M
- 참고: 3번 기준(분할 호출 동일성)이 이 태스크의 핵심이다. 여기서 실패하면 렌더러와 시뮬레이터가 다른 결과를 낸다.

#### T1.4 자동 강화 그리디 (타이브레이크 결정)
- 목표: `ΔATK/비용` 최대 항목을 반복 구매하는 결정적 그리디를 구현한다(리더 결정 ②).
- 의존: T1.2
- 입력: 밸런스 모델 9.3, GDD 5.2, 모호 지점 2
- 산출: `packages/core/src/upgrade.ts` + 테스트
- 규칙:
  ```
  반복 {
    후보 = 해금된 형님 중 C_i(L_i) ≤ gold
    선택 = argmax( ΔATK_i / C_i(L_i) )
    동률이면 → 트랙 index(= brothers.slot) 오름차순      ← 리더 결정 ②
    없으면 종료
    gold -= C_i(L_i); L_i += 1
  }
  ```
  - `ΔATK_i = ATK_i(L_i + 1) − ATK_i(L_i)` (25레벨 점프가 걸치는 구간에서 큰 값이 나오는 것은 의도된 동작이다)
  - 동률 비교는 `a === b`가 아니라 `Math.abs(a-b) <= 1e-12 * Math.max(|a|,|b|)`로 판정한다. 순수 `===`는 계산 순서에 따라 동률을 놓친다.
  - `x1 / x10 / x100 / MAX` 수동 구매도 같은 함수를 쓴다(MAX = 그리디 무한 반복).
- 수용 기준:
  1. `npm test -w packages/core -- upgrade` → **14 passed, 0 failed**
  2. **타이브레이크 테스트**: 형님 0·1의 `ΔATK/C`가 정확히 동률이 되도록 구성한 픽스처에서 100회 반복 구매 → 매번 slot 0이 먼저 선택됨(결정적)
  3. **경계 케이스**: ① gold가 최저가보다 1 적을 때 0회 구매 ② gold=0에서 무한 루프 없이 즉시 종료 ③ 해금되지 않은 형님은 후보에서 제외 ④ `L=24`에서 `ΔATK`가 점프 때문에 다른 트랙을 역전하는 케이스 ⑤ 100만 골드 투입 시 반복 횟수가 유한(< 10,000)하고 종료
  4. 결정성: 동일 초기 상태·동일 골드로 2회 실행 → `levels` 배열 완전 일치
- 크기: S
- 참고: 밸런스 모델 9.3은 "slot 오름차순"이라 적었고 리더 결정 ②는 "트랙 index 낮은 쪽"이다. `brothers.slot === 트랙 index`이므로 두 표현은 동일하다 — 스키마의 `slot` 유일성 제약이 이 동치를 보장한다.

#### T1.5 사냥터 자동 최적화 `f*`
- 목표: `f* = max{ s : HP(s) ≤ DPS · t_min_kill }`를 이진 탐색으로 구하고 파밍 수입률을 계산한다.
- 의존: T1.3
- 입력: 밸런스 모델 4.2·4.3, GDD 5.5
- 산출: `packages/core/src/farm.ts` + 테스트
- 규칙: `rate(f*) = G(f*) / t_min_kill`. `HP(s)`가 `s`에 대해 단조 증가이므로 이진 탐색 가능. 탐색 범위는 `[1, min(runBest, STAGE_TABLE_MAX)]`. f* 파밍 중 스테이지는 오르지 않는다.
- 수용 기준:
  1. `npm test -w packages/core -- farm` → **11 passed, 0 failed**
  2. 선형 스캔 구현과 이진 탐색 구현의 결과가 `s ∈ [1, 1200]`, DPS 20단계(1e1~1e30)의 전 조합에서 **완전 일치**
  3. **경계 케이스**: ① DPS가 너무 작아 `HP(1) > DPS·0.5` → `f* = 1`(0이나 음수 금지) ② DPS가 매우 커 `f* > runBest` → `f* = runBest`로 클램프 ③ `HP(f*) == DPS·0.5` 정확 동률 → 그 `s`를 포함
  4. 밸런스 모델 4.3의 "보스 전선이 `f*`보다 +38.1 스테이지" 관계가 `g_hp=1.058`·계단 항 제외 근사에서 **±2 스테이지 이내**로 재현됨
- 크기: S
- 참고: 이진 탐색 상한을 `STAGE_TABLE_MAX`로 잡으면 테이블 범위 예외를 건드린다. 상한은 `runBest`와 테이블 상한의 min이다.

#### T1.6 장비 드랍과 결정적 합성
- 목표: 스테이지 드랍·4개→1개 결정적 합성·등급 배수 `E(s)`를 구현하고, 리더 결정 ③의 이중 모드를 만든다.
- 의존: T1.3, T0.2
- 입력: GDD 5.3·4.1, 밸런스 모델 3.1, 모호 지점 5, 리더 결정 ③
- 산출: `packages/core/src/equip.ts` + 테스트
- 규칙:
  - 드랍 등급은 `floor(s / equip_tier_span)` 중심의 결정적 분포. 드랍 판정은 `rng.fork("drop")` 스트림만 사용.
  - **합성은 확률 없음**: 동일 등급 4개 → 상위 1개, 100%. 불변식 "소모 4 / 생성 1 / 등급 +1"을 단언한다.
  - `E(s) = equip_tier_mult^min(tier, 40)`에서 `tier`의 출처가 모드에 따라 다르다:
    - `equip_recovery_mode = "instant"` → `tier = min(floor(s / 60), 40)` (밸런스 모델 근사, **회귀 테스트 기준값**)
    - `equip_recovery_mode = "drop_wait"` → `tier = 실제 보유 최고 등급` (리더 결정 ③, **실게임 기본**)
  - 세대 교체 시 `run.equip`은 전부 리셋되고 시작 스테이지에서 드랍부터 다시 모은다.
- 수용 기준:
  1. `npm test -w packages/core -- equip` → **15 passed, 0 failed**
  2. 합성 불변식 테스트: 무작위 시드 1,000회 합성 시퀀스에서 `Σ(보유수 × 1.20^tier 환산 가치)`가 합성 전후 보존되고, 4개 미만이면 합성이 **일어나지 않음**
  3. **경계 케이스**: ① tier 40에서 추가 합성 시도 → 등급 상한 유지(41 생성 금지) ② 3개 보유 상태에서 합성 호출 → 변화 없음, 반환값 `false` ③ 드랍 스트림이 다른 스트림 소비에 영향받지 않음(`fork("craft")`를 10만 회 돌려도 drop 시퀀스 불변)
  4. 모드 동등성 테스트: `instant` 모드에서 `s=600` → `tier=10`, `E=1.20^10`; `drop_wait` 모드에서 같은 상태·보유 0 → `tier=0`, `E=1.0` 임을 단언 (두 모드가 **의도적으로 다름**을 테스트가 명시)
- 크기: M
- 참고: 리더 결정 ③은 "리셋 후 시작 스테이지 기준 드랍 대기"이므로 실게임 기본은 `drop_wait`다. 그러나 밸런스 모델의 목표 벽 표는 `instant` 근사로 산출되었으므로 T2.5 회귀는 `instant`로 판정하고, 두 모드의 격차는 T2.7이 리포트로 뽑아 기획에 회신한다. **파라미터를 바꿔 맞추지 않는다**(리더 결정 ④의 원칙을 여기에도 적용).

#### T1.7 오프라인 보상
- 목표: `R_off = min(t, T_cap) · rate(f*) · r_off · (광고 시 ×2)`를 오프라인 **시작 시점 DPS** 기준으로 구현한다.
- 의존: T1.5
- 입력: 밸런스 모델 5절, GDD 6.3, 모호 지점 3·6
- 산출: `packages/core/src/offline.ts` + 테스트
- 규칙:
  - `applyOffline(state, elapsedSec, { ad: boolean, capSec: number })`. `elapsedSec`은 정수, 코어는 벽시계를 모른다(1.5).
  - **`rate(f*)`는 오프라인 시작 시점의 DPS로 계산한다**(모호 지점 3의 결정). 복귀 시점 DPS나 오프라인 중 자동 강화는 구현하지 않는다.
  - **오프라인 중 스테이지는 오르지 않는다**(모호 지점 6의 결정). 보스 도전 없음, f* 파밍만.
  - `capSec`은 `offline_cap_sec` + 패스 보유 시 `pass_offline_cap_sec`으로 대체 + 탈것 `offline_cap_add_sec` 가산.
- 수용 기준:
  1. `npm test -w packages/core -- offline` → **12 passed, 0 failed**
  2. 밸런스 모델 5절 유효 수입 시간 표 4행이 단언됨: 무과금 8h → `4.8h`분, 무과금 8h+광고 → `9.6h`분, 패스 12h → `7.2h`분, 패스 12h+광고 → `14.4h`분 (상대오차 1e-9)
  3. **경계 케이스**: ① `elapsedSec = 0` → 보상 0, 상태 불변 ② `elapsedSec = capSec` 정확히 → 상한 미도달로 처리(`offline_capped = false`) ③ `capSec + 1` → `offline_capped = true` ④ 오프라인 전후 `state.run.stage`·`runBest` 불변 ⑤ 오프라인 중 `levels` 불변(자동 강화가 돌지 않음) ⑥ 오프라인 적용 후 `tick`이 `elapsedSec × 10`만큼 증가
  4. 시작/복귀 DPS 구분 테스트: 오프라인 직전 DPS를 기록해 두고, 오프라인 적용 후 강화를 실행했을 때 보상액이 **변하지 않음**을 단언
- 크기: S
- 참고: 광고 ×2는 `ad_offline_mult`를 곱하는 것이지 시간을 2배로 늘리는 것이 아니다(상한은 그대로).

#### T1.8 세대 교체와 불씨 노드
- 목표: 프레스티지 전 과정과 불씨 노드(불 계열)를 구현하고 GDD 4.1 리셋/유지 표를 단언 테스트로 고정한다.
- 의존: T1.6, T1.7
- 입력: GDD 4.1, 밸런스 모델 6절, 모호 지점 4
- 산출: `packages/core/src/prestige.ts`, `packages/core/src/node.ts` + 테스트
- 규칙:
  - `Q = floor(ember_c · s_reached^ember_p)` — `s^1.45`는 정수 지수가 아니므로 테이블화할 수 없다. **여기서만 `Math.pow`를 허용**하고, 허용 지점을 `core/src/prestige.ts` 한 줄로 한정한 뒤 `// ALLOW_POW: 비정수 지수` 주석 + `check:deps`의 화이트리스트에 등록한다(1건만 허용).
  - `cost(A) = node_cost_base + node_cost_slope · A` (등차), `누적(A) = base·A + slope·A(A−1)/2`, `M = node_effect^A` (사전 계산 테이블).
  - `start_stage = max(1, floor(start_stage_ratio × best_ever))`, 시작 시 `run_best = start_stage` → **형님 즉시 재해금**(모호 지점 4의 결정).
  - 트리거: 해금 `best_ever ≥ 120`, 권장선 `run_best ≥ 1.15 × last_best`, 정체 `30분 이동창 증가 < 5`.
- 수용 기준:
  1. `npm test -w packages/core -- prestige node` → **19 passed, 0 failed**
  2. 밸런스 모델 6.1 표 8행(s = 120, 138, 200, 360, 450, 700, 950, 1150 → Q = 362, 443, 759, 1781, 2461, 4671, 7273, 9595)이 **정확히 일치**(floor 포함)
  3. 6.2 표 7행(A = 10, 50, 100, 200, 400, 589, 724 → 누적 불씨 82, 1108, 3965, 14930, 57860, 124161, 188000 / M = 1.63, 11.5, 132, 1.73e4, 2.99e8, 3.02e12, 1.43e15)이 상대오차 1e-3 이내
  4. **리셋/유지 단언 테스트**: 모든 필드에 고유한 마커 값을 채운 상태에서 `prestige()` 실행 후 GDD 4.1 표의 리셋 8항목이 전부 초기화되고 **유지 12항목이 바이트 단위로 불변**임을 단언(12개 개별 단언)
  5. **경계 케이스**: ① `best_ever = 119` → 프레스티지 호출이 거부됨(`false` 반환, 상태 불변) ② `best_ever = 120` → 허용 ③ `start_stage`가 280을 넘는 경우 형님 6명 전원 즉시 해금 ④ `pity.grind` 카운터가 프레스티지로 리셋되지 않음 ⑤ 불씨 잔액이 노드 비용보다 1 적을 때 구매 실패
- 크기: M
- 참고: 4번 기준이 11.3-4 회귀 시나리오의 코어 측 구현이다. T3.3에서 저장·복원을 얹어 E2E로 다시 검증한다.

#### T1.9 도감 카운트와 카드 보너스
- 목표: 몬스터 종별 누적 처치 10/100/1,000에서 카드를 지급하고 전역 % 보너스를 DPS·골드·드랍에 반영한다.
- 의존: T1.3, T1.8
- 입력: GDD 5.9·4.2, 8.10
- 산출: `packages/core/src/codex.ts` + 테스트
- 규칙: `account.codexKills[monsterId]`는 프레스티지로 리셋되지 않는다. 카드 획득은 임계 **도달 즉시 1회**(중복 지급 금지). 보너스 합산은 `1 + Σ(card.value)` 가산이며 곱셈이 아니다(곱셈 인플레 억제).
- 수용 기준:
  1. `npm test -w packages/core -- codex` → **10 passed, 0 failed**
  2. **경계 케이스**: ① 누적 9 → 카드 0, 10 → 카드 1개 ② 10을 넘어 11, 12로 가도 추가 지급 없음 ③ 한 번에 100마리 처치를 주입해도 1단계·2단계 카드가 **각각 1개씩만** 지급 ④ 프레스티지 후 `codexKills` 불변, 카드 보너스 유지 ⑤ 카드 0개일 때 보너스 배수 정확히 1.0
  3. DPS 반영 테스트: `atk_mult` 카드 2장(+0.005 ×2) 보유 시 `DPS_total`이 정확히 `×1.01`
- 크기: S
- 참고: 밸런스 모델 11절 미검증 항목 2번(카드 % 보너스가 모델에서 생략됨)에 해당한다. **MVP 회귀(T2.5)는 카드 보너스를 0으로 둔 프로파일로 판정**하고, 카드 포함 곡선은 T2.7의 diff 리포트로 별도 산출한다.

#### T1.10 세션 파사드·표기 유틸·이벤트 싱크 인터페이스
- 목표: 렌더러와 시뮬레이터가 공유하는 단일 진입점(`GameSession`)과 큰 수 표기 유틸을 만든다.
- 의존: T1.4, T1.5, T1.9
- 산출: `packages/core/src/session.ts`, `packages/core/src/format.ts`, `packages/core/src/events.ts` + 테스트
- 규칙:
  - `GameSession`은 상태를 소유하지만 계산은 전부 순수 함수에 위임한다. 공개 API: `stepTicks(n)`, `buy(targetId, count)`, `setAutoUpgrade(b)`, `prestige()`, `buyNode(branch)`, `applyOffline(sec, opts)`, `snapshot()`(읽기 전용 셀렉터), `toSave()` / `static fromSave()`.
  - 표기(GDD 12.2): `K/M/B/T` 이후 `aa, ab, ac...`. 표기 유틸은 **코어에** 두고 렌더러가 참조한다.
  - `EventSink` 인터페이스와 공통 필드 주입(`withCommon`). `data_version`은 필수 필드(누락 시 타입 에러).
- 수용 기준:
  1. `npm test -w packages/core -- session format events` → **17 passed, 0 failed**
  2. 표기 **경계 케이스**: `999` → `"999"`, `1000` → `"1.00K"`, `999_999` → `"1000.00K"` 아님(`"999.99K"` 규칙 확정), `1e12` → `"1.00T"`, `1e15` → `"1.00aa"`, `1e18` → `"1.00ab"`, `0` → `"0"`, 음수 → `"-"` 접두, `1e30` → `"1.00ae"`
  3. `snapshot()`이 반환한 객체를 변경해도 내부 상태가 변하지 않음(동결 단언)
  4. 이벤트 싱크 테스트: 임의 이벤트 1개 발행 시 GDD 11.1 공통 14필드가 **전부** 채워져 있고 `data_version === balance.version`
- 크기: M
- 참고: `snapshot()`이 매 틱 깊은 복사를 하면 배속 ×1000에서 렌더러가 죽는다. 구조 공유 + `Object.freeze`로 처리한다.

---
### Phase 2 — 헤드리스 시뮬레이터와 밸런스 회귀 (8태스크)

#### T2.1 시뮬레이터 CLI 골격과 압축 일정
- 목표: `npm run sim -- --days 7 --bot balanced --seed 42`가 도는 CLI와 프로파일·일정 엔진을 만든다.
- 의존: T1.10
- 입력: 밸런스 모델 9.1·9.2, 본 문서 6절
- 산출: `packages/sim/src/{cli,profiles,schedule}.ts` + 테스트
- 규칙:
  - 프로파일 `f2p` / `payer`는 밸런스 모델 9.1의 `Profile` 타입 그대로. **`emberMult`는 양쪽 다 1.00 고정**(이력 #7: 결제 보너스를 프레스티지 통화에 붙이면 안 된다) — 스키마 레벨에서 `const 1.0`으로 막는다.
  - 1일 스케줄: `블록A(활성) → 오프라인(11h − 블록B) → 블록B(활성) → 오프라인(13h − 블록A)`. 하루 합이 정확히 24h임을 단언한다.
  - 활성 블록 안에서는 T1.3의 `stepTicks`만 호출한다(시뮬레이터가 별도 전투 코드를 갖지 않는다).
  - CLI 옵션: `--days`(필수), `--bot`(balanced|aggressive|idle), `--seed`, `--profile`(f2p|payer), `--out`, `--equip-mode`(instant|drop_wait), `--ad-policy`(none|moderate|max), `--cards`(on|off).
- 수용 기준:
  1. `npm run sim -- --days 1 --bot balanced --seed 42 --profile f2p` → 종료 코드 0, stdout에 `day=1 stage=… gold=… prestige=…` 요약 1줄, `reports/{runId}/summary.json` 생성
  2. `npm test -w packages/sim -- schedule` → **9 passed**. 포함 케이스: ① 1일 스케줄 합 = 86,400초 ② 활성 블록 분 수가 프로파일과 일치 ③ 오프라인 상한 초과분이 버려짐 ④ **경계**: `--days 0` → 사용법 출력 후 exit 1 ⑤ 알 수 없는 `--bot` → exit 1
  3. `grep -rn "hp_growth\|1.058\|1.075\|0.35" packages/sim/src/` → **0줄**(수치 하드코딩 금지, 전부 balance.json에서 읽는다)
  4. `npm run sim -- --days 1 --bot balanced --seed 42` 2회 실행 → 두 `summary.json`이 `runId` 필드를 제외하고 **완전 동일**
- 크기: M
- 참고: `runId`는 `{botId}-{profile}-{seed}-{days}d`처럼 **결정적**으로 만든다. 타임스탬프를 넣으면 결정성 비교가 불가능해진다.

#### T2.2 봇 3종 (balanced / aggressive / idle)
- 목표: 서로 다른 플레이 성향의 결정적 의사결정 정책 3개를 구현한다.
- 의존: T2.1
- 입력: 스킬 절차 4, GDD 3.4, 밸런스 모델 6.3
- 산출: `packages/sim/src/bots/{balanced,aggressive,idle}.ts` + 테스트
- 규칙:

  | 봇 | 강화 정책 | 프레스티지 정책 | 접속 | 광고 |
  |---|---|---|---|---|
  | `balanced` | `ΔATK/C` 최대 그리디(T1.4), 동률 시 slot 오름차순 | 권장선(1.15) **또는** 30분 정체 | 프로파일 기본(2세션) | `moderate`(오프라인 ×2만) |
  | `aggressive` | 구매 가능한 **최고 index 트랙 우선**, 불가 시 그리디로 폴백 | 권장선 `1.05`로 조기 + 정체 | 프로파일 기본 | `max`(전 슬롯 상한까지) |
  | `idle` | 자동 강화만(수동 개입 0), 그리디 | **정체 감지만**(권장선 무시) | 1일 3회 × 10분 | `none` |

  - 봇은 코어 규칙을 바꾸지 않는다. 오직 "언제 무엇을 호출할지"만 다르다.
  - 각 봇의 난수 소비는 `rng.fork("bot")` 스트림으로 격리한다(봇을 바꿔도 드랍 시퀀스가 밀리지 않도록).
- 수용 기준:
  1. `npm test -w packages/sim -- bots` → **12 passed**
  2. `for b in balanced aggressive idle; do npm run sim -- --days 7 --bot $b --seed 42 --profile f2p; done` → 3회 전부 종료 코드 0
  3. 성향 단언 테스트(D7, seed 42, f2p 기준): `idle`의 도달 스테이지 < `balanced`의 도달 스테이지, `aggressive`의 프레스티지 횟수 > `balanced`의 프레스티지 횟수
  4. **경계**: `idle` 봇이 30일 동안 프레스티지를 1회 이상 수행함(정체 감지만으로도 트리거가 걸리는지 확인 — 0회면 밸런스 모델 이력 #5의 회귀)
  5. 각 봇 결정성: 동일 시드 2회 실행 결과 `summary.json` 동일
- 크기: M
- 참고: `aggressive`의 "최고 index 트랙 우선"은 초반에 명백히 손해다. 그것이 의도다 — 곡선의 하한을 재는 봇이다.

#### T2.3 출력물 (CSV·요약 JSON·마크다운 리포트)
- 목표: 사람이 읽을 수 있는 실행 산출물 4종을 생성한다.
- 의존: T2.2
- 입력: 스킬 절차 4, 본 문서 6.3
- 산출: `packages/sim/src/report.ts` + 테스트, `reports/` 샘플
- 규칙: 산출 파일과 필수 열은 다음과 같다.

  | 파일 | 열 / 키 |
  |---|---|
  | `gold_curve.csv` | `t_sec,stage,run_best,gold_total,gold_rate_per_sec,dps_total,equip_tier,nodes,M` |
  | `stage_curve.csv` | `t_sec,stage_best,prestige_count,ember_total` |
  | `walls.csv` | `t_sec,stage,wall_type,dps_total,hp_required,gap_ratio` |
  | `summary.json` | `runId, botId, profile, seed, days, dataVersion, stageReached, bestEver, prestigeCount, emberTotal, nodesOwned, atkMult, firstWallSec, checkpoints[{label,tSec,stage}]` |
  | `report.md` | 실행 파라미터 표, 체크포인트 대조표, 벽 목록 상위 10, 골드·스테이지 곡선 요약 통계 |
  | `events.jsonl` | 분석 이벤트(T5.1 완료 후 채워짐. 그 전에는 빈 파일) |

  - 샘플링 간격은 `--sample-sec`(기본 600초). CSV 행 수가 30일 기준 4,320행을 넘지 않게 한다.
  - 부동소수점 출력은 `toPrecision(12)`로 **고정 폭 문자열화**한다. 기본 `toString()`은 엔진별 표기 차이가 날 수 있고 diff가 지저분해진다.
- 수용 기준:
  1. `npm run sim -- --days 7 --bot balanced --seed 42 --profile f2p` → `reports/balanced-f2p-42-7d/` 아래 6개 파일 전부 생성
  2. `head -1 reports/balanced-f2p-42-7d/gold_curve.csv` → 위 표의 9개 열 이름과 **정확히 일치**
  3. `npm test -w packages/sim -- report` → **8 passed**. 포함: ① CSV 열 순서 고정 ② 숫자 표기 폭 고정 ③ `summary.json`이 JSON Schema(`sim/schema/summary.schema.json`) 통과 ④ **경계**: 0개 벽 발생 시 `walls.csv`가 헤더만 있는 파일로 생성(파일 누락 아님)
  4. `report.md`를 열었을 때 체크포인트 대조표에 목표값·시뮬값·편차%가 표시됨(육안 확인용 — 자동 판정은 T2.5)
- 크기: M
- 참고: `gold_rate_per_sec`는 그 시점의 `rate(f*)`다. 벽 구간에서 이 값이 평평해지는 것이 곡선 리포트의 핵심 관전 포인트다.

#### T2.4 결정성 회귀 (리더 결정 ① 범위)
- 목표: "동일 Node 22.x · 동일 시드 → 바이트 동일"을 자동 검증한다.
- 의존: T2.3
- 입력: 본 문서 1.2 (D-4), GDD 13.3-2
- 산출: `packages/sim/src/determinism.ts`, `npm run sim:determinism` 스크립트 + 테스트
- 규칙:
  - 판정 방법: 같은 인자로 2회 실행 → `reports/{runId}/` 내 `runId` 제외 전 파일의 SHA-256 목록을 비교. 1비트라도 다르면 exit 1, 어느 파일의 몇 번째 줄이 다른지 출력.
  - 추가 판정: 최종 `GameState`를 `JSON.stringify`한 문자열의 SHA-256도 비교(파일 출력에 안 실리는 내부 상태까지 커버).
  - 판정 범위를 **문서에 명시**한다: 다른 JS 엔진·다른 Node 메이저 버전과의 바이트 동일성은 요구하지 않는다.
- 수용 기준:
  1. `npm run sim:determinism` → `deterministic: 6/6 files identical, state hash match`, 종료 코드 0
  2. `npm run sim:determinism -- --matrix` → `{balanced,aggressive,idle} × {f2p,payer} × {seed 42, 20260918} = 12`조합 전부 통과
  3. `npm test -w packages/sim -- determinism` → **6 passed**. 포함: ① `Date.now()`를 코어 경로에 넣으면 실패함을 증명하는 회귀 테스트(주입식 시계로 시뮬레이션) ② **경계**: 30일 실행에서도 통과(장기 누적에서 깨지지 않음)
  4. `packages/core/src/step.ts`에 `Math.random()` 1회 호출을 임시로 넣고 `npm run sim:determinism` → **종료 코드 1**, 차이 나는 파일명 출력 (되돌린다)
- 크기: S
- 참고: `runId`에 타임스탬프가 들어가면 이 태스크 전체가 무의미해진다. T2.1의 결정적 `runId` 규칙이 선행 조건이다.

#### T2.5 목표 진행 벽 표 회귀 (10 체크포인트 ±10%)
- 목표: `npm run sim:regress`가 밸런스 모델 8.2 표를 자동 대조하고 초과 시 실패하게 한다.
- 의존: T2.4
- 입력: 밸런스 모델 7절·8.2·9.4 (T1·T2)
- 산출: `packages/sim/src/regress.ts`, `packages/sim/fixtures/targets.json`, `npm run sim:regress` + 테스트
- 규칙: 기준값은 **`fixtures/targets.json`에서 읽는다**(테스트 코드에 하드코딩 금지). 회귀 실행 조건은 `--equip-mode instant --cards off --bot balanced`로 고정한다(밸런스 모델의 근사 조건과 일치시키기 위함, T1.6·T1.9 참고).

  | # | 시점 | 프로파일 | 목표 s | 허용 구간 (±10%) |
  |---|---|---|---|---|
  | 1 | 1시간 | f2p | 105 | 94.5 ~ 115.5 |
  | 2 | 1시간 | payer | 120 | 108 ~ 132 |
  | 3 | D1 | f2p | 140 | 126 ~ 154 |
  | 4 | D1 | payer | 210 | 189 ~ 231 |
  | 5 | D3 | f2p | 350 | 315 ~ 385 |
  | 6 | D3 | payer | 400 | 360 ~ 440 |
  | 7 | D7 | f2p | 450 | 405 ~ 495 |
  | 8 | D7 | payer | 520 | 468 ~ 572 |
  | 9 | D30 | f2p | 950 | 855 ~ 1,045 |
  | 10 | D30 | payer | 1,150 | 1,035 ~ 1,265 |

  추가 단언: **첫 벽 체감 시각 53.5분 ± 10%** (48.15 ~ 58.85분), **D30 소과금/무과금 도달 비 ≤ 1.2**, **D1 f2p 프레스티지 ≥ 1회**.
- 수용 기준:
  1. `npm run sim:regress` → `PASS 13/13 (checkpoints 10, firstWall 1, payerGap 1, d1Prestige 1)`, 종료 코드 0
  2. 실패 시 출력 형식 확인: `fixtures/targets.json`의 D30 f2p 목표를 `1500`으로 임시 변경 후 `npm run sim:regress` → **종료 코드 1**, `#9 D30/f2p: target 1500, actual 950, dev -36.7% (limit ±10%)` 출력 (되돌린다)
  3. `npm test -w packages/sim -- regress` → **7 passed**. 포함: ① 허용 구간 경계값 정확히 ±10.0%는 **통과**, ±10.01%는 실패 ② 목표 파일이 없으면 즉시 실패(조용한 스킵 금지)
  4. 전체 실행 시간이 **10분 이내**(CI 게이트로 쓸 수 있어야 한다). 넘으면 샘플링 간격을 늘리지 말고 스텝 병합을 최적화한다.
- 크기: M
- 참고: 이 태스크가 실패하면 **밸런스 파라미터를 바꾸지 않는다.** 원인이 구현 버그인지 모델 가정 차이인지 먼저 가려서 `docs/ASSUMPTIONS.md`에 기록하고 기획 담당에게 회신한다(7.3 참조).

#### T2.6 확률 검증 하네스와 천장 단언
- 목표: 표기 확률을 `balance.drop_rates`에서 읽어 `N ≥ 900(1−p)/p` 규칙으로 시행수를 자동 산출하고 검증한다.
- 의존: T2.4
- 입력: GDD 7.3, 밸런스 모델 8.4, 모호 지점 9
- 산출: `packages/sim/src/prob.ts`, `npm run sim:prob` + 테스트
- 규칙:
  - 시행수: `N_i = max(100_000, ceil(900 × (1 − p_i) / p_i))`를 100,000 단위로 올림. → 전설(0.005) **N = 1,800,000**, 영웅(0.03) N = 100,000, 희귀(0.15) N = 100,000, 일반(0.815) N = 100,000.
  - 판정: 관측 빈도가 `p ± 3√(p(1−p)/N)` 안.
  - **표기값 하드코딩 금지**: 테스트는 `balance.json`을 읽는다. `grep`으로 검증한다.
  - 천장(GDD 7.3): 20회 누적 → 다음 시행 영웅 이상 확정, 40회 누적 → 전설 확정. 천장 카운터는 계정 영구(프레스티지로 리셋 안 됨).
  - 시행 로직 자체(뼈 갈기)는 확장 기능이지만 **하네스는 MVP에 넣는다**(GDD 13.1 M11). MVP에서는 `rollGrind()` 순수 함수만 코어에 두고 UI는 만들지 않는다.
- 수용 기준:
  1. `npm run sim:prob` → 4행 표 출력(`grade, declared p, N, observed, 3σ band, verdict`)에서 **4/4 PASS**, 종료 코드 0
  2. 출력의 `N` 열이 `1800000 / 100000 / 100000 / 100000`과 일치
  3. `npm test -w packages/sim -- prob` → **9 passed**. 포함: ① 천장 단언 — 40회 연속 시행 × 1,000회 반복에서 전설 미획득 **0건** ② 20회 시점 영웅 이상 확정 × 1,000회 반복에서 위반 0건 ③ 천장 카운터가 `prestige()` 후에도 유지 ④ **경계**: 39회에서는 천장이 걸리지 않음, 40회에서 걸림 ⑤ `N` 산출식 자체의 단위 테스트(p=0.01 → 89,100 → 100,000으로 올림)
  4. `grep -rn "0.005\|0.815\|\b0.03\b\|\b0.15\b" packages/sim/src/prob.ts packages/sim/src/prob.test.ts` → **0줄**
  5. 전설 1.8e6 시행 실행 시간이 **60초 이내**
- 크기: M
- 참고: 1.8e6 시행에서 `nextFloat()`을 매번 새 객체로 감싸면 GC로 시간이 폭발한다. 루프 안에서 할당하지 않는다.

#### T2.7 곡선 diff 리포트 (`sim:diff`)
- 목표: 두 밸런스 버전(또는 두 실행 변형)의 곡선 차이를 마크다운 리포트로 자동 생성한다.
- 의존: T2.5
- 입력: 밸런스 모델 9.4 T7, 9.5, GDD 13.3-3
- 산출: `packages/sim/src/diff.ts`, `npm run sim:diff` + 테스트
- 규칙:
  - `npm run sim:diff -- --base bal_v1 --head bal_v2` — `--base`/`--head`는 `data/balance.{id}.json` 파일 또는 `reports/{runId}` 디렉터리를 가리킬 수 있다.
  - 리포트 내용: 파라미터 diff 표(변경된 키·이전값·새값), 체크포인트 10개의 base/head/변화율, 첫 벽 시각 변화, 프레스티지 횟수 변화, 골드 곡선 요약(각 샘플 구간 평균 상대차), 판정(`±10% 초과 항목 N개`).
  - **리더 결정 ④의 원칙을 여기에도 적용**: diff는 리포트만 만든다. 파라미터를 자동 조정하지 않는다.
- 수용 기준:
  1. `cp data/balance.json data/balance.bal_v2.json && <bal_v2의 hp_growth를 1.060으로 수정>` 후 `npm run sim:diff -- --base bal_v1 --head bal_v2` → `reports/diff-bal_v1-bal_v2.md` 생성, 파라미터 diff 표에 `hp_growth 1.058 → 1.060` 1행, 체크포인트 10행 전부 표시, 종료 코드 0
  2. **장비 모드 diff**(리더 결정 ③의 회신 근거): `npm run sim:diff -- --base equip_instant --head equip_drop_wait` → `reports/diff-equip_instant-equip_drop_wait.md` 생성, 체크포인트 10개의 도달 스테이지 격차가 표로 산출됨
  3. **카드 보너스 diff**(밸런스 모델 11절 미검증 2): `npm run sim:diff -- --base cards_off --head cards_on` → 리포트 생성
  4. `npm test -w packages/sim -- diff` → **6 passed**. 포함: ① 동일 입력 2개 → `변경 없음` 리포트 ② **경계**: base에만 있는 키/head에만 있는 키가 각각 `(추가)`/`(삭제)`로 표시
  5. 생성된 리포트를 사람이 읽었을 때 "어느 체크포인트가 왜 움직였는지"가 파라미터 diff 표와 나란히 보임
- 크기: M
- 참고: 2번·3번 기준이 이 태스크를 단순 유틸이 아니라 **기획 회신 문서 생성기**로 만든다. 8절 D3·U-2의 해소 경로다.

#### T2.8 60일·90일 장기 프로파일 (리더 결정 ④)
- 목표: 등차 노드 비용의 장기 인플레를 측정해 **리포트만** 생성한다.
- 의존: T2.5
- 입력: 밸런스 모델 6.2 미검증 리스크, 11절 미검증 1, GDD 모호 지점 8, 리더 결정 ④
- 산출: `packages/sim/src/long.ts`, `npm run sim:long`, `reports/long-term/report.md`
- 규칙:
  - 실행 조합: `{f2p, payer} × {60일, 90일} × bot=balanced × seed=rng_seed_default` = 4회.
  - 리포트 항목: 도달 스테이지, 노드 수 `A`, `M = 1.05^A`, 불씨 누적, 프레스티지 횟수, 스테이지/일 증가율의 시계열, `STAGE_TABLE_MAX(2000)` 및 f64 한계(1e308) 대비 여유.
  - **결과가 목표표 범위를 벗어나도 `balance.json`을 수정하지 않는다.** 리포트에 `[기획 확인 필요]` 섹션을 만들어 관측된 값과 우려 지점만 적는다.
  - `npm run sim:regress`의 게이트에 포함시키지 않는다(장기 실행은 CI를 막는다). 별도 수동/야간 실행.
- 수용 기준:
  1. `npm run sim:long -- --days 90 --profile f2p` → 종료 코드 0, `reports/long-term/f2p-90d/summary.json` 생성
  2. `npm run sim:long -- --all` → 4개 조합 전부 실행, `reports/long-term/report.md` 생성. 실행 시간 **30분 이내**
  3. 리포트에 다음 4개 항목이 반드시 포함됨: ① D60·D90 도달 스테이지 ② D60·D90 노드 수와 `M` ③ `STAGE_TABLE_MAX` 초과 여부 ④ `[기획 확인 필요]` 섹션
  4. **경계**: 도달 스테이지가 `STAGE_TABLE_MAX`를 넘으면 `RangeError`로 죽지 않고, 리포트에 `stage table exhausted at day N`을 기록한 뒤 정상 종료(종료 코드 0). 상수 확장은 기획 회신 후에 한다.
  5. `git diff --stat data/balance.json` → **0줄**(이 태스크가 파라미터를 건드리지 않았음을 증명)
- 크기: M
- 참고: 밸런스 모델 6.2의 "등차 비용은 상한이 없으므로 60·90일에서 인플레가 가속될 수 있다"가 이 태스크가 답할 질문이다. 답을 내되 고치지는 않는다 — 파라미터 결정은 기획 담당의 권한이다.

---

### Phase 3 — 저장·영속성·회귀 시나리오 (4태스크)

#### T3.1 저장 포맷과 라운드트립
- 목표: `schemaVersion`을 가진 저장 포맷과 직렬화/역직렬화를 구현한다.
- 의존: T1.10
- 입력: 본 문서 1.5
- 산출: `packages/core/src/save/{format,serialize}.ts` + 테스트
- 규칙: 1.5의 포맷 그대로. `GameState`는 JSON 직렬화 가능해야 한다(함수·Map·Set·`undefined`·`NaN`·`Infinity` 금지). RNG 스트림 상태 전부 포함.
- 수용 기준:
  1. `npm test -w packages/core -- save` → **11 passed**
  2. 라운드트립 테스트: 30일 시뮬레이션 최종 상태를 `toSave()→JSON→fromSave()` 후 **`JSON.stringify` 완전 일치**
  3. 이어하기 결정성: 임의 시점에 저장→복원한 뒤 이어서 10,000틱 진행한 결과가, 저장 없이 연속 진행한 결과와 **완전 일치**(RNG 상태 보존 증명)
  4. **경계 케이스**: ① `schemaVersion`이 현재보다 큰 세이브 → 로드 거부(예외), 상태 훼손 없음 ② 손상된 JSON → 예외, 기존 상태 유지 ③ `NaN`/`Infinity`가 상태에 들어가면 저장 시점에 예외(조용한 `null` 변환 금지) ④ 빈 문자열 → 예외
- 크기: S
- 참고: `JSON.stringify`는 `undefined` 필드를 조용히 삭제한다. 3번 기준이 이걸 잡는다.

#### T3.2 마이그레이션 프레임워크
- 목표: 저장 포맷 버전 업그레이드 경로를 만들고, 마이그레이션 없는 필드 변경을 테스트로 막는다.
- 의존: T3.1
- 산출: `packages/core/src/save/migrations.ts` + 테스트, `packages/core/fixtures/saves/v1.json`
- 규칙: `migrations: Record<number, (save) => save>`. `load()`는 `schemaVersion`부터 현재까지 순차 적용. 샘플로 v1→v2 마이그레이션 1개를 실제로 구현한다(예: `account.settings`에 `bossRaidPreset` 기본값 추가).
- 수용 기준:
  1. `npm test -w packages/core -- migrations` → **8 passed**
  2. 고정 픽스처 `fixtures/saves/v1.json`(커밋된 실제 v1 세이브)이 현재 버전으로 로드되고, 마이그레이션 후 스키마 검사 통과
  3. **구조 잠금 테스트**: `SCHEMA_VERSION`과 `Object.keys(migrations).length + 1`이 일치하지 않으면 실패 → 마이그레이션 없이 버전만 올리는 것을 막는다
  4. **필드 잠금 테스트**: `GameState`의 최상위·`run`·`account` 키 목록 스냅샷과 현재 키 목록이 다르면 실패하며, 실패 메시지가 `add a migration for: <키명>`을 출력
  5. **경계**: v1 → v3 2단계 점프가 순서대로 적용됨, 미등록 버전(v0) → 명시적 예외
- 크기: S
- 참고: 4번 기준이 "마이그레이션 함수 없이 필드 변경 금지"(AGENTS.md 규칙)를 코드로 강제하는 장치다.

#### T3.3 세대 교체 유지 자산 12종 E2E 회귀
- 목표: GDD 11.3-4 시나리오를 저장·복원까지 포함한 E2E로 단언한다.
- 의존: T3.1, T1.8
- 입력: GDD 4.1 리셋/유지 표, 11.3-4
- 산출: `packages/sim/src/scenarios/prestige-persist.test.ts`
- 규칙: 시나리오 = (1) 30일 시뮬레이션으로 실제 자산이 쌓인 상태 생성 → (2) 저장 → (3) 복원 → (4) `prestige()` → (5) 저장 → (6) 복원 → (7) 유지 12항목 단언. 마커 값이 아니라 **실제 플레이로 쌓인 값**을 쓰는 것이 T1.8과의 차이다.
- 수용 기준:
  1. `npm test -w packages/sim -- prestige-persist` → **14 passed** (유지 12항목 + 리셋 대표 2항목)
  2. 12개 단언이 GDD 4.1 표의 유지 항목명과 1:1로 대응되고, 테스트 이름에 항목명이 들어감(`유지: 불씨 잔액·노드`, `유지: 우편함·미수령 상품` 등)
  3. **경계**: 우편함에 미수령 상품 3건이 있는 상태에서 프레스티지 → 3건 전부 보존(결제 미수령 방지, GDD 4.1 비고)
  4. 저장·복원을 2회 더 반복해도 유지 자산이 동일(누적 손실 없음)
- 크기: S
- 참고: 이 테스트는 "프레스티지 구현을 건드릴 때마다 깨질 수 있는" 의도적 방벽이다. 깨지면 구현이 아니라 GDD 4.1 표를 먼저 다시 읽는다.

#### T3.4 설정·우편함 영속성 회귀 (전작 UX 마찰 대응)
- 목표: GDD 11.3-2·11.3-3 시나리오(재기동 후 설정 유지 / 미수령 상품 복구)를 회귀 테스트로 고정한다.
- 의존: T3.2
- 입력: GDD 11.3, 2장(보스토벌 설정 초기화 이슈), 진단자 메모(결제 미수령)
- 산출: `packages/core/src/settings.ts`, `packages/core/src/mailbox.ts`, `packages/sim/src/scenarios/persistence.test.ts`
- 규칙:
  - `account.settings`는 **항상 저장 경로에 포함**되고, 기본값은 마이그레이션이 채운다(로드 시점에 코드 기본값으로 덮어쓰기 금지 — 이것이 전작 "보스토벌 설정 초기화"의 전형적 원인이다).
  - 우편함: `grantPending(item)` → 저장 → 복원 → `claimPending()`이 항상 가능. 지급이 완료되어야만 제거된다(먼저 제거하고 지급하는 순서 금지).
- 수용 기준:
  1. `npm test -w packages/sim -- persistence` → **10 passed**
  2. 시나리오 단언: ① 설정 변경 → 저장 → 복원 → **변경값 유지**(기본값으로 되돌아가지 않음) ② 새 설정 키가 추가된 버전으로 마이그레이션해도 기존 사용자 설정값 유지 ③ 지급 직전 강제 종료(= 저장 후 claim 미완료) → 복원 시 우편함에 남아 있고 재지급 가능 ④ **중복 지급 금지**: 같은 `transaction_id`로 2회 claim → 1회만 반영
  3. **경계**: 우편함 0건 상태에서 `claimPending()` → 예외 없이 no-op
  4. `npm run sim:regress` 여전히 통과(회귀 영향 없음)
- 크기: S
- 참고: 이 태스크는 밸런스와 무관하지만 **매출 직결**이다. 진단 보고서에서 확인된 "결제 3회 중 2회만 반영"의 구조적 예방책이며, 신작에서 같은 CS를 만들지 않기 위한 최소 장치다.

---
### Phase 4 — 렌더러 MVP (5태스크)

#### T4.1 웹 앱 스캐폴드 (PixiJS · PWA · 배속)
- 목표: 코어를 구동하는 PixiJS 렌더러 셸과 배속 버튼을 만든다.
- 의존: T1.10
- 입력: GDD 12.3
- 산출: `apps/web/{index.html,manifest.webmanifest,src/main.ts,src/bind/loop.ts,src/render/stage.ts}`, `vite.config.ts`
- 규칙:
  - 루프: `requestAnimationFrame`에서 실경과 ms를 누적해 `floor(acc/100) × speed` 틱만큼 `session.stepTicks()`를 호출한다. **렌더러는 게임 규칙을 한 줄도 갖지 않는다.**
  - 배속 ×1/×10/×100/×1000. ×1000에서도 한 프레임의 `stepTicks` 호출 시간이 16ms를 넘으면 남은 틱을 다음 프레임으로 이월한다(프레임 드랍은 허용, 상태 스킵은 금지).
  - PWA: `manifest.webmanifest` + 서비스 워커(오프라인 셸만). 30fps 목표.
- 수용 기준:
  1. `npm run build -w apps/web` → 종료 코드 0
  2. `npm run dev -w apps/web` 기동 후 `curl -sf http://localhost:5173/` → HTTP 200
  3. `npm run check:deps` → `apps/web`에서 게임 수식 식별자(`hp_growth`, `cost_growth`, `1.058`, `1.075`, `Math.pow`) 검출 0건
  4. `npm run e2e -- --grep speed` → 배속 ×1000으로 10초 구동 시 콘솔 에러 0, 스테이지가 ×1 대비 증가(스크린샷 `speed-x1000.png` 생성)
- 크기: M
- 참고: PixiJS 8은 `await Application.init()` 비동기 초기화다. 동기 생성자 예제를 복사하면 동작하지 않는다.

#### T4.2 메인 전투 화면
- 목표: GDD 12.1의 메인 화면(배경·형님 4·웨이브·HP바·HUD·스테이지 ±)을 구현한다.
- 의존: T4.1
- 입력: GDD 12.1·12.2
- 산출: `apps/web/src/ui/main.ts`, `apps/web/src/render/{brothers,monsters,hud}.ts`
- 규칙: **숫자가 주인공이다**(GDD 12.2) — 데미지·골드·레벨업 팝이 이펙트에 가리지 않게 z-order를 고정한다. 큰 수 표기는 코어 `format.ts`를 호출한다(렌더러에 표기 로직 금지). 스테이지 ±버튼은 `runBest` 범위 안에서만 동작.
- 수용 기준:
  1. `npm run e2e -- --grep main` → `tests/e2e/__screenshots__/main.png` 생성, **콘솔 에러 0건**
  2. 스크린샷에 골드·DPS·스테이지 HUD 3요소가 모두 보임(Playwright `toBeVisible` 단언 3건)
  3. 배속 ×100으로 30초 구동 후 스테이지 표시가 증가하고 HP바가 0~1 범위를 벗어나지 않음
  4. **경계**: 스테이지 −버튼을 `s=1`에서 눌러도 0 이하로 내려가지 않음, +버튼을 `runBest`에서 눌러도 넘어가지 않음
- 크기: M
- 참고: 에셋은 `assets/_index.json`을 통해서만 참조한다. 경로 문자열을 코드에 쓰면 T0.4 게이트에서 고아 참조로 잡히지 않고 런타임에 깨진다.

#### T4.3 강화 화면과 장비 화면
- 목표: GDD 12.1의 강화·장비 두 화면을 구현한다.
- 의존: T4.2
- 입력: GDD 5.2·5.3, 12.1
- 산출: `apps/web/src/ui/{upgrade,equip}.ts`
- 규칙: 강화 — 형님 리스트, 레벨/비용/ΔDPS 표시, `x1/x10/x100/MAX`, **자동 강화 토글**. 장비 — 인벤토리 그리드, 장착 슬롯 3, 결정적 합성 버튼(확률 표기 없음 — 100%이므로 표기 의무 자체가 없다). 모든 구매는 `session.buy()`를 호출하며 화면이 직접 골드를 차감하지 않는다.
- 수용 기준:
  1. `npm run e2e -- --grep "upgrade|equip"` → `upgrade.png`, `equip.png` 생성, **콘솔 에러 0건**
  2. 강화 화면에서 `x10` 클릭 → 해당 형님 레벨이 정확히 10 증가(골드 충분 시), 골드가 `Σ C(L)`만큼 감소
  3. 자동 강화 토글 ON → 10초 후 레벨 증가, OFF → 레벨 불변
  4. **경계**: 골드 부족 상태에서 `MAX` 클릭 → 구매 0회, 에러 없음, 버튼이 비활성 표시
  5. 장비 4개 보유 상태에서 합성 버튼 → 보유 4 감소·상위 1 증가(`instant`/`drop_wait` 모드와 무관하게 인벤토리 동작은 동일)
- 크기: M
- 참고: ΔDPS 표시는 `ATK` 차이가 아니라 **`DPS_total` 차이**여야 한다(모든 배수가 곱해진 뒤 값). 여기를 틀리면 유저가 보는 숫자와 자동 강화의 판단 근거가 어긋난다.

#### T4.4 세대 교체·불씨 노드·오프라인 보상 화면
- 목표: 프레스티지 확인 화면(리셋/유지 표 노출), 불씨 노드 트리, 오프라인 보상 팝업을 구현한다.
- 의존: T4.2
- 입력: GDD 12.1, 4.1, 6.3
- 산출: `apps/web/src/ui/{prestige,nodes,offline}.ts`
- 규칙:
  - 세대 교체 화면은 **GDD 4.1의 리셋/유지 표를 그대로 화면에 띄운다**(설계 리스크 "전작 유저의 리셋 거부감" 완화책). 예상 불씨 `Q`를 상단에 표시.
  - 불씨 노드 화면: 불 계열 트리, 현재 `M` 표시, 다음 노드 비용 `cost(A)`.
  - **오프라인 복귀 팝업은 2초 이내에 닫을 수 있어야 한다**(GDD 12.2, 장기 유저 일일 마찰 1순위). 강제 연출·광고 자동 재생 금지. 광고 ×2는 **선택 버튼**.
- 수용 기준:
  1. `npm run e2e -- --grep "prestige|nodes|offline"` → `prestige.png`, `nodes.png`, `offline.png` 생성, **콘솔 에러 0건**
  2. 프레스티지 화면 스크린샷에 유지 항목이 **12행 전부** 보임(Playwright로 행 수 12 단언)
  3. **2초 규칙 자동 검증**: 오프라인 팝업 표시 후 닫기 버튼이 활성화되기까지의 시간이 `< 2000ms`임을 Playwright 타이밍 단언으로 측정
  4. **경계**: `best_ever < 120`일 때 세대 교체 버튼이 비활성이고 사유 문구가 표시됨; 불씨 부족 시 노드 구매 버튼 비활성
- 크기: M
- 참고: 3번 기준은 UX 요구를 테스트로 바꾼 것이다. "닫기 버튼에 3초 딜레이" 같은 광고 유도 패턴이 나중에 슬쩍 들어오는 것을 막는다.

#### T4.5 Playwright E2E — 6화면 스크린샷·콘솔 에러 0·Node/브라우저 동치
- 목표: MVP 6화면의 스크린샷 회귀와 브라우저 결정성 확인을 자동화한다.
- 의존: T4.3, T4.4
- 입력: GDD 12.1의 ● 6개, 본 문서 1.2 (D-4)
- 산출: `playwright.config.ts`, `tests/e2e/*.spec.ts`, `tests/e2e/__screenshots__/`
- 규칙: 대상 6화면 = 메인 / 강화 / 장비 / 세대 교체 / 불씨 노드 / 오프라인 보상. 뷰포트 고정(390×844 모바일 + 1280×720 데스크톱). 스크린샷 비교 임계 `maxDiffPixelRatio: 0.01`. **콘솔 에러·경고·`pageerror`·실패한 네트워크 요청이 1건이라도 있으면 실패**.
- 수용 기준:
  1. `npm run e2e` → **12 passed**(6화면 × 2뷰포트), 0 failed, `__screenshots__/`에 12개 PNG
  2. 콘솔 리스너 단언: 전 테스트 합계 `console.error` 0건, `pageerror` 0건, 4xx/5xx 요청 0건
  3. **Node/브라우저 동치 테스트**: 브라우저에서 시드 42로 1시간(36,000틱) 진행한 뒤 `session.snapshot()`의 `{stage, gold, levels, nodes}`를 추출 → 같은 조건 `npm run sim`의 값과 **완전 일치**(골드는 상대오차 0)
  4. CI에서 동일하게 통과(헤드리스 크로미움)
- 크기: M
- 참고: 3번이 이 Phase의 진짜 목적이다. 여기서 값이 갈리면 (D-1) 정수 틱 또는 (D-3) 사전 계산 테이블이 렌더러 경로에서 새고 있는 것이다. 스크린샷은 눈으로 보는 용도, 동치 테스트는 결정성 보증 용도다.

---

### Phase 5 — 분석 이벤트·수익모델 스텁 (4태스크)

#### T5.1 이벤트 버스와 JSONL 싱크
- 목표: GDD 11.1 공통 14필드를 강제하는 이벤트 버스와 로컬 싱크를 만든다.
- 의존: T1.10
- 입력: GDD 11.1, 모호 지점 10
- 산출: `packages/core/src/events.ts`(확장), `packages/sim/src/sinks/jsonl.ts`, `apps/web/src/bind/sink.ts`, `data/schema/analytics.schema.json`
- 규칙:
  - 공통 14필드는 TS 타입에서 **필수**로 선언한다. 특히 `data_version`(= `balance.version`)은 누락 시 컴파일 에러가 나야 한다(모호 지점 10의 결정).
  - 시뮬레이터 싱크 → `reports/{runId}/events.jsonl`. 웹 싱크 → IndexedDB 버퍼 + 다운로드.
  - 코어는 I/O를 하지 않는다. 싱크는 주입된다.
- 수용 기준:
  1. `npm test -w packages/core -- events` → **9 passed**. 포함: ① 공통 14필드 전량 존재 단언 ② `data_version` 누락 시 타입 에러(`tsd`/`expectTypeOf` 사용) ③ **경계**: 싱크가 예외를 던져도 게임 루프가 멈추지 않음(이벤트 발행 실패는 게임을 죽이지 않는다)
  2. `npm run sim -- --days 1 --bot balanced --seed 42` → `events.jsonl` 생성, `wc -l` > 0
  3. `npx tsx packages/sim/src/sinks/validate-jsonl.ts reports/.../events.jsonl` → 전 줄이 `analytics.schema.json` 통과, `0 invalid`
  4. `jq -r '.data_version' events.jsonl | sort -u` → **`1` 한 줄만** 출력(전 이벤트에 동일 `data_version`)
- 크기: M

#### T5.2 이벤트 10종 발행 지점 연결
- 목표: GDD 11.2의 이벤트 10종을 코어의 정확한 지점에서 발행한다.
- 의존: T5.1
- 입력: GDD 11.2 표
- 산출: `packages/core/src/**`의 발행 호출 + `packages/sim/src/scenarios/events.test.ts`
- 규칙: 대상 10종 = `session_start`, `session_end`, `stage_clear`, `wall_hit`, `upgrade`, `prestige`, `purchase`, `ad_reward`, `gacha_roll`, `content_enter`. 각 이벤트의 고유 필수 필드를 GDD 11.2 표대로 채운다. `wall_hit.gap_ratio = 필요DPS / 현재DPS`.
- 수용 기준:
  1. `npm test -w packages/sim -- events` → **13 passed** (10종 × 고유 필드 단언 + 3개 경계)
  2. `npm run sim -- --days 1 --bot balanced --seed 42 && jq -r '.event_name' events.jsonl | sort | uniq -c` → **최소 6종**(`session_start/end`, `stage_clear`, `wall_hit`, `upgrade`, `prestige`)이 1건 이상. 나머지 4종은 T5.3·T5.4·T6.4에서 채워진다.
  3. `wall_hit` 이벤트의 `gap_ratio`가 항상 `> 1.0`(벽이니까), `stage_clear`의 `clear_time_sec`이 항상 `≥ t_min_kill × 몬스터 수`
  4. **경계**: 1일 실행에서 `prestige` 이벤트 수 == `summary.json`의 `prestigeCount`
- 크기: M
- 참고: `wall_hit`은 벽에 **진입할 때 1회**만 발행한다. 매 틱 발행하면 JSONL이 폭발하고 분석이 못 쓰게 된다.

#### T5.3 광고 슬롯과 `ad_policy` 프로파일
- 목표: GDD 7.4의 광고 슬롯 4종을 `AdReward` 이벤트 경로로만 들어오게 하고, 시뮬레이터 프로파일로 대체한다.
- 의존: T5.2
- 입력: GDD 7.4
- 산출: `packages/core/src/ads.ts`, `packages/sim/src/profiles.ts`(확장), `apps/web/src/ui/ad-slots.ts`(스텁)
- 규칙:
  - 슬롯 4종: `ad_offline_x2`(3회/일), `ad_gold_boost`(3회/일, 5분 골드 ×3), `ad_shard`(2회/일), `ad_revive_tower`(1회/일).
  - 코어는 광고 SDK를 모른다. `grantAdReward(slotId)`만 있고, 웹은 스텁(즉시 성공), 시뮬은 `ad_policy = none | moderate | max`로 대체한다.
  - **광고 제거 구매자는 같은 횟수를 광고 없이 받는다**(구매자 페널티 금지, GDD 7.4).
- 수용 기준:
  1. `npm test -w packages/core -- ads` → **10 passed**. 포함: ① 일 상한 초과 시 거부 ② 일 리셋 후 회복 ③ **광고 제거 보유 시 광고 없이 동일 횟수 지급**(단언) ④ **경계**: 상한 정확히 3회째 성공, 4회째 실패
  2. `npm run sim -- --days 7 --bot idle --seed 42 --ad-policy none` vs `--ad-policy max` → 도달 스테이지가 `max` 쪽이 더 큼
  3. `jq -r 'select(.event_name=="ad_reward") | .slot_id' events.jsonl | sort -u` → 슬롯 id가 `data`의 정의와 일치
  4. **밸런스 모델 11절 미검증 6 해소**: `--ad-policy none` 프로파일의 D30 도달 스테이지를 `reports/ad-policy-none.md`로 리포트 생성(파라미터 조정 없음)
- 크기: M

#### T5.4 상점 스텁과 `purchase.grant_status` E2E 회귀
- 목표: 비확률 상품 지급 경로를 스텁으로 만들고, GDD 11.3-1·11.3-2 회귀 시나리오를 고정한다.
- 의존: T5.2, T3.4
- 입력: GDD 7.2, 11.2 `purchase`, 11.3-1·2
- 산출: `packages/core/src/shop.ts`, `packages/sim/src/scenarios/purchase.test.ts`
- 규칙:
  - 지급 순서 고정: **검증 → 우편함 적재 → 인벤토리 반영 → `purchase.grant_status="granted"` 발행 → 우편함 제거.** 어느 단계에서 끊겨도 재기동 시 복구된다.
  - `grant_status`(`granted|pending|failed`)와 `grant_latency_ms`는 **협상 불가 필수 필드**다(GDD 11.2). 타입에서 필수로 선언한다.
  - MVP는 실제 결제를 붙이지 않는다. `fakeStore.purchase(productId)`만 있다.
- 수용 기준:
  1. `npm test -w packages/sim -- purchase` → **12 passed**
  2. 시나리오 단언: ① 정상 구매 → `grant_status="granted"`, `grant_latency_ms ≥ 0` ② 지급 직전 강제 종료 시뮬레이션 → 재기동 후 우편함에서 복구되어 최종 `granted` ③ **중복 방지**: 같은 `transaction_id` 2회 → 지급 1회, 2번째는 `grant_status="granted"`이되 인벤토리 변화 0 ④ 지급 실패 주입 → `failed` 이벤트 발행 후 우편함에 **남아 있음**
  3. `jq -r 'select(.event_name=="purchase") | select(.grant_status!="granted")' events.jsonl | wc -l` → 정상 시나리오에서 **0**
  4. `shop_products.json`의 9행 전부에 대해 `grants` 적용 후 상태 변화가 단언됨(특히 `p_season_pass`의 `offline_cap_sec` 43200 반영, `p_growth_1`의 DPS ×1.12)
- 크기: M
- 참고: 이것이 진단 보고서에서 확인된 "결제 3회 중 2회만 반영"을 신작에서 구조적으로 막는 장치다. 점수는 낮아 보이지만 **매출 직결·CS 직결**이라 MVP에 넣었다.

---

### Phase 6 — 확장 (5태스크, v1.1~v1.3)

#### T6.1 부족 캠프 (v1.1)
- 목표: GDD 5.10의 5×5 배치·건물 3종·인접 보너스를 구현한다.
- 의존: T2.5 (회귀 통과 상태에서만 착수)
- 입력: GDD 5.10, 8.14, 밸런스 모델 11절 미검증 3
- 산출: `data/camp_buildings.json` + 스키마 활성화, `packages/core/src/camp.ts`, `apps/web/src/ui/camp.ts`
- 규칙: 화톳불(인접 +10%, 불씨 +5%) / 사냥막(골드 +X%) / 뼈공방(드랍 +X%). **최대 효과와 최소 효과 차이는 1.3배 이내**(배치를 틀려도 막히지 않게). 건물 레벨은 세대 교체로 리셋, 해금은 유지.
- 수용 기준:
  1. `npm test -w packages/core -- camp` → **12 passed**. 포함: ① 최적 배치/최악 배치 비가 **≤ 1.3** 단언 ② 프레스티지 후 레벨 0·해금 유지 ③ **경계**: 5×5 밖 좌표 배치 거부, 같은 칸 중복 배치 거부
  2. `npm run sim:diff -- --base camp_off --head camp_on` → 리포트 생성. 캠프가 `g_gold` 실효값을 바꾸므로 **전 구간 재검산이 필요함**이 리포트에 명시됨(밸런스 모델 11절 미검증 3)
  3. `npm run sim:regress` → 캠프 OFF 기준으로 여전히 13/13 PASS
  4. `npm run e2e -- --grep camp` → `camp.png` 생성, 콘솔 에러 0
- 크기: M

#### T6.2 도감 UI · 스킨 · 탈것 · 상점 · 시즌 패스 (v1.1)
- 목표: 수집·비확률 수익 축의 화면과 지급 경로를 붙인다.
- 의존: T5.4, T1.9
- 입력: GDD 5.8·5.9, 7.2, 4.4, 12.1
- 산출: `data/pass_tracks.json` 활성화, `apps/web/src/ui/{codex,skins,shop,pass}.ts`, `packages/core/src/{skin,mount,season}.ts`
- 규칙: 미발견 몬스터는 `_silh` 에셋. 스킨 옵션 상한 +5%(스키마가 이미 강제). 탈것은 오프라인 상한·시작 스테이지에만 기여(전투력 ≤ +5%). 시즌 28일, 전환은 **테이블 3종 교체만으로**(`events`·`skins`·`monsters`) — 코드 변경이 필요하면 설계 실패.
- 수용 기준:
  1. `npm test -w packages/core -- skin mount season` → **16 passed**. 포함: 스킨 +5% 초과 데이터 거부, 탈것 `atk_mult` 상한, 시즌 종료 시 패스 레벨 리셋·스킨/카드/불씨 유지
  2. **시즌 전환 테스트**: `events.json`·`skins.json`·`monsters.json` 3개만 교체하고 `npm test && npm run sim:regress` → **코드 변경 0줄로** 통과
  3. `npm run e2e -- --grep "codex|shop|pass"` → 3개 스크린샷 생성, 콘솔 에러 0
  4. 도감 미발견 항목이 `_silh` 에셋을 참조하고 `validate:assets` 통과
- 크기: M

#### T6.3 얼음 절벽 · 보스 원정 · 주간 랭킹 (v1.2)
- 목표: 방치로 풀리지 않는 도전 축과 랭킹을 붙인다.
- 의존: T6.2, T3.4
- 입력: GDD 4.3, 5.6, 10.3, 11.3-3
- 산출: `data/stages.json`에 `tower`/`raid` 행 추가, `packages/core/src/{tower,raid,ranking}.ts`, UI
- 규칙: 절벽 — 층별 고정 HP·고정 제한시간, **오프라인 진행 없음**. 보스 원정 — 일 3회, 5분, 누적 딜량. **설정은 서버 영속화가 원칙이고 로컬 캐시는 보조**(GDD 2장, 전작 UX 마찰 직접 대응). 랭킹은 100인 그룹.
- 수용 기준:
  1. `npm test -w packages/core -- tower raid` → **14 passed**. 포함: 절벽에서 오프라인 보상 0, 원정 일 3회 상한, **경계**: 제한시간 정확히 소진 시 실패 판정
  2. **설정 영속성 회귀(11.3-3)**: 보스 원정 설정 변경 → 저장 → 재기동 → **설정 유지** 단언이 T3.4 스위트에 추가되어 통과
  3. `npm run e2e -- --grep "tower|raid"` → 스크린샷 생성, 콘솔 에러 0
  4. `npm run sim:regress` → 여전히 13/13 PASS(신규 콘텐츠가 메인 곡선을 건드리지 않음)
- 크기: M

#### T6.4 뼈 갈기 — 확률형 1종 구현 (v1.2)
- 목표: GDD 7.3의 유일한 확률형 요소를 구현하고, T2.6 하네스로 검증한다.
- 의존: T2.6, T6.2
- 입력: GDD 7.3, 밸런스 모델 8.4
- 산출: `packages/core/src/grind.ts`, `apps/web/src/ui/{grind,rates}.ts`
- 규칙:
  - 등급 4종(전설 0.5 / 영웅 3 / 희귀 15 / 일반 81.5%). **실패 개념 없음** — 모든 시행이 옵션 1줄을 부여한다. 재료는 미획득 시 「갈린 뼈」로 환급 → 순수 손실 없음.
  - 천장: 20회 → 영웅 이상 확정, 40회 → 전설 확정. 카운터는 계정 영구.
  - **확률 표기 4곳 전부**: ① 실행 버튼 바로 위 인라인(접기 금지) ② `설정 > 확률 정보` 상시 화면 ③ 스토어 상품 상세(원석 관여 시) ④ 공식 홈페이지용 정적 페이지 생성기(`tools/gen-rates-page.ts`, 버전별 이력 보존).
  - 표기값은 **`balance.drop_rates`에서 읽어 렌더링**한다. UI에 숫자를 타이핑하면 표기-구현 불일치가 규제 리스크가 된다.
- 수용 기준:
  1. `npm run sim:prob` → 4/4 PASS (T2.6 하네스가 실제 구현을 검증)
  2. `npm test -w packages/core -- grind` → **13 passed**. 포함: 천장 20/40 단언, 환급 불변식(시행 전후 순손실 0), **경계**: 39회/40회, 프레스티지 후 카운터 유지
  3. `npm run e2e -- --grep "grind|rates"` → `grind.png`, `rates.png` 생성, 콘솔 에러 0. **스크린샷에 4개 등급 확률이 전부 보임**(Playwright 텍스트 단언 4건)
  4. `npx tsx tools/gen-rates-page.ts --out dist/rates/v1.html` → 생성된 HTML의 확률 4개가 `balance.json` 값과 일치(파싱 단언)
  5. `grep -rn "0.5%\|0.005\|81.5" apps/web/src/ui/` → **0줄**(표기 하드코딩 금지)
- 크기: M
- 참고: 기능 자체는 v1.2지만 **검증 하네스는 T2.6에서 이미 MVP에 들어가 있다**(GDD 13.1 M11). 그래서 이 태스크는 "구현 + 하네스 통과"만 하면 되고, 규제 대응 논의를 다시 열지 않는다.

#### T6.5 대수 표현 로그 공간 전환 (리더 결정 ①의 확장 태스크)
- 목표: f64 한계(1e308) 접근 시나리오에 대비해 로그 공간 또는 `{mantissa, exponent}` 표현으로 전환할 수 있게 한다.
- 의존: T2.8 (60/90일 리포트에서 필요성이 확인된 뒤에만 착수)
- 입력: 본 문서 1.2 (D-3), GDD 모호 지점 1, 밸런스 모델 2.3 구현 주의
- 산출: `packages/core/src/bignum.ts`, `packages/core/src/tables.ts` 전환, 교차 검증 테스트
- 규칙:
  - 표현: `{ m: number, e: number }` (정규화 `1 ≤ m < 10`) 또는 `log10` 저장 중 하나를 선택하고 **선택 근거를 `docs/ASSUMPTIONS.md`에 기록**한다.
  - 전환 범위: HP·골드·ATK·DPS·불씨만. 스테이지·레벨·노드 수·틱은 계속 정수.
  - **회귀 동등성이 이 태스크의 성패다**: 전환 전후 D30 체크포인트가 완전 일치해야 한다.
  - 착수 조건: T2.8의 90일 리포트에서 `max(HP, gold)`가 1e250을 넘거나, 기획이 D90 이상 운영을 확정한 경우. 그 전에는 **착수하지 않는다**(YAGNI — f64로 D30은 충분하다).
- 수용 기준:
  1. `npm test -w packages/core -- bignum` → **18 passed**. 포함: 곱·나눗셈·비교·정규화, **경계**: `1e308 × 10`(f64 오버플로 지점), `1e-320`(subnormal), `m=1.0` 정규화 경계, 0과 음수 처리
  2. **동등성 회귀**: `npm run sim:regress` → 전환 전과 **13/13 동일 PASS**, 체크포인트 10개의 도달 스테이지가 **정수 단위로 완전 일치**
  3. `npm run sim:determinism` → 여전히 통과
  4. `npm run sim:long -- --all` → D90에서 오버플로 없이 완주, 리포트에 최대 지수 기록
  5. 성능: `npm run sim:regress` 실행 시간이 전환 전 대비 **3배 이내**(넘으면 핫패스만 f64 유지하는 하이브리드로 되돌린다)
- 크기: M (L로 커지면 "표현 구현"과 "코어 전환" 2개로 쪼갠다)
- 참고: 리더 결정 ①은 **MVP에서 이 태스크를 하지 않는다**는 결정이다. bal_v1의 D30 최대값은 약 1.2e32로 f64 여유가 매우 크다. 이 카드는 확장 경로를 미리 못 박아 두어 나중에 즉흥 설계가 나오는 것을 막기 위한 것이다.

---

## 5. GDD 시스템 ↔ 태스크 대응표

**검수 방법**: 아래 표에서 "태스크" 열이 비어 있는 행이 하나라도 있으면 빌드 플랜이 불완전하다. 현재 **빈 행은 0개**다. MVP 시스템은 전부 P0~P5에 태스크가 있고, 확장 시스템은 P6 태스크 또는 명시적 제외 근거를 갖는다.

### 5.1 GDD 5장 시스템 (전수)

| GDD 절 | 시스템 | MVP/확장 | 태스크 | 비고 |
|---|---|---|---|---|
| 5.1 | 형님(동료) 6종·해금·ATK 곡선 | MVP(4종) | **T0.3, T1.2, T4.3** | 5·6번 형님은 `brothers.json` 2행 추가로 확장 |
| 5.2 | 강화 + 자동 강화(그리디) | MVP | **T1.4, T4.3** | 타이브레이크 = 리더 결정 ② |
| 5.3 | 장비 드랍 + 결정적 합성 | MVP | **T1.6, T4.3** | 확률 없음 |
| 5.3 | 「뼈 갈기」(확률형 1종) | 확장 v1.2 | **T2.6(하네스, MVP), T6.4(구현)** | GDD 13.1 M11대로 하네스만 MVP |
| 5.4 | 토템·유산 = 불씨 노드(불 계열) | MVP | **T1.8, T4.4** | 나머지 3계열은 `totems.json` 로더 플래그 해제만 |
| 5.5 | 스테이지·보스·시대·월드 | MVP | **T1.1, T1.3, T4.2** | 월드2는 `stages.json` 1행 추가(코드 0줄) |
| 5.5 | 사냥터 자동 최적화 `f*` | MVP | **T1.5** | 밸런스 모델 4.3 |
| 5.6 | 얼음 절벽(탑) | 확장 v1.2 | **T6.3** | |
| 5.6 | 보스 원정 | 확장 v1.2 | **T6.3** (+ 설정 영속성은 **T3.4**에서 MVP 선반영) | 전작 UX 마찰 대응은 MVP로 앞당김 |
| 5.7 | 길드 | 확장 v1.3 | **명시적 제외** + `data/schema/guilds.schema.json`만 작성(**T0.3**) | 근거: 9명 팀에서 소셜은 CS·밸런스 부하가 가장 크고(GDD 5.7), 신작 검증 단계의 성공 판정(GDD 13.3)과 무관하다. `account.guildId` 필드 자리만 예약한다 |
| 5.8 | 탈것 | 확장 v1.1 | **T0.3(스키마·1행), T6.2(지급·효과)** | 전투력 ≤ +5% 상한은 스키마가 강제 |
| 5.8 | 스킨 | MVP(1종) / 확장(상점) | **T0.3, T1.2(배수 경로), T6.2(UI·상점)** | +5% 상한 스키마 강제 |
| 5.9 | 도감·카드 | MVP(카운트·보너스) / 확장(UI) | **T1.9, T6.2** | 회귀는 `--cards off` 기준(T2.5), 포함 곡선은 T2.7 diff |
| 5.10 | 부족 캠프 | 확장 v1.1 | **T6.1** | 효과 상한 1.3배를 테스트로 단언 |

### 5.2 GDD 3·4·6·7·10·11·12장 대응

| GDD 절 | 항목 | 태스크 |
|---|---|---|
| 3.2 | 고정 dt=100ms 틱 파이프라인 | **T1.3** (+ 1.2절 D-1 계약) |
| 3.3 | 벽 정의 3종(보스·웨이브·체감) | **T1.3** |
| 3.4 | 벽 돌파 자원 6종 | **T1.5**(파밍) **T1.7**(오프라인·광고) **T1.6**(장비) **T1.8**(프레스티지) **T5.4**(성장 패키지) |
| 4.1 | 세대 교체 + 리셋/유지 표 | **T1.8**(코어 단언) **T3.3**(E2E) **T4.4**(화면 노출) |
| 4.1 | 불씨 노드 트리(등차 비용) | **T1.8, T4.4**, 장기 검증 **T2.8** |
| 4.2 | 수집 메타 5축 | **T1.9**(도감·카드) **T6.2**(스킨·탈것) **T1.2**(형님) |
| 4.3 | 주간 콘텐츠 4종 | **T6.3** (길드 대항전은 5.7과 함께 제외) |
| 4.4 | 시즌 28일·테이블 교체 | **T6.2** (수용 기준 2번이 "코드 0줄" 검증) |
| 6.1 | 자원 7종·상한·리셋 | **T0.3**(스키마) **T1.x**(각 자원 경로) **T3.3**(리셋 단언) |
| 6.3 | 인플레이션 규칙(`reward_hours`) | **T0.3**(스키마 0.5~10 강제) **T5.4**(지급) |
| 7.2 | 비확률 상품 9종 | **T5.4** |
| 7.3 | 확률형 1종·표기 4곳·검증·천장 | **T2.6**(검증) **T6.4**(구현·표기) |
| 7.4 | 광고 슬롯 4종 + `ad_policy` | **T5.3** |
| 10.1 | 라이브 이벤트 4타입 | **T0.3**(`events` 스키마) **T6.2**(시즌 전환) |
| 10.3 | 랭킹 3종 | **T6.3** |
| 11.1 | 분석 공통 14필드(`data_version` 포함) | **T5.1** |
| 11.2 | 이벤트 10종 고유 필드 | **T5.2** (+ `purchase` **T5.4**, `ad_reward` **T5.3**, `gacha_roll` **T6.4**) |
| 11.3 | 회귀 시나리오 5종 | 1·2 → **T5.4** / 3 → **T3.4, T6.3** / 4 → **T3.3** / 5 → **T2.6** |
| 12.1 | MVP 6화면 | **T4.2, T4.3, T4.4** (검증 **T4.5**) |
| 12.2 | 큰 수 표기·연출 원칙·2초 규칙 | **T1.10**(표기 유틸) **T4.4**(2초 자동 검증) |
| 12.3 | 배속·렌더러 읽기 전용 | **T4.1, T4.5** |
| 13.1 | MVP M1~M11 | M1→T1.3 / M2→T0.3 / M3→T1.1,T1.3,T1.5 / M4→T1.4 / M5→T1.6 / M6→T1.7 / M7→T1.8 / M8→T2.1~T2.5 / M9→T5.1,T5.2 / M10→T4.1~T4.5 / M11→T2.6 |
| 13.3 | 성공 판정 4개 | 1→T2.5 / 2→T2.4 / 3→T2.7 / 4→T1.1 수용 기준 5 |
| 8.1, 9.2 | 에셋 거버넌스(원본/변형 분리) | **T0.4** |

### 5.3 명시적 제외 목록 (근거 포함)

| 제외 대상 | 근거 |
|---|---|
| 길드(5.7)·부족 대항전(4.3) | GDD가 v1.2 이후로 명시. 9명 팀 CS·밸런스 부하 최대. 스키마 자리만 예약(T0.3) |
| 서버·계정 동기화 | GDD 13.1 "MVP 제외 명시". 프로토타입 성공 판정(13.3)이 전부 로컬에서 판정 가능 |
| 실제 결제 SDK·광고 SDK | T5.3·T5.4에서 **스텁 인터페이스만**. 실 SDK 연동은 본편 트랙 |
| 형님 패시브(5.1) | GDD가 "MVP는 패시브 없음" 명시. `passives` 스키마만 작성(T0.3), `passive_id: null` |
| Unity/C# 포팅 | 2차 트랙(1.9절). 프로토타입 성공 판정 통과 후 별도 문서로 분해 |

---

## 6. 시뮬레이터 · 회귀 테스트 명세

### 6.1 CLI

```bash
# 단일 실행
npm run sim -- --days 7 --bot balanced --seed 42
npm run sim -- --days 30 --bot idle --seed 20260918 --profile payer --ad-policy none

# 회귀 (CI 게이트)
npm run sim:regress                 # 목표 벽 표 10 + 첫 벽 + 격차 + D1 프레스티지 = 13 단언
npm run sim:prob                    # 확률 4종 + 천장
npm run sim:determinism             # 동일 시드 바이트 동일
npm run sim:determinism -- --matrix # 12조합

# 리포트 (게이트 아님)
npm run sim:diff -- --base bal_v1 --head bal_v2
npm run sim:diff -- --base equip_instant --head equip_drop_wait
npm run sim:long -- --days 90 --profile f2p
npm run sim:long -- --all
```

| 옵션 | 값 | 기본 |
|---|---|---|
| `--days` | 정수 ≥ 1 (압축 일정 일수) | 필수 |
| `--bot` | `balanced` \| `aggressive` \| `idle` | `balanced` |
| `--seed` | 정수 | `balance.rng_seed_default` (20260918) |
| `--profile` | `f2p` \| `payer` | `f2p` |
| `--equip-mode` | `instant` \| `drop_wait` | `balance.equip_recovery_mode` |
| `--ad-policy` | `none` \| `moderate` \| `max` | 봇 기본값 |
| `--cards` | `on` \| `off` | `off` (회귀 기준 조건) |
| `--sample-sec` | 정수 | 600 |
| `--out` | 경로 | `reports/{runId}` |

### 6.2 봇 3종 요약

| 봇 | 목적 | 강화 | 프레스티지 | 접속 | 광고 |
|---|---|---|---|---|---|
| `balanced` | **회귀 기준 봇** — 밸런스 모델 9.2·9.3의 합리적 유저 근사 | `ΔATK/C` 그리디, 동률 시 slot↑ | 권장선 1.15 또는 30분 정체 | 프로파일 기본 2세션 | `moderate` |
| `aggressive` | 곡선 상한 탐색 — 조기·과다 프레스티지의 영향 측정 | 최고 index 트랙 우선 | 권장선 1.05 + 정체 | 프로파일 기본 | `max` |
| `idle` | **곡선 하한 탐색** — 진짜 방치 유저. 목표표가 이 봇에게도 성립하는지 확인 | 자동 강화만 | 정체 감지만 | 1일 3회 × 10분 | `none` |

### 6.3 출력물

```
reports/{botId}-{profile}-{seed}-{days}d/
  summary.json      # 기계 판독용. 회귀·diff의 입력
  gold_curve.csv    # t_sec,stage,run_best,gold_total,gold_rate_per_sec,dps_total,equip_tier,nodes,M
  stage_curve.csv   # t_sec,stage_best,prestige_count,ember_total
  walls.csv         # t_sec,stage,wall_type,dps_total,hp_required,gap_ratio
  report.md         # 사람 판독용. 체크포인트 대조표 + 벽 목록 + 곡선 요약
  events.jsonl      # GDD 11장 분석 이벤트
```

곡선 diff 리포트(`reports/diff-{base}-{head}.md`) 구성: ① 파라미터 diff 표 ② 체크포인트 10개 base/head/변화율 ③ 첫 벽 시각 변화 ④ 프레스티지 횟수 변화 ⑤ 골드 곡선 구간별 평균 상대차 ⑥ 판정(±10% 초과 항목 수). **리포트는 판정만 하고 파라미터를 고치지 않는다.**

### 6.4 회귀 단언 목록 (밸런스 모델 9.4 T1~T7 대응)

| # | 단언 | 태스크 | 명령 | 게이트 |
|---|---|---|---|---|
| T1 | 목표 벽 표 10 체크포인트 ±10% | T2.5 | `npm run sim:regress` | CI 필수 |
| T2 | 첫 벽 53.5분 ±10% (48.15~58.85분) | T2.5 | 동상 | CI 필수 |
| T3 | 동일 시드 2회 완전 일치 | T2.4 | `npm run sim:determinism` | CI 필수 |
| T4 | 세대 교체 후 유지 자산 12종 보존 | T1.8, T3.3 | `npm test -w packages/sim -- prestige-persist` | CI 필수 |
| T5 | 확률 표기값을 `balance.drop_rates`에서 읽어 검증 | T2.6 | `npm run sim:prob` | CI 필수 |
| T6 | 천장 단언(40회×1,000회 전설 미획득 0건, 20회 영웅 확정) | T2.6 | 동상 | CI 필수 |
| T7 | balance 상수 1개 변경 시 곡선 diff 자동 생성 | T2.7 | `npm run sim:diff -- --base bal_v1 --head bal_v2` | 수동 |
| +1 | D30 소과금/무과금 도달 비 ≤ 1.2 | T2.5 | `npm run sim:regress` | CI 필수 |
| +2 | D1 f2p 프레스티지 ≥ 1회 | T2.5 | 동상 | CI 필수 |
| +3 | 60/90일 장기 리포트 생성(판정 아님) | T2.8 | `npm run sim:long -- --all` | 수동·야간 |

### 6.5 확률 검증 시행수 (모호 지점 9의 결정)

`N_i = max(100_000, ceil(900 × (1 − p_i) / p_i))`를 100,000 단위로 올림.

| 등급 | 표기 p | 산식값 | 채택 N | 3σ 허용 구간 |
|---|---|---|---|---|
| 전설 | 0.005 | 1,791,000 | **1,800,000** | p ± 3√(p(1−p)/N) = 0.005 ± 0.000158 |
| 영웅 | 0.03 | 29,100 | 100,000 | 0.03 ± 0.001618 |
| 희귀 | 0.15 | 5,100 | 100,000 | 0.15 ± 0.003387 |
| 일반 | 0.815 | 204 | 100,000 | 0.815 ± 0.003676 |

전 확률에 N=100,000을 일괄 적용하면 전설의 상대오차가 42%라 검증력이 사실상 0이다. 그래서 산식을 코드에 넣고 표기표에서 자동 산출한다.

---

## 7. Codex 실행 가이드

### 7.1 저장소 준비 순서 (사람이 1회 수행)

1. 빈 저장소 생성: `git init primitive-brothers-2 && cd primitive-brothers-2`
2. `05b_AGENTS.md`를 루트 `AGENTS.md`로 배치
3. `docs/` 생성 후 배치: `04_gdd_primitive_brothers_2.md` → `docs/GDD.md`, `04b_balance_model.md` → `docs/BALANCE.md`, 본 문서 → `docs/BUILD_PLAN.md`
4. `docs/ASSUMPTIONS.md` 생성 — **본 문서 8절을 그대로 초기 내용으로 복사**한다(Codex가 여기에 행을 추가한다)
5. `.nvmrc`에 `22` 작성, `nvm use 22`로 확인
6. 첫 커밋: `git commit -m "chore: docs and AGENTS.md"`
7. T0.1부터 태스크 순서대로 Codex 세션 실행. **의존 태스크가 끝나기 전에 착수하지 않는다.**

### 7.2 태스크별 프롬프트 템플릿

```
저장소 루트의 AGENTS.md를 먼저 읽고 그 규칙을 따르세요.
docs/BUILD_PLAN.md의 태스크 카드 「{태스크 id} {제목}」 하나만 구현합니다.
다른 태스크의 범위를 침범하지 마세요.

읽을 문서: docs/BUILD_PLAN.md {카드가 지시한 절}, docs/GDD.md {절}, docs/BALANCE.md {절}
구현 후 카드의 수용 기준 명령을 **전부** 실행하고 출력을 그대로 보고하세요.
기준 중 하나라도 통과하지 못하면 커밋하지 말고 무엇이 왜 실패했는지 보고하세요.

제약:
- data/balance.json의 값을 수정하지 마세요(기획 담당 결정 사항입니다).
- 수치를 코드에 하드코딩하지 마세요. 전부 data/*.json에서 읽습니다.
- packages/core에 런타임 의존성·DOM·Math.random·Date.now를 넣지 마세요.
- GDD에 없는 규칙이 필요하면 임의로 정하지 말고 가장 보수적인 선택을 한 뒤
  docs/ASSUMPTIONS.md에 "가정: …" 한 줄을 추가하고 보고하세요.

커밋: 메시지 첫머리에 태스크 id를 붙입니다. 예) "{태스크 id}: 스테이지 곡선과 사전 계산 테이블"
보고: 변경 요약 3줄 + 수용 기준 명령별 실행 결과 + 새로 추가한 가정.
```

### 7.3 실제 프롬프트 예시 2개

**예시 A — P0.1 스캐폴드**

```
저장소 루트의 AGENTS.md를 먼저 읽고 그 규칙을 따르세요.
docs/BUILD_PLAN.md의 태스크 카드 「T0.1 모노레포 스캐폴드와 CI 게이트」 하나만 구현합니다.

읽을 문서: docs/BUILD_PLAN.md 1.1절(패키지 경계·의존 규칙), 2절(저장소 구조·npm 스크립트), T0.1 카드

만들 것:
- npm workspaces 루트 package.json (engines.node ">=22 <23"), .nvmrc="22"
- packages/core, packages/data, packages/sim, apps/web 의 package.json + tsconfig.json + src/index.ts
- tsconfig.base.json, vitest.workspace.ts, .gitignore, .github/workflows/ci.yml
- tools/check-deps.ts — packages/core의 dependencies가 비어 있는지, 그리고
  packages/core/src/** 에 Math.random / Date.now / document / window / setTimeout /
  setInterval / performance / process. / require( 가 있는지 검사해 1건이라도 있으면 exit 1
- docs/ASSUMPTIONS.md 템플릿 (표 헤더: 번호 | 구분 | 내용 | 근거 | 상태)

packages/core의 dependencies는 반드시 빈 객체여야 합니다.

수용 기준을 전부 실행하고 출력을 보고하세요:
1. node -v            → v22.* 로 시작
2. npm ci             → 종료 코드 0
3. npm run build      → 4개 패키지 tsc 성공
4. npm test           → vitest 0 failed (스모크 1개)
5. npm run check:deps → "OK: core has 0 runtime deps, 0 forbidden identifiers"
6. packages/core/src/index.ts에 Math.random() 한 줄을 임시로 넣고 npm run check:deps
   → 종료 코드 1 + 파일·라인 출력. 확인 후 그 줄을 되돌리고 다시 5번이 통과하는지 확인

커밋 메시지: "T0.1: 모노레포 스캐폴드와 CI 게이트"
```

**예시 B — P2.5 목표 벽 표 회귀 테스트**

```
저장소 루트의 AGENTS.md를 먼저 읽고 그 규칙을 따르세요.
docs/BUILD_PLAN.md의 태스크 카드 「T2.5 목표 진행 벽 표 회귀 (10 체크포인트 ±10%)」 하나만 구현합니다.
선행 태스크 T2.4까지 완료된 상태여야 합니다. 완료되지 않았으면 착수하지 말고 보고하세요.

읽을 문서: docs/BALANCE.md 7절(목표 진행 벽 표), 8.2절(검산 대조표), 9.4절(회귀 단언),
          docs/BUILD_PLAN.md T2.5 카드, 6.4절

만들 것:
- packages/sim/fixtures/targets.json — 체크포인트 10개 {label, profile, atSec, targetStage, tolerance:0.10}
  + firstWallSec 3210(=53.5분), payerGapMax 1.2, d1MinPrestige 1
  (기준값은 반드시 이 파일에서 읽습니다. 테스트 코드에 숫자를 쓰지 마세요.)
- packages/sim/src/regress.ts 와 npm 스크립트 "sim:regress"
- 회귀 실행 조건 고정: --bot balanced --equip-mode instant --cards off,
  프로파일별 시드는 balance.rng_seed_default

수용 기준을 전부 실행하고 출력을 보고하세요:
1. npm run sim:regress → "PASS 13/13 (checkpoints 10, firstWall 1, payerGap 1, d1Prestige 1)", 종료 코드 0
2. fixtures/targets.json의 D30 f2p 목표를 1500으로 임시 변경 → npm run sim:regress
   → 종료 코드 1 + "#9 D30/f2p: target 1500, actual …, dev …% (limit ±10%)" 형식 출력.
   확인 후 950으로 되돌리고 1번을 다시 실행
3. npm test -w packages/sim -- regress → 7 passed
   (±10.00%는 통과, ±10.01%는 실패하는 경계 테스트와 목표 파일 부재 시 즉시 실패 테스트 포함)
4. time npm run sim:regress → 실행 시간 10분 이내

중요: 회귀가 통과하지 않아도 data/balance.json의 값을 절대 바꾸지 마세요.
실패하면 (a) 구현 버그인지 (b) 모델 가정 차이인지 판단해 보고하고,
(b)라면 docs/ASSUMPTIONS.md에 관측값과 함께 한 줄 추가하세요.

커밋 메시지: "T2.5: 목표 벽 표 회귀 테스트(10 체크포인트 ±10%)"
```

### 7.4 실패 시 대응

| 상황 | 대응 |
|---|---|
| **유닛 테스트 실패** | Codex가 자체 해결한다. 단, **테스트를 약화시켜 통과시키는 것은 금지**(기대값 변경·단언 삭제·`skip` 추가). 수용 기준의 테스트 개수가 줄면 그 자체가 실패다. 3회 시도 후에도 실패하면 중단하고 실패 원인·시도 내역을 보고한다 |
| **밸런스 회귀 실패(`sim:regress`)** | **`balance.json`을 절대 수정하지 않는다.** 순서: ① 최근 커밋 diff에서 곡선에 영향 주는 변경을 찾는다 ② `npm run sim:diff`로 이전 통과 시점과 곡선을 비교한다 ③ 구현 버그면 고친다 ④ 모델 가정 차이(예: 100ms 양자화, 장비 모드)면 `docs/ASSUMPTIONS.md`에 관측값과 함께 기록하고 **기획 담당(game-design-director)에게 회신**한다. 파라미터 조정은 기획 담당의 결정이다(밸런스 모델 9.5 워크플로) |
| **결정성 실패(`sim:determinism`)** | 최우선 수정 대상. 체크 순서: `Math.random`/`Date.now` 유입 → 실수 시간 누적(D-1 위반) → `Math.pow` 사용(D-3 위반) → 객체 키 순회 순서 의존 → 부동소수점 덧셈 순서 변경. 고칠 때까지 다음 태스크로 넘어가지 않는다 |
| **Playwright 스크린샷 차이** | 의도한 UI 변경이면 스크린샷을 갱신하고 커밋에 명시한다. 의도하지 않았으면 회귀다. **콘솔 에러 0건 기준은 어떤 경우에도 완화하지 않는다** |
| **에셋 게이트 실패(`validate:assets`)** | 게이트를 우회하지 않는다(`--ignore-scripts` 금지). `origin:"ai"` 항목에 `source_id`·`reviewed_by`를 채우거나, 감수 전이면 해당 에셋을 커밋에서 제외한다 |
| **가정이 필요한 상황** | 임의로 정하지 않는다. ① 가장 **보수적인**(유저에게 불리하지 않고 곡선을 빠르게 만들지 않는) 선택을 한다 ② `docs/ASSUMPTIONS.md`에 `가정: {내용} / 근거: {왜 이 선택} / 영향: {어느 태스크·곡선}` 한 행을 추가한다 ③ 보고에 명시한다. **`balance.json` 값 변경은 가정으로 처리할 수 없다** — 항상 기획 담당 회신 대상이다 |
| **태스크가 1세션을 넘음** | 중간 상태로 커밋하지 않는다. 카드를 2개로 쪼개는 제안(각각의 목표·산출·수용 기준)을 보고하고 사람의 승인을 받는다 |

### 7.5 사람 검토 포인트 (각 Phase 종료 시)

| Phase | 검토자가 실행할 명령 | 눈으로 볼 것 | 넘어가도 되는 조건 |
|---|---|---|---|
| P0 종료 | `npm ci && npm run build && npm test && npm run check:deps && npm run validate:assets` | `packages/core/package.json`의 `dependencies`가 `{}`인지, `data/*.json` 12개가 3.2의 행 수와 맞는지 | 5개 명령 전부 종료 코드 0 |
| P1 종료 | `npm test -w packages/core` | 테스트 개수 합계가 카드들의 합(약 152개) 이상인지, 리셋/유지 12항목 단언이 **항목명으로** 보이는지 | 코어 테스트 0 failed, `check:deps` 통과 |
| P2 종료 | `npm run sim:regress && npm run sim:prob && npm run sim:determinism -- --matrix` | `report.md`의 체크포인트 대조표를 **밸런스 모델 8.2 표와 눈으로** 대조. `sim:long` 리포트의 `[기획 확인 필요]` 섹션 | 13/13 + 4/4 + 12/12 PASS. **여기가 프로젝트의 분기점** — 통과하지 못하면 P4로 가지 않는다 |
| P3 종료 | `npm test -w packages/sim -- "prestige-persist|persistence"` | 유지 12항목 단언 이름이 GDD 4.1 표와 1:1인지 | 0 failed |
| P4 종료 | `npm run e2e && npm run dev -w apps/web` | **실제로 30분 플레이**한다. 첫 벽이 55분 근처에 오는 체감, 오프라인 팝업이 2초 안에 닫히는지, 숫자가 이펙트에 가리지 않는지 | e2e 12 passed, 콘솔 에러 0, Node/브라우저 동치 테스트 통과 |
| P5 종료 | `npm run sim -- --days 1 …` 후 `jq` 로 `events.jsonl` 확인 | `data_version`이 전 이벤트에 있는지, `purchase.grant_status`가 전부 `granted`인지 | 스키마 검증 0 invalid |
| P6 각 태스크 | `npm run sim:regress` | 확장 기능이 메인 곡선을 건드리지 않았는지 | 13/13 유지 |

**P2 종료 검토가 전체에서 가장 중요하다.** 여기서 목표 벽 표가 재현되지 않으면 렌더러를 붙여도 검증할 대상이 없다. 시뮬레이터-퍼스트 원칙의 실제 의미가 이 게이트다.

---

## 8. 가정 · 미결 목록

`docs/ASSUMPTIONS.md`의 초기 내용이다. 상태는 **결정**(이 문서로 확정, 구현자 재량 없음) / **가정**(GDD에 없어 보수적으로 채움, 기획 회신 시 변경 가능) / **보류**(측정 후 판단).

### 8.1 리더 결정 4건 (디렉터 회신 요청에 대한 응답)

| # | 대응 GDD 모호 지점 | 결정 내용 | 구현 위치 | 상태 |
|---|---|---|---|---|
| **D1** | 3-1 부동소수점 결정성 | **IEEE754 f64 사용.** bal_v1의 D30 값(HP≈1.07e26, M≈3.02e12, 소과금 s=1150에서 HP≈1.2e32)은 f64 범위 안이다. 단 `Math.pow` 금지 — `g^n`은 **반복 곱으로 만든 사전 계산 테이블**(스테이지별 HP·골드, 레벨별 비용, 노드별 배수)에서 읽어 엔진 간 차이를 최소화한다. 결정성 테스트는 "동일 Node 22.x · 동일 시드 → 바이트 동일"로 한정한다. 1e300 초과 대비 로그 공간 전환은 **확장 태스크 T6.5로만** 명시하고 MVP에서 하지 않는다 | 1.2 D-3/D-4, T1.1, T2.4, T6.5 | **결정** |
| **D2** | 3-2 자동 강화 타이브레이크 | **비용 동률 시 트랙 index(= `brothers.slot`) 낮은 쪽 우선.** 동률 판정은 상대오차 1e-12 허용 비교 | T1.4 | **결정** |
| **D3** | 3-5 장비 세대 교체 후 | **GDD 4.1 리셋/유지 표를 따른다**(장비 인벤토리·장착 = 리셋). 표에 없는 "리셋 직후 즉시 되찾는가"는 보수적으로 **「리셋 후 시작 스테이지 기준 드랍 대기」**를 채택한다. 밸런스 모델은 즉시 반영(`1.20^floor(s/60)`)으로 근사했으므로, `balance.equip_recovery_mode`(`instant`/`drop_wait`) 두 모드를 구현해 **회귀는 `instant`로 판정하고 실게임 기본은 `drop_wait`**로 둔다. 두 모드의 곡선 격차는 T2.7이 리포트로 산출해 기획에 회신한다. **목표 벽 표 재검산이 필요하다**(GDD 메모 3-5가 요구한 회신 사항) | 3.4, T1.6, T2.5, T2.7 | **결정**(재검산은 기획 담당) |
| **D4** | 3-8 노드 상한 부재 / 60·90일 | **시뮬레이터 Phase의 별도 태스크(T2.8)로 실행한다.** 결과가 목표표 범위를 벗어나도 **파라미터를 바꾸지 않고 리포트만** 생성한다(`[기획 확인 필요]` 섹션). 파라미터 결정은 기획 담당의 권한이다. `sim:regress` 게이트에도 넣지 않는다(장기 실행이 CI를 막는다) | T2.8 | **결정** |

### 8.2 GDD 모호 지점 10개 처리

| # | 모호 지점 | 처리 | 상태 |
|---|---|---|---|
| 1 | 부동소수점 결정성(f64 vs 로그공간 vs BigNumber) | **D1** 적용. f64 + 사전 계산 테이블 + `Math.pow` 금지. 예외 1건(`Q = 0.35·s^1.45`의 비정수 지수)만 화이트리스트로 허용 | **결정** |
| 2 | 자동 강화 그리디 타이브레이크 | **D2** 적용. 밸런스 모델 9.3의 "slot 오름차순"과 동치(스키마가 `slot` 유일성을 강제해 동치가 보장된다) | **결정** |
| 3 | 오프라인 골드의 DPS 시점 | **오프라인 시작 시점 DPS로 고정.** GDD가 지시한 그대로. 오프라인 중 자동 강화는 돌지 않는다 | **결정** |
| 4 | `start_stage`와 형님 재해금 | **즉시 해금.** 시작 시 `run_best = start_stage`이고 해금 판정은 `run_best ≥ unlock_stage`. 밸런스 모델 계산과 일치 | **결정** |
| 5 | 장비 등급과 세대 교체 | **D3** 적용. `drop_wait` 채택 + `instant` 회귀 모드 병행 + 격차 리포트로 회신 | **결정**(기획 재검산 대기) |
| 6 | 보스 타이머와 오프라인 | **오프라인은 `f*` 파밍만. 스테이지 상승·보스 도전 없음.** GDD 전제 유지 | **결정** |
| 7 | `t_min_kill_sec` 적용 범위 | **몬스터 1마리당 0.5초.** 일반 웨이브 최소 2.0초(20틱), 보스 최소 0.5초(5틱). `f*` 정의의 근거이므로 정확히 지킨다 | **결정** |
| 8 | 불씨 노드 상한 부재 | **D4** 적용. T2.8에서 60·90일 측정 → 리포트만. 상한/기울기 변경은 기획 결정 | **보류**(측정 후 기획 판단) |
| 9 | 확률 검증의 N | **`N = max(100_000, ceil(900(1−p)/p))`를 코드가 표기표에서 자동 산출.** 전설 0.5% → N=1,800,000. 표기값 하드코딩은 `grep` 기준으로 금지 | **결정** |
| 10 | 분석 이벤트 `data_version` | **공통 14필드에 `data_version`(= `balance.version`)을 TS 타입 필수로 선언.** 누락 시 컴파일 에러. MVP 로컬 JSONL 싱크에도 포함하고 `jq` 기준으로 검증 | **결정** |

### 8.3 본 빌드 플랜이 추가로 도입한 가정

| # | 가정 | 근거 | 영향 | 상태 |
|---|---|---|---|---|
| A-D5 | RNG를 GDD 13.1 M1의 `xorshift128+` 대신 **`xoshiro128**`**로 한다 | xorshift128+는 64비트 상태라 JS에서 BigInt(성능) 또는 분할 구현(엔진 차이)이 필요하다. xoshiro128**은 `Math.imul` 기반 32비트 정수 연산만 쓴다 | T0.2, 결정성 전반. GDD 13.1 M1 문구 수정 필요 | **가정** |
| A-D6 | `data/balance.json`이 모든 튜닝 파라미터의 **유일한 원본**이고, `stages.json`/`upgrades.json`의 곡선 필드는 **선택 필드**(생략 시 balance 상속)다 | 같은 값을 두 파일에 적으면 언젠가 갈라진다. GDD 8.3/8.6 예시 JSON의 인라인 값은 문서용 예시로 해석 | T0.3, 3.1절 | **가정** |
| A-D7 | 코어의 시간은 **정수 틱(100ms)만** 사용하고, 시뮬레이터도 해석적으로 구한 시간을 `ceil(t×10)` 틱으로 올림해 같은 함수를 호출한다 | GDD 3.2의 `dt=100ms`와 12.3의 "렌더러를 제거해도 동일 결과"를 동시에 만족시키는 유일한 방법 | 1.2 D-1, T1.3, T4.5. **밸런스 모델 9.2의 연속 시간과 미세 편차 발생**(U-3) | **가정** |
| A-D8 | 장비 회복 모드를 `balance.json`의 신설 키 `equip_recovery_mode`로 스위칭한다 | D3을 실행 가능하게 만들면서 회귀 기준(밸런스 모델 근사)을 보존하기 위함 | 3.4, T1.6, T2.5, T2.7 | **가정** |
| A-D9 | MVP 회귀(T2.5)는 **카드 보너스 OFF**(`--cards off`) 조건으로 판정한다 | 밸런스 모델 11절 미검증 2가 "카드 % 보너스는 모델에서 생략"이라고 명시. 모델과 같은 조건으로 재현해야 ±10% 판정이 성립 | T1.9, T2.5, T2.7 | **가정** |
| A-D10 | 확장 전용 테이블 5종(`camp_buildings`, `guilds`, `pass_tracks`, `drop_tables`, `passives`)은 스키마만 작성하고 `_manifest.json`에 `"loaded": false`로 등록한다 | GDD 8.14·팀원 전달 메모 2)의 "스키마만 선작성, 로더는 무시" | T0.3 | **가정** |
| A-D11 | 애니메이션 프레임 에셋(`fx_anim_*`)은 `origin:"human"`만 허용해 빌드 게이트가 AI 생성을 차단한다 | GDD 9.2가 "프레임 간 일관성은 현 시점 AI 한계"로 사람 생산을 명시 | T0.4 | **가정** |
| A-D12 | `packages/data`를 신설해 ajv·파일 I/O를 격리하고 `packages/core`의 의존성 0을 지킨다 | 스킬 기본 구조는 core/sim/web 3개지만, 로더가 core에 들어가면 "의존성 0"이 깨진다 | 1.1, T0.3 | **가정** |
| A-D13 | Phase 3을 "저장·영속성·회귀 시나리오"로 재정의하고, 오프라인·프레스티지를 Phase 1로 올린다 | 시뮬레이터(P2)가 프레스티지·오프라인 없이는 목표 벽 표를 재현할 수 없고, 디렉터 우선순위표도 같은 순서 | 4절 Phase 구성 | **가정** |

### 8.4 미결·미검증 (측정 후 판단)

| # | 항목 | 왜 미결인가 | 해소 경로 |
|---|---|---|---|
| U-1 | 60·90일 곡선과 등차 노드 인플레 | 30일까지만 검산됨 | T2.8 리포트 → 기획 결정 |
| U-2 | `drop_wait` 모드의 실제 곡선 | 밸런스 모델이 `instant` 근사로 산출 | T2.7 장비 모드 diff → 기획 재검산 |
| U-3 | 100ms 양자화로 인한 목표표 편차 | 밸런스 모델은 연속 시간 | T2.5 실행 결과의 편차 폭으로 측정. ±10% 밴드 안이면 수용 |
| U-4 | 카드 % 보너스 포함 곡선 | 모델에서 생략 | T2.7 `cards_off` vs `cards_on` diff |
| U-5 | 캠프 건물 보너스의 `g_gold` 실효값 변화 | v1.1 | T6.1 수용 기준 2 (전 구간 재검산 명시) |
| U-6 | 형님 5·6번(unlock 150/280) 기여 | 4트랙까지만 정밀 검증 | `brothers.json` 2행 추가 후 6트랙 프로파일 재실행 |
| U-7 | 광고 미시청 유저 프로파일 | `ad_policy=none` 미실행 | T5.3 수용 기준 4 |
| U-8 | 전작 전투 로직 분리 여부(진단 U-06) | 첫 미팅 세션 B에서 해소 | 1.9절 — 결과에 따라 Unity 트랙이 "추출"인지 "신규 작성"인지 갈린다 |
| U-9 | 실제 세션 길이 분포 | 일 2세션 고정 가정 | 전작 Firebase 데이터 확보 시 프로파일 교체 |

---

## 팀원 전달 메모

**수신: ax-deliverable-reviewer (검수자) · 참조: game-design-director**
**발신: codex-build-planner**

### 1) GDD ↔ 태스크 대응표 위치

**5절**입니다. 5.1이 GDD 5장 시스템 전수(5.1~5.10, 14행), 5.2가 3·4·6·7·10·11·12·13장 대응, 5.3이 명시적 제외 목록과 근거입니다. **"태스크" 열이 빈 행은 0개**이며, 확장 시스템은 전부 P6 태스크 또는 근거가 적힌 제외 항목으로 처리했습니다. 검수 시 5.1의 14행을 GDD 5장 목차와 1:1로 대조해 주시면 누락 여부가 바로 보입니다. 태스크 총수는 **40개**(P0:4 / P1:10 / P2:8 / P3:4 / P4:5 / P5:4 / P6:5)이고, 각 카드의 수용 기준은 전부 `실행 명령 → 기대 결과` 형식으로 썼습니다.

디렉터가 회신을 요청한 4건은 **8.1절에 리더 결정으로 기록**했습니다(D1 f64+사전계산테이블 / D2 트랙 index 타이브레이크 / D3 드랍 대기 + 이중 모드 / D4 60·90일은 리포트만). 이 중 **D3는 기획 담당의 목표 벽 표 재검산이 필요한 항목**입니다 — GDD 메모 3-5가 "드랍 대기를 택할 경우 반드시 회신"을 요구했고, 저는 드랍 대기를 택했습니다. T2.7이 그 재검산에 쓸 격차 리포트를 자동 생성하도록 설계했습니다.

### 2) 제가 스스로 확신하지 못하는 판단 3개

**① 100ms 정수 틱 양자화(A-D7)가 목표 벽 표를 밀어낼 수 있습니다.** GDD 3.2는 `dt=100ms`를, 밸런스 모델 9.2의 의사코드는 연속 시간(`advance(tw)`)을 씁니다. 저는 "렌더러를 제거해도 동일 결과"(GDD 12.3)를 지키려고 시뮬레이터까지 정수 틱으로 통일했는데, 이 올림이 **웨이브마다 최대 0.1초씩 누적**됩니다. D30이면 수십만 웨이브이므로 이론상 무시할 수 없습니다. 다만 f* 파밍 구간이 시간의 대부분을 차지해 실제 영향은 작을 것으로 보고 ±10% 밴드가 흡수한다고 판단했습니다. **T2.5를 처음 돌린 시점의 편차 폭이 ±5%를 넘으면 이 판단을 재검토해야 합니다** — 반대 선택지는 시뮬레이터만 연속 시간으로 두는 것인데, 그러면 13.3-2(결정성)와 12.3(렌더러 동치)이 동시에 약해집니다. 어느 쪽이 더 나쁜지 저는 확신이 없습니다.

**② 리더 결정 ③의 "드랍 대기"가 밸런스 모델과 구조적으로 어긋납니다.** 보수적 선택이라는 원칙에는 동의하지만, 이건 단순히 "느려지는" 게 아니라 **세대 교체 직후 구간의 곡선 형태 자체가 달라지는** 변경입니다(장비 배수가 계단이 아니라 드랍 확률에 의존하는 확률 과정이 됩니다). 저는 `equip_recovery_mode` 이중 모드로 회귀 기준과 실게임 동작을 분리해 회피했는데, 이건 정직하게 말하면 **문제를 푼 게 아니라 나중으로 미룬 것**입니다. 실게임 기본값이 회귀 게이트에 걸리지 않는 구성은 장기적으로 위험합니다. T2.7 리포트가 나온 뒤 기획이 목표표를 재검산하면 회귀 기준을 `drop_wait`로 옮기는 것이 옳다고 봅니다.

**③ `Math.pow` 금지와 사전 계산 테이블이 오히려 오차를 키울 수 있습니다.** 리더 결정 ①의 취지(엔진 간 차이 최소화)는 이해했고 그대로 적용했지만, 순수 수치해석으로 보면 `pow[i] = pow[i-1] × g` 반복 곱은 **오차가 i에 비례해 누적**되는 반면 잘 구현된 `Math.pow`는 상대오차가 대체로 1~2 ulp에 머뭅니다. 즉 s=1200에서 테이블 값이 `Math.pow`보다 **덜 정확할** 수 있습니다. 결정성(같은 엔진에서 항상 같은 값)은 확실히 좋아지지만 정확성은 나빠질 수 있고, 저는 이 트레이드오프에서 결정성을 택했습니다. 밸런스 모델 2.3 표와의 대조(T1.1 수용 기준 2, 상대오차 1e-3)가 이 판단의 안전망인데, 만약 s=1200 근처에서 1e-3을 못 지키면 "구간별 재정규화"(예: 100스테이지마다 테이블 값을 고정밀 기준값으로 리셋) 같은 보정이 필요합니다. 그 설계는 아직 안 했습니다.

### 3) 추가로 검수해 주셨으면 하는 곳

- **7.4 실패 시 대응 표의 "테스트를 약화시켜 통과시키는 것 금지"** — 코딩 에이전트가 가장 흔히 하는 회피입니다. 수용 기준에 테스트 **개수**를 박아 둔 것이 이 방어의 전부라서, 더 나은 방법이 있으면 지적해 주십시오.
- **1.7 에셋 게이트** — `prebuild`/`pretest` 훅은 `npm ci --ignore-scripts`로 우회됩니다. CI 독립 잡을 같이 두어 막았지만, 로컬에서는 여전히 뚫립니다.
- **T2.5의 실행 시간 10분 제한** — CI 게이트로 쓰려면 필요한데, 30일 × 2프로파일을 10분 안에 돌릴 수 있을지는 구현해 봐야 압니다. 넘으면 회귀를 야간 잡으로 내리는 선택지가 있지만 그러면 "배포 전 곡선 검증"이라는 목적이 흐려집니다.
