import os
import time
import cv2
import numpy as np
import pyautogui
import random


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

def findFloat(confidence, region=(1010, 435, 550, 450)):
    sticker = './imgs/bobber_sticker.png'
    try:
        btn = pyautogui.locateOnScreen(sticker,
                                       confidence=confidence,
                                       region=region)
        if btn:
            x, y, w, h = btn
            newImg = saveImg('./imgs/im1.png', x, y)
            pyautogui.moveTo(x, y)
            behavior = saveBehavior('./imgs/behavior.png', x, y)
            return newImg, behavior, x, y
    except pyautogui.ImageNotFoundException:
        pass

    return None, None, 0, 0


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
