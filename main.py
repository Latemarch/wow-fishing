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


time.sleep(2)

SEARCH_REGION = ftns.calibrateSearchRegion()
overlay_root, overlay_bars = create_search_border(SEARCH_REGION)

trycount = 0
failCount = 0
startedAt = time.time()
biteTime = time.time()
next_shutdown = ftns.get_next_kst_shutdown()
print(f"[session] will end at {next_shutdown.strftime('%Y-%m-%d %H:%M KST')}")

while True:
  if ftns.shutdown_if_kst_target(next_shutdown):
    break

  overlay_root.update()
  if ftns.findCenterGoop():
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    elapsed = int(time.time() - startedAt)
    print(f'[STOP] Strange Goop found  time={now}  elapsed={elapsed}s')
    break

  trycount += 1
  failCount += 1
  if failCount > 7:
    ftns.saveScreen('./imgs/fail.png')
    print("fail")
    os.system('shutdown -s -f')
    break
  print(trycount)

  biteTime = ftns.applybite('2',biteTime,600)

  time.sleep(1)
  pyautogui.moveTo(100,100)
  pyautogui.press('1')
  time.sleep(2)
  
  newImg, _, x, y = ftns.findFloat(0.55, SEARCH_REGION)

  if not newImg:
    continue

  failCount = 0
  if ftns.waitForSplash(timeout=14, on_tick=overlay_root.update):
    pyautogui.moveTo(x,y+120)
    time.sleep(0.1)
    pyautogui.click()
    time.sleep(1.0)
    overlay_root.update()
    if ftns.findCenterGoop():
      now = time.strftime('%Y-%m-%d %H:%M:%S')
      elapsed = int(time.time() - startedAt)
      print(f'[STOP] Strange Goop found  time={now}  elapsed={elapsed}s')
      break


