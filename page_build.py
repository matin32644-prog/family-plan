# -*- coding: utf-8 -*-
"""가족 적립 «지금 할 일» 페이지 그리기. 상태(state.json)만 읽어 index.html·mom.html·sib.html을 쓴다.
단계: ① QQQ 모으는 중 → ② QLD로 바꾸는 날 → ③ QLD 모으는 중 (setup_done이면 진행 표시 없음)
hold(전환 전 보류)면 ①에 머물고 경보 날 더 사는 몫도 QQQ로 쓴다.
실행은 family_cloud.py가 부른다(깃허브 액션)."""
import datetime as dt
import html
import io
import json
import os
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://matin32644-prog.github.io/family-plan/"
STATE = os.path.join(HERE, "state.json")
ET = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
E = html.escape
WD = "월화수목금토일"
PEOPLE = [("mom", "엄마", 2, 3), ("sib", "동생네", 3, 4.5)]


def man(x):
    return ("%g" % x) + "만원"


def tier_of(mv, dd):
    if dd > -7.5 or mv >= 20:
        return 0
    return 2 if mv < 10 else 1


def is_session(d):
    import holidays
    return d.weekday() < 5 and d not in holidays.financial_holidays("NYSE", years=d.year)


def next_session(day):
    d = day
    for _ in range(12):
        d = d + dt.timedelta(days=1)
        if is_session(d):
            return d
    return d


def md(d):
    return "%d/%d(%s)" % (d.month, d.day, WD[d.weekday()])


def open_kst(d):
    t = dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET).astimezone(KST)
    return "%s 밤 %d시%s" % (md(t.date()), t.hour - 12, " 30분" if t.minute else "")


def status(st):
    mv = float(st["last_mmtw"]); dd = float(st["last_dd"])
    qday = dt.date.fromisoformat(st["last_qqq_day"])
    t = tier_of(mv, dd)
    sw, on = bool(st.get("switched")), st.get("switched_on")
    # hold: QLD를 아직 못 사는 동안(증권사 교육·예탁금) 바꾸는 날을 미루고 경보 날 몫도 QQQ로
    hold = bool(st.get("hold")) and not sw
    if hold:
        stage = 1
    elif sw and on == st["last_qqq_day"]:
        stage = 2
    elif not sw and (t >= 1 or st.get("switch_pending")):
        stage = 2
    elif sw:
        stage = 3
    else:
        stage = 1
    # setup_done: 두 집 갈아타기·자동적립 바꾸기가 끝났다는 표시 → 진행 표시·바꾸기 전 안내를 지운다
    done = sw and bool(st.get("setup_done"))
    if done:
        stage = 3
    act = next_session(qday)
    missed = None
    if stage == 3 and on and not done:
        od = dt.date.fromisoformat(on)
        if (qday - od).days <= 7:
            missed = next_session(od)
    return dict(mv=mv, dd=dd, tier=t, stage=stage, qday=qday, act=act, open=open_kst(act),
                fallen=(100 - mv) / 10, missed=missed, on=on, done=done, hold=hold,
                extra="QQQ" if hold else "QLD",
                mday=st.get("last_mmtw_day"), check=st.get("last_check", ""))


CSS = """
:root{--bg:#f7f6f3;--card:#ffffff;--ink:#1c1a17;--mute:#6e6860;--faint:#9a948b;--line:#e3e0da;
--grey:#ebe9e4;--new:#105c62;--newbg:#e2f0f1;--hot:#b0622a;--hotbg:#fdf0de;--hot2:#b4443a;--hot2bg:#fae8e6;
--good:#1e6e46;--warnbg:#fff4c2;--warn:#7a5a00}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171614;--card:#211f1c;--ink:#f0ede8;
--mute:#b3ada4;--faint:#857f77;--line:#34312d;--grey:#2b2926;--new:#7cc7cc;--newbg:#16302f;--hot:#e8a46e;
--hotbg:#3a2a1b;--hot2:#ef8b80;--hot2bg:#3a1f1c;--good:#7fd1a2;--warnbg:#3d3410;--warn:#f0d56a}}
:root[data-theme="dark"]{--bg:#171614;--card:#211f1c;--ink:#f0ede8;--mute:#b3ada4;--faint:#857f77;--line:#34312d;
--grey:#2b2926;--new:#7cc7cc;--newbg:#16302f;--hot:#e8a46e;--hotbg:#3a2a1b;--hot2:#ef8b80;--hot2bg:#3a1f1c;
--good:#7fd1a2;--warnbg:#3d3410;--warn:#f0d56a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif;word-break:keep-all}
main{max-width:640px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:26px;margin:4px 0 2px;line-height:1.3}
h2{font-size:19px;margin:30px 0 10px}
.sub{color:var(--mute);font-size:14px;margin:0}
.band{display:none;background:var(--warnbg);color:var(--warn);border-radius:12px;padding:10px 14px;margin:14px 0;font-size:15px}
.steps{display:flex;gap:6px;margin:18px 0 6px}
.st{flex:1;text-align:center;font-size:13px;color:var(--faint);border-top:5px solid var(--line);padding-top:6px}
.st b{display:block;font-size:15px}
.st.on{color:var(--new);border-color:var(--new)}
.st.done{color:var(--mute);border-color:var(--mute)}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;margin:14px 0}
.act{border:3px solid var(--new);background:var(--newbg)}
.act.t1{border-color:var(--hot);background:var(--hotbg)}
.act.t2{border-color:var(--hot2);background:var(--hot2bg)}
.lab{font-size:15px;color:var(--mute);margin:0 0 4px}
.big{font-size:30px;font-weight:800;line-height:1.25;margin:0}
.act .big{color:var(--new)}
.act.t1 .big{color:var(--hot)}
.act.t2 .big{color:var(--hot2)}
.when{font-size:16px;margin:8px 0 0}
ol.do{margin:12px 0 0;padding-left:0;list-style:none;counter-reset:n}
ol.do li{counter-increment:n;position:relative;padding:6px 0 6px 40px;font-size:18px}
ol.do li::before{content:counter(n);position:absolute;left:0;top:6px;width:28px;height:28px;border-radius:50%;
background:var(--new);color:var(--bg);font-weight:800;text-align:center;line-height:28px;font-size:16px}
ol.do li small{display:block;color:var(--mute);font-size:14px}
.note{font-size:14px;color:var(--mute);margin:10px 0 0}
.gauge{margin:6px 0 18px}
.gt{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.gt b{font-size:22px}
.bar{position:relative;height:16px;background:var(--grey);border-radius:8px;margin:8px 0 4px}
.fill{position:absolute;left:0;top:0;bottom:0;border-radius:8px;background:var(--mute)}
.fill.hot{background:var(--hot2)}
.mark{position:absolute;top:-5px;bottom:-5px;width:3px;background:var(--ink);border-radius:2px}
.ml{position:absolute;top:22px;font-size:12px;color:var(--mute);transform:translateX(-50%);white-space:nowrap}
.gs{font-size:14px;color:var(--mute);margin-top:22px}
.gs.yes{color:var(--hot2);font-weight:700}
.grid{display:grid;grid-template-columns:76px 1fr 1fr;gap:6px;font-size:14px}
.gh{color:var(--mute);text-align:center;font-size:13px;padding:2px}
.rh{color:var(--ink);font-weight:700;font-size:14px;align-self:center}
.rh small{display:block;color:var(--mute);font-weight:400;font-size:12px}
.cell{background:var(--grey);border-radius:12px;padding:10px 6px;text-align:center;min-height:74px;border:3px solid transparent}
.cell b{display:block;font-size:15px}
.cell.c1{background:var(--hotbg);color:var(--hot)}
.cell.c2{background:var(--hot2bg);color:var(--hot2)}
.cell.now{border-color:var(--ink)}
.chip{display:table;margin:6px auto 0;font-size:11px;background:var(--ink);color:var(--bg);border-radius:8px;padding:1px 7px}
.act.t0{border-color:var(--ink);background:var(--card)}
.act.t0 .big{color:var(--ink)}
.ml.l1{transform:none;right:20%;padding-right:6px}
.ml.l2{transform:none;right:0}
details{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin:10px 0}
summary{font-weight:700;cursor:pointer}
details ul{padding-left:18px;margin:10px 0 2px}
details li{margin:4px 0;font-size:15px}
.foot{font-size:12px;color:var(--faint);margin-top:28px;line-height:1.6}
a.pick{display:block;background:var(--card);border:2px solid var(--line);border-radius:18px;padding:22px;margin:14px 0;
text-decoration:none;color:var(--ink);font-size:24px;font-weight:800}
a.pick small{display:block;font-size:15px;color:var(--mute);font-weight:400;margin-top:4px}
"""

JS = """<script>
(function(){try{var b=document.body.getAttribute('data-built');var h=(Date.now()-Date.parse(b))/36e5;
if(h>80){var e=document.getElementById('stale');e.style.display='block';
e.textContent='이 페이지가 '+Math.floor(h/24)+'일째 안 바뀌었어요. 집 컴퓨터가 꺼졌을 수 있으니 알려주세요.';}}catch(x){}})();
</script>"""


def head(title):
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex">'
            '<meta name="googlebot" content="noindex,nofollow,noarchive,nosnippet,noimageindex">'
            '<meta name="referrer" content="no-referrer">'
            '<title>%s</title><style>%s</style></head>' % (E(title), CSS))


def today_buy(S, u1, u2):
    base = "QLD" if S["stage"] >= 2 else "QQQ"
    t = S["tier"]
    if t == 0:
        return base + " 1만원", None
    add = u1 if t == 1 else u2
    return "%s 1만원 + %s %s" % (base, S["extra"], man(add)), "그날 합계 " + man(1 + add)


def stepper(S):
    """진행 표시. «1단계 경보»와 헷갈리지 않게 «단계» 대신 ①②③. 끝났으면(done) 통째로 없앤다."""
    if S["done"]:
        return ""
    out = []
    for k, (a, b) in enumerate([("①", "QQQ 모으는 중"), ("②", "QLD로 바꾸는 날"), ("③", "QLD 모으는 중")], 1):
        c = "on" if k == S["stage"] else ("done" if k < S["stage"] else "")
        out.append('<div class="st %s"><b>%s</b>%s</div>' % (c, a, b))
    return '<div class="steps">' + "".join(out) + "</div>"


def action(S, u1, u2):
    buy, tot = today_buy(S, u1, u2)
    tcls = " t%d" % S["tier"] if S["stage"] != 2 else ""
    when = '<p class="when">%s 미국장이 열리면</p>' % E(S["open"])
    if S["stage"] == 2:
        return ('<section class="card act"><p class="lab">지금 할 일</p>'
                '<p class="big">오늘이 QLD로 바꾸는 날</p>' + when +
                '<ol class="do">'
                '<li>모아둔 <b>QQQ를 전부 판다</b><small>손해 보고 파는 것 같아도 줄어든 돈은 팔든 안 팔든 같아요</small></li>'
                '<li>판 달러 그대로 <b>같은 날 QLD를 산다</b><small>원화로 바꿨다가 다시 사면 환전 수수료가 두 번 나가요</small></li>'
                '<li>매일 사던 1만원을 <b>QLD로 바꾼다</b><small>자동으로 사고 있다면 종목만 QQQ에서 QLD로 바꾸면 돼요</small></li>'
                '<li>오늘 몫: <b>%s</b>%s</li></ol>'
                '<p class="note">한 번 바꾸면 경보가 꺼져도 QQQ로 되돌리지 않아요.</p></section>'
                % (E(buy), "<small>%s</small>" % E(tot) if tot else ""))
    if S["tier"] == 0:
        lab, extra = "매일 하던 대로", '<p class="note">자동으로 사고 있다면 따로 할 일은 없어요.</p>'
    else:
        lab = "경보 날: 평소보다 더 사요" + (" (2단계)" if S["tier"] == 2 else " (1단계)")
        extra = '<p class="note">%s · 경보가 켜진 날만 더 사요. 다음 날 꺼지면 다시 1만원만.</p>' % E(tot)
    s = ('<section class="card act%s"><p class="lab">%s</p><p class="big">%s</p>%s%s'
         % (tcls, E(lab), E(buy), when, extra))
    if S["hold"]:
        s += ('<p class="note"><b>QLD는 아직 살 수 없어서 미뤄 두었어요.</b> 증권사 교육과 예탁금 조건이 갖춰질 때까지 '
              '매일 몫도 경보 날 더 사는 몫도 QQQ로 사요. 준비가 끝나면 이 칸이 초록색 «바꾸는 날» 안내로 바뀌어요.</p>')
    elif S["stage"] == 1:
        s += '<p class="note">QLD로 바꾸는 날이 오면 이 칸이 초록색 «바꾸는 날» 안내로 바뀌어요.</p>'
    if S["missed"]:
        s += ('<p class="note"><b>혹시 아직 QQQ가 남아 있다면</b> %s에 바꿨어야 해요. '
              '다음 미국장에서 QQQ를 전부 팔고 판 달러로 QLD를 사세요.</p>' % E(md(S["missed"])))
    return s + "</section>"


def gauges(S):
    f = max(0.0, min(10.0, S["fallen"]))
    if S["tier"] == 0 and S["mv"] >= 20:
        left = 8 - S["fallen"]
        g1 = "1단계 경보선(8개)까지 %s" % ("거의 닿았어요" if left < 0.15 else "%.1f개 남음" % left)
        c1 = ""
    else:
        g1 = "%d단계 경보선을 넘었어요" % (2 if S["mv"] < 10 else 1)
        c1 = " yes"
    dd = S["dd"]
    w2 = max(0.0, min(30.0, -dd)) / 30 * 100
    if dd <= -7.5:
        g2, c2 = "기준(7.5%)보다 더 빠졌어요", " yes"
    else:
        g2, c2 = "기준까지 %.1f%%p 더 빠져야 해요" % (dd + 7.5), ""
    if S["done"]:
        g2 += " · QQQ는 이제 사지 않고 경보 기준으로만 봐요"
    both = ("두 가지가 같이 맞아서 오늘은 경보 날이에요." if S["tier"]
            else "두 가지가 같이 맞는 날만 경보 날이에요.")
    return ('<h2>지금 시장은</h2><section class="card">'
            '<div class="gauge"><div class="gt"><span>미국 주식 10개 중 무너진 수</span><b>약 %.1f개</b></div>'
            '<div class="bar"><div class="fill%s" style="width:%.1f%%"></div>'
            '<div class="mark" style="left:80%%"></div><div class="ml l1">8개 · 1단계</div>'
            '<div class="mark" style="left:90%%"></div><div class="ml l2">9개 · 2단계</div></div>'
            '<div class="gs%s">%s</div></div>'
            '<div class="gauge"><div class="gt"><span>QQQ가 최고점(최근 3년)에서 빠진 폭</span><b>%.1f%%</b></div>'
            '<div class="bar"><div class="fill%s" style="width:%.1f%%"></div>'
            '<div class="mark" style="left:25%%"></div><div class="ml" style="left:25%%">7.5%%</div></div>'
            '<div class="gs%s">%s</div></div>'
            '<p class="note" style="margin-top:4px">%s «무너졌다» = 그 주식이 최근 한 달 평균값 아래로 내려갔다는 뜻. '
            '평소엔 10개 중 5개쯤이 무너져 있어요.</p></section>'
            % (S["fallen"], " hot" if c1 else "", f * 10, c1, E(g1),
               dd, " hot" if c2 else "", w2, c2, E(g2), E(both)))


def grid(S, u1, u2):
    base = "QLD" if S["stage"] >= 2 else "QQQ"
    col = 1 if S["dd"] <= -7.5 else 0
    row = 0 if S["mv"] >= 20 else (2 if S["mv"] < 10 else 1)
    rows = [("경보 없음", "5개쯤 무너짐"), ("1단계 경보", "8개 넘게"), ("2단계 경보", "9개 넘게")]
    out = ['<div class="grid"><div></div><div class="gh">QQQ 7.5%보다 덜 빠짐</div><div class="gh">QQQ 7.5% 넘게 빠짐</div>']
    for r, (a, b) in enumerate(rows):
        out.append('<div class="rh">%s<small>%s</small></div>' % (a, b))
        for c in range(2):
            now = r == row and c == col
            chip = '<span class="chip">지금 여기</span>' if now else ""
            if r == 0 or c == 0:
                out.append('<div class="cell%s"><b>%s 1만원만</b>%s</div>' % (" now" if now else "", base, chip))
            else:
                add = u1 if r == 1 else u2
                out.append('<div class="cell c%d%s"><b>%s 1만원</b>+ %s %s<br>합계 %s%s</div>'
                           % (r, " now" if now else "", base, S["extra"], man(add), man(1 + add), chip))
    out.append("</div>")
    if S["done"]:
        lab, nt = "QLD", "경보가 켜진 날만 더 사요. 다음 날 경보가 꺼지면 다시 QLD 1만원만."
    elif S["hold"]:
        lab, nt = "지금(QLD 준비 중)", ("QLD를 살 수 있게 될 때까지는 경보 날 더 사는 몫도 QQQ예요. "
                                   "준비가 끝나면 표의 QQQ가 QLD로 바뀌어요. 더 사는 금액은 그대로예요.")
    elif S["stage"] >= 2:
        lab, nt = "QLD로 바꾼 뒤", "경보 날 더 사는 금액은 바꾸기 전과 같아요. 매일 1만원만 QQQ에서 QLD로 바뀌었어요."
    else:
        lab, nt = "지금(바꾸기 전)", "QLD로 바꾼 뒤에는 표의 QQQ 1만원이 QLD 1만원이 돼요. 경보 날 더 사는 금액은 그대로예요."
    return ('<h2>매일 사는 법 · %s</h2><section class="card">%s<p class="note">%s</p></section>'
            % (lab, "".join(out), nt))


def facts(done=False):
    risk = ('<details><summary>대신 이건 각오해야 해요</summary><ul>'
            '<li>QLD는 QQQ보다 보통 2배쯤 더 출렁여요. 1년 안에 더 빠지는 폭도 보통 2배쯤이에요.</li>'
            '<li>2008년 같은 해가 오면 1억이 1년 뒤 3,200만까지 줄었어요.</li>'
            '<li>보통의 10년에도 계좌가 최고점에서 한 번은 반토막 가까이(-51%) 빠졌어요.</li>'
            '<li>그래도 경보 날 더 사고 매일 1만원을 이어가는 게 규칙이에요.</li></ul></details>')
    if done:
        return risk
    return ('<details><summary>왜 모아둔 QQQ까지 QLD로 바꾸나</summary><ul>'
            '<li>바꾸는 날 조건이 처음 맞은 날 갈아탄 경우 36번을 전부 계산했어요 (2006년부터).</li>'
            '<li>1억이면 1년 뒤 보통 <b>1억 4,400만</b> (그대로 QQQ였으면 1억 2,500만)</li>'
            '<li>갈아탄 쪽이 더 많았던 비율: 1년 뒤 <b>80%</b> · 3년 뒤 <b>85%</b> · 5년 뒤 <b>92%</b></li>'
            '<li>해외주식 손실은 같은 해 이익하고만 계산돼서, 올해 다른 이익이 없으면 세금 손해도 득도 거의 없어요.</li></ul></details>'
            '<details><summary>대신 이건 각오해야 해요</summary><ul>'
            '<li>바꾼 뒤 1년 안에 더 빠지는 폭이 보통 QQQ의 2배쯤 (-15.6% vs -7.2%)</li>'
            '<li>2008년 같은 해가 오면 1억이 1년 뒤 3,200만까지 줄었어요 (QQQ였으면 6,200만)</li>'
            '<li>보통의 10년에도 계좌가 최고점에서 한 번은 반토막 가까이(-51%) 빠졌어요.</li>'
            '<li>1년이 지난 35번 중 진 7번은 전부 긴 하락장 한가운데였어요 (2007~2008년, 2022년).</li></ul></details>')


def foot(S, unit):
    return ('<p class="foot">기준: %s 미국장 마감 값 · 갱신 %s (월~토 아침 10시쯤 바뀜)<br>'
            '시장 경보 = MMTW 지표(미국 주식 중 20일 평균 위 비율) 20 미만 / 10 미만 · 경보 날 더 사는 금액 %s · 1단위 = 1만원<br>'
            '숫자는 2006~2026년 실제 가격으로 계산, 세금·환율 빼고. 앞으로도 같다는 보장은 없어요.</p>'
            % (E(md(S["qday"])), E(fmt_check(S["check"])), unit))


def fmt_check(s):
    try:
        t = dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
        return "%s %s" % (md(t.date()), t.strftime("%H:%M"))
    except Exception:
        return s


def page(S, key, who, u1, u2, built):
    unit = "%g / %g단위" % (u1, u2)
    body = ('<body data-built="%s"><main><h1>%s 적립 · 지금 할 일</h1>'
            '<p class="sub">%s 미국장 마감 기준</p><div class="band" id="stale"></div>%s%s%s%s%s%s</main>%s</body></html>'
            % (built, E(who), E(md(S["qday"])), stepper(S), action(S, u1, u2), gauges(S), grid(S, u1, u2),
               facts(S["done"]), foot(S, unit), JS))
    return head("%s 적립" % who) + body


def index(S, built):
    lab = {1: " · 지금 ① QQQ 모으는 중", 2: " · 지금 ② 오늘이 QLD로 바꾸는 날", 3: " · 지금 ③ QLD 모으는 중"}[S["stage"]]
    if S["done"]:
        lab = ""
    elif S["hold"]:
        lab += " (QLD는 준비 중)"
    body = ('<body data-built="%s"><main><h1>우리 집 적립 · 지금 할 일</h1><p class="sub">%s 미국장 마감 기준%s</p>'
            '<div class="band" id="stale"></div>'
            '<a class="pick" href="mom.html">엄마<small>매일 1만원 · 경보 날 +2만 / +3만</small></a>'
            '<a class="pick" href="sib.html">동생네<small>매일 1만원 · 경보 날 +3만 / +4.5만</small></a>'
            '</main>%s</body></html>' % (built, E(md(S["qday"])), E(lab), JS))
    return head("우리 집 적립") + body


def check(doc):
    assert "\u2014" not in doc and "\u2013" not in doc, "줄표"
    assert doc.count("<title>") == 1 and "noindex" in doc
    plain = doc.replace("MMTW 지표(미국 주식 중 20일 평균 위 비율)", "")
    assert plain.count("MMTW") == 0


def build(st=None, out=HERE, now=None):
    if st is None:
        st = json.load(io.open(STATE, encoding="utf-8"))
    S = status(st)
    built = (now or dt.datetime.now(KST)).astimezone(KST).isoformat(timespec="seconds")
    os.makedirs(out, exist_ok=True)
    docs = {"index.html": index(S, built)}
    for key, who, u1, u2 in PEOPLE:
        docs[key + ".html"] = page(S, key, who, u1, u2, built)
    for name, doc in docs.items():
        check(doc)
        if S["done"]:
            for w in ("QQQ 모으는 중", "바꾸는 날", 'class="steps"', "혹시 아직", "바꾸기 전"):
                assert w not in doc, "끝난 뒤인데 남음: " + w
        if S["hold"]:
            for w in ("+ QLD", "오늘이 QLD로 바꾸는 날"):
                assert w not in doc, "보류 중인데 남음: " + w
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(doc)
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("Personal project.\n")
    open(os.path.join(out, ".nojekyll"), "w").close()
    print("[page_build] 조립: 단계 %d · 경보 %d · MMTW %.2f · 낙폭 %.2f%% · 다음 장 %s"
          % (S["stage"], S["tier"], S["mv"], S["dd"], S["open"]))
    return S


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
