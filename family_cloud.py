# -*- coding: utf-8 -*-
"""가족 적립 감시 (깃허브 액션에서 실행).

    python family_cloud.py --check     # 아침: 시장 값 → 상태 → 바꾸는 날 알림·«끝났나요?» 묻기 → 페이지
    python family_cloud.py --remind    # 밤: 바꾸는 날 미국장 개장 전 한 번 더 알림
    python family_cloud.py --probe     # 시장 값만 받아서 출력(시험)
    python family_cloud.py --done | --undo   # 두 집 다 끝났다는 표시(로컬에서 쓰고 푸시)

비밀값(저장소 Settings > Secrets > Actions): TG_TOKEN, TG_CHAT. 없으면 메시지를 출력만 한다.
바꾸는 날 = 시장 경보 값 20 미만 이면서 QQQ가 최근 3년(756거래일) 최고가보다 7.5% 넘게 빠진 날이 처음 오는 날.
"""
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import page_build as PB  # noqa: E402

STATE = os.path.join(HERE, "state.json")
URL = "https://matin32644-prog.github.io/family-plan/"
KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")
MMTW_T, DD_GATE, ATH_WIN = 20.0, -7.5, 756


def now_kst():
    return dt.datetime.now(KST)


# ── 시장 값 ────────────────────────────────────────────────
def get_mmtw():
    """트레이딩뷰 INDEX:MMTW 일봉 마지막 종가 (값, 'YYYY-MM-DD'). 2번 시도."""
    from tvDatafeed import TvDatafeed, Interval
    err = None
    for _ in range(3):
        try:
            h = TvDatafeed().get_hist(symbol="MMTW", exchange="INDEX", interval=Interval.in_daily, n_bars=30)
            if h is not None and len(h) > 5:
                return float(h["close"].iloc[-1]), h.index[-1].strftime("%Y-%m-%d")
            err = "빈 응답"
        except Exception as e:
            err = repr(e)[:160]
        time.sleep(5)
    raise RuntimeError("MMTW 조회 실패: %s" % err)


def get_qqq():
    """야후 QQQ 배당 반영 종가 5년 → (최근 3년 최고가 대비 %, 종가, 날짜)."""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/QQQ?range=5y&interval=1d&events=div"
    err = None
    for k in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            ts = res["timestamp"]
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            raw = res["indicators"]["quote"][0]["close"]
            rows = [(t, a, c) for t, a, c in zip(ts, adj, raw) if a is not None and c is not None]
            if len(rows) < ATH_WIN:
                raise RuntimeError("봉 부족 %d" % len(rows))
            a = [x[1] for x in rows]
            last = a[-1]
            ath = max(a[-ATH_WIN:])
            day = dt.datetime.fromtimestamp(rows[-1][0], ET).strftime("%Y-%m-%d")
            return (last / ath - 1) * 100, float(rows[-1][2]), day
        except Exception as e:
            err = repr(e)[:160]
            time.sleep(5 * (k + 1))
    raise RuntimeError("QQQ 조회 실패: %s" % err)


# ── 상태 ────────────────────────────────────────────────
def load():
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


def save(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


# ── 텔레그램 ────────────────────────────────────────────────
def send(msg):
    tok, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not tok or not chat:
        print("=== 비밀값 없음: 출력만 ===\n" + msg)
        return True
    for k in range(3):
        try:
            r = requests.post("https://api.telegram.org/bot%s/sendMessage" % tok, timeout=20,
                              json={"chat_id": chat, "text": msg, "parse_mode": "HTML",
                                    "disable_web_page_preview": True})
            if r.ok:
                return True
            print("[발송 실패]", r.status_code, r.text[:200])
        except Exception as e:
            print("[발송 오류]", repr(e)[:200])
        time.sleep(3)
    return False


def fired(mv, dd):
    return mv < MMTW_T and dd <= DD_GATE


def session_txt(qday):
    d = PB.next_session(dt.date.fromisoformat(qday))
    return PB.open_kst(d), d


def switch_msg(mv, mday, dd, qday, px):
    when, _ = session_txt(qday)
    return ("🔀 <b>엄마·동생네 QLD 전환 신호</b>\n\n"
            "<b>%s 미국장, 두 집 모두</b>\n"
            "1. 모아둔 <b>QQQ 전부 매도</b>\n"
            "2. 판 달러 그대로 <b>같은 날 QLD 매수</b> (원화로 바꿨다 다시 사면 환전 수수료가 두 번)\n"
            "3. 매일 1만원 자동적립 종목을 <b>QQQ → QLD</b>로\n\n"
            "경보 날 더 사는 금액은 그대로: 엄마 <b>QLD 2/3단위</b> · 동생네 <b>QLD 3/4.5단위</b>\n\n"
            "MMTW <b>%.1f</b> (%s) · QQQ 낙폭 <b>%.2f%%</b> (%s 종가 $%.2f)\n"
            "기준: MMTW&lt;20 이면서 최근 3년 최고가 대비 -7.5%% 이하\n\n"
            "<i>한 번 바꾸면 신호가 꺼져도 되돌리지 않습니다. "
            "2006~ 신호 첫날 36번: 갈아타기 1년 뒤 80%% 이김(1억 → 1.44억 vs 그대로 1.25억), "
            "1년 안 추가 하락 가운데 -15.6%% vs -7.2%%. 전환 뒤 10년 창 최대 하락 엄마 -51.1%% · 동생네 -51.0%%</i>\n\n"
            "가족 페이지: %s\n"
            "개장 전에 한 번 더 알려드립니다. 두 집 다 끝나면 클로드에게 «가족 전환 끝»이라고 보내주세요."
            % (when, mv, mday, dd, qday, px, URL))


def ask_msg(s):
    n = int(s.get("setup_asked_n", 0)) + 1
    return ("❓ <b>엄마·동생네 QLD 전환 끝났나요?</b>%s\n\n"
            "%s 기준으로 바꾸는 날이었어요. 두 집 다 아래 두 가지가 끝났는지 확인해 주세요.\n"
            "1. 모아둔 QQQ 전부 매도 → 판 달러로 QLD 매수\n"
            "2. 매일 1만원 자동적립 종목을 QQQ → QLD로 변경\n\n"
            "끝났으면 클로드에게 <b>«가족 전환 끝»</b>이라고 보내주세요. 가족 페이지에서 첫 단계를 지웁니다.\n"
            "<i>답이 올 때까지 평일 아침마다 한 번씩 물어봅니다.</i>"
            % ((" (%d번째)" % n) if n > 1 else "", s.get("switched_on")))


def remind_msg(s):
    return ("⏰ <b>개장 전: 엄마·동생네 QLD로 바꾸는 날</b>\n\n"
            "1. 두 집 모아둔 <b>QQQ 전부 매도</b>\n"
            "2. 판 달러 그대로 <b>QLD 매수</b>\n"
            "3. 매일 1만원 자동적립 종목 QQQ → QLD\n\n"
            "가족 페이지: %s" % URL)


# ── 실행 ────────────────────────────────────────────────
def check():
    s = load()
    mv, mday = get_mmtw()
    dd, px, qday = get_qqq()
    nk = now_kst()
    s.update(last_check=nk.strftime("%Y-%m-%d %H:%M"), last_mmtw=round(mv, 2), last_mmtw_day=mday,
             last_dd=round(dd, 2), last_qqq_day=qday)
    print("[check] MMTW %.2f(%s) · QQQ %.2f%% $%.2f(%s) · 전환 %s" % (mv, mday, dd, px, qday, s.get("switched")))
    rc = 0
    if not s.get("switched"):
        # 발송이 실패한 날이 있으면(switch_pending) 다음 날 조건이 풀려도 다시 보낸다
        if fired(mv, dd) or s.get("switch_pending"):
            if send(switch_msg(mv, mday, dd, qday, px)):
                _, d = session_txt(qday)
                s.update(switched=True, switched_on=qday, households=["엄마", "동생네"],
                         remind_session=d.isoformat(), reminded=False)
                s.pop("switch_pending", None)
                print("[check] 전환 알림 발송 · 기록")
            else:
                s.setdefault("switch_pending", qday)
                print("[check] 전환 알림 발송 실패: 기록 보류, 다음 실행에 재시도")
                rc = 1
    elif (not s.get("setup_done") and s.get("switched_on") != qday and nk.weekday() < 5
          and s.get("setup_asked_day") != nk.strftime("%Y-%m-%d")):
        if send(ask_msg(s)):
            s["setup_asked_day"] = nk.strftime("%Y-%m-%d")
            s["setup_asked_n"] = int(s.get("setup_asked_n", 0)) + 1
            print("[check] 끝났나요 묻기 발송")
        else:
            rc = 1
    save(s)
    PB.build(s, HERE)
    return rc


def remind():
    s = load()
    if not s.get("switched") or s.get("reminded") or not s.get("remind_session"):
        print("[remind] 할 일 없음")
        return 0
    now = dt.datetime.now(ET)
    if now.date().isoformat() != s["remind_session"]:
        print("[remind] 오늘(%s)은 바꾸는 날(%s)이 아님" % (now.date(), s["remind_session"]))
        return 0
    opn = now.replace(hour=9, minute=30, second=0, microsecond=0)
    mins = (opn - now).total_seconds() / 60
    if not (0 <= mins <= 100):
        print("[remind] 개장까지 %.0f분: 창(0~100분) 밖" % mins)
        return 0
    if send(remind_msg(s)):
        s["reminded"] = True
        save(s)
        print("[remind] 발송 (개장까지 %.0f분)" % mins)
        return 0
    return 1


def mark(done):
    s = load()
    if done:
        if not s.get("switched"):
            print("아직 전환 전이라 거부")
            return 1
        s["setup_done"] = True
        s["setup_done_on"] = now_kst().strftime("%Y-%m-%d %H:%M")
    else:
        s.pop("setup_done", None)
        s.pop("setup_done_on", None)
    save(s)
    PB.build(s, HERE)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if a == "--probe":
        print("MMTW", get_mmtw())
        print("QQQ", get_qqq())
        sys.exit(0)
    if a == "--remind":
        sys.exit(remind())
    if a == "--tgtest":
        sys.exit(0 if send("🧪 <b>[시험]</b> 가족 감시가 깃허브 서버에서 텔레그램으로 보냈습니다. 실제 알림 아님.") else 1)
    if a in ("--done", "--undo"):
        sys.exit(mark(a == "--done"))
    sys.exit(check())
