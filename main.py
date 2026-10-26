import pyautogui
import time
import random
import ftns
import os
import tkinter as tk
import ctypes

end_time = 9999
limit = 10
interference_limit = 3  # 보라 방해 패턴 연속 감지 시 로그아웃

# 실패 한도(방해 포함) 도달 후, 로그아웃 전에 기다리는 시간
FAIL_LOGOUT_WAIT_MIN = 5
# 다음 캐릭이 마법사·주술사일 때 로그아웃 뒤 추가 대기(분)
RECONNECT_EXTRA_WAIT_MIN = (5, 10)
# m/s 방해 로그아웃 후 p 재접속까지 대기(분)
INTERFERENCE_PRIEST_WAIT_MIN = 1
# 사제 낚시 시간(시간). 끝나면 m 또는 s로 재접속
PRIEST_SESSION_HOURS = 2

CHAR_IMAGES = {
  'm': './imgs/mage.png',
  's': './imgs/shamon.png',
  'p': './imgs/priest.png',
}
# m 또는 s에서 로그아웃할 때 다음 캐릭 가중치
RECONNECT_WEIGHTS = (
  ('m', 4),
  ('s', 4),
  ('p', 2),
)
START_CHAR = 'm'


def create_search_border(region):
  """탐색 범위를 가리지 않는 초록색 닫힌 테두리를 표시한다."""
  try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
  except Exception:
    try:
      ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
      pass

  root = tk.Tk()
  root.withdraw()
  bars = []
  left, top, width, height = region
  thickness = 3

  edges = [
    (left, top, width, thickness),
    (left, top + height - thickness, width, thickness),
    (left, top, thickness, height),
    (left + width - thickness, top, thickness, height),
  ]

  for x, y, w, h in edges:
    bar = tk.Toplevel(root)
    bar.overrideredirect(True)
    bar.attributes('-topmost', True)
    bar.configure(bg='#00ff00')
    bar.geometry(f'{w}x{h}+{x}+{y}')
    bar.update_idletasks()

    # 마우스 클릭이 와우 창으로 통과하도록 설정한다.
    hwnd = bar.winfo_id()
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    ctypes.windll.user32.SetWindowLongW(
      hwnd, -20, style | 0x00000020 | 0x00000080
    )
    bars.append(bar)

  root.update()
  return root, bars


def set_overlay_visible(bars, visible, root=None):
  """끈적이 중앙 감지 시 초록 테두리가 가리지 않도록 숨긴다."""
  for bar in bars:
    if visible:
      bar.deiconify()
    else:
      bar.withdraw()
  if root is not None:
    root.update()


def check_goop_alert():
  """기묘한 끈적이만 우편 처리. 대해가오리는 여기 해당 없음.

  - 텔레그램은 1회만
  - 우편 실패해도 남아 있으면 낚시 없이 우편만 재시도
  """
  global mail_cooldown_until, goop_alerted

  if time.time() < mail_cooldown_until:
    return False

  set_overlay_visible(overlay_bars, False, overlay_root)
  time.sleep(0.08)
  item_name = ftns.findCenterGoop()
  set_overlay_visible(overlay_bars, True, overlay_root)

  if not item_name:
    goop_alerted = False
    return False

  if not goop_alerted:
    notify_goop_alert(
      startedAt, trycount, lastFishCount, consecutiveFails, next_shutdown,
      item_name=item_name,
    )
    goop_alerted = True
  else:
    print(f'[GOOP] still in bag ({item_name}) - skip fishing, retry mail')

  while True:
    if ftns.mailGoop():
      print('[GOOP] mailed, resume fishing')
      goop_alerted = False
      mail_cooldown_until = time.time() + 8
      return True

    set_overlay_visible(overlay_bars, False, overlay_root)
    time.sleep(0.08)
    still = ftns.findCenterGoop()
    set_overlay_visible(overlay_bars, True, overlay_root)
    if not still:
      print('[GOOP] no longer present - resume fishing')
      goop_alerted = False
      mail_cooldown_until = time.time() + 5
      return False

    print('[GOOP] mail failed — will retry, fishing blocked')
    time.sleep(4)


def check_ray_count():
  """대해가오리 개수 증가 시 텔레그램만 (우편 없음).

  겹치지 않으므로 보통 +1. 오독 방지: 연속 2회 동일 값 + 증가폭 1만 인정.
  """
  global lastRayCount
  ray_count = ftns.readRayCount()
  if ray_count is None:
    return
  if lastRayCount is None:
    lastRayCount = ray_count
    return

  if ray_count < lastRayCount:
    print(f'[ray] count dropped {lastRayCount} -> {ray_count} (baseline update)')
    lastRayCount = ray_count
    return

  if ray_count <= lastRayCount:
    return

  gained = ray_count - lastRayCount
  if gained != 1:
    print(
      f'[ray] reject suspicious gain +{gained} '
      f'({lastRayCount} -> {ray_count})'
    )
    return

  # 같은 값이 한 번 더 읽혀야 확정
  time.sleep(0.15)
  confirm = ftns.readRayCount()
  if confirm != ray_count:
    print(
      f'[ray] confirm mismatch first={ray_count} second={confirm} '
      f'(ignore)'
    )
    return

  print(f'[ray] +{gained}  {lastRayCount} -> {ray_count}')
  notify_ray_alert(
    startedAt, trycount, lastFishCount, consecutiveFails, next_shutdown,
    ray_count=ray_count, gained=gained,
  )
  lastRayCount = ray_count



def resume_after_reconnect():
  """재접속 후 낚시 상태를 새 캐릭터 기준으로 맞추고 루프를 이어간다."""
  global SEARCH_REGION, overlay_root, overlay_bars
  global consecutiveFails, interferenceFails, lastFishCount, biteTime
  global goop_alerted, mail_cooldown_until
  global next_shutdown, startedAt, trycount
  global next_vendor_sell_at, lastRayCount

  consecutiveFails = 0
  interferenceFails = 0
  goop_alerted = False
  mail_cooldown_until = 0
  next_vendor_sell_at = time.time() + 30 * 60
  biteTime = 0  # 재접속 직후 미끼(2)부터 다시
  trycount = 0
  startedAt = time.time()
  next_shutdown = ftns.get_next_kst_shutdown(end_time)

  ftns.focusWow()
  set_overlay_visible(overlay_bars, False, overlay_root)
  SEARCH_REGION = ftns.calibrateSearchRegion()
  overlay_root, overlay_bars = create_search_border(SEARCH_REGION)

  count = ftns.waitForWorldReady(timeout=20.0)
  if count is None:
    count = ftns.readFishCount()
  lastFishCount = 0 if count is None else count
  ray = ftns.readRayCount()
  lastRayCount = 0 if ray is None else ray
  print(f'[fish-count] baseline after reconnect={lastFishCount}')
  print(f'[ray-count] baseline after reconnect={lastRayCount}')
  print(f"[session] resume fishing until {next_shutdown.strftime('%Y-%m-%d %H:%M KST')}")


def sell_junk_now():
  """잡템을 팔고 다음 판매 시각을 30분 뒤로 민다."""
  global next_vendor_sell_at
  ftns.sellAllJunk()
  next_vendor_sell_at = time.time() + 30 * 60
  print('[vendor] next sell-all-junk in 30min')


def _wait_minutes(minutes, label):
  """대기 중 오버레이를 갱신한다. 세션 종료 시각이면 False."""
  deadline = time.time() + minutes * 60
  print(f'[session] {label} {minutes}min')
  while time.time() < deadline:
    if ftns.shutdown_if_kst_target(next_shutdown):
      return False
    overlay_root.update()
    time.sleep(1)
  return True


def _pick_next_char(leaving, reason):
  """다음 캐릭터와 로그아웃 뒤 추가 대기(분)를 정한다."""
  if reason.startswith('interference') and leaving in ('m', 's'):
    return 'p', INTERFERENCE_PRIEST_WAIT_MIN
  if reason == 'priest_2h':
    return random.choice(('m', 's')), 0
  if leaving == 'p':
    return 'm', 0
  names, weights = zip(*RECONNECT_WEIGHTS)
  picked = random.choices(names, weights=weights, k=1)[0]
  if picked == 'p':
    return picked, 0
  lo, hi = RECONNECT_EXTRA_WAIT_MIN
  return picked, random.randint(lo, hi)


def reconnect(reason):
  """로그아웃과 재접속을 한 곳에서 처리한다. True면 낚시를 이어간다.

  실패 한도: 5분 대기 후 로그아웃.
  m/s에서 방해 한도면 5분 뒤 로그아웃하고 1분 후 p로 접속. p는 PRIEST_SESSION_HOURS 뒤 m 또는 s.
  그 외 m/s 로그아웃은 m4:s4:p2.
  p면 바로 접속, m/s면 5–10분 더 기다린 뒤 접속.
  """
  global current_char, priest_until, reconnect_count

  leaving = current_char
  failure = reason != 'priest_2h'
  if failure:
    if not _wait_minutes(FAIL_LOGOUT_WAIT_MIN, '실패 한도, 로그아웃 전 대기'):
      return False

  next_name, extra_wait = _pick_next_char(leaving, reason)
  next_image = CHAR_IMAGES[next_name]
  elapsed = format_elapsed(time.time() - startedAt)
  print(
    f'[session] reconnect {leaving} -> {next_name} '
    f'reason={reason} extra_wait={extra_wait}min'
  )
  ftns.notifyTelegram(
    '낚시 중단 - 캐릭터 선택으로 이동합니다\n'
    f'시간: {ftns.now_kst_str()}\n'
    f'경과: {elapsed}\n'
    f'원인: {reason}\n'
    f'{leaving} → {next_name}\n'
    f'로그아웃 후 추가 대기: {extra_wait}분\n'
    f'재접속 #{reconnect_count + 1}'
  )
  ftns.saveScreen('./imgs/fail.png')
  ftns.logoutWow('3')

  if not ftns.reconnectAfterFail(
    image=next_image,
    wait_minutes=extra_wait,
    char_name=next_name,
    keep_alive_every_min=5,
  ):
    print('[session] reconnect failed - stop all')
    ftns.notifyTelegram(
      f'재접속 실패 ({next_name})\n시간: {ftns.now_kst_str()}\n원인: {reason}'
    )
    return False

  resume_after_reconnect()
  current_char = next_name
  reconnect_count += 1
  if next_name == 'p':
    priest_until = time.time() + PRIEST_SESSION_HOURS * 3600
    print(f'[session] priest fishes for {PRIEST_SESSION_HOURS}h')
    sell_junk_now()
  else:
    priest_until = None
  ftns.notifyTelegram(
    f'낚시 재개 ({next_name})\n'
    f'시간: {ftns.now_kst_str()}\n'
    f'재접속 횟수={reconnect_count}\n'
    f'기준 합계={lastFishCount}\n'
    f'세션 종료 예정={next_shutdown.strftime("%Y-%m-%d %H:%M KST")}'
  )
  return True


def mark_consecutive_fail(fail_count, reason, limit=limit):
  fail_count += 1
  print(f'[fish] consecutive fail {fail_count}/{limit} ({reason})')
  if fail_count >= limit:
    return fail_count, reason
  return fail_count, None


def mark_interference_fail(fail_count, ratio, limit=interference_limit):
  """보라 방해 패턴 연속 감지. 한도 도달 시 재접속."""
  fail_count += 1
  print(f'[interference] consecutive {fail_count}/{limit} (purple_ratio={ratio:.3f})')
  if fail_count >= limit:
    return fail_count, f'interference x{limit}'
  return fail_count, None


def format_elapsed(seconds):
  seconds = max(0, int(seconds))
  hours, rem = divmod(seconds, 3600)
  minutes, secs = divmod(rem, 60)
  if hours:
    return f'{hours}h {minutes}m {secs}s'
  if minutes:
    return f'{minutes}m {secs}s'
  return f'{secs}s'


def notify_goop_alert(
  started_at, trycount, fish_count, consecutive_fails, next_shutdown,
  item_name='기묘한 끈적이',
):
  now = ftns.now_kst_str()
  elapsed_sec = time.time() - started_at
  elapsed = format_elapsed(elapsed_sec)
  msg = (
    f'{item_name} 획득!\n'
    f'시간: {now}\n'
    f'경과: {elapsed} ({int(elapsed_sec)}초)\n'
    f'캐스트 시도: {trycount}회\n'
    f'낚시 합계: {fish_count}\n'
    f'연속 실패: {consecutive_fails}\n'
    f'세션 종료 예정: {next_shutdown.strftime("%Y-%m-%d %H:%M KST")}'
  )
  print(f'[GOOP] {item_name}  time={now}  elapsed={elapsed}  casts={trycount}')
  ftns.notifyTelegram(msg)


def notify_ray_alert(
  started_at, trycount, fish_count, consecutive_fails, next_shutdown,
  ray_count, gained=1,
):
  now = ftns.now_kst_str()
  elapsed_sec = time.time() - started_at
  elapsed = format_elapsed(elapsed_sec)
  msg = (
    f'대해가오리 획득! (+{gained})\n'
    f'대해가오리 합계: {ray_count}\n'
    f'시간: {now}\n'
    f'경과: {elapsed} ({int(elapsed_sec)}초)\n'
    f'캐스트 시도: {trycount}회\n'
    f'낚시 합계: {fish_count}\n'
    f'연속 실패: {consecutive_fails}\n'
    f'세션 종료 예정: {next_shutdown.strftime("%Y-%m-%d %H:%M KST")}'
  )
  print(f'[ray] 대해가오리 +{gained} total={ray_count} time={now}')
  ftns.notifyTelegram(msg)


time.sleep(2)

SEARCH_REGION = ftns.calibrateSearchRegion()
overlay_root, overlay_bars = create_search_border(SEARCH_REGION)

trycount = 0
consecutiveFails = 0
interferenceFails = 0
reconnect_count = 0
current_char = START_CHAR
priest_until = None
startedAt = time.time()
biteTime = time.time()
mail_cooldown_until = 0
goop_alerted = False
next_vendor_sell_at = time.time() + 30 * 60
lastFishCount = ftns.readFishCount()
if lastFishCount is None:
  lastFishCount = 0
print(f'[fish-count] baseline={lastFishCount}')
lastRayCount = ftns.readRayCount()
if lastRayCount is None:
  lastRayCount = 0
print(f'[ray-count] baseline={lastRayCount}')
ftns.preloadEasyOcrAsync()
next_shutdown = ftns.get_next_kst_shutdown(end_time)
print(f"[session] will end at {next_shutdown.strftime('%Y-%m-%d %H:%M KST')}")
print(f'[session] start character={current_char}')
if current_char == 'p':
  priest_until = time.time() + PRIEST_SESSION_HOURS * 3600
  print(f'[session] priest fishes for {PRIEST_SESSION_HOURS}h')
  sell_junk_now()
else:
  print(f'[vendor] next sell-all-junk in 30min')

while True:
  if ftns.shutdown_if_kst_target(next_shutdown):
    break

  if (
    current_char == 'p'
    and priest_until is not None
    and time.time() >= priest_until
  ):
    if reconnect('priest_2h'):
      continue
    break

  overlay_root.update()

  trycount += 1
  print(trycount)

  biteTime = ftns.applybite('2',biteTime,600)

  time.sleep(1)
  pyautogui.moveTo(100,100)
  pyautogui.press('1')
  time.sleep(2)

  # 검색 스코프에 보라 방해 패턴이 있으면 연속 카운트
  set_overlay_visible(overlay_bars, False, overlay_root)
  time.sleep(0.05)
  interfered, purple_ratio, _purple_n = ftns.detectPurpleInterference(SEARCH_REGION)
  set_overlay_visible(overlay_bars, True, overlay_root)
  if interfered:
    interferenceFails, stop = mark_interference_fail(interferenceFails, purple_ratio)
    if stop:
      if reconnect(stop):
        continue
      break
    continue
  interferenceFails = 0

  newImg, _, x, y = ftns.findFloat(0.55, SEARCH_REGION)

  if not newImg:
    consecutiveFails, stop = mark_consecutive_fail(consecutiveFails, 'float_not_found')
    if stop:
      if reconnect(stop):
        continue
      break
    continue

  if not ftns.waitForSplash(timeout=22, on_tick=overlay_root.update):
    consecutiveFails, stop = mark_consecutive_fail(consecutiveFails, 'splash_timeout')
    if stop:
      if reconnect(stop):
        continue
      break
    continue
  pyautogui.click()
  pyautogui.moveTo(x+10,y+70)
  time.sleep(0.1)
  pyautogui.click()
  pyautogui.moveTo(x+10,y+110)
  time.sleep(0.1)
  pyautogui.click()

  pyautogui.click()
  # OCR은 백그라운드 — 낚시는 기다리지 않음
  ftns.ocrChatWindowAsync(delay=0.8)

  # 막대 반영용 짧은 대기 (OCR 대기 아님)
  time.sleep(1.0)
  overlay_root.update()
  fish_count = ftns.readFishCount()
  prev_ray = lastRayCount
  check_ray_count()
  ray_gained = lastRayCount is not None and prev_ray is not None and lastRayCount > prev_ray

  if lastFishCount is not None and fish_count is not None and fish_count > lastFishCount:
    print(
      f'[fish] success {lastFishCount} -> {fish_count}  '
      f'consecutive fail reset'
    )
    lastFishCount = fish_count
    consecutiveFails = 0
    interferenceFails = 0
  elif ray_gained:
    # 대해가오리만 잡혀도 낚시 실패로 치지 않음
    print('[fish] no fish gain but ray gained - fail not counted')
    consecutiveFails = 0
    interferenceFails = 0
  else:
    stuck = lastFishCount if fish_count is None else fish_count
    print(
      f'[fish] count unchanged ({stuck}). '
      'GoopAlert 기준 증가 없음 — 룻 실패 또는 미등록 아이템'
    )
    consecutiveFails, stop = mark_consecutive_fail(consecutiveFails, f'count={stuck}')
    if stop:
      if reconnect(stop):
        continue
      break

  # 30분마다 회색 잡템 상인 판매 (4 → 중앙+20 → 1초 → 6)
  if time.time() >= next_vendor_sell_at:
    sell_junk_now()

  # 끈적이만 우편 (대해가오리는 우편 없음)
  if check_goop_alert():
    continue


