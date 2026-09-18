---
name: ax-consulting-orchestrator
description: "지방(부산) 게임사 AX 컨설팅 기획서·세부 자료·신작 GDD·Codex 빌드 플랜을 에이전트 팀으로 생성하는 오케스트레이터. '게임사 AX 컨설팅 기획서 만들어줘', '썬더게임즈 AX 전략', '부산 게임사 컨설팅 자료', '방치형 RPG 신작 기획 + Codex로 구현' 같은 요청, 또는 게임 스튜디오 대상 AI 전환 제안서·진단·로드맵을 한 묶음으로 요청하면 반드시 이 스킬을 사용할 것. 단일 문서(예: 시장 브리핑만, GDD만)만 필요하면 해당 개별 스킬을 직접 사용."
---

# AX Consulting Orchestrator

게임 스튜디오 AX 컨설팅 산출물 묶음(시장 브리핑 → 진단 → 전략 청사진 → 기획서 → 신작 GDD → Codex 빌드 플랜 → 검수)을 생성하는 통합 스킬.

## 실행 모드: 에이전트 팀 (기본) / 서브 에이전트 (폴백)

팀 도구(TeamCreate)가 있으면 팀 모드로, 없으면 `Agent` 도구 병렬 호출로 같은 Phase 구조를 실행한다. 두 모드 모두 산출물은 `_workspace/`에 파일로 남기므로 데이터 흐름은 동일하다. 모든 Agent 호출은 `model: "opus"`.

## 에이전트 구성

| 팀원 | 정의 파일 | 역할 | 사용 스킬 | 출력 (`_workspace/`) |
|---|---|---|---|---|
| ax-market-analyst | `.claude/agents/ax-market-analyst.md` | 시장·지역·정책 브리핑 | regional-game-market-brief | `01_market_analyst_brief.md` |
| ax-studio-diagnostician | `.claude/agents/ax-studio-diagnostician.md` | 스튜디오 진단·미팅 키트 | studio-ax-diagnosis | `02_diagnostician_studio_diagnosis.md` |
| ax-strategy-architect | `.claude/agents/ax-strategy-architect.md` | AX 전략 청사진 | ax-strategy-blueprint | `03_strategy_ax_blueprint.md` |
| game-design-director | `.claude/agents/game-design-director.md` | 신작 GDD·밸런스 모델 | idle-rpg-gdd | `04_gdd_*.md`, `04b_balance_model.md` |
| codex-build-planner | `.claude/agents/codex-build-planner.md` | Codex 빌드 플랜·AGENTS.md | codex-build-spec | `05_codex_build_plan.md`, `05b_AGENTS.md` |
| ax-proposal-writer | `.claude/agents/ax-proposal-writer.md` | 고객 제출용 기획서 | ax-proposal-writer | `06_proposal_main.md`, `06b_*`, `06c_*` |
| ax-deliverable-reviewer | `.claude/agents/ax-deliverable-reviewer.md` | 교차 정합성 검수 | ax-deliverable-review | `07_review_report.md` |

## 워크플로우

### Phase 0: 준비 (리더)
1. 사용자 입력에서 대상사·지역·대표 게임·신작 요청·요청 범위(아트/QA 등)를 추출한다.
2. `_workspace/00_input/`에 입력 리포트·메모를 저장한다. 없으면 대상사 이름만으로도 시작 가능하나, 산출물 전체에 "진단 후 갱신" 표시가 늘어난다는 점을 사용자에게 알린다.
3. 출력 경로를 정한다. 기본: `deliverables/{company-slug}/`.

### Phase A: 팬아웃 (병렬, 상호 독립)
market-analyst, studio-diagnostician, game-design-director를 동시에 실행한다. 세 작업은 입력 리포트만 있으면 시작할 수 있어 서로 기다릴 필요가 없다.

팀 모드 통신 규칙:
- analyst → diagnostician: 규제·경쟁 신호 (체크리스트 반영용)
- diagnostician → game-design-director: 전작 시스템 목록·UX 마찰
- analyst → game-design-director: 정면 경쟁 회피 구간·수익모델 트렌드

서브 에이전트 모드: 위 정보는 리더가 프롬프트에 입력 리포트 경로와 함께 미리 명시한다.

### Phase B: 수렴 (01·02 → 전략, 04 → 빌드 플랜)
- strategy-architect: 01·02를 읽고 03 작성. 병목 점수 순위와 우선순위가 어긋나면 diagnostician과 토론 후 병기.
- codex-build-planner: 04·04b를 읽고 05·05b 작성. GDD 모호 규칙은 director에게 질의(팀 모드) 또는 "가정" 표시(서브 모드).
두 작업은 서로 독립이므로 병렬 실행.

### Phase C: 기획서 + 검수
1. proposal-writer가 01~05를 읽고 06 세트 작성.
2. reviewer가 01~06 교차 검수 → 07 작성 → 차단/중요 항목을 원저자(또는 리더)에게 전달.
3. 수정 루프 최대 2회. 서브 모드에서는 리더가 07의 차단 항목을 직접 반영한다.

### Phase D: 조립 (리더)
`_workspace/` 산출물을 `deliverables/{company-slug}/` 구조로 복사·정리한다:

```
deliverables/{company-slug}/
├── 00_executive_summary.md        ← 06b
├── 01_ax_consulting_proposal.md   ← 06
├── 02_market_and_region_brief.md  ← 01
├── 03_studio_diagnosis.md         ← 02
├── 04_ax_strategy_blueprint.md    ← 03
├── 05_first_meeting_kit.md        ← 06c
├── 06_review_report.md            ← 07
└── gdd/{game-slug}/
    ├── 01_gdd.md                  ← 04
    ├── 02_balance_model.md        ← 04b
    ├── 03_codex_build_plan.md     ← 05
    └── AGENTS.md                  ← 05b
```

`_workspace/`는 보존한다(감사 추적). 사용자에게 산출물 목록과 리뷰의 잔여 리스크를 보고한다.

## 데이터 흐름

```
00_input ─┬→ [analyst] ──→ 01 ─┐
          ├→ [diagnostician] → 02 ─┼→ [strategy] → 03 ─┐
          └→ [director] ─→ 04/04b ─→ [codex-planner] → 05/05b ─┼→ [writer] → 06 ─→ [reviewer] → 07
                                                                 └────────────────────────┘
                                                                        ↓
                                                              [리더: deliverables/ 조립]
```

## 에러 핸들링

| 상황 | 전략 |
|---|---|
| Phase A 팀원 1명 실패 | 1회 재시도. 재실패 시 입력 리포트의 해당 장을 대체 입력으로 사용, 문서에 "에이전트 산출 아님" 표시 |
| 01·02 모두 실패 | 사용자에게 알리고 입력 리포트만으로 전략을 쓸지 확인 |
| director↔planner 질의 응답 없음 | planner는 "가정" 표시 후 진행, 리뷰어가 가정 목록을 첫 미팅 확인 항목으로 승격 |
| 리뷰 차단 항목 2회 후 잔존 | 최종 보고에 미해결 목록 명시, 조립은 진행 |
| 산출물 간 수치 상충 | 출처 병기, 삭제 금지 |

## 테스트 시나리오

### 정상 흐름
1. 입력: 컨설팅 내부 리포트 + "썬더게임즈 AX 기획서와 원시인 형님 2 GDD를 Codex용으로"
2. Phase A: 01·02·04(+04b) 생성
3. Phase B: 03·05(+05b) 생성
4. Phase C: 06 세트, 07 생성. 리뷰 차단 항목 0~2개 → 수정
5. Phase D: `deliverables/thundergames/` 12개 파일 조립
6. 검증: 06의 KPI 4개가 03과 동일, 05의 태스크 목록이 04의 시스템을 전부 커버

### 에러 흐름
1. Phase A에서 market-analyst 웹 조사 실패(네트워크)
2. 1회 재시도 실패 → 입력 리포트 4~5장을 01로 대체, "추가 조사 필요" 섹션 생성
3. Phase B·C 정상 진행, 07에 "시장 브리핑 경쟁작 비교 미수집" 기록
4. 최종 보고에 누락 명시
