"""캐릭터 선택 화면 매칭 테스트 (Enter/접속 없음)."""
import time
import ftns

CHARS = [
  ('주술사', './imgs/shamon.png'),
  ('마법사', './imgs/mage.png'),
  ('사제', './imgs/priest.png'),
]

print('WoW 캐릭터 선택 화면에 두세요. 3초 후 시작...')
for i in range(3, 0, -1):
  print(i)
  time.sleep(1)

ftns.focusWow()
time.sleep(0.3)

region = ftns._char_select_region()
print(f'region={region}')

for name, path in CHARS:
  found = ftns._char_match_score(path, region=region, confidence=0.30)
  if found is None:
    print(f'{name}: NO MATCH')
    continue
  center, score, scale = found
  print(f'{name}: score={score:.3f} scale={scale:.2f} center={center}')

for name, path in CHARS:
  print(f'--- click {name} (no Enter) ---')
  ok = ftns.clickCharSelect(path, char_name=name, timeout=8.0, confidence=0.50)
  print(f'{name} ok={ok}')
  time.sleep(0.8)
print('done (Enter not pressed)')
