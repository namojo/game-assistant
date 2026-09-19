#!/usr/bin/env bash
# docs/ 를 빌드하고 gh-pages 브랜치 루트에 배포한다 → https://namojo.github.io/game-assistant/
# 사용: bash site/scripts/deploy_pages.sh            (빌드 + 배포)
#       bash site/scripts/deploy_pages.sh --no-build (docs/ 그대로 배포)
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ "${1:-}" != "--no-build" ]; then
  python3 site/build.py
fi
[ -f docs/index.html ] || { echo "docs/index.html 이 없습니다. 빌드가 실패했는지 확인하세요."; exit 1; }

WT="$(mktemp -d "${TMPDIR:-/tmp}/ghp.XXXXXX")"
trap 'git worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$WT"' EXIT

git fetch -q origin gh-pages 2>/dev/null || true
if git show-ref -q --verify refs/remotes/origin/gh-pages; then
  git worktree add -q "$WT" -B gh-pages origin/gh-pages
else
  git worktree add -q --detach "$WT"
  (cd "$WT" && git checkout -q --orphan gh-pages && git rm -rfq . 2>/dev/null || true)
fi

# 기존 내용을 비우고 docs/ 로 교체 (.git 제외)
find "$WT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R docs/. "$WT"/
touch "$WT/.nojekyll"

cd "$WT"
git add -A
if git diff --cached --quiet; then
  echo "변경 없음 — 배포할 내용이 없습니다."
  exit 0
fi
git commit -q -m "Deploy site $(date +%Y-%m-%d\ %H:%M) from $(git -C "$ROOT" rev-parse --short HEAD)"
git push -u origin gh-pages
echo "배포 완료 → https://namojo.github.io/game-assistant/  (반영까지 보통 1~2분)"
