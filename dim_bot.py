r"""쿠키런: 크럼블 차원의 이면 투력컷 디스코드 봇.

실행:   python -I dim_bot.py             (토큰: token.txt 또는 환경변수 DISCORD_TOKEN)
        pythonw -I dim_bot.py            (창 없이. 출력은 dimbot.log)
검사:   python -I dim_bot.py --selftest  (디스코드 연결 없이 데이터/포맷 확인)
기타:   --stop (실행 중인 봇 끄기), --autostart on|off (윈도우 로그인 시 자동 실행)

명령어:
  32  또는  30-35          (숫자만 있는 메시지에 바로 반응. channels.txt 로 채널 제한 가능)
  /투력컷 층:32        !투력컷 32      !컷 32
  /투력컷 층:30-35     !투력컷 30-35   !컷 30-35     (범위는 한 번에 최대 20층)

데이터: dim_stages.json (build_data.py 가 클라 데이터에서 생성).
"""
import json
import math
import os
import re
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "dim_stages.json")
TOKEN_PATH = os.path.join(HERE, "token.txt")
CHANNELS_PATH = os.path.join(HERE, "channels.txt")   # 숫자만 친 메시지에 반응할 채널 (비우면 전부)
LOG_PATH = os.path.join(HERE, "dimbot.log")          # 창 없이(pythonw) 돌릴 때 출력
LOCK_PORT = 57931                                     # 중복 실행 방지용 (두 개 켜면 답이 두 번 옴)
_LOCK = None
MAX_RANGE = 20
CP_COLUMNS = (20, 40, 60, 80, 100)      # 커뮤니티 표의 열 = 추천 전투력의 N%
EMBED_CP_ROWS = (120, 100, 80, 60, 40, 20)
EMBED_COLOR = 0x7B5CFF
USAGE = "층 번호를 숫자로 줘. 예: `!컷 32`, `!컷 30-35`, `/투력컷 층:32`"


# ───────────────────────── 데이터 ─────────────────────────
class DimData:
    def __init__(self, path=DATA_PATH):
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        self.meta = d["meta"]
        self.groups = sorted(d["groups"], key=lambda g: g["index"])
        self.seasons = sorted(d["seasons"], key=lambda s: s["start_ms"])
        self.stages = d["stages"]
        self.by_group_floor = {(s["group_index"], s["floor"]): s for s in self.stages}
        self.damage_pct = {int(k): float(v) for k, v in self.meta.get("damage_pct_by_cp_pct", {}).items()}
        ov = os.environ.get("DIMBOT_GROUP", "").strip()
        self.group_override = int(ov) if ov.isdigit() else None   # 시즌 자동 선택 대신 풀 고정 (1~4)

    def season_at(self, now_ms=None):
        """지금(또는 now_ms) 기준 시즌: 시작 시각이 지난 것 중 가장 최근."""
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        cur = None
        for s in self.seasons:
            if s["start_ms"] <= now_ms:
                cur = s
            else:
                break
        return cur or self.seasons[0]

    def group_index_at(self, now_ms=None):
        if self.group_override:
            return self.group_override
        return self.season_at(now_ms)["group_index"]

    def max_floor(self, now_ms=None):
        g = self.groups[self.group_index_at(now_ms) - 1]
        return g["stage_range"][1] - g["stage_range"][0] + 1

    def floor(self, n, now_ms=None):
        return self.by_group_floor.get((self.group_index_at(now_ms), n))

    def damage_label(self, cp_pct):
        v = self.damage_pct.get(cp_pct)
        return f"{v:g}%" if v is not None else f"투력 {cp_pct}%"


# ───────────────────────── 포맷 ─────────────────────────
def fmt_sig(x, n=5):
    """유효숫자 n자리, 끝의 0 제거, 천단위 콤마. 1055.03 -> '1,055', 211.006 -> '211.01'."""
    if x == 0:
        return "0"
    digits = max(n - int(math.floor(math.log10(abs(x)))) - 1, 0)
    s = f"{x:,.{digits}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def fmt_kr(v):
    v = int(v)
    if v >= 10**12:
        return fmt_sig(v / 1e12) + "조"
    if v >= 10**8:
        return fmt_sig(v / 1e8) + "억"
    if v >= 10**4:
        return fmt_sig(v / 1e4) + "만"
    return f"{v:,}"


def fmt_pct(x):
    return f"{x:g}%"


def cp_at(stage, pct):
    return stage["recommended_cp"] * pct // 100


def reward_text(stage):
    parts = []
    for r in stage["reward"]:
        parts.append(r["name"] + (f" ×{r['amount']:,}" if r["amount"] > 1 else ""))
    return " + ".join(parts) if parts else "-"


def reward_short(stage):
    out = []
    for r in stage["reward"]:
        name, amt = r["name"], r["amount"]
        m = re.search(r"(\d+)단계 달성 테두리", name)
        if m:
            out.append(f"테두리{m.group(1)}")
        elif name == "차원의 조각":
            out.append(f"조각{amt}")
        elif name == "1분 가속권":
            out.append(f"가속권{amt}")
        elif name == "시럽쇳물":
            out.append(f"쇳물{amt}")
        elif name.startswith("SSR 쿠키 선택상자"):
            out.append("SSR상자")
        else:
            out.append(name.replace(" ", "")[:6] + (str(amt) if amt > 1 else ""))
    return "+".join(out) if out else "-"


def idle_text(stage):
    if not stage.get("idle_reward"):
        return ""
    parts = [f"{r['name']} ×{r['amount']:,}" for r in stage["idle_reward"]]
    mins = stage.get("idle_minutes")
    per = f" ({mins:g}분마다)" if mins else ""
    return "방치: " + ", ".join(parts) + per


def boss_text(stage):
    parts = [b["name"] + (f" ×{b['count']}" if b["count"] > 1 else "") for b in stage.get("boss", [])]
    s = ", ".join(parts) if parts else "-"
    lim = stage.get("boss_time_limit_sec")
    if lim:
        s += f" (제한 {lim:g}초)"
    return s


def dw(s):
    """표시 폭 (한글 등 전각 = 2칸)."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def pad(s, width, right=False):
    gap = max(width - dw(s), 0)
    return (" " * gap + s) if right else (s + " " * gap)


def table(rows, right_cols):
    widths = [max(dw(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(pad(c, widths[i], i in right_cols) for i, c in enumerate(r)).rstrip() for r in rows)


def cut_block(data, stage):
    """피해량별 필요 전투력 표 (코드블록 안에 넣을 문자열)."""
    rows = [["피해량", "필요 전투력", "비율"]]
    for p in EMBED_CP_ROWS:
        if p != 100 and p not in data.damage_pct:
            continue
        tag = "추천" if p == 100 else f"{p}%"
        rows.append([data.damage_label(p), fmt_kr(cp_at(stage, p)), tag])
    return table(rows, right_cols={0, 2})


def floor_title(stage):
    return f"차원의 이면 {stage['floor']}층 투력컷"


def floor_footer(data, stage, now_ms=None):
    season = data.season_at(now_ms)
    pool = f"시즌 {season['name']} 풀" if not data.group_override else f"풀 {data.group_override} 고정"
    return f"{pool} · 스테이지 {stage['stage']} · 전투력이 추천의 N% 이상이면 피해량 %"


def floor_text(data, stage, now_ms=None):
    """셀프테스트/디버그용 평문 (임베드와 같은 내용)."""
    lines = [floor_title(stage), cut_block(data, stage),
             f"명중 {stage['accuracy']:,} | 집중 {stage['focus']:,} | 적 치명저항 {fmt_pct(stage['crit_resist_pct'])}",
             f"보상: {reward_text(stage)}"]
    idle = idle_text(stage)
    if idle:
        lines.append(idle)
    lines.append(f"보스: {boss_text(stage)}")
    lines.append(floor_footer(data, stage, now_ms))
    return "\n".join(lines)


def range_table(data, lo, hi, now_ms=None):
    header = ["층"] + [data.damage_label(p) for p in CP_COLUMNS] + ["명중", "집중", "치저", "보상"]
    rows = [header]
    for n in range(lo, hi + 1):
        s = data.floor(n, now_ms)
        rows.append([str(n)] + [fmt_kr(cp_at(s, p)) for p in CP_COLUMNS]
                    + [f"{s['accuracy']:,}", f"{s['focus']:,}", fmt_pct(s["crit_resist_pct"]), reward_short(s)])
    body = table(rows, right_cols=set(range(0, 9)))
    note = "열 = 피해량 % (전투력이 추천 전투력의 20/40/60/80/100% 이상일 때) · 치저 = 적 치명저항"
    return f"차원의 이면 {lo}~{hi}층 투력컷\n```\n{body}\n```{note}"


def parse_floors(text):
    t = (text or "").strip().replace("층", "").replace("~", "-").replace("–", "-")
    m = re.fullmatch(r"\s*(\d{1,3})\s*(?:[-\s]\s*(\d{1,3}))?\s*", t)
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


BARE_RE = re.compile(r"\s*\d{1,3}\s*층?\s*(?:[-~–]\s*\d{1,3}\s*층?\s*)?")


def bare_floors(text):
    """'32', '32층', '30-35' 처럼 숫자만 있는 메시지면 (lo, hi), 아니면 None."""
    if not text or len(text) > 16 or not BARE_RE.fullmatch(text):
        return None
    return parse_floors(text)


def load_channel_filter(path=CHANNELS_PATH):
    """channels.txt: 채널 이름 또는 ID 한 줄씩. 없거나 비어 있으면 빈 집합(= 모든 채널 허용)."""
    allowed = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip().lstrip("#").strip().lower()   # '#투력컷' 처럼 써도 됨
                if line:
                    allowed.add(line)
    return allowed


def channel_allowed(channel, allowed):
    if not allowed:
        return True
    name = (getattr(channel, "name", "") or "").lower()
    return str(getattr(channel, "id", "")) in allowed or name in allowed


def build_reply(data, text, now_ms=None):
    """-> {"text": str} 또는 {"stage": dict} 또는 {"error": str}"""
    pf = parse_floors(text)
    if not pf:
        return {"error": USAGE}
    lo, hi = pf
    mx = data.max_floor(now_ms)
    if lo < 1 or hi > mx:
        return {"error": f"{lo if lo < 1 else hi}층은 없어. 1~{mx}층만 가능해."}
    if lo == hi:
        return {"stage": data.floor(lo, now_ms)}
    if hi - lo + 1 > MAX_RANGE:
        return {"error": f"범위는 한 번에 최대 {MAX_RANGE}층까지. 예: `!컷 {lo}-{lo + MAX_RANGE - 1}`"}
    return {"text": range_table(data, lo, hi, now_ms)}


# ───────────────────────── 디스코드 ─────────────────────────
def read_token():
    tok = os.environ.get("DISCORD_TOKEN", "").strip()
    if not tok and os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "r", encoding="utf-8-sig") as f:
            tok = f.read().strip().strip('"').strip("'")
    return tok


def looks_like_token(tok):
    """디스코드 봇 토큰 모양: 점 2개로 나뉜 70자쯤 되는 문자열."""
    return len(tok) >= 50 and " " not in tok and tok.count(".") == 2


def prompt_token(path=TOKEN_PATH, ask=input):
    """콘솔에서 토큰을 받아 token.txt 에 저장하고 돌려줌. 안 주면 None."""
    print("봇 토큰이 없어. 디스코드 개발자 포털 → 내 앱 → Bot → Reset Token 으로 받은 토큰을 붙여넣고 엔터.")
    print("(README.md 2번. 창에 붙여넣기는 Ctrl+V 또는 마우스 오른쪽 클릭)")
    for _ in range(3):
        try:
            tok = ask("토큰: ").strip().strip('"').strip("'")
        except (EOFError, KeyboardInterrupt):
            return None
        if not tok:
            return None
        if looks_like_token(tok):
            with open(path, "w", encoding="utf-8") as f:
                f.write(tok + "\n")
            print(f"저장함: {path}  (다음부턴 안 물어봄. 토큰 바꾸려면 이 파일 지우고 다시 실행)")
            return tok
        print("토큰 모양이 아니야. 점(.)이 두 개 들어간 70자쯤 되는 문자열이어야 해. Bot 탭의 Reset Token 눌러서 나온 걸 통째로 붙여넣어.")
    return None


def acquire_lock(port=LOCK_PORT):
    """같은 PC에서 두 번째로 켜지면 None. 소켓은 프로세스가 끝날 때까지 들고 있어야 함."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None


def setup_hidden_logging(path=LOG_PATH):
    """pythonw 로 실행돼 콘솔이 없으면 stdout/stderr 를 로그 파일로 돌림. 돌렸으면 True."""
    if sys.stdout is not None and sys.stderr is not None:
        return False
    try:
        if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
            os.remove(path)
    except OSError:
        pass
    f = open(path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = f
    return True


def stop_running(marker="dim_bot.py"):
    """커맨드라인에 marker 가 들어간 다른 python 프로세스를 전부 끔 (윈도우). 끈 PID 목록을 돌려줌."""
    import subprocess
    if os.name != "nt":
        print("리눅스 서버에선: sudo systemctl stop dimbot")
        return []
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*%s*' -and $_.ProcessId -ne %d "
          "-and $_.Name -match '^python' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }"
          % (marker, os.getpid()))
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    return [p for p in out.stdout.split() if p.isdigit()]


def autostart(on, startup_dir=None):
    """윈도우 로그인 시 창 없이 자동 실행되는 바로가기를 시작프로그램 폴더에 만들거나 지움."""
    import subprocess
    if os.name != "nt":
        print("윈도우 전용. 리눅스 서버는 deploy/setup_server.sh 가 systemd 로 자동 시작 등록함.")
        return 1
    startup_dir = startup_dir or os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                                              "Start Menu", "Programs", "Startup")
    lnk = os.path.join(startup_dir, "CrumbleDimbot.lnk")
    if not on:
        if os.path.exists(lnk):
            os.remove(lnk)
            print("자동 시작 해제함. (지금 돌고 있는 봇은 그대로, 끄려면 stop_bot.bat)")
        else:
            print("자동 시작 설정이 원래 없어.")
        return 0
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        print(f"[!] {pythonw} 가 없어. 파이썬 설치가 이상함.")
        return 1
    script = os.path.join(HERE, "dim_bot.py")
    ps = (f'$s = (New-Object -ComObject WScript.Shell).CreateShortcut("{lnk}"); '
          f'$s.TargetPath = "{pythonw}"; $s.Arguments = \'-I "{script}"\'; '
          f'$s.WorkingDirectory = "{HERE}"; $s.Description = "Crumble dimbot"; $s.Save()')
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(lnk):
        print("[!] 바로가기 못 만듦:", (r.stderr or r.stdout).strip())
        return 1
    print("윈도우 로그인할 때 봇이 창 없이 자동으로 켜짐. 해제는 autostart_off.bat")
    print(f"바로가기: {lnk}")
    return 0


def start_keepalive_http(port):
    """Render 같은 무료 웹 호스팅용: 아무 GET 에나 200 'dimbot ok' 를 주는 초간단 HTTP 서버 (백그라운드 스레드).
    환경변수 PORT(Render 가 자동으로 줌) 또는 DIMBOT_HTTP_PORT 가 있을 때만 켜짐."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"dimbot ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):      # 핑 로그는 조용히
            pass

    srv = ThreadingHTTPServer(("0.0.0.0", int(port)), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def invite_url(discord, client_id):
    """봇 서버 초대 링크: bot + applications.commands 스코프, 메시지 보내기/링크 임베드/메시지 기록 보기 권한."""
    perms = discord.Permissions(send_messages=True, embed_links=True, read_message_history=True)
    return discord.utils.oauth_url(client_id, permissions=perms, scopes=("bot", "applications.commands"))


def run_bot(token):
    import logging
    import discord
    from discord import app_commands
    from discord.ext import commands

    data = DimData()
    allowed_channels = load_channel_filter()
    intents = discord.Intents.default()
    intents.message_content = True          # !명령어·숫자 반응용 (개발자 포털에서 MESSAGE CONTENT INTENT 켜야 함)
    bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents, help_command=None)
    synced = set()

    async def send_reply(message, **kw):
        """답글로 보내고, 답글 권한(메시지 기록 보기)이 없으면 그냥 채널에 보냄."""
        try:
            await message.reply(**kw, mention_author=False)
        except discord.HTTPException:
            await message.channel.send(**kw)

    def make_embed(stage):
        e = discord.Embed(title=floor_title(stage), color=EMBED_COLOR)
        e.add_field(name="피해량별 필요 전투력", value=f"```\n{cut_block(data, stage)}\n```", inline=False)
        e.add_field(name="명중", value=f"**{stage['accuracy']:,}**", inline=True)
        e.add_field(name="집중", value=f"**{stage['focus']:,}**", inline=True)
        e.add_field(name="적 치명저항", value=f"**{fmt_pct(stage['crit_resist_pct'])}**", inline=True)
        rw = reward_text(stage)
        idle = idle_text(stage)
        e.add_field(name="보상", value=rw + (f"\n{idle}" if idle else ""), inline=False)
        e.add_field(name="보스", value=boss_text(stage), inline=False)
        e.set_footer(text=floor_footer(data, stage))
        return e

    def payload(text):
        r = build_reply(data, text)
        if "stage" in r:
            return {"embed": make_embed(r["stage"])}, False
        if "text" in r:
            return {"content": r["text"]}, False
        return {"content": r["error"]}, True

    async def sync_guild(guild):
        if guild.id in synced:
            return
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            synced.add(guild.id)
            print(f"슬래시 명령어 등록: {guild.name}")
        except Exception as e:                       # 권한/레이트리밋 등
            print(f"슬래시 명령어 등록 실패 ({guild.name}): {e}")

    @bot.event
    async def on_ready():
        print(f"로그인 완료: {bot.user}  (서버 {len(bot.guilds)}개)")
        invite = invite_url(discord, bot.user.id)
        if not bot.guilds:
            print("\n아직 어느 서버에도 안 들어가 있어. 아래 링크를 복사해서 브라우저 주소창에 붙여넣고, 서버 고른 뒤 '승인':")
            print(f"  {invite}\n")
            print("초대되면 이 창에 '서버 입장' 이라고 뜸. 창은 그대로 켜 둬.")
        else:
            for g in bot.guilds:
                await sync_guild(g)
            print(f"다른 서버에도 넣고 싶으면 이 링크: {invite}")
            where = f"채널 {', '.join(sorted(allowed_channels))} 에서만" if allowed_channels else "모든 채널에서"
            print(f"준비 끝. {where} 숫자만 쳐도 반응 (예: 32, 30-35). !컷 32 / /투력컷 도 됨. "
                  f"끄려면 Ctrl+C, 창 닫기, 또는 stop_bot.bat")

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return
        if bare_floors(message.content) and channel_allowed(message.channel, allowed_channels):
            r = build_reply(data, message.content)
            if "stage" in r:
                await send_reply(message, embed=make_embed(r["stage"]))
            elif "text" in r:
                await send_reply(message, content=r["text"])
            return                      # 없는 층·너무 긴 범위는 조용히 무시 (일반 잡담일 수 있음)
        await bot.process_commands(message)

    @bot.event
    async def on_guild_join(guild):
        print(f"서버 입장: {guild.name}")
        await sync_guild(guild)
        print("준비 끝. 채널에서 숫자만 쳐봐 (예: 32). 끄려면 Ctrl+C 또는 창 닫기.")

    @bot.tree.command(name="투력컷", description="차원의 이면 층별 투력컷 (예: 32 또는 30-35)")
    @app_commands.describe(층="층 번호(1~100) 또는 범위 (예: 32, 30-35)")
    async def slash_cut(interaction: discord.Interaction, 층: str):
        kw, is_err = payload(층)
        await interaction.response.send_message(**kw, ephemeral=is_err)

    @bot.command(name="투력컷", aliases=["컷"])
    async def prefix_cut(ctx, *, arg: str = ""):
        kw, _ = payload(arg)
        await send_reply(ctx.message, **kw)

    @bot.event
    async def on_command_error(ctx, err):
        if isinstance(err, commands.CommandNotFound):
            return
        print(f"명령 오류: {err}")

    try:
        bot.run(token, log_level=logging.WARNING)
    except discord.PrivilegedIntentsRequired:
        print("\n[!] MESSAGE CONTENT INTENT 가 꺼져 있어. discord.com/developers → 내 앱 → Bot → "
              "Privileged Gateway Intents → MESSAGE CONTENT INTENT 켜고 Save 후 다시 실행.")
        return 3
    except discord.LoginFailure:
        print("\n[!] 토큰이 틀렸어. Bot 탭에서 Reset Token 눌러 새 토큰을 token.txt 에 한 줄로 붙여넣어.")
        return 4
    return 0


# ───────────────────────── 셀프테스트 ─────────────────────────
# 커뮤니티 표 스크린샷 값 (시즌 4 이후 풀 = 스테이지 301~400)
EXPECTED = {
    1:  {"cp": "1,055억", "cp80": "844.02억", "cp60": "633.02억", "cp40": "422.01억", "cp20": "211.01억",
         "acc": 1204, "focus": 1338, "crit": "0%", "reward": "무한바퀴"},
    2:  {"cp": "1,365.2억", "cp80": "1,092.1억", "acc": 1324, "focus": 1472, "crit": "10%", "reward": "차원의 조각 ×170"},
    10: {"cp": "5,037.5억", "acc": 2287, "focus": 2543, "crit": "90%", "reward": "차원의 이면 10단계 달성 테두리"},
    20: {"cp": "1.2913조", "cp80": "1.0331조", "cp60": "7,748.1억", "acc": 3490, "focus": 3880, "crit": "190%",
         "reward": "무한바퀴"},
    45: {"cp": "5.0038조", "cp80": "4.003조", "cp20": "1.0008조", "acc": 6499, "focus": 7224, "crit": "440%",
         "reward": "SSR 쿠키 선택상자2"},
    70: {"cp": "11.431조", "cp80": "9.145조", "cp20": "2.2863조", "acc": 9508, "focus": 10569, "crit": "690%",
         "reward": "시럽쇳물 ×50"},
}


def selftest():
    import datetime
    data = DimData()
    fails = []

    def check(label, got, want):
        ok = got == want
        if not ok:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        return ok

    now = int(datetime.datetime(2026, 11, 8, 12, 0).timestamp() * 1000)
    season = data.season_at(now)
    print(f"[시즌] 2026-11-08 기준 시즌 {season['name']} → 풀 {season['group_index']} "
          f"(스테이지 {data.groups[season['group_index'] - 1]['stage_range']})")
    check("season group 2026-11-08", season["group_index"], 4)
    check("season group 2026-10-25", data.season_at(int(datetime.datetime(2026, 10, 25).timestamp() * 1000))["group_index"], 3)
    check("season group 2026-09-01", data.season_at(int(datetime.datetime(2026, 9, 1).timestamp() * 1000))["group_index"], 1)
    live = data.season_at()
    print(f"[시즌] 지금 실제 시즌 {live['name']} → 풀 {live['group_index']}")
    check("max floor", data.max_floor(now), 100)

    for n in (1, 10, 45, 70):
        print("\n" + floor_text(data, data.floor(n, now), now))
    print("\n" + build_reply(data, "30-35", now)["text"])

    for n, want in EXPECTED.items():
        s = data.floor(n, now)
        check(f"{n}층 100%", fmt_kr(cp_at(s, 100)), want["cp"])
        for k, p in (("cp80", 80), ("cp60", 60), ("cp40", 40), ("cp20", 20)):
            if k in want:
                check(f"{n}층 {p}%", fmt_kr(cp_at(s, p)), want[k])
        check(f"{n}층 명중", s["accuracy"], want["acc"])
        check(f"{n}층 집중", s["focus"], want["focus"])
        check(f"{n}층 치명저항", fmt_pct(s["crit_resist_pct"]), want["crit"])
        check(f"{n}층 보상", reward_text(s), want["reward"])

    # 보상 규칙: 2~4층 170/180/190, 6~29층 +10, 31층부터 400, 5의 배수 특수 보상
    for n in range(1, 101):
        s = data.floor(n, now)
        if n % 5 == 0 or n == 1:
            check(f"{n}층 특수보상", s["reward"][0]["name"] != "차원의 조각", True)
        else:
            exp = min(400, 160 + 10 * (n - 1 - n // 5))
            check(f"{n}층 조각 수", (s["reward"][0]["name"], s["reward"][0]["amount"]), ("차원의 조각", exp))
        check(f"{n}층 치명저항 규칙", s["crit_resist_pct"], (n - 1) * 10)

    # 명령 파싱/오류
    check("parse 32", parse_floors("32"), (32, 32))
    check("parse 32층", parse_floors("32층"), (32, 32))
    check("parse 30-35", parse_floors("30-35"), (30, 35))
    check("parse 35~30", parse_floors("35~30"), (30, 35))
    check("parse bad", parse_floors("abc"), None)
    check("bare 32", bare_floors("32"), (32, 32))
    check("bare 32층", bare_floors(" 32층 "), (32, 32))
    check("bare 30-35", bare_floors("30-35"), (30, 35))
    check("bare 30~35", bare_floors("30 ~ 35"), (30, 35))
    check("bare chat", bare_floors("32 맞음?"), None)
    check("bare 4 digits", bare_floors("2024"), None)
    check("bare empty", bare_floors(""), None)
    check("bare 0 → 조용히 무시", "error" in build_reply(data, "0", now), True)
    check("channel filter empty", channel_allowed(type("C", (), {"id": 1, "name": "x"})(), set()), True)
    check("channel filter name", channel_allowed(type("C", (), {"id": 1, "name": "투력컷"})(), {"투력컷"}), True)
    check("channel filter id", channel_allowed(type("C", (), {"id": 12345, "name": "x"})(), {"12345"}), True)
    check("channel filter miss", channel_allowed(type("C", (), {"id": 1, "name": "잡담"})(), {"투력컷"}), False)
    check("err 0", "error" in build_reply(data, "0", now), True)
    check("err 101", "error" in build_reply(data, "101", now), True)
    check("err range", "error" in build_reply(data, "1-50", now), True)
    r = build_reply(data, "1-20", now)
    check("range 20 ok", "text" in r, True)
    check("range 20 length < 2000", len(r.get("text", "")) < 2000, True)
    r = build_reply(data, "81-100", now)
    check("range 81-100 length < 2000", len(r.get("text", "")) < 2000, True)
    # 토큰 입력 (실제 token.txt 는 건드리지 않음)
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "dimbot_selftest_token.txt")
    fake = "x" * 24 + "." + "y" * 6 + "." + "z" * 30      # 토큰 모양만 흉내 (깃허브 비밀 검사에 안 걸리게 조립)
    answers = iter(["이건 토큰 아님", fake])
    check("token prompt saves", prompt_token(tmp, ask=lambda _: next(answers)), fake)
    check("token file content", open(tmp, encoding="utf-8").read().strip(), fake)
    os.remove(tmp)
    check("token prompt empty", prompt_token(tmp, ask=lambda _: ""), None)
    check("token file not created", os.path.exists(tmp), False)
    check("looks_like_token no", looks_like_token("abc"), False)
    # 중복 실행 방지 (실제 봇 포트와 다른 포트로)
    l1 = acquire_lock(57999)
    check("lock first", l1 is not None, True)
    check("lock second refused", acquire_lock(57999), None)
    l1.close()
    check("lock released", acquire_lock(57999) is not None, True)
    # 창 없이 실행 시 로그 파일 전환 (stdout 을 잠깐 None 으로)
    logp = os.path.join(tempfile.gettempdir(), "dimbot_selftest.log")
    real_out, real_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = None
    try:
        switched = setup_hidden_logging(logp)
        print("hidden-log-line")
        logf = sys.stdout
    finally:
        sys.stdout, sys.stderr = real_out, real_err
    logf.close()
    check("hidden logging switched", switched, True)
    check("hidden log written", "hidden-log-line" in open(logp, encoding="utf-8").read(), True)
    os.remove(logp)
    check("console keeps stdout", setup_hidden_logging(logp), False)
    # 호스팅용 HTTP 응답 서버
    import urllib.request
    srv = start_keepalive_http(0)
    port = srv.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
        check("keepalive http 200", resp.status, 200)
        check("keepalive body", resp.read().strip(), b"dimbot ok")
    srv.shutdown()
    srv.server_close()
    if os.name == "nt":
        # 자동 시작 바로가기 (임시 폴더에)
        sdir = os.path.join(tempfile.gettempdir(), "dimbot_selftest_startup")
        os.makedirs(sdir, exist_ok=True)
        check("autostart on", autostart(True, sdir), 0)
        check("autostart lnk exists", os.path.exists(os.path.join(sdir, "CrumbleDimbot.lnk")), True)
        check("autostart off", autostart(False, sdir), 0)
        check("autostart lnk removed", os.path.exists(os.path.join(sdir, "CrumbleDimbot.lnk")), False)
        os.rmdir(sdir)
        # --stop: 표식이 들어간 가짜 프로세스만 끄는지 (실제 봇은 안 건드림)
        import subprocess
        marker = "dimbot_selftest_marker"
        p = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep(60)  # {marker}"])
        time.sleep(1.0)
        killed = stop_running(marker)
        check("stop kills marked process", str(p.pid) in killed, True)
        check("stop leaves others", len(killed), 1)
        p.wait(timeout=10)
    check("fmt 1055.03억", fmt_kr(105503109842), "1,055억")
    check("fmt 만", fmt_kr(123456), "12.346만")
    check("fmt 작은수", fmt_kr(999), "999")

    print()
    if fails:
        print("FAIL", len(fails))
        for f in fails:
            print(" -", f)
        return 1
    print(f"ALL OK (스테이지 {len(data.stages)}개, 검사 통과)")
    return 0


def main():
    global _LOCK
    hidden = setup_hidden_logging()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if "--selftest" in sys.argv:
        return selftest()
    if "--stop" in sys.argv:
        pids = stop_running()
        print(f"봇 {len(pids)}개 껐어. (PID {', '.join(pids)})" if pids else "실행 중인 봇이 없어.")
        return 0
    if "--autostart" in sys.argv:
        i = sys.argv.index("--autostart")
        mode = sys.argv[i + 1].lower() if i + 1 < len(sys.argv) else ""
        if mode not in ("on", "off"):
            print("사용법: dim_bot.py --autostart on|off")
            return 2
        return autostart(mode == "on")
    if hidden:
        import datetime
        print(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} 창 없이 시작 (끄기: stop_bot.bat) ===")
    if not os.path.exists(DATA_PATH):
        print(f"[!] {DATA_PATH} 가 없어. build_data.py 를 먼저 실행해.")
        return 2
    _LOCK = acquire_lock()
    if _LOCK is None:
        print("[!] 봇이 이미 켜져 있어. 두 개 켜면 답이 두 번 오니까 이건 그냥 닫아. 전부 끄려면 stop_bot.bat.")
        return 5
    http_port = os.environ.get("PORT") or os.environ.get("DIMBOT_HTTP_PORT")
    if http_port:
        start_keepalive_http(http_port)
        print(f"HTTP 응답 서버 켬 (포트 {http_port}) - 호스팅이 봇을 안 재우게 하는 용도")
    token = read_token()
    if not token and sys.stdin is not None and sys.stdin.isatty():
        token = prompt_token()
    if not token:
        print("[!] 토큰이 없어. token.txt 에 봇 토큰을 한 줄로 붙여넣거나 환경변수 DISCORD_TOKEN 을 설정해. (README.md 참고)")
        return 2
    return run_bot(token)


if __name__ == "__main__":
    sys.exit(main())
