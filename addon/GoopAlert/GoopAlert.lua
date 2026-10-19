local GOOP_ITEM_ID = 187662 -- 기묘한 끈적이 (중앙알림 + 우편)
local RAY_ITEM_ID = 163131 -- 대해 가오리 (개수 막대만, 우편 없음)

local FISH_ITEM_IDS = {
  173032,
  173043,
  187712,
  173038,
  187702,
  173073,
  173037,
  6522,
  6289,
  6291,
  6308,
  152544,
  152543,
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

local function RayTotal()
  return ItemCount(RAY_ITEM_ID)
end

local function ContainerItemID(bag, slot)
  if C_Container and C_Container.GetContainerItemID then
    return C_Container.GetContainerItemID(bag, slot)
  end
  if GetContainerItemID then
    return GetContainerItemID(bag, slot)
  end
  return nil
end

local function ContainerNumSlots(bag)
  if C_Container and C_Container.GetContainerNumSlots then
    return C_Container.GetContainerNumSlots(bag) or 0
  end
  if GetContainerNumSlots then
    return GetContainerNumSlots(bag) or 0
  end
  return 0
end

-- 화면 중앙: 끈적이만 (대해가오리는 우편 불필요)
local goopFrame = CreateFrame("Frame", "GoopAlertFrame", UIParent)
goopFrame:SetSize(64, 64)
goopFrame:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
goopFrame:SetFrameStrata("HIGH")
goopFrame:EnableMouse(false)
goopFrame:Hide()

local goopIcon = goopFrame:CreateTexture(nil, "ARTWORK")
goopIcon:SetAllPoints(goopFrame)
goopIcon:SetTexCoord(0.08, 0.92, 0.08, 0.92)

local goopPresence = goopFrame:CreateTexture(nil, "OVERLAY")
goopPresence:SetSize(22, 22)
goopPresence:SetPoint("TOPRIGHT", goopFrame, "TOPRIGHT", 6, 6)
goopPresence:SetColorTexture(128 / 255, 0, 1, 1) -- 보라 = 끈적이

-- 우측 상단: 낚시 합계 막대
local CELL = 16
local GAP = 2
local BITS = 20
local CELLS = BITS + 2

local function MakeCountBar(frameName, anchorY, startR, startG, startB, endR, endG, endB, labelR, labelG, labelB)
  local panel = CreateFrame("Frame", frameName, UIParent)
  panel:SetSize(CELLS * (CELL + GAP) - GAP, 52)
  panel:SetPoint("TOPRIGHT", UIParent, "TOPRIGHT", -16, anchorY)
  panel:SetFrameStrata("TOOLTIP")
  panel:EnableMouse(false)
  panel:Show()

  local label = panel:CreateFontString(nil, "OVERLAY", "GameFontNormalHuge")
  label:SetPoint("TOPRIGHT", panel, "TOPRIGHT", 0, 0)
  label:SetTextColor(labelR, labelG, labelB)

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

  local function Update(count)
    SetRGB(cells[1], startR, startG, startB)
    for i = 1, BITS do
      local bitOn = math.floor(count / (2 ^ (i - 1))) % 2 == 1
      if bitOn then
        SetRGB(cells[i + 1], 0.94, 0.94, 0.94)
      else
        SetRGB(cells[i + 1], 0.04, 0.04, 0.04)
      end
    end
    SetRGB(cells[CELLS], endR, endG, endB)
    label:SetText(tostring(count))
  end

  return Update
end

-- 낚시: 시작(255,0,80) ~ 끝(0,255,80), 노란 숫자
local UpdateFishBar = MakeCountBar(
  "GoopAlertFishBar", -16,
  1, 0, 80 / 255,
  0, 1, 80 / 255,
  1, 1, 0.2
)
-- 대해가오리: 시작(0,180,255) ~ 끝(255,100,0), 하늘색 숫자
local UpdateRayBar = MakeCountBar(
  "GoopAlertRayBar", -72,
  0, 180 / 255, 1,
  1, 100 / 255, 0,
  0.4, 0.85, 1
)

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
    goopPresence:SetColorTexture(128 / 255, 0, 1, 1)
    goopFrame:Show()
  else
    goopFrame:Hide()
  end
end

-- 색 마커: 탭=마젠타, 보내기=시안, 가방끈적이=노랑
local function MakeMark(name, size, r, g, b)
  local f = CreateFrame("Frame", name, UIParent)
  f:SetSize(size, size)
  f:SetFrameStrata("TOOLTIP")
  f:SetFrameLevel(10000)
  f:EnableMouse(false)
  local t = f:CreateTexture(nil, "OVERLAY")
  t:SetAllPoints()
  t:SetColorTexture(r, g, b, 1)
  f.tex = t
  f:Hide()
  return f
end

local mailTabMark = MakeMark("GoopAlertMailTabMark", 28, 1, 0, 1)
local mailSendMark = MakeMark("GoopAlertMailSendMark", 28, 0, 1, 1)
local bagGoopMark = MakeMark("GoopAlertBagGoopMark", 18, 1, 1, 0)
local mailAttachMark = MakeMark("GoopAlertMailAttachMark", 26, 1, 0.45, 0)

local function AnchorMark(mark, parent, point)
  if not parent then
    mark:Hide()
    return
  end
  point = point or "CENTER"
  mark:ClearAllPoints()
  mark:SetParent(parent)
  mark:SetFrameStrata("TOOLTIP")
  mark:SetFrameLevel(10000)
  if point == "TOPLEFT" then
    mark:SetPoint("TOPLEFT", parent, "TOPLEFT", 1, -1)
  else
    mark:SetPoint("CENTER", parent, "CENTER", 0, 0)
  end
  mark:Show()
end

local function MailHasGoopAttached()
  local maxSend = ATTACHMENTS_MAX_SEND or 12
  for i = 1, maxSend do
    if HasSendMailItem and HasSendMailItem(i) then
      local _name, itemID = GetSendMailItem(i)
      if itemID == GOOP_ITEM_ID then
        return i
      end
    end
  end
  return nil
end

local function GetSendAttachmentButton(index)
  if SendMailFrame and SendMailFrame.SendMailAttachments then
    return SendMailFrame.SendMailAttachments[index]
  end
  return _G["SendMailAttachment" .. tostring(index)]
end

local function UpdateMailMarks()
  local mailOpen = MailFrame and MailFrame:IsShown()
  if not mailOpen then
    mailTabMark:Hide()
    mailSendMark:Hide()
    mailAttachMark:Hide()
    return
  end

  local tab = _G["MailFrameTab2"] or _G["MailFrameTab_2"]
  if tab and tab:IsShown() then
    AnchorMark(mailTabMark, tab, "CENTER")
  else
    mailTabMark:Hide()
  end

  local attachIdx = MailHasGoopAttached()
  if attachIdx then
    AnchorMark(mailAttachMark, GetSendAttachmentButton(attachIdx), "CENTER")
  else
    mailAttachMark:Hide()
  end

  local sendBtn = _G["SendMailMailButton"]
  if (
    attachIdx
    and sendBtn
    and sendBtn:IsShown()
    and SendMailFrame
    and SendMailFrame:IsShown()
  ) then
    AnchorMark(mailSendMark, sendBtn, "CENTER")
  else
    mailSendMark:Hide()
  end
end

local function BagIndexRange()
  local first = 0
  local last = NUM_BAG_SLOTS or 4
  if Enum and Enum.BagIndex then
    first = Enum.BagIndex.Backpack or 0
    if Enum.BagIndex.ReagentBag then
      last = Enum.BagIndex.ReagentBag
    elseif NUM_TOTAL_EQUIPPED_BAG_SLOTS then
      last = NUM_TOTAL_EQUIPPED_BAG_SLOTS
    end
  elseif NUM_TOTAL_EQUIPPED_BAG_SLOTS then
    last = NUM_TOTAL_EQUIPPED_BAG_SLOTS
  end
  return first, last
end

local function FindGoopItemButton()
  local first, last = BagIndexRange()
  for bag = first, last do
    local slots = ContainerNumSlots(bag)
    for slot = 1, slots do
      if ContainerItemID(bag, slot) == GOOP_ITEM_ID then
        if ContainerFrameUtil_GetItemButtonAndContainer then
          local btn = ContainerFrameUtil_GetItemButtonAndContainer(bag, slot)
          if btn and btn:IsVisible() then
            return btn
          end
        end
      end
    end
  end
  return nil
end

local function EnsureBagsOpen()
  if OpenAllBags then
    OpenAllBags()
  end
end

local function UpdateBagGoopMark()
  if not (MailFrame and MailFrame:IsShown()) then
    bagGoopMark:Hide()
    return
  end
  if MailHasGoopAttached() then
    bagGoopMark:Hide()
    return
  end
  if ItemCount(GOOP_ITEM_ID) <= 0 then
    bagGoopMark:Hide()
    return
  end

  EnsureBagsOpen()
  local btn = FindGoopItemButton()
  if btn then
    AnchorMark(bagGoopMark, btn, "TOPLEFT")
  else
    bagGoopMark:Hide()
  end
end

local function Refresh()
  UpdateGoop()
  UpdateFishBar(FishTotal())
  UpdateRayBar(RayTotal())
  UpdateMailMarks()
  UpdateBagGoopMark()
end

local function RefreshMailDelayed()
  UpdateMailMarks()
  UpdateBagGoopMark()
  C_Timer.After(0.05, function()
    UpdateMailMarks()
    UpdateBagGoopMark()
  end)
  C_Timer.After(0.25, function()
    UpdateMailMarks()
    UpdateBagGoopMark()
  end)
  C_Timer.After(0.6, function()
    UpdateMailMarks()
    UpdateBagGoopMark()
  end)
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("BAG_UPDATE_DELAYED")
events:RegisterEvent("BAG_UPDATE")
events:RegisterEvent("MAIL_SHOW")
events:RegisterEvent("MAIL_CLOSED")
events:RegisterEvent("MAIL_SEND_INFO_UPDATE")
events:RegisterEvent("MAIL_FAILED")
events:RegisterEvent("MAIL_SEND_SUCCESS")
events:SetScript("OnEvent", function(_, event)
  if event == "MAIL_SHOW" then
    EnsureBagsOpen()
    Refresh()
    RefreshMailDelayed()
  elseif event == "MAIL_CLOSED" then
    mailTabMark:Hide()
    mailSendMark:Hide()
    mailAttachMark:Hide()
    bagGoopMark:Hide()
    Refresh()
  else
    Refresh()
    if MailFrame and MailFrame:IsShown() then
      RefreshMailDelayed()
    end
  end
end)

if MailFrame then
  MailFrame:HookScript("OnShow", function()
    EnsureBagsOpen()
    RefreshMailDelayed()
  end)
  MailFrame:HookScript("OnHide", function()
    mailTabMark:Hide()
    mailSendMark:Hide()
    mailAttachMark:Hide()
    bagGoopMark:Hide()
  end)
end

if ContainerFrameCombinedBags then
  ContainerFrameCombinedBags:HookScript("OnShow", function()
    C_Timer.After(0.05, UpdateBagGoopMark)
    C_Timer.After(0.2, UpdateBagGoopMark)
  end)
end

SLASH_GOOPALERT1 = "/goopalert"
SlashCmdList.GOOPALERT = function()
  EnsureBagsOpen()
  Refresh()
  print(
    "GoopAlert 끈적이=", ItemCount(GOOP_ITEM_ID),
    "대해가오리=", RayTotal(),
    "낚시합계=", FishTotal(),
    "우편탭=", mailTabMark:IsShown() and "Y" or "N",
    "첨부주황=", mailAttachMark:IsShown() and "Y" or "N",
    "보내기=", mailSendMark:IsShown() and "Y" or "N",
    "가방노랑=", bagGoopMark:IsShown() and "Y" or "N"
  )
end

Refresh()
