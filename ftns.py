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
def findTargetItem(item, shutDown=False):
    pyautogui.screenshot('./imgs/item1.png', region=(1225, 475, 100, 100))  # Capture a screenshot for debugging
    try:
        item_ = pyautogui.locateOnScreen(item, confidence=0.7, region=(1225, 475, 100, 100))
        if item_:
            print('I got the item!')
            if shutDown: os.system('shutdown -s -f')  # Uncomment to shut down
            return True
    except pyautogui.ImageNotFoundException:
        # print(f"Item not found: {item}")
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
