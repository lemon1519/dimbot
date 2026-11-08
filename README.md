# 크럼블 투력컷 봇 (dimbot)

디스코드에서 층 번호만 치면 차원의 이면 투력컷 표 한 줄을 돌려주는 봇.

```
32                 ← 그냥 숫자만 쳐도 됨 (32층, 30-35 도 됨)
!투력컷 32        !컷 32        /투력컷 층:32
!투력컷 30-35     !컷 30-35     /투력컷 층:30-35   (범위는 한 번에 최대 20층)
```

한 층이면 임베드(피해량별 필요 전투력, 명중, 집중, 적 치명저항, 보상, 보스), 범위면 코드블록 표.

숫자만 친 메시지는 기본적으로 봇이 보는 모든 채널에서 반응함. 잡담방에서 "2" 같은 거에 끼어드는 게 싫으면
이 폴더에 `channels.txt` 만들고 반응할 채널 이름(또는 채널 ID)을 한 줄에 하나씩 적어. 예:

```
투력컷
차원의-이면
```

그러면 그 채널에서만 숫자에 반응하고, `!컷 32` 랑 `/투력컷` 은 어디서나 됨. 바꾼 뒤엔 봇 재시작.
없는 층(0, 101)이나 20층 넘는 범위는 숫자만 쳤을 땐 조용히 무시하고, `!컷` 으로 치면 왜 안 되는지 알려줌.

## 처음 한 번만 하는 설정 (5분)

1. **봇 만들기** — https://discord.com/developers/applications → `New Application` → 이름 아무거나 → `Create`
2. **토큰 받기** — 왼쪽 `Bot` 탭 → `Reset Token` → `Copy`. 복사만 해 두면 됨.
   `run_bot.bat` 처음 실행하면 "토큰:" 하고 물어보는데, 거기 붙여넣고(Ctrl+V) 엔터 치면 `token.txt`에 알아서 저장됨.
   (직접 만들어도 됨: 이 폴더에 `token.txt` 파일, 내용은 토큰 한 줄. 토큰은 비밀번호임. 아무 데도 올리지 마. 유출됐으면 Reset Token 다시.)
3. **메시지 읽기 권한 켜기** — 같은 `Bot` 탭 아래로 내려서 `Privileged Gateway Intents` → **MESSAGE CONTENT INTENT** 켜고 `Save Changes`.
   숫자만 치는 거랑 `!컷 32` 같은 느낌표 명령어가 이게 있어야 돌아감. (`/투력컷` 슬래시만 쓸 거면 없어도 됨)
4. **실행** — `run_bot.bat` 더블클릭 → `토큰:` 뜨면 2번에서 복사한 토큰 붙여넣고(Ctrl+V) 엔터 → `로그인 완료: 봇이름` 뜸.
5. **서버에 초대** — 같은 창에 `https://discord.com/oauth2/authorize?client_id=...` 초대 링크가 찍힘.
   그걸 복사해서 브라우저 주소창에 붙여넣기 → 서버 고르고 `승인`. 창에 `서버 입장` 뜨면 끝. 디코 채널에서 `32` 쳐봐.
   (개발자 포털 `OAuth2` 탭의 URL Generator 로 만들어도 됨: SCOPES `bot` + `applications.commands`, 권한 `Send Messages`, `Embed Links`, `Read Message History`.)
   채널 설정의 "웹후크" URL 은 이거랑 전혀 다른 물건이니 헷갈리지 말 것. 웹후크 URL 은 아무나 그 채널에 글 쓸 수 있는 비밀키라 밖에 보여주면 안 됨.

봇 창을 닫으면 봇도 꺼짐. 다시 켤 땐 `run_bot.bat`만 더블클릭 (토큰은 저장돼 있어서 안 물어봄).

## 창 안 띄우고 돌리기 / 윈도우 켤 때 자동 시작

| 파일 | 하는 일 |
|---|---|
| `run_hidden.bat` | 창 없이 봇 실행 (이미 켜진 봇은 먼저 끄고 새로 켬). 출력은 `dimbot.log` |
| `stop_bot.bat` | 돌고 있는 봇 전부 끄기 (창으로 켠 것, 숨긴 것 다) |
| `autostart_on.bat` | 윈도우 로그인할 때 창 없이 자동으로 켜지게 등록 |
| `autostart_off.bat` | 자동 시작 해제 |

봇은 한 번에 하나만 켜짐. 두 번째로 켜면 "이미 켜져 있어" 하고 꺼짐 (두 개 돌면 답이 두 번 오니까).
PC가 절전 모드에 들어가면 봇도 같이 멈추니, 계속 받고 싶으면 전원 옵션에서 절전을 끄기. PC 자체를 끄면 당연히 봇도 꺼짐.

## 서버에 올리기 (PC 꺼도 봇이 살아 있게)

PC 끄고도 돌리려면 24시간 켜진 남의 컴퓨터, 즉 클라우드 서버가 필요함. 이 봇은 메모리 100MB도 안 써서 제일 작은 무료 서버면 충분.

**추천: Google Cloud 무료 VM (e2-micro, "Always Free")** — 카드 등록은 해야 하지만 아래 조건대로만 만들면 요금 0원.
1. https://cloud.google.com 에서 구글 계정으로 가입, 결제 정보(카드) 등록.
2. 콘솔 → `Compute Engine` → `VM 인스턴스` → `인스턴스 만들기`
   - 리전: **us-west1** (오리건) 또는 us-central1, us-east1 ← 이 세 곳만 무료. 서울 고르면 돈 나감
   - 머신 유형: **e2-micro** ← 이것만 무료
   - 부팅 디스크: **Ubuntu 24.04 LTS**, 표준 영구 디스크 **10GB** (30GB까지 무료)
   - 나머지 기본값 → `만들기`
3. 여기 PC에서 `make_server_zip.bat` 더블클릭 → 바탕화면에 `dimbot.zip` 생김 (토큰은 안 들어감).
4. VM 목록의 `SSH` 버튼 → 브라우저에 검은 터미널 뜸 → 오른쪽 위 톱니 → `파일 업로드` → `dimbot.zip`
5. 터미널에 한 줄씩:
   ```
   sudo apt-get install -y unzip && unzip -o dimbot.zip && cd dimbot && bash deploy/setup_server.sh
   ```
   중간에 토큰 물어보면 붙여넣고 엔터 (화면엔 안 보임). 마지막에 `로그인 완료` 보이면 끝.
   재부팅돼도 알아서 켜지고, 죽으면 10초 뒤 다시 켜짐.
6. 집 PC 봇은 `stop_bot.bat` 으로 끄기 (서버랑 둘 다 켜져 있으면 답이 두 번 옴).

서버에서 쓰는 명령: 로그 `journalctl -u dimbot -f`, 재시작 `sudo systemctl restart dimbot`, 끄기 `sudo systemctl stop dimbot`.
코드/데이터 바꿨으면 zip 다시 만들어 올리고 5번 다시.

구글이 결제 계정을 거절하거나(OR_BACR2_59) 선결제를 요구하면 이 길은 포기. e2-micro 는 어차피 0원이라 선결제한 돈은 그냥 묶이기만 함.

### 대안 B: Render 무료 (카드 없이, 깃허브 계정 필요)

Render 는 무료 웹 서비스를 15분 동안 아무도 안 찾아오면 재워버림. 그래서 봇에 "dimbot ok" 라고 답하는 HTTP 응답을 붙여놨고(`PORT` 환경변수가 있으면 자동으로 켜짐),
5분마다 그 주소를 찔러주는 무료 모니터를 하나 걸면 안 잠. 한 달 750시간 무료라 봇 하나는 24시간 딱 들어감.

1. https://github.com 가입 → `New repository` → 이름 `dimbot`, **Private** → `Create repository`
   → `uploading an existing file` 링크 → 이 폴더의 파일을 전부 드래그 (**token.txt 는 빼고**, `deploy` 폴더도 필요 없음) → `Commit changes`
2. https://render.com 가입 (GitHub 로 로그인) → `New` → `Blueprint` → `dimbot` 저장소 연결 → `DISCORD_TOKEN` 칸에 봇 토큰 붙여넣기 → `Apply`
   (Blueprint 가 안 보이면 `New` → `Web Service` → 저장소 선택 → Free 플랜, Build `pip install -r requirements.txt`, Start `python -I dim_bot.py`, 환경변수 `DISCORD_TOKEN` 추가)
3. 몇 분 뒤 로그에 `로그인 완료` 뜨고, `https://dimbot-xxxx.onrender.com` 주소가 생김. 브라우저로 열면 `dimbot ok` 나오면 정상.
4. 재우기 방지: https://uptimerobot.com 가입 → `New Monitor` → HTTP(s), 위 주소, 간격 5분 → 저장. (cron-job.org 도 됨)
5. 집 PC 봇은 `stop_bot.bat` 으로 끄기.

Render 가 가끔 재시작해서 1분쯤 끊길 수 있고, 코드 바꾸면 깃허브에 파일 다시 올리면 자동 재배포됨.

### 대안 C: 안 쓰는 안드로이드 폰

계정도 카드도 필요 없음. F-Droid 에서 Termux 설치 → `pkg install python` → `pip install discord.py` → 이 폴더 복사해서 `python dim_bot.py`.
폰 설정에서 Termux 배터리 최적화 끄고 `termux-wake-lock` 걸어두면 됨. 원하면 자세히 적어줄 테니 말할 것.

Oracle Cloud 도 Always Free VM 이 있지만 가입 심사가 구글보다 더 까다로움. Koyeb·클라우드타입은 카드 필요 + 자동 중지, Railway·fly.io 는 유료라 탈락.

이 PC가 켜져 있고 창이 떠 있는 동안만 봇이 살아 있음. 24시간 돌리고 싶으면 Railway나 Render 같은 무료 호스팅에 이 폴더를 올리고 환경변수 `DISCORD_TOKEN`에 토큰 넣으면 됨 (여기선 설정 안 함).

필요한 것: Python 3.12 + `discord.py` (`python -m pip install discord.py`, 이 PC엔 이미 설치됨).

## 표 읽는 법

커뮤니티 투력컷 표와 같은 값이고, 전부 클라 데이터에서 뽑은 거라 손으로 옮긴 오타가 없음.

| 봇에 뜨는 것 | 뜻 | 데이터 출처 |
|---|---|---|
| 피해 100% (추천) | 게임이 정한 그 층의 **추천 전투력** = 커뮤니티 표의 100% 열 | `dimensionStageBattleSettings.recommendedCombatPower` |
| 피해 75 / 55 / 35 / 15% | 전투력이 추천의 80 / 60 / 40 / 20% 이상일 때 내는 피해량. 그 옆 숫자가 그 전투력 | `gameSettings.combatPowerDamagePenaltyPve*` (20%→15%, 40%→35%, 60%→55%, 80%→75%) |
| 피해 120% | 추천의 120% 이상이면 피해 120%. 커뮤니티 표엔 없는 줄이라 덤으로 넣음 | 위와 같음 |
| 명중 | 적 회피 수치 ×100. 내 명중이 이거 이상이면 안 빗나감 | `avoidanceRate` |
| 집중 | 적 저항 수치 ×100. 내 집중이 이거 이상이면 디버프 기본 확률대로 들어감 | `resistRate` |
| 적 치명저항 | 1층 0%, 한 층마다 +10%p | `criticalResist` |
| 보상 | 클리어 보상 (+ 방치 보상 1분당 차원의 힘) | `dimensionStageRewards` |

### 시즌 자동 선택

차원의 이면은 시즌마다 100층짜리 풀을 바꿔 씀. 클라에 풀이 4개(스테이지 1~100, 101~200, 201~300, 301~400) 들어 있고,
시즌 0~1은 1번, 시즌 2는 2번, 시즌 3은 3번, **시즌 4(2026-11-05~)부터 2028년 3월까지 전부 4번 풀**임.
봇은 시즌 날짜표(`dimensionStageSeasons`)를 보고 지금 시즌의 풀에서 층을 찾음. 스크린샷 표는 4번 풀 값이고 셀프테스트도 그걸로 맞춤.
옛 풀 값이 보고 싶으면 환경변수 `DIMBOT_GROUP=1` 처럼 풀 번호를 고정하면 됨.

## 파일

- `dim_bot.py` — 봇 본체. `python -I dim_bot.py --selftest` 하면 디스코드 연결 없이 1·10·45·70층과 30~35층 표를 찍고 스크린샷 값과 대조함.
- `dim_stages.json` — 400개 스테이지 데이터 (봇은 이 파일만 읽음)
- `build_data.py` — 패치 후 `..\gamedata` 갱신했으면 `python -I build_data.py` 로 json 다시 생성
- `run_bot.bat` — 실행 (창 있음). `run_hidden.bat` / `stop_bot.bat` / `autostart_on.bat` / `autostart_off.bat` 는 위 표 참고
- `token.txt` — 처음 실행 때 자동 생성. `.gitignore`에 들어 있음
- `channels.txt` — (선택) 숫자만 쳤을 때 반응할 채널 목록
- `dimbot.log` — 창 없이 돌릴 때의 출력
- `deploy/setup_server.sh`, `make_server_zip.bat` — 리눅스 서버(VM)에 올릴 때
- `requirements.txt`, `render.yaml` — Render 에 올릴 때

## 문제 해결

- `MESSAGE CONTENT INTENT 가 꺼져 있어` → 위 3번. 켜고 저장한 뒤 다시 실행.
- `토큰이 틀렸어` → Bot 탭에서 Reset Token 하고, `token.txt` 지운 뒤 `run_bot.bat` 다시 실행해서 새 토큰 붙여넣기.
- 느낌표 명령어는 되는데 `/투력컷`이 안 보임 → 초대할 때 `applications.commands` 스코프를 빠뜨린 것. 4번 URL로 다시 초대. 디스코드 앱 재시작하면 바로 뜸.
- 봇이 글을 못 씀 → 그 채널에 봇 역할의 `메시지 보내기`, `링크 임베드` 권한이 있는지 확인.
- 창이 바로 꺼짐 → `run_bot.bat`은 끝나도 창을 안 닫으니 위에 뜬 빨간 글 읽기. Python이 없다고 하면 Python 3.12 설치하고 `python -m pip install discord.py`.
