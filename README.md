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
| `codex-starter/primitive-brothers-2/` | **Codex에 바로 넘기는 스타터**: `AGENTS.md` + `docs/{GDD,BALANCE,BUILD_PLAN,ASSUMPTIONS}.md` + `data/balance.json` + `.nvmrc` (`scripts/make_codex_starter.py`로 생성) |
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

## 컨셉 아트 생성 (Codex image_generation)

`site/images/*.svg`는 벡터 자리표시자입니다. Codex CLI에 로그인된 PC에서 아래를 실행하면 4장이 병렬 생성되어 `site/images/gen/`에 저장되고, 재빌드 시 자동으로 PNG가 사용됩니다. 프롬프트는 `site/images/PROMPTS.md`.

```bash
bash site/scripts/gen_concept_images.sh && python3 site/build.py
```

## Codex로 원시인 형님 2 프로토타입 만들기

1. `codex-starter/primitive-brothers-2/`를 새 저장소 루트로 복사합니다. AGENTS.md와 `docs/`(GDD·BALANCE·BUILD_PLAN·ASSUMPTIONS), `data/balance.json`이 이미 배치되어 있습니다.
2. 스타터의 README에 있는 프롬프트 템플릿으로 T0.1부터 순서대로 Codex에 넘깁니다.
3. 각 태스크의 수용 기준 명령(`npm test`, `npm run sim:regress` 등)을 통과했을 때만 다음 태스크로 넘어갑니다.
