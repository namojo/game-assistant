# -*- coding: utf-8 -*-
"""Static site builder: deliverables/*.md + .claude/agents → docs/ (GitHub Pages)."""
import re, shutil, html, pathlib, json
import markdown

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
SITE = ROOT / "site"
DELIV = ROOT / "deliverables" / "thundergames"
GDD = DELIV / "gdd" / "primitive-brothers-2"
AGENTS = ROOT / ".claude" / "agents"
SKILLS = ROOT / ".claude" / "skills"
REPO = "https://github.com/namojo/game-assistant"

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=Noto+Serif+KR:wght@600;700;900&display=swap" rel="stylesheet">'

DOCS = [
  # (group, src, slug, title, subtitle, reader, badges)
  ("thundergames", DELIV/"00_executive_summary.md", "executive-summary", "경영진 요약", "1장. 배경 · 진단 가설 3 · 0+3단계 · KPI 4 · 다음 단계", "대표", ["제출용","1장"]),
  ("thundergames", DELIV/"01_ax_consulting_proposal.md", "proposal", "AX 컨설팅 기획서", "본 기획서 12절 + 부록 A~E. 첫 3페이지에 제품명 없음, 약속은 KPI 4개만.", "대표·실무진", ["제출용","v1.0"]),
  ("thundergames", DELIV/"02_market_and_region_brief.md", "market-brief", "시장·지역·정책 브리핑", "5개 축(장르·시장·수익모델/규제·AI 도입·지역/지원) × 대상사 함의 × '귀사는?' 질문", "컨설턴트 · 세션 A 재료", ["내부","5축"]),
  ("thundergames", DELIV/"03_studio_diagnosis.md", "diagnosis", "스튜디오 진단", "프로파일(사실/추정/미확인), 3.60 업데이트 사이클 분해, 병목 점수표, Quick Win 3, 진단 계획", "컨설턴트", ["내부","병목 점수"]),
  ("thundergames", DELIV/"04_ax_strategy_blueprint.md", "strategy", "AX 전략 청사진", "시나리오 A/B/C, 우선순위 매트릭스, 영역별 AX, 에이전트 하네스 아키텍처, 로드맵, KPI, 거버넌스", "컨설턴트·실무진", ["내부","청사진"]),
  ("thundergames", DELIV/"05_first_meeting_kit.md", "meeting-kit", "첫 미팅 키트", "반나절 아젠다, 사전 요청 자료(신작 검토용 전작 확인 14건 포함), 메일 전문", "고객", ["제출용","반나절"]),
  ("thundergames", DELIV/"06_review_report.md", "review", "교차 검수 리포트", "차단 2 · 중요 10 · 권고 9, 직접 수정 28곳, 리더 결정 7건, 잔여 리스크", "컨설턴트", ["내부","QA"]),
  ("gdd", GDD/"01_gdd.md", "gdd", "원시인 형님 2 — GDD v0.1", "부족 캠프 경영 메타 + 빙하기 세대 교체 프레스티지. 데이터 스키마 12 테이블, 확률 ppm 규격.", "기획·Codex 입력", ["GDD","14장"]),
  ("gdd", GDD/"02_balance_model.md", "balance", "밸런스 모델 bal_v1", "수식·파라미터, 목표 진행 벽 표(10 체크포인트 ±10% 검산 통과), 조정 이력, 시뮬레이터 계약", "기획·시뮬레이터 구현", ["bal_v1","검산"]),
  ("gdd", GDD/"03_codex_build_plan.md", "build-plan", "Codex 빌드 플랜", "TypeScript 모노레포(core/sim/web), 41 태스크(P0~P6), 시뮬레이터 CLI·회귀 명세, 실행 가이드", "Codex · 테크니컬 디렉터", ["41 태스크","P0~P6"]),
  ("gdd", GDD/"AGENTS.md", "agents-md", "AGENTS.md", "Codex 저장소 루트용 규칙 파일. 명령·규칙·완료 정의·막힐 때 행동.", "Codex", ["저장소 루트"]),
]

AGENT_META = [
  ("ax-market-analyst","시장·지역·정책 분석가","MK"),
  ("ax-studio-diagnostician","스튜디오 진단가","DX"),
  ("ax-strategy-architect","AX 전략 설계자","ST"),
  ("game-design-director","게임디자인 디렉터","GD"),
  ("codex-build-planner","Codex 빌드 플래너","CB"),
  ("ax-proposal-writer","기획서 작성자","PW"),
  ("ax-deliverable-reviewer","산출물 검수자","QA"),
]

IMAGES = SITE / "images"
DEMO_URL = "https://ember-clan.robin-hwang.chatgpt.site/"

def img(name, rel):
    """gen/<name>.png 가 있으면 PNG, 없으면 SVG 자리표시자."""
    if (IMAGES/"gen"/f"{name}.png").exists():
        return f"{rel}images/gen/{name}.png"
    return f"{rel}images/{name}.svg"

def md_to_html(text):
    md = markdown.Markdown(extensions=["tables","fenced_code","toc","attr_list","md_in_html","sane_lists","pymdownx.tilde","pymdownx.betterem","pymdownx.tasklist"],
                           extension_configs={"toc":{"toc_depth":"2-3","permalink":False}})
    body = md.convert(text)
    body = body.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")
    return body, md.toc_tokens

def frontmatter(p):
    t = p.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", t, re.S)
    d = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k,v = line.split(":",1); d[k.strip()] = v.strip().strip('"')
        return d, m.group(2)
    return d, t

def toc_html(tokens):
    out = []
    for t in tokens:
        out.append(f'<a href="#{t["id"]}">{html.escape(t["name"])}</a>')
        for c in t.get("children", []):
            out.append(f'<a class="l3" href="#{c["id"]}">{html.escape(c["name"])}</a>')
    return "\n".join(out)

def nav(rel, active=""):
    items = [("index.html","홈"),("thundergames/proposal.html","기획서"),("thundergames/strategy.html","전략"),("gdd/gdd.html","원시인 형님 2"),("index.html#demo","데모"),("harness/index.html","하네스"),(REPO,"GitHub")]
    links = "".join(f'<a href="{rel+h if not h.startswith("http") else h}" class="{"on" if a==active else ""}"{" target=_blank rel=noopener" if h.startswith("http") else ""}>{n}</a>' for h,n in items for a in [n])
    return f'''<header class="nav"><div class="wrap"><a class="brand" href="{rel}index.html"><span class="dot"></span>game-assistant</a><nav class="nav-links">{links}</nav><button class="theme" aria-label="테마 전환" title="테마 전환">◐</button></div></header>'''

def page(rel, title, body, active="", desc=""):
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">{FONTS}<link rel="stylesheet" href="{rel}assets/style.css"><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='14' fill='%230B1F3A'/%3E%3Ccircle cx='16' cy='16' r='6' fill='%2338E1FF'/%3E%3C/svg%3E"></head><body>{nav(rel, active)}{body}<footer><div class="wrap"><div>game-assistant · 부산 게임사 AX 컨설팅 하네스 · 2026-09-18</div><div>산출물은 Claude Code 에이전트 팀이 생성했고, 컨설턴트 검토 전 초안입니다. <a href="{REPO}" target="_blank" rel="noopener">저장소</a></div></div></footer><script src="{rel}assets/app.js"></script></body></html>'''

def doc_page(group, src, slug, title, sub, reader, badges, prev, nxt):
    text = src.read_text(encoding="utf-8")
    body, toks = md_to_html(text)
    rel = "../"
    crumbs = f'<a href="{rel}index.html">홈</a> / <a href="{rel}{ "gdd/gdd.html" if group=="gdd" else "thundergames/proposal.html"}">{ "원시인 형님 2" if group=="gdd" else "썬더게임즈 산출물"}</a> / {html.escape(title)}'
    bd = "".join(f'<span class="badge">{html.escape(b)}</span>' for b in badges+[f"독자: {reader}"])
    def pn(d, cls, label):
        if not d: return "<span></span>"
        return f'<a class="{cls}" href="{d[2]}.html"><small>{label}</small>{html.escape(d[3])}</a>'
    inner = f'''<div class="doc-head"><div class="wrap"><div class="crumbs">{crumbs}</div><h1>{html.escape(title)}</h1><p class="sub">{html.escape(sub)}</p><div class="badges">{bd}</div></div></div>
<div class="wrap doc-grid"><aside class="toc"><div class="t">CONTENTS</div>{toc_html(toks)}</aside><article class="md">{body}<div class="pn">{pn(prev,"prev","← 이전")}{pn(nxt,"next","다음 →")}</div></article></div>'''
    return page(rel, f"{title} · game-assistant", inner, "기획서" if group=="thundergames" else "원시인 형님 2", sub)

def flow_svg():
    # harness data-flow diagram
    return '''<svg viewBox="0 0 1100 340" role="img" aria-label="하네스 데이터 흐름">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#7CC4FF"/></marker>
<linearGradient id="gA" x1="0" x2="1"><stop offset="0" stop-color="#1E54D6"/><stop offset="1" stop-color="#2A63E8"/></linearGradient></defs>
<style>.b{fill:url(#gA);stroke:#7CC4FF;stroke-opacity:.5;rx:12}.t{fill:#fff;font-size:14px;font-weight:600}.s{fill:#A9BEDF;font-size:11.5px}.ph{fill:#38E1FF;font-size:11px;letter-spacing:.14em;font-family:IBM Plex Mono,monospace}.l{stroke:#7CC4FF;stroke-width:1.6;fill:none;marker-end:url(#ar);opacity:.85}.in{fill:#0E2140;stroke:#38E1FF;stroke-dasharray:4 4}</style>
<text x="20" y="28" class="ph">INPUT</text><text x="230" y="28" class="ph">PHASE A · 팬아웃</text><text x="500" y="28" class="ph">PHASE B · 수렴</text><text x="745" y="28" class="ph">PHASE C · 생성-검증</text><text x="985" y="28" class="ph">PHASE D</text>
<rect x="20" y="130" width="150" height="80" rx="12" class="in"/><text x="95" y="165" text-anchor="middle" class="t">내부 리포트</text><text x="95" y="186" text-anchor="middle" class="s">inputs/ · 00_input</text>
<rect x="230" y="50" width="200" height="66" rx="12" class="b"/><text x="330" y="78" text-anchor="middle" class="t">시장·지역 분석가</text><text x="330" y="98" text-anchor="middle" class="s">01 브리핑 (5축 · 귀사는?)</text>
<rect x="230" y="137" width="200" height="66" rx="12" class="b"/><text x="330" y="165" text-anchor="middle" class="t">스튜디오 진단가</text><text x="330" y="185" text-anchor="middle" class="s">02 진단 (병목 점수표)</text>
<rect x="230" y="224" width="200" height="66" rx="12" class="b"/><text x="330" y="252" text-anchor="middle" class="t">게임디자인 디렉터</text><text x="330" y="272" text-anchor="middle" class="s">04 GDD · 04b 밸런스</text>
<rect x="500" y="93" width="200" height="66" rx="12" class="b"/><text x="600" y="121" text-anchor="middle" class="t">AX 전략 설계자</text><text x="600" y="141" text-anchor="middle" class="s">03 청사진 (매트릭스·KPI)</text>
<rect x="500" y="224" width="200" height="66" rx="12" class="b"/><text x="600" y="252" text-anchor="middle" class="t">Codex 빌드 플래너</text><text x="600" y="272" text-anchor="middle" class="s">05 빌드 플랜 · AGENTS.md</text>
<rect x="745" y="93" width="200" height="66" rx="12" class="b"/><text x="845" y="121" text-anchor="middle" class="t">기획서 작성자</text><text x="845" y="141" text-anchor="middle" class="s">06 기획서·요약·미팅 키트</text>
<rect x="745" y="224" width="200" height="66" rx="12" class="b"/><text x="845" y="252" text-anchor="middle" class="t">산출물 검수자</text><text x="845" y="272" text-anchor="middle" class="s">07 교차 검수 → 수정</text>
<rect x="985" y="137" width="100" height="80" rx="12" class="in"/><text x="1035" y="170" text-anchor="middle" class="t">조립</text><text x="1035" y="190" text-anchor="middle" class="s">deliverables/</text>
<path class="l" d="M170 160 C200 160 200 83 230 83"/><path class="l" d="M170 170 L230 170"/><path class="l" d="M170 180 C200 180 200 257 230 257"/>
<path class="l" d="M430 83 C465 83 465 126 500 126"/><path class="l" d="M430 170 C465 170 465 126 500 126"/><path class="l" d="M430 257 L500 257"/>
<path class="l" d="M700 126 L745 126"/><path class="l" d="M700 257 C722 257 722 145 745 140"/>
<path class="l" d="M845 159 L845 224"/><path class="l" d="M945 257 C965 257 965 190 985 185"/><path class="l" d="M945 126 C965 126 965 165 985 165"/>
<path class="l" d="M745 240 C720 240 700 200 700 165" stroke-dasharray="3 4"/><text x="700" y="195" class="s" text-anchor="end">이의·질의·수정 요청</text>
</svg>'''

def index():
    rel = ""
    cards_t = "".join(f'''<div class="card"><span class="k">{html.escape(d[2].upper())}</span><h3><a class="stretch" href="thundergames/{d[2]}.html">{html.escape(d[3])}</a></h3><p>{html.escape(d[4])}</p><div class="meta">{"".join(f'<span class="tag">{html.escape(b)}</span>' for b in d[6])}<span class="tag ice">독자 · {html.escape(d[5])}</span></div></div>''' for d in DOCS if d[0]=="thundergames")
    cards_g = "".join(f'''<div class="card"><span class="k">{html.escape(d[2].upper())}</span><h3><a class="stretch" href="gdd/{d[2]}.html">{html.escape(d[3])}</a></h3><p>{html.escape(d[4])}</p><div class="meta">{"".join(f'<span class="tag">{html.escape(b)}</span>' for b in d[6])}</div></div>''' for d in DOCS if d[0]=="gdd")
    agents = ""
    for name, role, ic in AGENT_META:
        fm, _ = frontmatter(AGENTS/f"{name}.md")
        agents += f'<a class="agent" href="harness/{name}.html" style="color:inherit"><div class="ic">{ic}</div><div><b>{role} <code style="font-size:12px;color:var(--muted)">{name}</code></b><small>{html.escape(fm.get("description","")[:110])}…</small></div></a>'
    skills = ""
    for p in sorted(SKILLS.glob("*/SKILL.md")):
        fm,_ = frontmatter(p)
        skills += f'<span class="chip"><code>{p.parent.name}</code>{"오케스트레이터" if "orchestrator" in p.parent.name else ""}</span>'
    body = f'''
<section class="hero"><div class="wrap">
<div><div class="eyebrow reveal">Busan · Game Studio · AI Transformation</div>
<h1 class="reveal" style="animation-delay:.08s">지방 게임사의 약점은<br><em>에이전트로 상쇄할 수 있는</em><br>종류의 약점이다</h1>
<p class="lead reveal" style="animation-delay:.16s">부산 게임사 썬더게임즈를 위한 AX 컨설팅 기획서·세부 자료와, 신작 방치형 RPG 「원시인 형님 2」의 GDD·Codex 빌드 플랜을 7개 전문 에이전트 팀이 생성했습니다. 이 페이지는 그 결과물과 하네스 구조를 정리한 것입니다.</p>
<div class="cta reveal" style="animation-delay:.24s"><a class="btn p" href="thundergames/executive-summary.html">경영진 요약 읽기</a><a class="btn g" href="gdd/gdd.html">원시인 형님 2 GDD</a><a class="btn g" href="harness/index.html">하네스 구조</a></div></div>
<div class="stats reveal" style="animation-delay:.3s"><div class="stat"><b>7</b><span>전문 에이전트</span></div><div class="stat"><b>11</b><span>최종 산출 문서</span></div><div class="stat"><b>41</b><span>Codex 빌드 태스크</span></div><div class="stat"><b>±10%</b><span>밸런스 검산 통과 (10 체크포인트)</span></div></div>
</div></section>

<section class="sec"><div class="wrap"><div class="sec-h"><span class="num">01</span><h2>먼저 약속하는 세 가지</h2><p>기획서의 핵심 메시지입니다. 도구 이름은 부록에만 있고, 약속은 측정 가능한 것만 합니다.</p></div>
<div class="msg">
<div class="card"><span class="n">1</span><h3>아트와 QA는 효율화가 아니라 매출과 법적 방어의 문제</h3><p>스킨은 곧 에셋이므로 아트 생산량의 상한이 비확률 매출의 상한입니다. 2025년 8월 시행 개정 게임산업법은 확률 표시 위반에 최대 3배 배상과 입증책임 전환을 붙였습니다. 확률 검증 자동화는 방어 증거를 쌓는 장치입니다.</p></div>
<div class="card"><span class="n">2</span><h3>병목은 총량이 아니라 "쪼갤 수 있는 처리량"</h3><p>배포 1회에는 콘텐츠 양과 무관한 고정비가 붙습니다. 지금 구조에서는 쪼갤수록 손해라서 분기 대형 투입은 합리적 대응입니다. AX의 목표는 총량 증가가 아니라 배포 1회당 고정비 인하입니다.</p></div>
<div class="card"><span class="n">3</span><h3>AI는 파이프라인 안쪽에만. 컨설턴트는 12개월에 나간다</h3><p>게임 안에 AI를 노출하지 않고 핵심 캐릭터 원화는 사람이 유지합니다. 의존 종료는 날짜가 아니라 조건 3개(운영 담당 지명·소유권 이관·회사가 지표를 스스로 측정)로 정의합니다.</p></div>
</div></div></section>

<section class="sec alt"><div class="wrap"><div class="sec-h"><span class="num">02</span><h2>약속하는 지표는 이 4개만</h2><p>기준선을 재기 전에는 목표 수치를 쓰지 않습니다. 방향만 씁니다.</p></div>
<div class="kpi">
<div class="card"><span class="idx">①</span><h3>에셋 1종당 리드타임</h3><p>기획 확정 → 게임 임포트 완료까지 달력 일수. 새 그림과 변형을 분리 측정.</p><div class="dir">↓ 단축 · 기준선 진단 1주차</div></div>
<div class="card"><span class="idx">②</span><h3>업데이트 주기</h3><p>(a) 메이저 간 일수 (b) 월간 배포 횟수. 총량은 보조 지표로 감시.</p><div class="dir">(a) ↓ 단축 + (b) ↑ 증가</div></div>
<div class="card"><span class="idx">③</span><h3>배포 후 회귀 버그 수</h3><p>배포 후 2주 내 핫픽스 대상 건수. 밸런스 기인분과 결제·서버 기인분 분리.</p><div class="dir">↓ 감소 · 기준선 진단 2주차</div></div>
<div class="card"><span class="idx">④</span><h3>CS 1차 응답 시간</h3><p>접수 → 첫 유효 답변까지 중앙값·90분위. 템플릿 비율이 함께 내려가야 의미.</p><div class="dir">↓ 단축 · 기준선 진단 2주차</div></div>
</div></div></section>

<section class="sec"><div class="wrap"><div class="sec-h"><span class="num">03</span><h2>썬더게임즈 산출물</h2><p>제출용 3종(경영진 요약·기획서·첫 미팅 키트)과 컨설턴트 내부 문서 4종. 사실 / (추정) / 미확인 표시를 그대로 유지했습니다.</p></div>
<div class="grid g3">{cards_t}</div>
<p class="note" style="margin-top:22px">제출 전 확인: 지원사업 금액 구간(3~10인 최대 1,000만 원)은 원문 미확인이라 확인되지 않으면 삭제합니다. 제안 조직명 "AX 컨설팅 팀"과 담당자 정보는 치환이 필요합니다.</p></div></section>

<section class="sec alt"><div class="wrap"><div class="sec-h"><span class="num">04</span><h2>신작 「원시인 형님 2」</h2><p>장르는 방치형 RPG를 유지하되 대형 IP 방치형과 정면 경쟁을 피하는 세 축으로 차별화했습니다. Codex가 웹 프로토타입을 자율 구현할 수 있는 스펙까지 내려갔습니다.</p></div>
<figure class="kv"><img src="{img('key-visual', rel)}" alt="원시인 형님 2 키 비주얼 — 빙하기 밤, 불씨를 지키는 부족 캠프" loading="lazy"><figcaption>키 비주얼 (컨셉). 프로덕션 에셋은 자사 원화 기반 스타일 모델로 만든다 — 핵심 캐릭터는 사람, 변형은 AI.</figcaption></figure>
<div class="split"><div>
<blockquote class="quote">8년째 형님들을 키워온 방치형 유저가, 빙하기에 쫓기는 원시 부족의 캠프를 경영하며 형님들을 강화해 사냥터를 밀어 올리고, 세대가 끝날 때마다 남는 「불씨」와 부족 유산이 다음 세대를 반드시 더 멀리 보내기 때문에 계속한다.</blockquote>
<div class="grid g3">
<div class="card"><span class="k">차별화 1</span><h3>부족 캠프 경영 메타</h3><p>대형사 키우기와 다른 동사. "키우는 사람"에서 "부족을 경영하는 사람"으로.</p></div>
<div class="card"><span class="k">차별화 2</span><h3>빙하기 세대 교체</h3><p>프레스티지를 서사로. 불씨 노드는 절대 리셋되지 않는 단조 증가 자산.</p></div>
<div class="card"><span class="k">차별화 3</span><h3>확률형 최소화 + 검증 내장</h3><p>슬롯머신 폐기, 합성은 결정적. 확률은 정수 ppm으로 관리해 표기=구현을 증명.</p></div>
</div>
<div class="grid g2" style="margin-top:18px">{cards_g}</div>
</div>
<div><table class="param"><thead><tr><th>bal_v1 파라미터</th><th>값</th></tr></thead><tbody>
<tr><td>스테이지 HP</td><td><code>HP0=25 · g_hp=1.058 · a_step=0.25 · m_boss=7</code></td></tr>
<tr><td>경제</td><td><code>G0=8 · g_gold=1.052 · C0=25 · g_cost=1.075</code></td></tr>
<tr><td>전투력</td><td><code>ATK0=6 · b=0.12 · g_atk=1.75/25Lv · 형님 6종</code></td></tr>
<tr><td>오프라인</td><td><code>T_cap=8h(패스 12h) · r_off=0.60 · 광고 ×2</code></td></tr>
<tr><td>프레스티지</td><td><code>Q=floor(0.35·s^1.45) · 노드 cost=5+0.7A · M=1.05^A</code></td></tr>
<tr><td>첫 벽</td><td>53.5분, s≈110 (보스 벽) · 목표 대비 −2.7%</td></tr>
<tr><td>D30 도달</td><td>무과금 950 / 소과금 1,110 (격차 1.17배)</td></tr>
</tbody></table>
<p class="note" style="margin-top:14px">아키텍처: TypeScript 모노레포. <code>packages/core</code>(무의존 결정적 룰) → <code>packages/sim</code>(헤드리스 CLI, exit code 2 = 임계 위반) → <code>apps/web</code>(PixiJS). 난수는 xoshiro128** 시드 하나, 수치는 <code>data/balance.json</code> 하나. Unity/C# 포팅은 2차 트랙.</p>
</div></div>
<div class="gallery">
<figure><img src="{img('brothers', rel)}" alt="형님 6종 라인업" loading="lazy"><figcaption><b>형님 6종 라인업</b> 슬롯 순서 = 그리디 타이브레이크 순서. <code>atk0_i = 6·4^i</code></figcaption></figure>
<figure><img src="{img('prestige', rel)}" alt="세대 교체 프레스티지 다이어그램" loading="lazy"><figcaption><b>세대 교체 프레스티지</b> 빙하기마다 리셋, 불씨 노드는 누적. 다음 세대는 ×1.15 더 멀리.</figcaption></figure>
<figure><img src="{img('core-loop', rel)}" alt="코어 루프 다이어그램" loading="lazy"><figcaption><b>코어 루프와 벽</b> 100ms 결정적 틱. 벽은 시뮬레이터가 배포 전에 확인한다.</figcaption></figure>
</div>
</div></section>

<section class="sec demo" id="demo"><div class="wrap"><div class="sec-h"><span class="num">05</span><h2>먼저 만들어 본 데모: Ember Clan</h2><p>기획서를 쓰기 전에, 같은 컨셉의 방치형 게임을 에이전틱 코딩으로 실제로 만들어 봤습니다. 문서가 아니라 돌아가는 게임이 컨설팅의 첫 증거입니다.</p></div>
<div class="demo-grid">
<a class="demo-card" href="{DEMO_URL}" target="_blank" rel="noopener">
<div class="demo-shot"><img src="{img('camp', rel) if (IMAGES/'gen'/'camp.png').exists() else img('key-visual', rel)}" alt="Ember Clan 데모" loading="lazy"><span class="play">▶ 데모 플레이</span></div>
<div class="demo-body"><span class="k">DEMO · PLAYABLE IN BROWSER</span><h3>Ember Clan</h3><p>불씨(Ember)를 지키는 부족(Clan). 원시인 형님 2와 같은 세계관의 방치형 게임을 에이전틱 코딩으로 브라우저 데모까지 만들어 봤습니다. 기획서의 "시뮬레이터-퍼스트"와 "데이터 주도" 원칙이 문서 밖에서도 돌아가는지 확인하는 용도입니다.</p><span class="url">{DEMO_URL}</span></div>
</a>
<div class="demo-side">
<div class="card era"><span class="k">WHY NOW</span><h3>누구나 게임을 만드는 시대</h3><p>GPT-6 Astral 같은 최신 모델과 Codex·Claude Code 같은 에이전틱 코딩 도구 덕분에, 기획 문서를 <em>실행 가능한 스펙</em>으로 쓰면 코딩 에이전트가 프로토타입을 스스로 만들고 테스트까지 돌립니다. 9명 규모 스튜디오에게 이것은 "신작을 검증할 여력"이 처음으로 생긴다는 뜻입니다.</p><ul><li>컨셉 → 플레이어블 데모: 며칠이 아니라 <b>몇 시간</b></li><li>사람이 하는 일은 코딩이 아니라 <b>규칙·수식·수용 기준을 쓰는 것</b></li><li>그래서 이 저장소의 GDD는 산문이 아니라 <b>41개 태스크 카드와 테스트 명령</b>으로 끝납니다</li></ul></div>
<div class="card"><span class="k">FROM DEMO TO PLAN</span><h3>데모에서 배운 것이 빌드 플랜이 됐다</h3><p>데모를 만들며 확인한 세 가지가 빌드 플랜의 원칙이 됐습니다: 난수는 시드 하나에서, 수치는 코드가 아니라 테이블에, 렌더러 없이 콘솔에서 수천 판을 돌릴 수 있어야 한다.</p></div>
</div></div></div></section>

<section class="sec"><div class="wrap"><div class="sec-h"><span class="num">06</span><h2>하네스: 누가, 어떤 순서로</h2><p>팬아웃(시장·진단·GDD 병렬) → 수렴(전략·빌드 플랜) → 생성-검증(기획서 → 검수) → 조립. 팀원 간 이의와 질의가 실제로 결과를 바꿨습니다.</p></div>
<div class="flow">{flow_svg()}</div>
<div class="grid g3" style="margin-top:22px">
<div class="card"><span class="k">실측 1</span><h3>진단가의 이의 → 전략가 수용</h3><p>"CS가 병목 2위이고 난이도 최저인데 아트 단독 1순위는 이상하다" → 1순위 3개 동순위 + 착수 시점 분리로 변경.</p></div>
<div class="card"><span class="k">실측 2</span><h3>디렉터의 질의 4건 → 리더 결정 → 플래너 적용</h3><p>대수 표현(f64+사전계산 테이블), 그리디 타이브레이크, 장비 회복 모드, 60/90일 프로파일.</p></div>
<div class="card"><span class="k">실측 3</span><h3>검수자가 잡은 차단 결함 2건</h3><p>확률 검증표 전설 행 자릿수 오류(그대로면 0.5% 표기가 항상 판정 탈락), 시행수 산식값 10배 오기. 단일 문서 검토로는 못 잡는 경계면 버그.</p></div>
</div>
<h3 style="font-family:var(--serif);margin:40px 0 14px;font-size:22px">에이전트 7</h3><div class="agents">{agents}</div>
<h3 style="font-family:var(--serif);margin:34px 0 14px;font-size:22px">스킬 8</h3><div class="chips">{skills}</div>
</div></section>

<section class="sec alt"><div class="wrap"><div class="sec-h"><span class="num">07</span><h2>Codex로 프로토타입 만들기</h2><p>코딩 에이전트는 모호함에 약하고 테스트로 완료를 증명할 수 있는 작업에 강합니다. 그래서 모든 태스크는 <code>실행 명령 → 기대 결과</code> 수용 기준을 갖습니다.</p></div>
<div class="steps">
<div class="step"><div><b>새 저장소 루트에 AGENTS.md, docs/에 GDD·BALANCE·BUILD_PLAN 배치</b><p>문서가 코드보다 우선. 문서와 코드가 다르면 문서를 고치지 말고 이슈로 남긴 뒤 문서를 따릅니다.</p></div></div>
<div class="step"><div><b>T0.1(스캐폴드)부터 순서대로 Codex에 프롬프트</b><p>빌드 플랜 7.3의 프롬프트 예시 2개(P0.1, P2.x)를 템플릿으로. 태스크 1개 = Codex 1세션.</p></div></div>
<div class="step"><div><b>수용 기준 명령이 통과할 때만 다음 태스크</b><p><code>npm test</code> · <code>npm run sim:regress</code>(목표 벽 표 ±10%) · <code>npm run e2e</code>. 밸런스 파라미터는 코딩 에이전트가 바꾸지 않습니다.</p></div></div>
<div class="step"><div><b>Phase 종료마다 사람 검토</b><p>P2 종료 시 시뮬레이터 리포트로 기획 담당이 목표표를 재검산. 가정은 docs/ASSUMPTIONS.md에 누적.</p></div></div>
</div></div></section>'''
    return page(rel, "game-assistant · 부산 게임사 AX 컨설팅 하네스", body, "홈", "부산 게임사 썬더게임즈를 위한 AX 컨설팅 기획서·세부 자료와 신작 원시인 형님 2 GDD·Codex 빌드 플랜")

def harness_index():
    rel = "../"
    cards = ""
    for name, role, ic in AGENT_META:
        fm, _ = frontmatter(AGENTS/f"{name}.md")
        cards += f'<div class="card"><span class="k">{ic} · {name}</span><h3><a class="stretch" href="{name}.html">{role}</a></h3><p>{html.escape(fm.get("description",""))}</p></div>'
    skills = ""
    for p in sorted(SKILLS.glob("*/SKILL.md")):
        fm,_ = frontmatter(p)
        refs = sorted(x.name for x in (p.parent/"references").glob("*.md")) if (p.parent/"references").exists() else []
        skills += f'<div class="card"><span class="k">SKILL</span><h3><a class="stretch" href="skill-{p.parent.name}.html">{p.parent.name}</a></h3><p>{html.escape(fm.get("description",""))}</p><div class="meta">{"".join(f"<span class=tag>{r}</span>" for r in refs)}</div></div>'
    inner = f'''<div class="doc-head"><div class="wrap"><div class="crumbs"><a href="{rel}index.html">홈</a> / 하네스</div><h1>하네스 구조</h1><p class="sub">에이전트(누가)와 스킬(어떻게)을 분리한 재사용 가능한 컨설팅 팀. <code>.claude/agents/</code> 7개, <code>.claude/skills/</code> 8개. 다른 부산 게임사에도 같은 오케스트레이터로 재실행할 수 있습니다.</p><div class="badges"><span class="badge">팬아웃 → 수렴 → 생성-검증</span><span class="badge">model: opus</span><span class="badge">서브 에이전트 폴백 지원</span></div></div></div>
<div class="wrap" style="padding:44px 20px 80px">
<div class="flow">{flow_svg()}</div>
<h2 style="font-family:var(--serif);margin:44px 0 16px">에이전트 7</h2><div class="grid g3">{cards}</div>
<h2 style="font-family:var(--serif);margin:44px 0 16px">스킬 8</h2><div class="grid g2">{skills}</div>
</div>'''
    return page(rel, "하네스 구조 · game-assistant", inner, "하네스", "에이전트 7개와 스킬 8개로 구성된 AX 컨설팅 하네스")

def harness_doc(title, sub, text, slug, kind):
    rel = "../"
    body, toks = md_to_html(text)
    inner = f'''<div class="doc-head"><div class="wrap"><div class="crumbs"><a href="{rel}index.html">홈</a> / <a href="index.html">하네스</a> / {kind}</div><h1>{html.escape(title)}</h1><p class="sub">{html.escape(sub)}</p></div></div>
<div class="wrap doc-grid"><aside class="toc"><div class="t">CONTENTS</div>{toc_html(toks)}</aside><article class="md">{body}<div class="pn"><a class="prev" href="index.html"><small>← 하네스</small>구조로 돌아가기</a><span></span></div></article></div>'''
    return page(rel, f"{title} · game-assistant", inner, "하네스", sub)

def build():
    if OUT.exists(): shutil.rmtree(OUT)
    (OUT/"assets").mkdir(parents=True)
    for f in (SITE/"assets").iterdir(): shutil.copy(f, OUT/"assets"/f.name)
    (OUT/"images"/"gen").mkdir(parents=True)
    for f in IMAGES.glob("*.svg"): shutil.copy(f, OUT/"images"/f.name)
    for f in (IMAGES/"gen").glob("*.png"): shutil.copy(f, OUT/"images"/"gen"/f.name)
    (OUT/".nojekyll").write_text("")
    (OUT/"index.html").write_text(index(), encoding="utf-8")
    for grp in ("thundergames","gdd"):
        ds = [d for d in DOCS if d[0]==grp]
        (OUT/grp).mkdir(exist_ok=True)
        for i,d in enumerate(ds):
            prev = ds[i-1] if i>0 else None; nxt = ds[i+1] if i<len(ds)-1 else None
            (OUT/grp/f"{d[2]}.html").write_text(doc_page(*d, prev, nxt), encoding="utf-8")
    (OUT/"harness").mkdir(exist_ok=True)
    (OUT/"harness"/"index.html").write_text(harness_index(), encoding="utf-8")
    for name, role, ic in AGENT_META:
        fm, txt = frontmatter(AGENTS/f"{name}.md")
        (OUT/"harness"/f"{name}.html").write_text(harness_doc(f"{role} — {name}", fm.get("description",""), txt, name, "에이전트"), encoding="utf-8")
    for p in sorted(SKILLS.glob("*/SKILL.md")):
        fm, txt = frontmatter(p)
        # append references inline
        refdir = p.parent/"references"
        if refdir.exists():
            for r in sorted(refdir.glob("*.md")):
                txt += f"\n\n---\n\n## 참조 문서: references/{r.name}\n\n" + re.sub(r"^# ", "### ", r.read_text(encoding="utf-8"), flags=re.M).replace("\n## ", "\n### ")
        (OUT/"harness"/f"skill-{p.parent.name}.html").write_text(harness_doc(f"스킬 — {p.parent.name}", fm.get("description",""), txt, p.parent.name, "스킬"), encoding="utf-8")
    n = len(list(OUT.rglob("*.html")))
    print(f"built {n} pages → {OUT}")

if __name__ == "__main__":
    build()
