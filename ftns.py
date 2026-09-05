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
            pyautogui.moveTo(x - 100, y)
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
