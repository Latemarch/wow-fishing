local GOOP_ITEM_ID = 187662 -- 기묘한 끈적이
local FISH_ITEM_IDS = {
  173043,
  187712,
  173038,
  187702,
}

local function ItemCount(itemId)
  if C_Item and C_Item.GetItemCount then
    return C_Item.GetItemCount(itemId) or 0
  end
  if GetItemCount then
    return GetItemCount(itemId) or 0
  end
  return 0
end

local function FishTotal()
  local total = 0
  for i = 1, #FISH_ITEM_IDS do
    total = total + ItemCount(FISH_ITEM_IDS[i])
  end
  return total
end

-- 화면 중앙: 끈적이가 가방에 있으면 아이콘
local goopFrame = CreateFrame("Frame", "GoopAlertFrame", UIParent)
goopFrame:SetSize(64, 64)
goopFrame:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
goopFrame:SetFrameStrata("HIGH")
goopFrame:EnableMouse(false)
goopFrame:Hide()

local goopIcon = goopFrame:CreateTexture(nil, "ARTWORK")
goopIcon:SetAllPoints(goopFrame)
goopIcon:SetTexCoord(0.08, 0.92, 0.08, 0.92)

-- 우측 상단: 숫자(사람용) + 색 막대(봇이 스크린샷으로 읽음)
local CELL = 16
local GAP = 2
local BITS = 20
local CELLS = BITS + 2
local panel = CreateFrame("Frame", "GoopAlertFishBar", UIParent)
panel:SetSize(CELLS * (CELL + GAP) - GAP, 52)
panel:SetPoint("TOPRIGHT", UIParent, "TOPRIGHT", -16, -16)
panel:SetFrameStrata("TOOLTIP")
panel:EnableMouse(false)
panel:Show()

local label = panel:CreateFontString(nil, "OVERLAY", "GameFontNormalHuge")
label:SetPoint("TOPRIGHT", panel, "TOPRIGHT", 0, 0)
label:SetTextColor(1, 1, 0.2)

local bar = CreateFrame("Frame", nil, panel)
bar:SetSize(CELLS * (CELL + GAP) - GAP, CELL)
bar:SetPoint("BOTTOMRIGHT", panel, "BOTTOMRIGHT", 0, 0)

local cells = {}
for i = 1, CELLS do
  local tex = bar:CreateTexture(nil, "ARTWORK")
  tex:SetSize(CELL, CELL)
  tex:SetPoint("LEFT", bar, "LEFT", (i - 1) * (CELL + GAP), 0)
  cells[i] = tex
end

local function SetRGB(tex, r, g, b)
  tex:SetColorTexture(r, g, b, 1)
end

local function UpdateFishBar(count)
  SetRGB(cells[1], 1, 0, 80 / 255)
  for i = 1, BITS do
    local bitOn = math.floor(count / (2 ^ (i - 1))) % 2 == 1
    if bitOn then
      SetRGB(cells[i + 1], 0.94, 0.94, 0.94)
    else
      SetRGB(cells[i + 1], 0.04, 0.04, 0.04)
    end
  end
  SetRGB(cells[CELLS], 0, 1, 80 / 255)
  label:SetText(tostring(count))
end

local function UpdateGoop()
  local count = ItemCount(GOOP_ITEM_ID)
  if count > 0 then
    local icon
    if C_Item and C_Item.GetItemIconByID then
      icon = C_Item.GetItemIconByID(GOOP_ITEM_ID)
    elseif GetItemIcon then
      icon = GetItemIcon(GOOP_ITEM_ID)
    end
    if icon then
      goopIcon:SetTexture(icon)
    end
    goopFrame:Show()
  else
    goopFrame:Hide()
  end
end

local function Refresh()
  UpdateGoop()
  UpdateFishBar(FishTotal())
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("BAG_UPDATE_DELAYED")
events:RegisterEvent("BAG_UPDATE")
events:SetScript("OnEvent", Refresh)

SLASH_GOOPALERT1 = "/goopalert"
SlashCmdList.GOOPALERT = function()
  Refresh()
  print("GoopAlert 끈적이=", ItemCount(GOOP_ITEM_ID), "낚시합계=", FishTotal())
end

Refresh()
