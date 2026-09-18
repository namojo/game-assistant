# game-assistant

**웹 페이지: https://namojo.github.io/game-assistant/** (gh-pages 브랜치, `site/build.py`로 생성)

부산 지역 게임사를 위한 **AX(AI Transformation) 컨설팅 하네스**와 그 첫 적용 사례(썬더게임즈)입니다.

## 무엇이 들어 있나

| 경로 | 내용 |
|---|---|
| `.claude/agents/` | 컨설팅 팀원 7명: 시장분석가 · 스튜디오 진단가 · AX 전략가 · 게임디자인 디렉터 · Codex 빌드 플래너 · 기획서 작성자 · 산출물 검수자 |
| `.claude/skills/` | 팀원이 쓰는 스킬 8개 (오케스트레이터 포함) |
| `deliverables/thundergames/` | 썬더게임즈 AX 컨설팅 기획서·경영진 요약·시장 브리핑·진단·전략 청사진·첫 미팅 키트·검수 리포트 |
| `deliverables/thundergames/gdd/primitive-brothers-2/` | 신작 '원시인 형님 2' GDD · 밸런스 모델 · Codex 빌드 플랜 · AGENTS.md |
| `inputs/` | 원천 자료(컨설턴트 내부 리포트) |
| `_workspace/` | 에이전트 중간 산출물 (감사 추적용 보존) |

## 하네스 흐름

```
inputs ─┬→ [시장분석가] ─→ 01 ─┐
        ├→ [진단가] ─────→ 02 ─┼→ [전략가] ─→ 03 ─┐
        └→ [디자인 디렉터] → 04 ─→ [Codex 플래너] → 05 ─┼→ [기획서 작성자] → 06 → [검수자] → 07
                                                              ↓
                                                   deliverables/{company}/
```

Claude Code에서 `ax-consulting-orchestrator` 스킬을 트리거하는 요청(예: "○○게임즈 AX 컨설팅 기획서와 신작 GDD 만들어줘")으로 다른 회사에도 재사용할 수 있습니다.

## Codex로 원시인 형님 2 프로토타입 만들기

1. 새 저장소를 만들고 `deliverables/thundergames/gdd/primitive-brothers-2/`의 `AGENTS.md`를 루트에, GDD·밸런스·빌드 플랜을 `docs/`에 둡니다.
2. 빌드 플랜의 Phase 0 태스크부터 순서대로 Codex에 프롬프트합니다(빌드 플랜 7장의 예시 프롬프트 참고).
3. 각 태스크의 수용 기준 명령(`npm test`, `npm run sim:regress` 등)을 통과했을 때만 다음 태스크로 넘어갑니다.
