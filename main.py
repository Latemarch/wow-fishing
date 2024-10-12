import pyautogui
import time
import ftns
time.sleep(2)

imgs = ftns.getFloats(8)

trycount = 0
istargetItem = False 
biteTime = time.time()

while istargetItem==False:
  trycount += 1
  print(trycount)

  istargetItem = ftns.findTargetItem('./imgs/item.png',shutDown=True)
  biteTime = ftns.applybite('2',biteTime,600)

  time.sleep(1)
  pyautogui.moveTo(100,100)
  pyautogui.press('1')
  time.sleep(2)
  
  newImg,x,y = ftns.findFloat(imgs,0.55)

  if not newImg:
    continue 
    
  for i in range(70):
    time.sleep(0.2)
    targetImg=ftns.saveImg('./imgs/im2.png',x,y)
    similarity=ftns.compareImg(newImg,targetImg)
    newImg = targetImg

    if similarity > 3:
      pyautogui.moveTo(x+40,y+30)
      time.sleep(0.1)
      pyautogui.click()
      break


