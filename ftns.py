import os
import re
import time
import ctypes
import threading
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


def _wow_hwnd():
  """WoW 메인 창 HWND."""
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
      hwnd = getattr(game_window, '_hWnd', None)
      if hwnd:
        return int(hwnd)
  except Exception:
    pass
  return None


def _wow_client_rect():
  """게임 클라이언트 영역(제목줄/테두리 제외)의 화면 좌표 (left, top, width, height)."""
  hwnd = _wow_hwnd()
  if hwnd is None:
    return _wow_window_rect()

  user32 = ctypes.windll.user32
  rect = ctypes.wintypes.RECT()
  if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
    return _wow_window_rect()

  point = ctypes.wintypes.POINT(0, 0)
  if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
    return _wow_window_rect()

  width = int(rect.right - rect.left)
  height = int(rect.bottom - rect.top)
  if width < 400 or height < 300:
    return _wow_window_rect()
  return (int(point.x), int(point.y), width, height)


def _wow_center():
  """게임 창 클라이언트 영역 중앙 (모니터 화면 중앙 아님)."""
  left, top, width, height = _wow_client_rect()
  return left + width // 2, top + height // 2


def readFishCount():
  """우측 상단 에드온 막대에서 낚시 아이템 총개수를 읽는다. 1000개 묶음도 합산값이다."""
  return _read_addon_count_bar(
    start_rgb=(255, 0, 80),
    end_rgb=(0, 255, 80),
    label='fish-count',
  )


def readRayCount():
  """대해가오리 개수 막대 (시작 하늘색 ~ 끝 주황)."""
  return _read_addon_count_bar(
    start_rgb=(0, 180, 255),
    end_rgb=(255, 100, 0),
    label='ray-count',
    tol=40,
    same_row_max=18,
  )


def _read_addon_count_bar(
  start_rgb, end_rgb, label='count', bits=20, tol=55, same_row_max=None
):
  start_rgb = np.array(start_rgb, dtype=np.int16)
  end_rgb = np.array(end_rgb, dtype=np.int16)
  left, top, width, height = _wow_window_rect()
  strip_w = max(420, int(round(width * 0.42)))
  # 낚시+가오리 두 줄
  strip_h = max(130, int(round(height * 0.22)))
  region_left = max(0, left + width - strip_w)
  region = (region_left, max(0, top), strip_w, strip_h)
  screenshot = pyautogui.screenshot(region=region)
  img = np.array(screenshot)
  if img.size == 0:
    print(f'[{label}] empty screenshot')
    return None

  start_dist = np.linalg.norm(img.astype(np.int16) - start_rgb, axis=2)
  end_dist = np.linalg.norm(img.astype(np.int16) - end_rgb, axis=2)
  start_pts = np.argwhere(start_dist < tol)
  end_pts = np.argwhere(end_dist < tol)
  if start_pts.size == 0 or end_pts.size == 0:
    print(f'[{label}] bar not found (GoopAlert 설치/리로드 확인)')
    return None

  # 시작/끝 마커가 비슷한 높이(같은 막대)에 있는 쌍만 사용
  if same_row_max is None:
    start_y, start_x = start_pts.mean(axis=0)
    end_y, end_x = end_pts.mean(axis=0)
  else:
    best = None
    for sy, sx in start_pts:
      for ey, ex in end_pts:
        if abs(int(sy) - int(ey)) > same_row_max:
          continue
        if int(ex) <= int(sx):
          continue
        span = int(ex) - int(sx)
        if span < bits:
          continue
        # 막대 길이가 너무 길면 UI 오탐 — 셀 폭 기준 상한
        if span > bits * 28:
          continue
        score = abs(int(sy) - int(ey)) + abs(span - bits * 18)
        if best is None or score < best[0]:
          best = (score, float(sy), float(sx), float(ey), float(ex))
    if best is None:
      print(f'[{label}] no same-row start/end pair')
      return None
    _, start_y, start_x, end_y, end_x = best

  if end_x - start_x < bits:
    print(f'[{label}] bar too short')
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
  print(f'[{label}] {count}')
  return count


OCR_ENABLED = True

_easyocr_reader = None
_ocr_lock = threading.Lock()
_ocr_pending = None  # (img, region) 최신 1장만 유지
_ocr_worker_running = False
_ocr_sent_chat = set()
_ocr_sent_chat_order = []
_OCR_SENT_MAX = 80
# 앞에 붙은 시각: 04.27.19 / 04:27:19 / 042719 등 → 숫자 6자리로 중복 판정
_NUMBERED_CHAT_RE = re.compile(r'^\d')
_LEADING_TIMESTAMP_RE = re.compile(
  r'^[\s·•|\[\](){}<>"\',;]*'
  r'(?P<ts>\d{1,2}[:.\-]\d{2}[:.\-]\d{2}|\d{6})'
)
# 유저 채팅: [캐릭터명] (NPC 대사 필터)
_PLAYER_BRACKET_RE = re.compile(r'[\[［][^\[\]［］]{1,32}[\]］]')


def _get_easyocr_reader():
  """한국어/영어 EasyOCR 리더 (첫 호출 시 로드)."""
  global _easyocr_reader
  with _ocr_lock:
    if _easyocr_reader is not None:
      return _easyocr_reader
  try:
    import easyocr
  except ImportError as error:
    raise ImportError('easyocr not installed') from error
  print('[ocr] loading EasyOCR (ko+en)...')
  reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
  with _ocr_lock:
    _easyocr_reader = reader
  print('[ocr] EasyOCR ready')
  return reader


def preloadEasyOcrAsync():
  """시작 시 모델 다운로드/로드를 백그라운드로 돌린다."""
  if not OCR_ENABLED:
    return
  def _load():
    try:
      _get_easyocr_reader()
    except Exception as error:
      print(f'[ocr] preload failed: {error}')

  threading.Thread(target=_load, daemon=True, name='easyocr-preload').start()
  print('[ocr] preload started')


def _chat_ocr_region():
  """좌측 하단 채팅창 근처."""
  left, top, width, height = _wow_window_rect()
  chat_w = max(420, int(round(width * 0.38)))
  chat_h = max(180, int(round(height * 0.28)))
  region_left = left
  region_top = max(0, top + height - chat_h)
  return _clamp_region((region_left, region_top, chat_w, chat_h))


def _timestamp_six_digits(line):
  """줄 앞 시각에서 숫자 6자리만. 04.27.19 / 04:27:19 → 042719."""
  text = str(line).strip().lstrip('·•|[](){}<>"\' .,;:')
  match = _LEADING_TIMESTAMP_RE.match(text)
  if match:
    digits = re.sub(r'\D', '', match.group('ts'))
    if len(digits) >= 6:
      return digits[:6]
  # OCR이 구분자를 이상하게 읽어도 앞쪽 숫자 6개면 사용
  digits = re.sub(r'\D', '', text[:20])
  if len(digits) >= 6:
    return digits[:6]
  return None


def _has_player_bracket(line):
  """[아이디] 형식이 있으면 유저 채팅으로 본다."""
  return bool(_PLAYER_BRACKET_RE.search(str(line)))


def _remember_ocr_chat_line(line):
  """시각 숫자 6자리 기준 중복 텔레그램 방지."""
  global _ocr_sent_chat_order
  key = _timestamp_six_digits(line)
  if not key:
    return False
  if key in _ocr_sent_chat:
    print(f'[ocr] skip duplicate timestamp={key}')
    return False
  _ocr_sent_chat.add(key)
  _ocr_sent_chat_order.append(key)
  while len(_ocr_sent_chat_order) > _OCR_SENT_MAX:
    old = _ocr_sent_chat_order.pop(0)
    _ocr_sent_chat.discard(old)
  return True


def _lines_starting_with_number(texts):
  """시각 + [아이디] 가 있는 유저 채팅 줄만 고른다."""
  hits = []
  for text in texts:
    line = str(text).strip()
    if not line:
      continue
    cleaned = line.lstrip('·•|[](){}<>"\' .,;:')
    if not (_NUMBERED_CHAT_RE.match(cleaned) or _NUMBERED_CHAT_RE.match(line)):
      continue
    if not _timestamp_six_digits(line):
      continue
    if not _has_player_bracket(line):
      print(f'[ocr] skip no [id]: {line[:60]}')
      continue
    hits.append(line)
  return hits


def _ocr_chat_image(img, region):
  """스크린샷 OCR → 콘솔 + 숫자 시작 줄은 텔레그램."""
  try:
    reader = _get_easyocr_reader()
  except ImportError:
    print('[ocr] easyocr not installed')
    return ''

  if img is None or getattr(img, 'size', 0) == 0:
    print('[ocr] empty screenshot region=%s' % (region,))
    return ''

  work = img
  h, w = work.shape[:2]
  if max(h, w) < 900:
    work = cv2.resize(work, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

  try:
    results = reader.readtext(work, detail=1, paragraph=False)
  except Exception as error:
    print(f'[ocr] easyocr failed: {error}')
    return ''

  raw_texts = []
  lines = []
  for item in results:
    if len(item) < 2:
      continue
    text = str(item[1]).strip()
    conf = float(item[2]) if len(item) > 2 else 0.0
    if not text:
      continue
    raw_texts.append(text)
    lines.append(f'{text}  ({conf:.2f})')

  cleaned = '\n'.join(lines)
  print(f'[ocr] chat region={region} hits={len(lines)}')
  print('[ocr] ----- chat begin -----')
  print(cleaned if cleaned else '(empty)')
  print('[ocr] ----- chat end -----')

  numbered = _lines_starting_with_number(raw_texts)
  new_numbered = [line for line in numbered if _remember_ocr_chat_line(line)]
  if new_numbered:
    msg = '채팅(유저)\n' + '\n'.join(new_numbered)
    print(f'[ocr] telegram player chat lines={len(new_numbered)}')
    notifyTelegram(msg)

  return cleaned


def _ocr_drain_worker():
  """대기 중인 최신 스크린샷만 OCR한다."""
  global _ocr_pending, _ocr_worker_running
  while True:
    with _ocr_lock:
      job = _ocr_pending
      _ocr_pending = None
      if job is None:
        _ocr_worker_running = False
        return
    img, region = job
    try:
      _ocr_chat_image(img, region)
    except Exception as error:
      print(f'[ocr] async failed: {error}')


def ocrChatWindowAsync(delay=0.8):
  """낚시 루프를 막지 않음. 채팅 반영 후 스크린샷 → 최신 1장만 OCR."""
  if not OCR_ENABLED:
    return
  def _capture_then_queue():
    global _ocr_pending, _ocr_worker_running
    try:
      if delay > 0:
        time.sleep(delay)
      region = _chat_ocr_region()
      screenshot = pyautogui.screenshot(region=region)
      img = np.array(screenshot)
      start_worker = False
      with _ocr_lock:
        replaced = _ocr_pending is not None
        _ocr_pending = (img, region)
        if not _ocr_worker_running:
          _ocr_worker_running = True
          start_worker = True
      if replaced:
        print('[ocr] queued latest (replaced previous)')
      else:
        print('[ocr] screenshot queued')
      if start_worker:
        threading.Thread(
          target=_ocr_drain_worker, daemon=True, name='chat-ocr'
        ).start()
    except Exception as error:
      print(f'[ocr] capture failed: {error}')

  threading.Thread(
    target=_capture_then_queue, daemon=True, name='chat-ocr-capture'
  ).start()


def confirmFishCatch(before_count):
  """찌 클릭 후 성공 여부 확인 (색 막대). OCR은 테스트용으로 별도."""
  bar_count = readFishCount()
  print(f'[fish] verify before={before_count} bar={bar_count}')
  if before_count is not None and bar_count is not None and bar_count > before_count:
    gain = bar_count - before_count
    if gain <= 50:
      return True, bar_count, 'bar'
    print(f'[fish] reject suspicious bar gain +{gain}')
  stuck = bar_count if bar_count is not None else before_count
  return False, stuck, 'none'


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


def detectPurpleInterference(region, min_ratio=0.05, min_pixels=800):
  """검색 영역에 보라/마젠타 패턴이 일정 비율 이상이면 방해로 본다.

  Returns: (is_interference, purple_ratio, purple_pixels)
  """
  left, top, width, height = _clamp_region(region)
  screenshot = pyautogui.screenshot(region=(left, top, width, height))
  img = np.array(screenshot)
  if img.ndim == 3 and img.shape[2] == 4:
    img = img[:, :, :3]
  bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
  hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

  # 탈것/오라 등 어두운 보라~자홍 (fail.png 용 기준 완화)
  mask_a = cv2.inRange(hsv, (120, 20, 20), (165, 255, 255))
  mask_b = cv2.inRange(hsv, (165, 20, 20), (179, 255, 255))
  mask = cv2.bitwise_or(mask_a, mask_b)
  purple_pixels = int(cv2.countNonZero(mask))
  total = max(1, width * height)
  ratio = purple_pixels / total
  is_hit = purple_pixels >= min_pixels and ratio >= min_ratio
  print(
    f'[interference] purple_ratio={ratio:.3f} pixels={purple_pixels} '
    f'hit={is_hit} need>={min_ratio:.2f}/{min_pixels}'
  )
  return is_hit, ratio, purple_pixels


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
def findCenterGoop(image='./imgs/goop.png', confidence=0.78, size=None):
    """중앙 끈적이 알림 감지. 있으면 '기묘한 끈적이', 없으면 None.

    대해가오리는 우편/중앙알림 대상이 아님(개수 막대만).
    """
    left, top, width, height = _wow_window_rect()
    if size is None:
        size = max(220, int(round(min(width, height) * 0.28)))
    region_left = max(left, left + width // 2 - size // 2)
    region_top = max(top, top + height // 2 - size // 2)
    region_w = min(size, left + width - region_left)
    region_h = min(size, top + height - region_top)
    region = _clamp_region((region_left, region_top, region_w, region_h))

    mark, mark_pixels = _find_color_blob(
      region,
      (128, 0, 255),
      tol=45,
      min_pixels=80,
      prefer_area=22 * 22,
      max_pixels=900,
    )
    if mark is not None:
      print(f'[GOOP] 기묘한 끈적이 mark at {mark} pixels={mark_pixels}')
      return '기묘한 끈적이'

    found = _match_template(
        image,
        region=region,
        confidence=confidence,
        scales=_ui_scales_tight(),
    )
    if found is not None and found[0] is not None:
        print(f'[GOOP] center match score={found[1]:.3f} scale={found[2]:.2f}')
        return '기묘한 끈적이'

    score = found[1] if found is not None else -1.0
    if score >= 0.55:
        print(f'[GOOP] near-miss best={score:.3f} need>={confidence} region={region}')
    return None


def _goop_by_color(region, min_pixels=25):
  """(미사용) 예전 청록+주황 보조 탐지. 오탐으로 비활성."""
  return False


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


def now_kst_str(fmt='%Y-%m-%d %H:%M:%S KST'):
  """한국 시간(Asia/Seoul) 문자열."""
  return datetime.now(KST).strftime(fmt)


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


def _clamp_region(region):
  """스크린샷 region은 음수 좌표를 쓸 수 없다."""
  left, top, width, height = [int(v) for v in region]
  screen_w, screen_h = pyautogui.size()
  if left < 0:
    width += left
    left = 0
  if top < 0:
    height += top
    top = 0
  width = max(1, min(width, screen_w - left))
  height = max(1, min(height, screen_h - top))
  return (left, top, width, height)


def _mail_region():
  """우편함 창은 게임 창 왼쪽 ~50%에 열린다."""
  left, top, width, height = _wow_window_rect()
  region_w = max(1, int(width * 0.50))
  return _clamp_region((left, top, region_w, height))


def _mail_tab_region():
  """발송 탭(우편 발송)은 우편창 중~하단에 있다. Open All 아래."""
  left, top, width, height = _wow_window_rect()
  region_w = max(1, int(width * 0.50))
  # 상단 22%는 제목/수신함 목록, 탭은 그 아래~하단
  y0 = top + int(height * 0.22)
  region_h = max(1, int(height * 0.78))
  return _clamp_region((left, y0, region_w, region_h))


def _bag_region():
  """가방은 보통 게임 창 오른쪽 중~하단. 상단 낚시막대 노란 글자는 제외."""
  left, top, width, height = _wow_window_rect()
  x0 = left + int(width * 0.28)
  y0 = top + int(height * 0.12)
  return _clamp_region((x0, y0, max(1, left + width - x0), max(1, top + height - y0)))


def _click_point(point, label='ui', duration=0.15):
  x, y = int(point[0]), int(point[1])
  pyautogui.moveTo(x, y, duration=duration)
  time.sleep(0.05)
  pyautogui.click()
  print(f'[mail] {label} click=({x}, {y})')


def show_match_square(center, template_path, scale=1.0, color='#ffcc00', hold=2.0, label='match'):
  """매칭된 UI 위치에 디버그 네모를 잠깐 표시한다."""
  import tkinter as tk

  template = cv2.imread(template_path)
  if template is None:
    tw = th = 80
  else:
    tw = max(20, int(round(template.shape[1] * scale)))
    th = max(16, int(round(template.shape[0] * scale)))

  cx, cy = int(center[0]), int(center[1])
  left = cx - tw // 2
  top = cy - th // 2
  thickness = 3
  print(f'[mail] {label} square=({left}, {top}, {tw}, {th})')

  root = tk.Tk()
  root.withdraw()
  bars = []
  edges = [
    (left, top, tw, thickness),
    (left, top + th - thickness, tw, thickness),
    (left, top, thickness, th),
    (left + tw - thickness, top, thickness, th),
  ]
  for x, y, w, h in edges:
    bar = tk.Toplevel(root)
    bar.overrideredirect(True)
    bar.attributes('-topmost', True)
    bar.configure(bg=color)
    bar.geometry(f'{w}x{h}+{x}+{y}')
    bar.update_idletasks()
    hwnd = bar.winfo_id()
    style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    ctypes.windll.user32.SetWindowLongW(
      hwnd, -20, style | 0x00000020 | 0x00000080
    )
    bars.append(bar)
  root.update()
  time.sleep(hold)
  for bar in bars:
    try:
      bar.destroy()
    except Exception:
      pass
  try:
    root.destroy()
  except Exception:
    pass


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


def _match_template(path, region=None, confidence=0.72, scales=None, mask_center=0, use_gray=False):
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
  if use_gray:
    haystack = cv2.cvtColor(haystack, cv2.COLOR_BGR2GRAY)
    template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

  if mask_center > 0:
    # 화면 전체가 아니라 현재 검색 기준의 게임 창 중앙을 가린다.
    game_left, game_top, game_w, game_h = _wow_window_rect()
    cx = game_left + game_w // 2 - origin[0]
    cy = game_top + game_h // 2 - origin[1]
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


def _wait_match(path, region=None, confidence=0.72, timeout=5.0, use_gray=False):
  deadline = time.time() + timeout
  best = None
  while time.time() < deadline:
    found = _match_template(
      path, region=region, confidence=confidence, use_gray=use_gray
    )
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


def _wait_match_any(paths, region=None, confidence=0.58, timeout=6.0, use_gray=True):
  """여러 템플릿으로 UI를 찾는다. 컬러 매칭을 회색조보다 우선한다.

  Returns: (center, score, scale, path) or None
  """
  deadline = time.time() + timeout
  best = None
  best_path = None
  gray_modes = (False, True) if use_gray else (False,)
  while time.time() < deadline:
    for path in paths:
      if not os.path.isfile(path):
        continue
      for gray in gray_modes:
        found = _match_template(
          path, region=region, confidence=confidence, use_gray=gray
        )
        if found is None:
          continue
        if found[0] is not None:
          print(
            f'[mail] matched {path} score={found[1]:.3f} '
            f'scale={found[2]:.2f} gray={gray}'
          )
          return found[0], found[1], found[2], path
        if best is None or found[1] > best[1]:
          best = found
          best_path = path
    time.sleep(0.2)
  if best is not None:
    print(
      f'[mail] no match any best={best[1]:.3f} scale={best[2]:.2f} '
      f'path={best_path} need>={confidence}'
    )
  return None


def press_esc_in_wow():
  """Esc를 와우 창에만 보낸다. 전역 Esc는 이 PC에서 검색 창을 연다."""
  hwnd = _wow_hwnd()
  user32 = ctypes.windll.user32
  vk = 0x1B
  scan = user32.MapVirtualKeyW(vk, 0)
  lparam_down = 1 | (scan << 16)
  lparam_up = 1 | (scan << 16) | (1 << 30) | (1 << 31)
  if hwnd:
    user32.PostMessageW(hwnd, 0x0100, vk, lparam_down)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, 0x0101, vk, lparam_up)
    print(f'[mail] esc posted to wow hwnd={hwnd}')
    return True
  print('[mail] wow hwnd missing, skip esc')
  return False


def dismiss_start_menu():
  """채팅 포커스를 게임 화면 클릭으로 벗긴다. Esc는 이 PC에서 검색 창을 연다."""
  user32 = ctypes.windll.user32
  key_up = 0x0002
  extended = 0x0001
  for vk in (0x11, 0xA2, 0xA3, 0x10, 0xA0, 0xA1, 0x12, 0xA4, 0xA5, 0x5B, 0x5C):
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.keybd_event(vk, scan, key_up, 0)
    user32.keybd_event(vk, scan, key_up | extended, 0)

  left, top, width, height = _wow_client_rect()
  x = left + max(30, min(120, width // 8))
  y = top + max(30, min(120, height // 8))
  pyautogui.click(x, y)
  print(f'[mail] dismiss start click=({x}, {y})')


def close_mail_ui():
  """우편창을 Esc로 닫고, 검색 창이 뜨면 게임 클릭으로 닫는다."""
  press_esc_in_wow()
  time.sleep(0.25)
  dismiss_start_menu()
  time.sleep(0.2)


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


def _find_color_blob(region, rgb, tol=55, min_pixels=12, prefer_area=None, max_pixels=None):
  """단색 마커(애드온)의 중심 좌표를 찾는다. prefer_area면 그 크기에 가까운 덩어리를 고른다."""
  left, top, width, height = _clamp_region(region)
  screenshot = pyautogui.screenshot(region=(left, top, width, height))
  img = np.array(screenshot)
  if img.ndim == 3 and img.shape[2] == 4:
    img = img[:, :, :3]
  img = img.astype(np.int16)
  target = np.array(rgb, dtype=np.int16)
  channel_ok = np.all(np.abs(img - target) <= tol, axis=2)
  dist = np.linalg.norm(img - target, axis=2)
  mask = (channel_ok | (dist <= tol)).astype(np.uint8)
  count = int(np.count_nonzero(mask))
  if count < min_pixels:
    return None, count

  num_labels, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
  best = None
  best_score = None
  for label_id in range(1, num_labels):
    area = int(stats[label_id, cv2.CC_STAT_AREA])
    if area < min_pixels:
      continue
    if max_pixels is not None and area > max_pixels:
      continue
    cx = left + int(round(centroids[label_id][0]))
    cy = top + int(round(centroids[label_id][1]))
    if prefer_area is None:
      score = -area  # 가장 큰 덩어리
    else:
      score = abs(area - prefer_area)
    if best_score is None or score < best_score:
      best_score = score
      best = ((cx, cy), area)

  if best is None:
    return None, count
  return best[0], best[1]


def _wait_color_blob(
  region,
  rgb,
  tol=55,
  min_pixels=12,
  timeout=2.5,
  label='mark',
  prefer_area=None,
  max_pixels=None,
):
  deadline = time.time() + timeout
  last_count = 0
  while time.time() < deadline:
    pos, count = _find_color_blob(
      region,
      rgb,
      tol=tol,
      min_pixels=min_pixels,
      prefer_area=prefer_area,
      max_pixels=max_pixels,
    )
    last_count = count
    if pos is not None:
      print(f'[mail] {label} at {pos} pixels={count}')
      return pos
    time.sleep(0.15)
  print(f'[mail] {label} not found (pixels={last_count}) region={_clamp_region(region)}')
  return None


def _find_mail_tab_mark():
  """애드온 마젠타 마커 = 우편 발송 탭 (중~하단)."""
  return _wait_color_blob(
    _mail_tab_region(),
    (255, 0, 255),
    tol=60,
    min_pixels=80,
    prefer_area=28 * 28,
    max_pixels=2500,
    timeout=2.5,
    label='tab mark',
  )


def _find_mail_send_mark():
  """애드온 시안 마커 = 보내기 버튼 (첨부 완료 후에만 표시)."""
  return _wait_color_blob(
    _mail_region(),
    (0, 255, 255),
    tol=60,
    min_pixels=80,
    prefer_area=28 * 28,
    max_pixels=2500,
    timeout=3.0,
    label='send mark',
  )


def _find_bag_goop_mark():
  """애드온 노란 마커 = 가방 끈적이 칸 모서리."""
  return _wait_color_blob(
    _bag_region(),
    (255, 255, 0),
    tol=40,
    min_pixels=60,
    prefer_area=18 * 18,
    max_pixels=900,
    timeout=4.0,
    label='bag goop mark',
  )


def _find_mail_attach_mark():
  """애드온 주황 마커 = 우편에 끈적이 첨부됨."""
  return _wait_color_blob(
    _mail_region(),
    (255, 115, 0),
    tol=55,
    min_pixels=80,
    prefer_area=26 * 26,
    max_pixels=2500,
    timeout=3.0,
    label='attach mark',
  )


def sellAllJunk():
  """키 4로 상인 대상 → 게임창 중앙 x+50,y+250 클릭 → 2초 → 키 6(잡템 일괄판매)."""
  print('[vendor] target NPC (4)')
  pyautogui.press('4')
  time.sleep(3.0)

  left, top, width, height = _wow_client_rect()
  cx, cy = left + width // 2, top + height // 2
  click_x = cx + 50
  click_y = cy + 250
  print(
    f'[vendor] wow-client=({left}, {top}, {width}, {height}) '
    f'center=({cx}, {cy}) click=({click_x}, {click_y})'
  )
  pyautogui.moveTo(click_x, click_y)
  time.sleep(0.1)
  pyautogui.click()
  time.sleep(2.0)

  print('[vendor] sell all junk (6)')
  pyautogui.press('6')
  time.sleep(2.0)
  print('[vendor] done')
  return True


def mailGoop(recipient='황장수'):
  """끈적이를 우편으로 보내고 True/False를 반환한다."""
  print('[mail] summon mailbox')
  pyautogui.press('5')
  time.sleep(1.8)

  cx, cy = _wow_center()
  print(f'[mail] click mailbox at wow center=({cx}, {cy})')
  pyautogui.moveTo(cx, cy)
  time.sleep(0.1)
  pyautogui.click()
  time.sleep(1.0)

  mail_region = _mail_region()
  tab_region = _mail_tab_region()
  print(f'[mail] search region={mail_region} tab_region={tab_region}')

  # 1순위: 애드온 마젠타 마커, 2순위: 템플릿
  tab_center = _find_mail_tab_mark()
  tab_path = './imgs/sending_tab_new.png'
  tab_scale = 1.0
  tab_score = 1.0
  if tab_center is None:
    tab = _wait_match_any(
      ['./imgs/sending_tab_new.png'],
      region=tab_region,
      confidence=0.72,
      timeout=3.0,
      use_gray=False,
    )
    if tab is None:
      tab = _wait_match_any(
        [
          './imgs/sending_tab_new.png',
          './imgs/sending_tab.png',
          './imgs/mail_send_tab.png',
        ],
        region=tab_region,
        confidence=0.62,
        timeout=4.0,
        use_gray=True,
      )
    if tab is None:
      print('[mail] send tab not found')
      close_mail_ui()
      return False
    tab_center, tab_score, tab_scale, tab_path = tab

  show_match_square(
    tab_center, tab_path, scale=tab_scale, color='#ff00ff', hold=1.0, label='send-tab'
  )
  _click_point(tab_center, label='send-tab')
  print(f'[mail] send tab score={tab_score:.3f} scale={tab_scale:.2f}')
  time.sleep(0.7)

  if not _paste_text(recipient):
    return False
  time.sleep(0.25)
  pyautogui.press('enter')
  time.sleep(0.5)

  # 노란 모서리 마커 → 칸 중앙 쪽으로 살짝 이동해 우클릭
  goop = _find_bag_goop_mark()
  if goop is None:
    goop = _find_bag_goop()
    click_xy = goop
  else:
    click_xy = (int(goop[0]) + 14, int(goop[1]) + 14)
  if click_xy is None:
    print('[mail] goop not found in bags (yellow mark / template)')
    close_mail_ui()
    return False

  attached = False
  for attempt in range(2):
    show_match_square(
      click_xy, './imgs/goop.png', scale=1.0, color='#ffff00', hold=0.6, label='bag-goop'
    )
    pyautogui.moveTo(click_xy[0], click_xy[1], duration=0.12)
    time.sleep(0.08)
    pyautogui.click(button='right')
    print(f'[mail] right-click goop at {click_xy} attempt={attempt + 1}')
    time.sleep(0.55)
    if _find_mail_attach_mark() is not None:
      attached = True
      break
    # 재시도 전에 마커 다시 찾기
    goop = _find_bag_goop_mark()
    if goop is not None:
      click_xy = (goop[0] + 14, goop[1] + 14)

  if not attached:
    print('[mail] attach confirm failed - skip send (empty mail blocked)')
    close_mail_ui()
    time.sleep(0.3)
    return False

  send_center = _find_mail_send_mark()
  send_path = './imgs/sending_button.png'
  send_scale = 1.0
  send_score = 1.0
  if send_center is None:
    send = _wait_match_any(
      [
        './imgs/sending_button.png',
        './imgs/mail_send_button.png',
      ],
      region=mail_region,
      confidence=0.62,
      timeout=5.0,
      use_gray=True,
    )
    if send is None:
      print('[mail] send button not found')
      close_mail_ui()
      return False
    send_center, send_score, send_scale, send_path = send

  show_match_square(
    send_center, send_path, scale=send_scale, color='#00ffff', hold=1.0, label='send-button'
  )
  _click_point(send_center, label='send-button')
  print(f'[mail] send button score={send_score:.3f} scale={send_scale:.2f}')
  time.sleep(1.2)
  close_mail_ui()
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


def logoutWow(key='3'):
  """로그아웃 매크로 키를 눌러 캐릭터 선택 화면으로 나간다.

  매크로가 캐릭터 선택 화면까지 가는 데 약 40초 걸린다.
  이 대기 동안에는 캐릭터를 찾지 않는다.
  """
  print(f'[session] logout key={key}')
  pyautogui.press(key)
  print('[session] logout in progress, wait 40s before character search')
  time.sleep(40.0)


def _char_select_region():
  """캐릭터 목록은 게임 창 우측 상단이다. 오른쪽 30%, 위쪽 절반만 본다."""
  left, top, width, height = _wow_window_rect()
  x0 = left + int(width * 0.70)
  y0 = top + int(height * 0.05)
  region_w = max(1, left + width - x0)
  region_h = max(1, int(height * 0.50))
  return _clamp_region((x0, y0, region_w, region_h))


def findCharSelect(image='./imgs/shamon.png', confidence=0.55, timeout=45.0):
  """우측 상단에서 클래스 글자 색으로 대상 캐릭터를 찾는다."""
  region = _char_select_region()
  print(f'[session] char select search region={region}')
  deadline = time.time() + timeout
  best = None
  while time.time() < deadline:
    found = _match_template(
      image,
      region=region,
      confidence=confidence,
      scales=_ui_scales(),
      use_gray=False,
    )
    if found is None:
      time.sleep(0.4)
      continue
    if found[0] is not None:
      print(
        f'[session] char matched score={found[1]:.3f} '
        f'scale={found[2]:.2f} gray=False at={found[0]}'
      )
      return found[0]
    if best is None or found[1] > best[1]:
      best = found
    time.sleep(0.4)
  if best is not None:
    print(f'[session] char not found best={best[1]:.3f} need>={confidence}')
  else:
    print('[session] char not found')
  return None


def clickCharSelect(image, char_name='캐릭터', timeout=8.0, confidence=0.55):
  """캐릭터 선택 화면에서 대상만 클릭한다 (Enter 없음)."""
  if not os.path.isfile(image):
    print(f'[session] char image missing: {image}')
    return False
  pos = findCharSelect(image=image, confidence=confidence, timeout=timeout)
  if pos is None:
    print(f'[session] char click miss: {char_name}')
    return False
  x, y = int(pos[0]), int(pos[1])
  pyautogui.moveTo(x, y, duration=0.15)
  time.sleep(0.08)
  pyautogui.click()
  print(f'[session] selected {char_name} at ({x}, {y})')
  time.sleep(0.35)
  return True


def _char_match_score(image, region=None, confidence=0.40):
  """캐릭 템플릿 최고 점수. (center, score, scale) 또는 None."""
  if not os.path.isfile(image):
    return None
  if region is None:
    region = _char_select_region()
  best = None
  for use_gray in (False, True):
    found = _match_template(
      image,
      region=region,
      confidence=confidence,
      scales=_ui_scales(),
      use_gray=use_gray,
    )
    if found is None:
      continue
    if best is None or found[1] > best[1]:
      best = found
  return best


def selectCharVerified(
  image,
  char_name='캐릭터',
  other_chars=None,
  timeout=60.0,
  confidence=0.55,
):
  """대상 캐릭을 클릭. 다른 캐릭이 '다른 칸'에서 더 높을 때만 거부.

  템플릿이 비슷한 UI(지역명 등)를 공유하면 같은 칸에서 둘 다 점수가
  나올 수 있으므로, 위치가 거의 같으면 대상 템플릿을 신뢰한다.
  """
  if not os.path.isfile(image):
    print(f'[session] char image missing: {image}')
    return False

  deadline = time.time() + timeout
  region = _char_select_region()
  last_score = -1.0
  while time.time() < deadline:
    target = _char_match_score(image, region=region, confidence=0.35)
    if target is None or target[0] is None:
      time.sleep(0.35)
      continue

    target_score = float(target[1])
    last_score = target_score
    if target_score < confidence:
      print(
        f'[session] {char_name} score={target_score:.3f} '
        f'need>={confidence} - retry'
      )
      time.sleep(0.35)
      continue

    tx, ty = float(target[0][0]), float(target[0][1])
    rival_best = None
    if other_chars:
      for other_name, other_image in other_chars:
        if other_image == image:
          continue
        other = _char_match_score(other_image, region=region, confidence=0.35)
        if other is None or other[0] is None:
          continue
        ox, oy = float(other[0][0]), float(other[0][1])
        # 같은 리스트 칸(가까운 좌표)이면 교차매칭으로 보고 무시
        if abs(ox - tx) < 80 and abs(oy - ty) < 40:
          print(
            f'[session] ignore same-slot rival {other_name}='
            f'{other[1]:.3f} near {char_name}'
          )
          continue
        if rival_best is None or other[1] > rival_best[1]:
          rival_best = (other_name, float(other[1]), other[0])

    if rival_best is not None and rival_best[1] > target_score:
      print(
        f'[session] reject wrong char lead: {char_name}={target_score:.3f} '
        f'< {rival_best[0]}={rival_best[1]:.3f} at {rival_best[2]}'
      )
      time.sleep(0.4)
      continue

    x, y = int(tx), int(ty)
    for _attempt in range(2):
      pyautogui.moveTo(x, y, duration=0.12)
      time.sleep(0.08)
      pyautogui.click()
      time.sleep(0.25)
    print(
      f'[session] verified select {char_name} at ({x}, {y}) '
      f'score={target_score:.3f}'
    )
    return True

  print(f'[session] verified select failed: {char_name} last={last_score:.3f}')
  return False


def reconnectAfterFail(
  image='./imgs/shamon.png',
  wait_minutes=20,
  load_wait=12.0,
  char_name='캐릭터',
  keep_alive_chars=None,
  keep_alive_every_min=5,
):
  """로그아웃 후 대기 → 우측 상단 클래스 글자 클릭 → Enter로 접속.

  대기 중 AFK 방지는 대상 클래스 글자만 다시 클릭한다.
  다른 클래스 점수가 더 높아도 대상 좌표 클릭을 막지 않는다.
  """
  wait_minutes = max(0, int(wait_minutes))
  if not os.path.isfile(image):
    print(f'[session] reconnect image missing: {image}')
    return False

  print(f'[session] waiting {wait_minutes} min before reconnect ({char_name})')
  clickCharSelect(
    image, char_name=char_name, timeout=15.0, confidence=0.50,
  )

  for minute in range(wait_minutes):
    left = wait_minutes - minute
    print(f'[session] reconnect in {left} min... ({char_name})')
    time.sleep(60)
    elapsed = minute + 1
    if (
      keep_alive_every_min > 0
      and elapsed % keep_alive_every_min == 0
      and elapsed < wait_minutes
    ):
      print(f'[session] keep-alive reselect {char_name} at {elapsed}min')
      clickCharSelect(
        image, char_name=char_name, timeout=12.0, confidence=0.50,
      )

  time.sleep(2.0)
  selected = clickCharSelect(
    image, char_name=char_name, timeout=60.0, confidence=0.50,
  )
  if not selected:
    print(f'[session] reconnect failed - {char_name} not found')
    return False

  time.sleep(0.6)
  pyautogui.press('enter')
  print(f'[session] pressed enter for {char_name} - loading world')
  time.sleep(load_wait)

  focusWow()
  ready_count = waitForWorldReady(timeout=50.0)
  if ready_count is None:
    print('[session] world ready check timed out - resume anyway')
  print(f'[session] reconnect done ({char_name})')
  return True


def focusWow():
  """게임 창 중앙을 클릭해 포커스를 맞춘다."""
  cx, cy = _wow_center()
  pyautogui.moveTo(cx, cy, duration=0.1)
  time.sleep(0.05)
  pyautogui.click()
  time.sleep(0.3)
  print(f'[session] focused wow at ({cx}, {cy})')


def waitForWorldReady(timeout=45.0):
  """접속 후 GoopAlert 낚시 막대가 보일 때까지 기다린다."""
  deadline = time.time() + timeout
  last = None
  while time.time() < deadline:
    last = readFishCount()
    if last is not None:
      print(f'[session] world ready fish-count={last}')
      return last
    time.sleep(1.0)
  print(f'[session] world ready timeout last={last}')
  return None


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
    ratio=8.0,
    match=0.7,
    min_energy=0.05,
    min_floor=0.0,
    confirm_hits=1,
    ignore_seconds=1.5,
    ref_path=SPLASH_REF_PATH,
):
  """입질 효과음 샘플과 스펙트럼을 비교해 찌가 걸린 소리를 찾는다.

  물기 전 오탐 줄이기:
  - 캐스트 직후 ignore_seconds 동안은 무시
  - 절대 에너지(min_energy) + 배경 대비(ratio) 둘 다 만족
  - 템플릿 유사도 match 이상
  - confirm_hits번 연속 통과해야 입질로 인정
  """
  samplerate = 44100
  blocksize = 4096
  window_blocks = 5  # 약 0.46초
  speaker, mic = _default_loopback_mic()
  ref = loadSplashReference(ref_path)
  print(f'[audio] default loopback={speaker.name} mode={"template" if ref is not None else "learn-first"}')

  baseline = []
  rolling = []
  hits = 0
  started = time.time()
  deadline = started + timeout

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

      # 초반에는 기준 소음만 모은다 (캐스트/찌 떨어지는 소리 제외)
      if time.time() - started < ignore_seconds:
        baseline.append(score)
        if len(baseline) > 20:
          baseline.pop(0)
        hits = 0
        continue

      if len(baseline) < 8:
        baseline.append(score)
        hits = 0
        continue

      floor = float(np.median(baseline))
      noise = max(floor, min_floor)
      loud = score >= min_energy and score > noise * ratio

      if ref is not None:
        sim = _cosine(_log_spectrum(window, samplerate), ref)
        if loud and sim >= match:
          hits += 1
          print(
            f'[audio] bite candidate {hits}/{confirm_hits} '
            f'sim={sim:.3f} energy={score:.4f}/{floor:.4f}'
          )
          if hits >= confirm_hits:
            print(f'[audio] bite match={sim:.3f} energy={score:.4f}/{floor:.4f}')
            return True
        else:
          hits = 0
          if not loud:
            baseline.append(score)
            if len(baseline) > 20:
              baseline.pop(0)
        continue

      # 샘플이 없으면 충분히 큰 첫 입질만 저장
      if loud:
        _save_wav(ref_path, window, samplerate)
        print(f'[audio] saved first bite as {ref_path} energy={score:.4f}/{floor:.4f}')
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


def get_next_kst_clock(hour, minute=0):
  """다음 KST 시각(시:분 정각)을 반환한다."""
  now = datetime.now(KST)
  target = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
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
