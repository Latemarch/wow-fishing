import os
import time
import cv2
import numpy as np
import pyautogui

def getFloats(length):
  imgs=[]
  for i in range(length):
    imgs.append(cv2.imread('./imgs/ref/%02d.png' % i))
  return  imgs

def findFloat(imgs,confidence):
  for i,img in enumerate(imgs):
    btn = pyautogui.locateOnScreen(img,
            confidence=confidence,
            grayscale=True, 
            region = (1010,435,650,650))
    if btn:
      x,y,w,h=btn
      newImg = saveImg('./imgs/im1.png',x,y)
      pyautogui.moveTo(x-100,y)
      return newImg, x,y
  return 0,0,0

def findTargetItem(item,shutDown = False):
  pyautogui.screenshot('./imgs/item1.png', region=(1225,475,100,100))
  item_= pyautogui.locateOnScreen(item,
      confidence=0.4, 
      region = (1225,475,100,100))
  if item_:
    print('I got the item!')
    if shutDown: os.system('shutdown -s -f')
    return True
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

def saveImg(location,x,y):
  return pyautogui.screenshot(location, region=(x,y-5,80,80))

def applybite(key,lastApplyingTime,interval):
  if time.time()-lastApplyingTime > interval:
    pyautogui.press(key)
    time.sleep(1)
    return time.time()
  return lastApplyingTime
