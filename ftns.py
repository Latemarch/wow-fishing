import os
import time
import cv2
import numpy as np
import pyautogui
import random
# def getFloats(length):
#   imgs=[]
#   for i in range(length):
#     imgs.append(cv2.imread('./imgs/ref/%02d.png' % i))
#   return  imgs

def getFloats(length=None):
  imgs=[]
  
  # length가 지정되지 않으면 imgs/ref 폴더의 PNG 파일 개수로 자동 설정
  if length is None:
    ref_dir = './imgs/ref'
    if os.path.exists(ref_dir):
      png_files = [f for f in os.listdir(ref_dir) if f.endswith('.png')]
      length = len(png_files)
    else:
      length = 8  # 기본값
  
  for i in range(length):
    img = cv2.imread('./imgs/ref/%02d.png' % i)
    if img is not None:
      imgs.append(img)
  
  return imgs

import pyautogui

def findFloat(confidence):
    imgs = getFloats()
    for i, img in enumerate(imgs):
        try:
            btn = pyautogui.locateOnScreen(img,
                                           confidence=confidence,
                                           grayscale=True,
                                           region=(1010, 435, 550, 450))
            if btn:
                x, y, w, h = btn
                newImg = saveImg('./imgs/im1.png', x, y)
                # num = random.randint(0, 20)
                # path = f'./imgs/ref/{num:02d}.png'
                # saveImg(path, x, y)
                pyautogui.moveTo(x - 100, y)
                behavior = saveBehavior('./imgs/behavior.png', x, y)
                return newImg, behavior, x, y
        except pyautogui.ImageNotFoundException:
            # print(f"Image not found: {img}")
            continue  # Move to the next image if the current one is not found
    
    # If no images are found, return (0, 0, 0)
    return 0, 0, 0


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
