import pyautogui
import time
import ftns
import os
import tkinter as tk
import ctypes


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


def mark_consecutive_fail(fail_count, reason, limit=10):
  fail_count += 1
  print(f'[fish] consecutive fail {fail_count}/{limit} ({reason})')
  if fail_count >= limit:
    ftns.saveScreen('./imgs/fail.png')
    print("fail")
    os.system('shutdown -s -f')
    return fail_count, True
  return fail_count, False


time.sleep(2)

SEARCH_REGION = ftns.calibrateSearchRegion()
overlay_root, overlay_bars = create_search_border(SEARCH_REGION)

trycount = 0
consecutiveFails = 0
startedAt = time.time()
biteTime = time.time()
mail_cooldown_until = 0
lastFishCount = ftns.readFishCount()
if lastFishCount is None:
  lastFishCount = 0
print(f'[fish-count] baseline={lastFishCount}')
next_shutdown = ftns.get_next_kst_shutdown()
print(f"[session] will end at {next_shutdown.strftime('%Y-%m-%d %H:%M KST')}")

while True:
  if ftns.shutdown_if_kst_target(next_shutdown):
    break

  overlay_root.update()
  if time.time() >= mail_cooldown_until and ftns.findCenterGoop():
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    elapsed = int(time.time() - startedAt)
    print(f'[GOOP] found  time={now}  elapsed={elapsed}s')
    ftns.notifyTelegram(f'기묘한 끈적이 획득! time={now} elapsed={elapsed}s')
    if ftns.mailGoop():
      print('[GOOP] mailed, resume fishing')
      mail_cooldown_until = time.time() + 8
    else:
      print('[GOOP] mail failed, retry later')
      time.sleep(2)
    continue

  trycount += 1
  print(trycount)

  biteTime = ftns.applybite('2',biteTime,600)

  time.sleep(1)
  pyautogui.moveTo(100,100)
  pyautogui.press('1')
  time.sleep(2)
  
  newImg, _, x, y = ftns.findFloat(0.55, SEARCH_REGION)

  if not newImg:
    consecutiveFails, stop = mark_consecutive_fail(consecutiveFails, 'float_not_found')
    if stop:
      break
    continue

  if not ftns.waitForSplash(timeout=14, on_tick=overlay_root.update):
    continue

  pyautogui.moveTo(x,y+120)
  time.sleep(0.1)
  pyautogui.click()
  # 룻/가방 반영이 늦을 수 있어 여러 번 읽는다.
  fish_count = None
  for _ in range(6):
    time.sleep(0.45)
    overlay_root.update()
    fish_count = ftns.readFishCount()
    if fish_count is not None and fish_count > lastFishCount:
      break

  if fish_count is not None and fish_count > lastFishCount:
    print(f'[fish] success {lastFishCount} -> {fish_count}  consecutive fail reset')
    lastFishCount = fish_count
    consecutiveFails = 0
  else:
    stuck = lastFishCount if fish_count is None else fish_count
    print(
      f'[fish] count unchanged ({stuck}). '
      'GoopAlert FISH_ITEM_IDS에 없는 물고기이거나 룻 실패. /goopalert 로 확인'
    )
    consecutiveFails, stop = mark_consecutive_fail(consecutiveFails, f'count={stuck}')
    if stop:
      break
    continue

  overlay_root.update()
  if time.time() >= mail_cooldown_until and ftns.findCenterGoop():
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    elapsed = int(time.time() - startedAt)
    print(f'[GOOP] found  time={now}  elapsed={elapsed}s')
    ftns.notifyTelegram(f'기묘한 끈적이 획득! time={now} elapsed={elapsed}s')
    if ftns.mailGoop():
      print('[GOOP] mailed, resume fishing')
      mail_cooldown_until = time.time() + 8
    else:
      print('[GOOP] mail failed, retry later')
      time.sleep(2)
    continue


