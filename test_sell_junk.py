"""잡템 판매 플로우만 테스트: 4 → 게임창 중앙 x+50,y+100 → 2초 → 6 (Esc 없음)"""
import time
import ftns

print('WoW로 포커스 맞추세요. 5초 후 시작...')
for i in range(5, 0, -1):
  print(i)
  time.sleep(1)

rect = ftns._wow_client_rect()
cx, cy = ftns._wow_center()
print(f'wow-client={rect} center=({cx}, {cy}) click=({cx + 50}, {cy + 100})')

ftns.focusWow()
time.sleep(0.3)
ftns.sellAllJunk()
print('done')
