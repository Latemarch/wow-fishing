# wow-fishing (Retail)

에드온 신호 + 파이썬 입력으로 낚시를 돌리고, **기묘한 끈적이(item 187662)** 가 룻되면 중단합니다.

## 1. 에드온 설치

`addon/FishingSignal/` 전체를 복사:

`World of Warcraft/_retail_/Interface/AddOns/FishingSignal/`

게임에서 에드온 활성화 후 `/reload`.  
우상단 8×8 색 점이 보이면 정상입니다.

- `/fsdebug` — 현재 신호 상태
- `/fsreset` — GOT_GOOP 플래그 초기화

| 색 | 의미 |
|----|------|
| 검정 | IDLE |
| 파랑 `#0033FF` | FISHING |
| 초록 | LOOTED (짧게) |
| 마젠타 `#FF00FF` | GOT_GOOP → 봇 중단 |

## 2. 파이썬

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

`bot/config.yaml` 에서 낚시 키, 신호 좌표, 찌 탐색 region, 입질 임계값을 맞춥니다.  
신호 `x: -4` 는 화면 오른쪽에서 4px 안쪽입니다.

### 찌 찾기

1. **낚시 훅 스티커** (`imgs/bobber_sticker.png`) — UI라 조명/지역에 거의 안 흔들림 (1순위)  
2. 시전 전후 **차분** + 색 점수  
3. `imgs/ref` **다중 스케일 템플릿** fallback  

로그에 `via sticker` / `diff` / `template` 이 찍힙니다.  
스티커를 못 찾으면 `sticker_confidence` 를 조금 낮추거나, 인게임 크기와 맞는 크롭으로 `bobber_sticker.png` 를 교체하세요.

## 3. 실행

와우를 포커스한 뒤:

```powershell
.\.venv\Scripts\python.exe -m bot.main
```

실행 중 화면에 박스가 표시됩니다.

- **청록** — 찌 탐색 범위  
- **초록** — 찾은 찌 (+ 십자)  
- **주황 점선** — 입질 감시 ROI  

끄려면 `debug_overlay: false` 또는 `--no-overlay`.

끈적이가 잡히면 콘솔에 `[STOP] Strange Goop (187662) looted` 를 찍고 종료합니다.  
`on_goop: log` 만 구현되어 있고, `shutdown` / `mail` 은 훅만 있습니다.
