# site/ — GitHub Pages 빌더

`python3 site/build.py` 를 실행하면 `deliverables/`·`.claude/agents`·`.claude/skills`의 마크다운을 읽어 `docs/`에 정적 사이트를 생성한다. 의존성: `pip install markdown pymdown-extensions`.

배포: `docs/`의 내용을 `gh-pages` 브랜치 루트에 푸시한다 (https://namojo.github.io/game-assistant/).
