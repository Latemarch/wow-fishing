# FishingAssist

Python 매크로가 읽을 수 있는 상태 LED를 게임 화면 좌상단에 표시하는 애드온입니다.

## 설치

1. `addon/FishingAssist` 폴더 전체를 아래로 복사합니다.

```
World of Warcraft\_retail_\Interface\AddOns\FishingAssist\
```

Classic이면 `_classic_` / `_classic_era_` 경로를 사용하세요.

2. 캐릭터 선택 화면에서 애드온이 켜져 있는지 확인합니다.
3. 게임 안에서 `/reload` 합니다.
4. 좌상단에 **검정/초록** LED 3칸이 보이면 정상입니다.
   - 1번(파랑): 낚시 채널 중
   - 2번(마젠타): 목표 아이템이 가방에 있음
   - 3번(초록): 애드온 동작 중

## 목표 아이템 설정

기본값: Strange Goop (`187662`)

```
/fa target 187662
/fa target [아이템 링크]
/fa clear
/fa status
```

Python 쪽은 `imgs/target.png` 아이콘 매칭도 같이 봅니다.

## Soft Interact

낚시 중 `SoftTargetInteractArc/Range`를 잠시 키워서 Interact 키로 찌를 집기 쉽게 합니다.
캐스트가 끝나면 원래 CVar로 되돌립니다.
