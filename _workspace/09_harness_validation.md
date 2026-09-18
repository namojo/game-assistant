# 하네스 검증 기록 (Phase 6)

## 6-1 구조 검증 — 통과
- 에이전트 7개: frontmatter(name·description·model=opus) 정상, 파일명=name, 필수 6절 존재
- 스킬 8개: frontmatter 정상, 폴더명=name, 본문 30~109줄(500줄 제한 내), references 포인터 전부 실재
- 에이전트→스킬 참조 전부 실재, 오케스트레이터가 7 에이전트·7 스킬을 모두 언급
- `.claude/commands/` 미생성

## 6-2 실행 모드 검증
- 팬아웃(A: 01·02·04 병렬) → 수렴(B: 03, 05 병렬) → 생성-검증(C: 06 → 07) 순서로 실제 실행 완료
- 서브 에이전트 폴백 모드로 실행. 팀 통신은 각 문서 말미 "팀원 전달 메모"로 대체되었고, 후속 에이전트 프롬프트에 리더가 메모 위치를 명시해 데이터 흐름 dead link 없음
- 실측: 진단자 이의(CS 우선순위) → 전략가 수용, 디렉터 질의 4건 → 리더 결정 → 플래너 적용, 검수자 차단 2건 → 즉시 수정. 경계면 토론이 실제로 결과를 바꿨음

## 6-3 스킬 실행 테스트 (실 실행 = 테스트 1회)
| 스킬 | 프롬프트(요약) | 결과 | 확인된 부가가치 |
|---|---|---|---|
| regional-game-market-brief | 썬더게임즈 5축 브리핑 | 01, 10절 전부 | 규제 신호(3배 배상·AI 기본법)를 "귀사는?" 질문으로 변환, 상충 수치 병기 |
| studio-ax-diagnosis | 3.60 사이클 해부·미팅 키트 | 02, 9절 전부 | 사실 14/추정 14/미확인 22 분리, 병목 점수표가 전략 입력으로 직결 |
| idle-rpg-gdd | 원시인 형님 2 GDD·밸런스 | 04·04b | 목표 벽 표 10체크포인트 python 검산 ±10% 통과, 목표표 자체 개정 이력 |
| codex-build-spec | Codex 빌드 플랜 | 05·05b | 40(→41) 태스크 전부 `명령→기대 결과` 수용 기준, GDD 시스템 대응 0 누락 |
| ax-strategy-blueprint | AX 청사진 | 03 | 순위와 착수 시점 분리, KPI ② 두 축, 의존 종료를 조건 3개로 |
| ax-proposal-writer | 기획서 3종 | 06·06b·06c | 첫 3페이지 제품명 0, 금지 단어 0, 상위 문서 불일치 7건 자체 발견 |
| ax-deliverable-review | 교차 검수 | 07 | 차단 2건(확률표 자릿수·시행수 10배 오기) 발견 — 단일 문서 검토로는 못 잡는 경계면 버그 |

발견된 개선 포인트(반영 완료): 로드맵 단계 번호 체계(0~3 vs 1~4)가 문서 간 어긋남 → 스킬 `regional-game-market-brief`·`ax-strategy-blueprint`에 "로드맵은 0 진단 / 1 Quick Win / 2 파이프라인화 / 3 조직화 번호를 쓴다" 명시 필요 → 아래 6-6에서 반영.

## 6-4 트리거 검증 (설계 검토)
### should-trigger → 기대 스킬
| 쿼리 | 기대 |
|---|---|
| "부산 게임사 AX 컨설팅 기획서와 신작 GDD 한 번에 만들어줘" | ax-consulting-orchestrator |
| "썬더게임즈 AX 전략 자료 갱신해줘" | ax-consulting-orchestrator |
| "방치형 RPG 시장 트렌드랑 부산 지원사업 정리해서 첫 미팅 슬라이드 재료로" | regional-game-market-brief |
| "이 게임사 업데이트 사이클 병목 분석하고 사전 요청 자료 목록 뽑아줘" | studio-ax-diagnosis |
| "진단 결과로 AI 도입 로드맵과 KPI 잡아줘" | ax-strategy-blueprint |
| "키우기 게임 신작 성장 곡선이랑 프레스티지 설계해줘" | idle-rpg-gdd |
| "이 GDD를 Codex가 구현할 수 있게 태스크로 쪼개고 AGENTS.md 써줘" | codex-build-spec |
| "분석 문서를 대표님 제출용 제안서로 바꿔줘" | ax-proposal-writer |
| "기획서랑 GDD랑 빌드 플랜이 서로 맞는지 검수해줘" | ax-deliverable-review |
| "게임 스튜디오 AI 전환 제안서, 진단, 로드맵 묶음으로" | ax-consulting-orchestrator |

### should-NOT-trigger (near-miss) → 올바른 처리
| 쿼리 | 트리거하면 안 되는 스킬 | 올바른 처리 |
|---|---|---|
| "이 게임의 스토어 리뷰 23만 건을 클러스터링해줘" | regional-game-market-brief | 데이터 분석 작업(일반 도구) |
| "Unity 프로젝트 전투 로직을 MonoBehaviour에서 분리해줘" | codex-build-spec | 코드 리팩터링(일반 코딩) |
| "이 TypeScript 시뮬레이터 코드 리뷰해줘" | ax-deliverable-review | code-review 스킬 |
| "방치형 RPG 밸런스 시트 D7 잔존 계산해줘" | idle-rpg-gdd | 단발 계산(일반 도구) — GDD 작성 아님 |
| "우리 회사 AI 도입 사례 블로그 글 써줘" | ax-proposal-writer | 일반 글쓰기 |
| "이 기획서 오탈자만 고쳐줘" | ax-deliverable-review | 단일 문서 교정(일반 편집) |
| "Spring Boot로 게임 서버 만들어줘" | codex-build-spec | spring-boot-init 스킬 |
| "부산 여행 일정 짜줘" | regional-game-market-brief | 무관 |
| "새 도메인용 에이전트 팀 하네스 만들어줘" | ax-consulting-orchestrator | harness 메타 스킬 |
| "이 리포트 아스키 다이어그램 그림으로 바꿔줘" | (모두) | ascii-to-diagram 스킬 |

판정: 각 description에 트리거 상황과 경계 조건("…은 대상이 아님", "…은 ○○가 담당")이 명시되어 near-miss 10건 모두 배제 근거가 description 안에 있음. 기존 스킬(code-review, spring-boot-init, ascii-to-diagram, harness)과 키워드 충돌 없음.

## 6-5 드라이런
- Phase 입력·출력 매칭: A(00→01,02,04) / B(01,02→03; 04→05) / C(01~05→06; 01~06→07) / D(→deliverables) — 빈 구간 없음
- 에러 폴백: 시장분석가 WebFetch 전량 차단(EGRESS_BLOCKED) 발생 → 스킬 절차 2("웹 조사는 공백에만")와 오케스트레이터 에러표("추가 조사 필요 섹션 생성")대로 처리됨. 실제 에러 흐름 1건 검증 완료.

## 6-6 검증 후 스킬 수정
- `regional-game-market-brief`, `ax-strategy-blueprint`, `ax-proposal-writer` 3개 SKILL.md에 로드맵 단계 번호 규약(0~3) 1줄 추가
