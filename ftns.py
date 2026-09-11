import os
import time
import cv2
import numpy as np
import pyautogui
import random
from datetime import datetime, timedelta, timezone

try:
  from zoneinfo import ZoneInfo
  KST = ZoneInfo("Asia/Seoul")
except Exception:
  KST = timezone(timedelta(hours=9))


def calibrateSearchRegion():
  """WoW 창 위치/크기를 기준으로 찌 탐색 범위를 한 번 계산한다."""
  screen_width, screen_height = pyautogui.size()
  game_left = 0
  game_top = 0
  game_width = screen_width
  game_height = screen_height
  source = 'screen'

  try:
    import pygetwindow

    title_keywords = ('world of warcraft', '월드 오브 워크래프트')
    windows = [
      window for window in pygetwindow.getAllWindows()
      if window.visible
      and window.width > 400
      and window.height > 300
      and any(keyword in window.title.lower() for keyword in title_keywords)
    ]
    if windows:
      game_window = max(windows, key=lambda window: window.width * window.height)
      game_left = int(game_window.left)
      game_top = int(game_window.top)
      game_width = int(game_window.width)
      game_height = int(game_window.height)
      source = game_window.title
  except Exception as error:
    print(f'[calibration] WoW window lookup failed: {error}')

  # 크기만 기존 비율을 쓰고, 너비는 절반, 위치는 정중앙에서 위로 20% 이동한다.
  width = max(1, round(game_width * (550 / 1920) / 2))
  height = max(1, round(game_height * (450 / 1080)))
  left = game_left + (game_width - width) // 2
  top = game_top + (game_height - height) // 2
  top -= round(game_height * 0.20)

  right_limit = game_left + game_width
  bottom_limit = game_top + game_height
  left = max(game_left, min(left, right_limit - width))
  top = max(game_top, min(top, bottom_limit - height))
  width = max(1, min(width, right_limit - left))
  height = max(1, min(height, bottom_limit - top))

  region = (left, top, width, height)
  print(
    f'[calibration] source={source!r} '
    f'window=({game_left}, {game_top}, {game_width}, {game_height}) '
    f'search={region}'
  )
  return region


def _wow_window_rect():
  """WoW 창 사각형을 찾는다. 실패하면 전체 화면을 쓴다."""
  screen_width, screen_height = pyautogui.size()
  try:
    import pygetwindow

    title_keywords = ('world of warcraft', '월드 오브 워크래프트')
    windows = [
      window for window in pygetwindow.getAllWindows()
      if window.visible
      and window.width > 400
      and window.height > 300
      and any(keyword in window.title.lower() for keyword in title_keywords)
    ]
    if windows:
      game_window = max(windows, key=lambda window: window.width * window.height)
      return (
        int(game_window.left),
        int(game_window.top),
        int(game_window.width),
        int(game_window.height),
      )
  except Exception:
    pass
  return (0, 0, screen_width, screen_height)


def readFishCount():
  """우측 상단 에드온 막대에서 낚시 아이템 총개수를 읽는다. 1000개 묶음도 합산값이다."""
  start_rgb = np.array([255, 0, 80], dtype=np.int16)
  end_rgb = np.array([0, 255, 80], dtype=np.int16)
  bits = 20
  left, top, width, height = _wow_window_rect()
  strip_w = max(420, int(round(width * 0.42)))
  strip_h = max(70, int(round(height * 0.16)))
  region_left = max(0, left + width - strip_w)
  region = (region_left, max(0, top), strip_w, strip_h)
  screenshot = pyautogui.screenshot(region=region)
  img = np.array(screenshot)
  if img.size == 0:
    print('[fish-count] empty screenshot')
    return None

  start_dist = np.linalg.norm(img.astype(np.int16) - start_rgb, axis=2)
  end_dist = np.linalg.norm(img.astype(np.int16) - end_rgb, axis=2)
  start_pts = np.argwhere(start_dist < 55)
  end_pts = np.argwhere(end_dist < 55)
  if start_pts.size == 0 or end_pts.size == 0:
    print('[fish-count] bar not found (GoopAlert 설치/리로드 확인)')
    return None

  start_y, start_x = start_pts.mean(axis=0)
  end_y, end_x = end_pts.mean(axis=0)
  if end_x - start_x < bits:
    print('[fish-count] bar too short')
    return None

  count = 0
  row = int(round((start_y + end_y) / 2))
  row = min(max(0, row), img.shape[0] - 1)
  for i in range(bits):
    col = int(round(start_x + (i + 1) * (end_x - start_x) / (bits + 1)))
    col = min(max(0, col), img.shape[1] - 1)
    luminance = float(img[row, col].mean())
    if luminance >= 120:
      count += 1 << i
  print(f'[fish-count] {count}')
  return count


# def getFloats(length):
#   imgs=[]
#   for i in range(length):
#     imgs.append(cv2.imread('./imgs/ref/%02d.png' % i))
#   return  imgs

def getFloats(length=None):
  imgs = []
  ref_dir = './imgs/ref'
  if not os.path.isdir(ref_dir):
    return imgs

  # 번호가 중간에 빠져 있어도 실제 존재하는 PNG만 읽는다.
  png_files = sorted(
    f for f in os.listdir(ref_dir)
    if f.lower().endswith('.png')
  )
  if length is not None:
    png_files = png_files[:length]

  for filename in png_files:
    img = cv2.imread(os.path.join(ref_dir, filename))
    if img is not None:
      imgs.append(img)

  return imgs

import pyautogui


def _sticker_template_and_mask(path='./imgs/bobber_sticker.png'):
  """훅만 매칭하도록 템플릿+마스크를 만든다.

  bobber_sticker.png 배경이 불투명 회색-파란색이라 낚시터 물이 바뀌면
  locateOnScreen이 실패한다. 알파가 있으면 그걸 쓰고, 없으면 모서리 배경을 제외한다.
  """
  img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
  if img is None:
    raise FileNotFoundError(path)

  if img.ndim == 2:
    bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    mask = np.full(img.shape, 255, dtype=np.uint8)
  elif img.shape[2] == 4 and int(img[:, :, 3].min()) < 255:
    bgr = img[:, :, :3]
    mask = (img[:, :, 3] > 128).astype(np.uint8) * 255
  else:
    bgr = img[:, :, :3] if img.ndim == 3 else img
    h, w = bgr.shape[:2]
    corners = np.concatenate([
      bgr[0:3, 0:3].reshape(-1, 3),
      bgr[0:3, w - 3:w].reshape(-1, 3),
      bgr[h - 3:h, 0:3].reshape(-1, 3),
      bgr[h - 3:h, w - 3:w].reshape(-1, 3),
    ])
    bg = corners.mean(axis=0)
    diff = np.linalg.norm(bgr.astype(np.float32) - bg, axis=2)
    mask = (diff > 25).astype(np.uint8) * 255

  if cv2.countNonZero(mask) == 0:
    mask = np.full(bgr.shape[:2], 255, dtype=np.uint8)
  return bgr, mask


def findFloat(confidence, region=(1010, 435, 550, 450)):
  """탐색 범위 안에서 bobber_sticker를 여러 배율·배경마스크로 찾는다."""
  left, top, width, height = [int(v) for v in region]
  try:
    template, mask = _sticker_template_and_mask()
  except FileNotFoundError:
    print('[findFloat] sticker template missing')
    return None, None, 0, 0

  screenshot = pyautogui.screenshot(region=(left, top, width, height))
  haystack = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

  best_score = -1.0
  best_loc = None
  best_size = None
  for scale in (0.6, 0.75, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0):
    tw = max(1, int(round(template.shape[1] * scale)))
    th = max(1, int(round(template.shape[0] * scale)))
    if tw >= width or th >= height:
      continue

    scaled = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA)
    scaled_mask = cv2.resize(mask, (tw, th), interpolation=cv2.INTER_NEAREST)
    if cv2.countNonZero(scaled_mask) == 0:
      continue

    result = cv2.matchTemplate(
      haystack, scaled, cv2.TM_CCORR_NORMED, mask=scaled_mask
    )
    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
    if max_val > best_score:
      best_score = float(max_val)
      best_loc = max_loc
      best_size = (tw, th)

  if best_loc is None or best_score < confidence:
    print(f'[findFloat] no match (best={best_score:.3f}, need>={confidence})')
    return None, None, 0, 0

  x = left + int(best_loc[0])
  y = top + int(best_loc[1])
  tw, th = best_size
  cx, cy = x + tw // 2, y + th // 2
  print(f'[findFloat] match={best_score:.3f} at ({x},{y}) size={best_size} center=({cx},{cy})')

  newImg = saveImg('./imgs/im1.png', x, y)
  pyautogui.moveTo(cx, cy)
  behavior = saveBehavior('./imgs/behavior.png', x, y)
  return newImg, behavior, x, y


# def findTargetItem(item,shutDown = False):
#   pyautogui.screenshot('./imgs/item1.png', region=(1225,475,100,100))
#   item_= pyautogui.locateOnScreen(item,
#       confidence=0.4, 
#       region = (1225,475,100,100)
#       )
#   if item_:
#     print('I got the item!')
#     # if shutDown: os.system('shutdown -s -f')
#     return True
#   return False
def findCenterGoop(image='./imgs/goop.png', confidence=0.82, size=None):
    """화면 중앙에서 기묘한 끈적이 아이콘을 찾는다."""
    screen_width, screen_height = pyautogui.size()
    if size is None:
        size = max(160, int(round(220 * screen_height / 1080.0)))
    left = max(0, screen_width // 2 - size // 2)
    top = max(0, screen_height // 2 - size // 2)
    width = min(size, screen_width - left)
    height = min(size, screen_height - top)
    found = _match_template(
        image,
        region=(left, top, width, height),
        confidence=confidence,
        scales=_ui_scales_tight(),
    )
    if found is None or found[0] is None:
        return False
    print(f'[GOOP] center match score={found[1]:.3f} scale={found[2]:.2f}')
    return True


def _load_dotenv(path='.env'):
  """간단한 KEY=VALUE .env 로더 (python-dotenv 없이)."""
  if not os.path.isfile(path):
    return
  try:
    with open(path, encoding='utf-8') as f:
      for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
          continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
          os.environ[key] = value
  except OSError as error:
    print(f'[telegram] .env read failed: {error}')


def notifyTelegram(text, token=None, chat_id=None):
  """텔레그램으로 텍스트를 보낸다. 성공 시 True.

  환경변수 또는 .env:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
  """
  import json
  import urllib.error
  import urllib.parse
  import urllib.request

  _load_dotenv()
  token = token or os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
  chat_id = chat_id or os.environ.get('TELEGRAM_CHAT_ID', '').strip()
  if not token or not chat_id or not chat_id.lstrip('-').isdigit():
    print('[telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 필요합니다')
    return False

  url = f'https://api.telegram.org/bot{token}/sendMessage'
  payload = urllib.parse.urlencode({
    'chat_id': chat_id,
    'text': text,
  }).encode('utf-8')
  req = urllib.request.Request(url, data=payload, method='POST')
  try:
    with urllib.request.urlopen(req, timeout=10) as resp:
      body = json.loads(resp.read().decode('utf-8'))
    if body.get('ok'):
      print('[telegram] sent')
      return True
    print(f'[telegram] api error: {body}')
    return False
  except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
    print(f'[telegram] send failed: {error}')
    return False


def findLootNearCursor(image='./imgs/loot_header.png', confidence=0.78, appear_after=0.2, visible_until=1.15):
  """자동획득 시 클릭 후 0.3~1초만 보이는 전리품 창을 빠르게 폴링한다."""
  if not os.path.isfile(image) and os.path.isfile('./imgs/loot.png'):
    image = './imgs/loot.png'
  template = cv2.imread(image)
  if template is None:
    print(f'[loot] template missing: {image}')
    return False

  mx, my = pyautogui.position()
  screen_width, screen_height = pyautogui.size()
  pad_x = max(220, int(round(340 * screen_width / 1920.0)))
  pad_y = max(140, int(round(200 * screen_height / 1080.0)))
  left = max(0, mx - pad_x)
  top = max(0, my - pad_y)
  width = min(screen_width - left, pad_x * 2)
  height = min(screen_height - top, pad_y * 2)
  region = (left, top, width, height)

  expected = screen_height / 1080.0
  scaled_templates = []
  for factor in (0.85, 1.0, 1.2):
    scale = expected * factor
    scaled, tw, th = _resize_template(template, scale)
    if tw < width and th < height:
      scaled_templates.append((scaled, tw, th, scale))
  if not scaled_templates:
    return False

  if appear_after > 0:
    time.sleep(appear_after)
  deadline = time.time() + max(0.05, visible_until - appear_after)
  best_score = -1.0
  while time.time() < deadline:
    screenshot = pyautogui.screenshot(region=region)
    haystack = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    hh, hw = haystack.shape[:2]
    for scaled, tw, th, scale in scaled_templates:
      if tw >= hw or th >= hh:
        continue
      result = cv2.matchTemplate(haystack, scaled, cv2.TM_CCOEFF_NORMED)
      _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
      if max_val > best_score:
        best_score = float(max_val)
      if max_val >= confidence:
        cx = left + int(max_loc[0]) + tw // 2
        cy = top + int(max_loc[1]) + th // 2
        print(f'[loot] found score={max_val:.3f} scale={scale:.2f} at ({cx},{cy})')
        return True
  print(f'[loot] not found best={best_score:.3f} need>={confidence}')
  return False


def _mail_region():
  """우편함 창은 화면 왼쪽 0~30%에 열린다."""
  screen_width, screen_height = pyautogui.size()
  width = max(1, int(screen_width * 0.3))
  return (0, 0, width, screen_height)


def _ui_scales():
  """해상도·UI 배율이 달라도 잡히도록 템플릿 축소/확대 비율을 만든다."""
  _screen_width, screen_height = pyautogui.size()
  expected = screen_height / 1080.0
  scales = list(np.linspace(0.45, 2.4, 20))
  scales.extend(np.linspace(expected * 0.65, expected * 1.4, 10))
  unique = sorted(set(float(round(scale, 3)) for scale in scales))
  return tuple(scale for scale in unique if 0.4 <= scale <= 2.8)


def _ui_scales_tight():
  """중앙 알림 아이콘용. 배율을 너무 넓히면 물/배경을 끈적이로 오인한다."""
  _screen_width, screen_height = pyautogui.size()
  expected = screen_height / 1080.0
  scales = [expected * factor for factor in (0.8, 0.9, 1.0, 1.1, 1.25, 1.4)]
  return tuple(float(round(scale, 3)) for scale in scales if 0.55 <= scale <= 2.2)


def _resize_template(template, scale):
  tw = max(1, int(round(template.shape[1] * scale)))
  th = max(1, int(round(template.shape[0] * scale)))
  interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
  return cv2.resize(template, (tw, th), interpolation=interpolation), tw, th


def _match_template(path, region=None, confidence=0.72, scales=None, mask_center=0):
  """템플릿을 여러 배율로 찾아 중심 좌표를 반환한다."""
  if scales is None:
    scales = _ui_scales()
  template = cv2.imread(path)
  if template is None:
    print(f'[mail] template missing: {path}')
    return None

  if region is None:
    screenshot = pyautogui.screenshot()
    origin = (0, 0)
  else:
    screenshot = pyautogui.screenshot(region=region)
    origin = (int(region[0]), int(region[1]))
  haystack = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
  if mask_center > 0:
    screen_width, screen_height = pyautogui.size()
    cx = screen_width // 2 - origin[0]
    cy = screen_height // 2 - origin[1]
    x0 = max(0, cx - mask_center)
    y0 = max(0, cy - mask_center)
    x1 = min(haystack.shape[1], cx + mask_center)
    y1 = min(haystack.shape[0], cy + mask_center)
    haystack[y0:y1, x0:x1] = 0
  hh, hw = haystack.shape[:2]

  best_score = -1.0
  best_center = None
  best_scale = 1.0
  for scale in scales:
    scaled, tw, th = _resize_template(template, scale)
    if tw >= hw or th >= hh:
      continue
    result = cv2.matchTemplate(haystack, scaled, cv2.TM_CCOEFF_NORMED)
    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
    if max_val > best_score:
      best_score = float(max_val)
      best_scale = scale
      best_center = (
        origin[0] + int(max_loc[0]) + tw // 2,
        origin[1] + int(max_loc[1]) + th // 2,
      )

  if best_center is None or best_score < confidence:
    return None, best_score, best_scale
  return best_center, best_score, best_scale


def _wait_match(path, region=None, confidence=0.72, timeout=5.0):
  deadline = time.time() + timeout
  best = None
  while time.time() < deadline:
    found = _match_template(path, region=region, confidence=confidence)
    if found is None:
      return None
    if found[0] is not None:
      return found
    if best is None or found[1] > best[1]:
      best = found
    time.sleep(0.25)
  if best is not None:
    print(f'[mail] no match {path} best={best[1]:.3f} scale={best[2]:.2f} need>={confidence}')
  return None


def _paste_text(text):
  """한글은 키 이벤트로 입력되지 않아서 클립보드로 붙여넣는다."""
  import ctypes

  cf_unicodetext = 13
  gmem_moveable = 0x0002
  user32 = ctypes.windll.user32
  kernel32 = ctypes.windll.kernel32
  kernel32.GlobalAlloc.restype = ctypes.c_void_p
  kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
  kernel32.GlobalLock.restype = ctypes.c_void_p
  kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
  user32.SetClipboardData.argtypes = (ctypes.c_uint, ctypes.c_void_p)
  user32.SetClipboardData.restype = ctypes.c_void_p

  payload = text.encode('utf-16-le') + b'\x00\x00'
  handle = kernel32.GlobalAlloc(gmem_moveable, len(payload))
  locked = kernel32.GlobalLock(handle)
  ctypes.memmove(locked, payload, len(payload))
  kernel32.GlobalUnlock(handle)

  opened = False
  for _ in range(8):
    if user32.OpenClipboard(None):
      opened = True
      break
    time.sleep(0.05)
  if not opened:
    print('[mail] clipboard open failed')
    return False

  user32.EmptyClipboard()
  user32.SetClipboardData(cf_unicodetext, handle)
  user32.CloseClipboard()
  time.sleep(0.1)
  pyautogui.hotkey('ctrl', 'v')
  return True


def _find_bag_goop(image='./imgs/goop.png', confidence=0.7, center_skip=None):
  """가방의 끈적이를 찾는다. 화면 중앙 알림 아이콘은 건너뛴다."""
  _screen_width, screen_height = pyautogui.size()
  if center_skip is None:
    center_skip = max(80, int(round(150 * screen_height / 1080.0)))
  found = _match_template(
    image,
    confidence=confidence,
    mask_center=center_skip,
  )
  if found is None or found[0] is None:
    return None
  return found[0]


def mailGoop(recipient='황장수'):
  """끈적이를 우편으로 보내고 True/False를 반환한다."""
  print('[mail] summon mailbox')
  pyautogui.press('5')
  time.sleep(1.8)

  screen_width, screen_height = pyautogui.size()
  pyautogui.click(screen_width // 2, screen_height // 2)
  time.sleep(1.0)

  mail_region = _mail_region()
  print(f'[mail] search region={mail_region}')
  tab = _wait_match('./imgs/sending_tab.png', region=mail_region, timeout=6)
  if tab is None:
    print('[mail] send tab not found')
    return False
  pyautogui.click(tab[0])
  print(f'[mail] clicked send tab score={tab[1]:.3f} scale={tab[2]:.2f}')
  time.sleep(0.4)

  if not _paste_text(recipient):
    return False
  time.sleep(0.25)
  pyautogui.press('enter')
  time.sleep(0.5)

  goop = _find_bag_goop()
  if goop is None:
    pyautogui.press('b')
    time.sleep(0.7)
    goop = _find_bag_goop()
  if goop is None:
    print('[mail] goop not found in bags')
    return False
  pyautogui.moveTo(goop[0], goop[1])
  time.sleep(0.1)
  pyautogui.click(button='right')
  print(f'[mail] attached goop at {goop}')
  time.sleep(0.6)

  send = _wait_match('./imgs/sending_button.png', region=mail_region, timeout=5)
  if send is None:
    print('[mail] send button not found')
    return False
  pyautogui.click(send[0])
  print(f'[mail] clicked send score={send[1]:.3f} scale={send[2]:.2f}')
  time.sleep(1.2)
  pyautogui.press('esc')
  time.sleep(0.4)
  print('[mail] done')
  return True


def findTargetItem(item, shutDown=False):
    pyautogui.screenshot('./imgs/item1.png', region=(1225, 475, 100, 100))
    try:
        item_ = pyautogui.locateOnScreen(item, confidence=0.7, region=(1225, 475, 100, 100))
        if item_:
            print('I got the item!')
            if shutDown:
                os.system('shutdown -s -f')
            return True
    except pyautogui.ImageNotFoundException:
        return False
    return False

def compareImgHist(img,img2,index):
  hist1 = cvtImg(img)
  hist2 = cvtImg(img2)
  ret = cv2.compareHist(hist1,hist2,index)
  # ret = ret/np.sum(hist1)
  return ret
def compareImg(img,img2):
  return np.sum(cv2.absdiff(
      np.array(img),np.array(img2)
      ))/100000

def cvtImg(img):
  hsv = cv2.cvtColor(np.array(img),cv2.COLOR_BGR2HSV)
  hist = cv2.calcHist([hsv], [0, 1], None, [180, 256], [0, 180, 0, 256])
  cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
  return hist

# def saveImg(location,x,y):
#   return pyautogui.screenshot(location, region=(x,y-5,80,80))

def saveImg(location, x, y):
    # Ensure x and y are integers, and cast them if needed
    x, y = int(x), int(y)
    
    # Capture the screenshot with the given region
    return pyautogui.screenshot(location, region=(x, y - 5, 100, 80))
def saveBehavior(location, x, y):
    # Ensure x and y are integers, and cast them if needed
    x, y = int(x), int(y)
    
    # Capture the screenshot with the given region
    return pyautogui.screenshot(location, region=(x, y - 5, 80, 80))

def saveScreen(location):
    return pyautogui.screenshot(location)

def applybite(key,lastApplyingTime,interval):
  if time.time()-lastApplyingTime > interval:
    pyautogui.press(key)
    time.sleep(1)
    return time.time()
  return lastApplyingTime


SPLASH_REF_PATH = './sounds/splash.wav'


def _default_loopback_mic():
  """Windows 기본 재생 장치의 WASAPI 루프백을 연다."""
  import soundcard as sc

  speaker = sc.default_speaker()
  if speaker is None:
    raise RuntimeError('default speaker not found')
  mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
  if mic is None:
    raise RuntimeError(f'loopback for default speaker not found: {speaker.name}')
  return speaker, mic


def _to_mono(samples):
  samples = np.asarray(samples, dtype=np.float32)
  if samples.ndim > 1:
    return samples.mean(axis=1)
  return samples


def _splash_band_energy(samples, samplerate, low_hz=800, high_hz=6500):
  samples = _to_mono(samples)
  windowed = samples * np.hanning(len(samples)).astype(np.float32)
  spectrum = np.abs(np.fft.rfft(windowed))
  freqs = np.fft.rfftfreq(len(samples), 1.0 / samplerate)
  band = spectrum[(freqs >= low_hz) & (freqs <= high_hz)]
  if band.size == 0:
    return 0.0
  return float(np.mean(band * band))


def _log_spectrum(samples, samplerate, low_hz=400, high_hz=8000, bins=128):
  """입질음 지문: 해당 대역 로그 스펙트럼을 정규화한다."""
  samples = _to_mono(samples)
  if samples.size < 256:
    return None
  windowed = samples * np.hanning(len(samples)).astype(np.float32)
  spectrum = np.abs(np.fft.rfft(windowed))
  freqs = np.fft.rfftfreq(len(samples), 1.0 / samplerate)
  mask = (freqs >= low_hz) & (freqs <= high_hz)
  band = spectrum[mask]
  if band.size < 8:
    return None
  # 길이가 다른 클립도 같은 지문으로 맞춘다.
  xs = np.linspace(0, 1, band.size)
  band = np.interp(np.linspace(0, 1, bins), xs, band)
  band = np.log1p(band)
  norm = float(np.linalg.norm(band))
  if norm < 1e-8:
    return None
  return (band / norm).astype(np.float32)


def _cosine(a, b):
  if a is None or b is None or a.shape != b.shape:
    return 0.0
  return float(np.dot(a, b))


def _save_wav(path, samples, samplerate):
  import wave

  samples = _to_mono(samples)
  peak = float(np.max(np.abs(samples))) if samples.size else 0.0
  if peak > 1e-6:
    samples = samples / peak * 0.9
  pcm = np.clip(samples, -1.0, 1.0)
  pcm = (pcm * 32767.0).astype(np.int16)
  folder = os.path.dirname(path)
  if folder:
    os.makedirs(folder, exist_ok=True)
  with wave.open(path, 'wb') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(int(samplerate))
    wav.writeframes(pcm.tobytes())


def _load_wav(path):
  import wave

  with wave.open(path, 'rb') as wav:
    samplerate = wav.getframerate()
    channels = wav.getnchannels()
    width = wav.getsampwidth()
    raw = wav.readframes(wav.getnframes())
  if width == 2:
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
  else:
    data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
    data = (data - 128.0) / 128.0
  if channels > 1:
    data = data.reshape(-1, channels).mean(axis=1)
  return data, samplerate


def loadSplashReference(path=SPLASH_REF_PATH):
  if not os.path.isfile(path):
    return None
  samples, samplerate = _load_wav(path)
  fingerprint = _log_spectrum(samples, samplerate)
  if fingerprint is None:
    return None
  print(f'[audio] splash reference={path}')
  return fingerprint


def waitForSplash(
    timeout=14,
    on_tick=None,
    ratio=4.0,
    match=0.86,
    ref_path=SPLASH_REF_PATH,
):
  """입질 효과음 샘플과 스펙트럼을 비교해 찌가 걸린 소리를 찾는다."""
  samplerate = 44100
  blocksize = 4096
  window_blocks = 5  # 약 0.46초
  speaker, mic = _default_loopback_mic()
  ref = loadSplashReference(ref_path)
  print(f'[audio] default loopback={speaker.name} mode={"template" if ref is not None else "learn-first"}')

  baseline = []
  rolling = []
  deadline = time.time() + timeout

  with mic.recorder(samplerate=samplerate) as recorder:
    recorder.record(numframes=blocksize)
    while time.time() < deadline:
      if on_tick is not None:
        on_tick()
      frames = recorder.record(numframes=blocksize)
      mono = _to_mono(frames)
      rolling.append(mono)
      if len(rolling) > window_blocks:
        rolling.pop(0)
      window = np.concatenate(rolling)
      score = _splash_band_energy(window, samplerate)

      if len(baseline) < 8:
        baseline.append(score)
        continue

      floor = float(np.median(baseline))
      noise = max(floor, 1e-8)
      loud = score > noise * ratio

      if ref is not None:
        sim = _cosine(_log_spectrum(window, samplerate), ref)
        if loud and sim >= match:
          print(f'[audio] bite match={sim:.3f} energy={score:.4f}/{floor:.4f}')
          return True
        if not loud:
          baseline.append(score)
          if len(baseline) > 20:
            baseline.pop(0)
        continue

      # 샘플이 없으면 첫 입질(큰 피크)을 녹음해 이후부터 그 소리로 특정한다.
      if loud:
        _save_wav(ref_path, window, samplerate)
        print(f'[audio] saved first bite as {ref_path}')
        return True

      baseline.append(score)
      if len(baseline) > 20:
        baseline.pop(0)

  print('[audio] splash timeout')
  return False


def get_next_kst_shutdown(session_hours=6, shutdown_hour=None):
  """세션 종료 시각(KST)을 계산한다.

  session_hours: 시작 시각부터 몇 시간 뒤 (기본 6)
  shutdown_hour: 0-23이면 그날/다음날 해당 시각 정각
  """
  now = datetime.now(KST)
  if shutdown_hour is None:
    return now + timedelta(hours=session_hours)
  if not isinstance(shutdown_hour, int):
    raise ValueError("shutdown_hour must be an int or None")
  target = now.replace(hour=shutdown_hour, minute=0, second=0, microsecond=0)
  if now >= target:
    target += timedelta(days=1)
  return target


def shutdown_if_kst_target(next_shutdown):
  """종료 시각이 되면 PC를 끄고 True를 반환한다."""
  if datetime.now(KST) >= next_shutdown:
    print(f"[session] {next_shutdown.strftime('%Y-%m-%d %H:%M KST')} reached, shutting down")
    os.system('shutdown -s -f')
    return True
  return False
