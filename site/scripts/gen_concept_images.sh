#!/usr/bin/env bash
# 원시인 형님 2 컨셉 아트 4장을 Codex image_generation 으로 병렬 생성해 site/images/gen/ 에 저장한다.
# 요구: codex CLI (0.128+), `codex login` 완료. 사용: bash site/scripts/gen_concept_images.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/site/images/gen"; mkdir -p "$OUT" "$OUT/.logs"
command -v codex >/dev/null || { echo "codex CLI가 없습니다. npm i -g @openai/codex 후 codex login"; exit 1; }

declare -A P
P[key-visual]="빙하기 밤, 눈 덮인 빙하 계곡의 원시 부족 캠프. 가운데 큰 모닥불의 불씨가 주황빛으로 빛나고, 그 주위에 근육질의 유머러스한 원시인 형님 4~6명이 모피를 걸치고 앉아 있다. 뒤에는 가죽 천막과 뼈로 만든 토템, 저 멀리 매머드 실루엣과 오로라. 스타일: 모바일 방치형 RPG 스토어 키아트, 카툰 렌더, 굵은 외곽선, 깊은 네이비·아이스블루 배경과 따뜻한 주황 불빛의 대비. 가로 16:9. 텍스트 없음."
P[brothers]="원시인 형님 6명이 크기순으로 나란히 선 캐릭터 라인업 시트. 각자 다른 무기(돌도끼, 뼈창, 방패, 활, 주술 지팡이, 매머드 뼈 곤봉)와 다른 모피 색. 과장된 근육과 유머러스한 표정, 카툰 스타일 2D 게임 캐릭터, 굵은 외곽선, 단색 네이비 배경, 발밑에 파란 빛의 원형 받침. 가로 와이드. 텍스트 없음."
P[camp]="위에서 내려다본 원시 부족 캠프 아이소메트릭 뷰. 모닥불, 가죽 천막 3개, 뼈 토템, 사냥감 건조대, 얼음 창고, 매머드 우리. 눈과 얼음, 네이비·아이스블루 톤에 주황 불빛 포인트. 모바일 게임 경영 시뮬 UI 배경용 카툰 렌더. 가로 16:9. 텍스트 없음."
P[ember]="손바닥 위에 떠 있는 작은 불씨. 안쪽은 크림색으로 밝고 바깥은 주황·붉은 불꽃, 주위에 얼음 결정 파편이 떠다닌다. 모바일 게임 아이콘, 카툰 렌더, 어두운 네이비 배경에 강한 대비, 정방형. 텍스트 없음."

pids=()
for name in key-visual brothers camp ember; do
  codex exec --sandbox workspace-write --skip-git-repo-check --cd "$OUT" \
    -o "$OUT/.logs/$name.md" \
    "이미지 생성 도구로 '${P[$name]}' 이미지를 생성하고 ./$name.png 로 저장. 파일 경로만 한 줄로 보고." \
    >"$OUT/.logs/$name.out" 2>&1 &
  pids+=($!)
  echo "started $name (pid ${pids[-1]})"
done
for pid in "${pids[@]}"; do wait "$pid" || echo "warn: pid $pid exited non-zero"; done
echo; file "$OUT"/*.png 2>/dev/null || true
echo "완료. python3 site/build.py 로 재빌드하면 PNG가 자동 반영됩니다."
