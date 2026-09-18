# game-assistant — 게임사 AX 컨설팅 하네스

부산 지역 게임사(1차 대상: 썬더게임즈)를 위한 AX(AI Transformation) 컨설팅 기획서·세부 자료와, 신작 방치형 RPG(원시인 형님 2)의 GDD·Codex 빌드 플랜을 에이전트 팀으로 생성하는 저장소.

## 구조
- `.claude/agents/` — 팀원 정의 7개 (누가). 모든 에이전트는 `model: opus`.
- `.claude/skills/` — 스킬 8개 (어떻게). `ax-consulting-orchestrator`가 진입점.
- `inputs/` — 컨설턴트 내부 리포트 등 원천 자료.
- `_workspace/` — 에이전트 중간 산출물 (`{순번}_{에이전트}_{산출물}.md`). 삭제하지 않는다(감사 추적).
- `deliverables/{company}/` — 최종 산출물. `gdd/{game}/`에 GDD·밸런스·빌드 플랜·AGENTS.md.

## 실행
"썬더게임즈 AX 기획서 갱신해줘", "다른 부산 게임사로 같은 산출물 만들어줘"처럼 요청하면 `ax-consulting-orchestrator` 스킬이 Phase A(시장·진단·GDD 병렬) → B(전략·빌드 플랜) → C(기획서·검수) → D(조립)로 실행한다. 팀 도구가 없으면 `Agent` 병렬 호출로 같은 Phase를 돈다.

## 원칙 (모든 산출물 공통)
- 도구 이름보다 병목 먼저. 기획서 첫 3페이지에 제품명 금지.
- 약속은 4대 KPI(에셋 리드타임·업데이트 주기·회귀 버그·CS 1차 응답)만.
- 사실 / (추정) / 미확인 을 섞지 않는다.
- 신작 코드는 결정적 코어·시드 RNG·JSON 테이블·헤드리스 시뮬레이터 원칙을 지킨다.

## 문서 언어
한국어. 코드 식별자·JSON 키·명령은 영문. 한글 등 비ASCII 문자열은 리터럴 UTF-8로 쓴다.
