# AGENTS.md 템플릿

```markdown
# AGENTS.md — {게임명} 프로토타입

## 이 저장소는
{한 문장}. 기획 문서는 `docs/GDD.md`, 밸런스 수식은 `docs/BALANCE.md`, 태스크는 `docs/BUILD_PLAN.md`. 코드보다 문서가 우선이며, 문서와 코드가 다르면 문서를 고치지 말고 이슈로 남긴 뒤 문서를 따른다.

## 구조
- `packages/core` — 순수 게임 룰. 외부 의존성 0. DOM·타이머·네트워크·`Math.random` 금지.
- `packages/sim` — 헤드리스 시뮬레이터 CLI. core만 의존.
- `apps/web` — 렌더러(PixiJS). core만 의존. 룰을 여기서 구현하지 않는다.
- `data/*.json` — 모든 콘텐츠·밸런스 테이블. 코드에 수치를 하드코딩하지 않는다.

## 명령
- 설치: `npm ci`
- 전체 테스트: `npm test`
- 코어만: `npm test -w packages/core`
- 시뮬레이터: `npm run sim -- --days 7 --bot balanced --seed 42`
- 회귀: `npm run sim:regress` (목표 벽 표 ±10%, 확률 검증)
- 웹 실행: `npm run dev -w apps/web` / 스크린샷: `npm run e2e`

## 규칙
- 난수는 `core/rng.ts`의 시드 RNG만 사용. 같은 시드 = 같은 결과.
- 시뮬레이션은 고정 틱(100ms). 프레임 시간에 의존하는 룰 금지.
- 저장 데이터에는 `schemaVersion` 필드. 마이그레이션 함수 없이 필드 변경 금지.
- 새 콘텐츠는 테이블 행 추가로만. 타입/스키마 변경은 `data/schema/*.json` 갱신 + 테스트 동반.
- 커밋 단위 = 태스크 카드 1개. 메시지 앞에 태스크 id (`T1.3: …`).

## 완료 정의
1. 태스크 카드의 수용 기준 명령이 모두 통과
2. `npm test` 전체 통과, `npm run sim:regress` 통과(밸런스 관련 변경 시)
3. 변경 요약 3줄 + 새로 생긴 가정은 `docs/ASSUMPTIONS.md`에 추가

## 막히면
규칙이 GDD에 없으면 임의로 정하지 말고 `docs/ASSUMPTIONS.md`에 "가정: …" 을 추가하고 가장 보수적인 선택으로 진행한다. 밸런스 파라미터 값은 바꾸지 않는다(기획 담당 결정).
```
