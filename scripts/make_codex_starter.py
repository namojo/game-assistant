# -*- coding: utf-8 -*-
"""빌드 플랜 7.1(저장소 준비 순서)을 자동화한다.
deliverables/thundergames/gdd/primitive-brothers-2/ → codex-starter/primitive-brothers-2/
  AGENTS.md, docs/{GDD,BALANCE,BUILD_PLAN,ASSUMPTIONS}.md, data/balance.json, .nvmrc, README.md
"""
import json, re, shutil, pathlib, hashlib, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "deliverables" / "thundergames" / "gdd" / "primitive-brothers-2"
DST = ROOT / "codex-starter" / "primitive-brothers-2"

def main():
    if DST.exists(): shutil.rmtree(DST)
    (DST / "docs").mkdir(parents=True); (DST / "data" / "schema").mkdir(parents=True)
    (DST / "assets" / "source").mkdir(parents=True); (DST / "assets" / "gen").mkdir(parents=True)
    plan = (SRC / "03_codex_build_plan.md").read_text(encoding="utf-8")

    # 1~3. AGENTS.md + docs/
    shutil.copy(SRC / "AGENTS.md", DST / "AGENTS.md")
    shutil.copy(SRC / "01_gdd.md", DST / "docs" / "GDD.md")
    shutil.copy(SRC / "02_balance_model.md", DST / "docs" / "BALANCE.md")
    shutil.copy(SRC / "03_codex_build_plan.md", DST / "docs" / "BUILD_PLAN.md")

    # 4. ASSUMPTIONS.md = 빌드 플랜 8절 그대로
    m = re.search(r"^## 8\. .*?(?=^## 9\.|\Z)", plan, re.S | re.M)
    assert m, "빌드 플랜 8절을 찾지 못함"
    sec8 = m.group(0).replace("## 8. 가정 · 미결 목록", "# ASSUMPTIONS — 결정 · 가정 · 보류", 1)
    sec8 = re.sub(r"^### 8\.(\d)", r"## 8.\1", sec8, flags=re.M)
    sec8 += "\n\n## 9. 구현 중 추가된 가정 (Codex가 여기에 행을 추가한다)\n\n| # | 가정 | 근거 | 영향(태스크·곡선) | 상태 |\n|---|---|---|---|---|\n"
    (DST / "docs" / "ASSUMPTIONS.md").write_text(sec8, encoding="utf-8")

    # data/balance.json = 빌드 플랜 3.4 코드 블록 + 공통 메타 3필드
    m = re.search(r"### 3\.4 .*?```json\n(.*?)```", plan, re.S)
    assert m, "3.4 balance.json 블록을 찾지 못함"
    bal = json.loads(m.group(1))
    ppm = bal["drop_rates_ppm"]["bone_grind"]
    assert all(isinstance(v, int) and 0 <= v <= 1_000_000 for v in ppm.values()) and sum(ppm.values()) == 1_000_000, "ppm 제약 위반"
    body = json.dumps(bal, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    meta = {"schema_version": 1, "generated_at": datetime.date.today().isoformat(),
            "checksum": "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()}
    out = {**meta, **bal}
    (DST / "data" / "balance.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 5. .nvmrc
    (DST / ".nvmrc").write_text("22\n")
    (DST / "assets" / "source" / ".gitkeep").write_text("")
    (DST / "assets" / "gen" / ".gitkeep").write_text("")
    (DST / "data" / "schema" / ".gitkeep").write_text("")

    # README: 시작 방법 + T0.1 프롬프트
    tmpl = re.search(r"### 7\.2 .*?```\n(.*?)```", plan, re.S)
    prompt_tmpl = tmpl.group(1).strip() if tmpl else ""
    (DST / "README.md").write_text(f"""# 원시인 형님 2 — Codex 스타터

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
{prompt_tmpl}
```

## 순서
T0.1 → T0.2 → T0.3 → T0.4 → T1.1 … 의존 태스크가 끝나기 전에 착수하지 않는다. 각 태스크는 수용 기준 명령(`npm test`, `npm run sim:regress` 등)이 통과해야 완료다. Phase 종료마다 사람이 검토한다(7.4).
""", encoding="utf-8")
    files = sorted(p.relative_to(DST).as_posix() for p in DST.rglob("*") if p.is_file())
    print("\n".join(files)); print(f"balance.json keys: {len(bal)} · checksum {meta['checksum'][:23]}…")

if __name__ == "__main__":
    main()
