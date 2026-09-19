# 원시인 형님 2 — Codex 스타터

`docs/BUILD_PLAN.md` 7.1의 "저장소 준비 순서"를 마친 상태다. 이 폴더를 새 저장소 루트로 복사하고 T0.1부터 순서대로 Codex에 넘긴다.

## 들어 있는 것
| 경로 | 내용 |
|---|---|
| `AGENTS.md` | Codex 규칙 파일 (명령·금지·완료 정의·막힐 때 행동) |
| `docs/GDD.md` | GDD v0.1 |
| `docs/BALANCE.md` | 밸런스 모델 bal_v1 (목표 진행 벽 표·검산) |
| `docs/BUILD_PLAN.md` | 41 태스크 카드 (P0~P6), 시뮬레이터·회귀 명세 |
| `docs/ASSUMPTIONS.md` | 결정·가정·보류 초기 목록. Codex가 9절에 행을 추가한다 |
| `data/balance.json` | bal_v1 단일 원본. **Codex는 이 값을 수정하지 않는다** |
| `.nvmrc` | Node 22 |

## 시작
```bash
cp -r codex-starter/primitive-brothers-2 ~/primitive-brothers-2 && cd ~/primitive-brothers-2
git init && git add -A && git commit -m "chore: docs and AGENTS.md"
nvm use 22
codex   # 아래 프롬프트로 T0.1부터
```

## 태스크 프롬프트 템플릿 (BUILD_PLAN 7.2)
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

## 순서
T0.1 → T0.2 → T0.3 → T0.4 → T1.1 … 의존 태스크가 끝나기 전에 착수하지 않는다. 각 태스크는 수용 기준 명령(`npm test`, `npm run sim:regress` 등)이 통과해야 완료다. Phase 종료마다 사람이 검토한다(7.4).
