--[[
  FishingAssist
  LED strip at TOPLEFT for an external Python helper:
    [1] FISHING : blue when channeling Fishing
    [2] TARGET  : magenta when target item is in bags
    [3] READY   : green when addon is healthy
  Slash: /fa status | /fa target <itemId|itemLink> | /fa clear
]]

local LED_SIZE = 48
local DEFAULT_TARGET_ITEM_ID = 187662

FishingAssistDB = FishingAssistDB or {}

local state = {
  fishing = false,
  hasTarget = false,
  savedArc = nil,
  savedRange = nil,
  softApplied = false,
}

local root, ledFishing, ledTarget, ledReady

local function Print(msg)
  if DEFAULT_CHAT_FRAME then
    DEFAULT_CHAT_FRAME:AddMessage("|cff00ccffFishingAssist|r: " .. tostring(msg))
  end
end

local function EnsureDB()
  if type(FishingAssistDB) ~= "table" then
    FishingAssistDB = {}
  end
  if FishingAssistDB.targetItemId == nil then
    FishingAssistDB.targetItemId = DEFAULT_TARGET_ITEM_ID
  end
end

local function SetLed(frame, r, g, b, on)
  if not frame or not frame.tex then
    return
  end
  if on then
    frame.tex:SetColorTexture(r, g, b, 1)
  else
    frame.tex:SetColorTexture(0, 0, 0, 1)
  end
end

local function RefreshLeds()
  SetLed(ledFishing, 0, 0, 1, state.fishing)
  SetLed(ledTarget, 1, 0, 1, state.hasTarget)
  SetLed(ledReady, 0, 1, 0, true)
end

local function CreateLed(parent, index)
  local f = CreateFrame("Frame", nil, parent)
  f:SetSize(LED_SIZE, LED_SIZE)
  f:SetPoint("TOPLEFT", parent, "TOPLEFT", (index - 1) * LED_SIZE, 0)
  f:EnableMouse(false)

  local border = f:CreateTexture(nil, "BACKGROUND")
  border:SetAllPoints(f)
  border:SetColorTexture(1, 1, 1, 1)

  local tex = f:CreateTexture(nil, "ARTWORK")
  tex:SetPoint("TOPLEFT", f, "TOPLEFT", 3, -3)
  tex:SetPoint("BOTTOMRIGHT", f, "BOTTOMRIGHT", -3, 3)
  tex:SetColorTexture(0, 0, 0, 1)
  f.tex = tex
  return f
end

local function BuildUI()
  if root then
    root:Show()
    RefreshLeds()
    return
  end

  root = CreateFrame("Frame", "FishingAssistLEDRoot", UIParent)
  root:SetSize(LED_SIZE * 3, LED_SIZE)
  root:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 0, 0)
  root:SetFrameStrata("FULLSCREEN_DIALOG")
  root:SetFrameLevel(10000)
  root:EnableMouse(false)
  if root.SetIgnoreParentScale then
    root:SetIgnoreParentScale(true)
  end
  root:SetScale(1)

  ledFishing = CreateLed(root, 1)
  ledTarget = CreateLed(root, 2)
  ledReady = CreateLed(root, 3)
  root:Show()
  RefreshLeds()
end

local function IsFishingChannel()
  local name = UnitChannelInfo("player")
  if not name then
    return false
  end
  name = string.lower(tostring(name))
  -- English "fish" covers Fishing / Fishing Bobber channel names.
  -- Korean client often still reports a name containing these bytes for fishing.
  if string.find(name, "fish", 1, true) then
    return true
  end
  -- UTF-8 for Korean fishing word without putting non-ASCII in source file
  if string.find(name, "\235\130\154\236\139\156", 1, true) then
    return true
  end
  return false
end

local function ApplySoftInteract(enable)
  if enable and not state.softApplied then
    state.savedArc = GetCVar("SoftTargetInteractArc")
    state.savedRange = GetCVar("SoftTargetInteractRange")
    SetCVar("SoftTargetInteractArc", "2")
    SetCVar("SoftTargetInteractRange", "30")
    state.softApplied = true
  elseif (not enable) and state.softApplied then
    if state.savedArc ~= nil then
      SetCVar("SoftTargetInteractArc", state.savedArc)
    end
    if state.savedRange ~= nil then
      SetCVar("SoftTargetInteractRange", state.savedRange)
    end
    state.savedArc = nil
    state.savedRange = nil
    state.softApplied = false
  end
end

local function UpdateFishingState()
  local fishing = IsFishingChannel()
  if fishing ~= state.fishing then
    state.fishing = fishing
    ApplySoftInteract(fishing)
    RefreshLeds()
  end
end

local function CountTargetItem()
  EnsureDB()
  local id = FishingAssistDB.targetItemId
  if not id or id == 0 then
    return 0
  end
  if C_Item and C_Item.GetItemCount then
    local ok, count = pcall(C_Item.GetItemCount, id)
    if ok and type(count) == "number" then
      return count
    end
  end
  if GetItemCount then
    local ok, count = pcall(GetItemCount, id)
    if ok and type(count) == "number" then
      return count
    end
  end
  return 0
end

local function UpdateTargetState()
  local has = CountTargetItem() > 0
  if has ~= state.hasTarget then
    state.hasTarget = has
    RefreshLeds()
    if has then
      Print("Target item found in bags - stop fishing.")
    end
  end
end

local function ParseItemId(input)
  if not input or input == "" then
    return nil
  end
  local id = string.match(input, "item:(%d+)")
  if id then
    return tonumber(id)
  end
  id = string.match(input, "^(%d+)$")
  if id then
    return tonumber(id)
  end
  return nil
end

local function Trim(s)
  return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", ""))
end

local function RegisterSlash()
  SLASH_FISHINGASSIST1 = "/fa"
  SLASH_FISHINGASSIST2 = "/fishingassist"
  SlashCmdList["FISHINGASSIST"] = function(msg)
    EnsureDB()
    msg = Trim(msg)
    local cmd, rest = string.match(msg, "^(%S+)%s*(.-)$")
    cmd = string.lower(cmd or "status")
    rest = Trim(rest)

    if cmd == "status" or cmd == "" then
      Print(string.format(
        "fishing=%s target=%s itemId=%s count=%d soft=%s",
        tostring(state.fishing),
        tostring(state.hasTarget),
        tostring(FishingAssistDB.targetItemId),
        CountTargetItem(),
        tostring(state.softApplied)
      ))
    elseif cmd == "target" then
      local id = ParseItemId(rest)
      if not id then
        Print("Usage: /fa target <itemId|itemLink>")
        return
      end
      FishingAssistDB.targetItemId = id
      UpdateTargetState()
      Print("Target item set to " .. id)
    elseif cmd == "clear" then
      FishingAssistDB.targetItemId = 0
      UpdateTargetState()
      Print("Target item cleared")
    else
      Print("Commands: /fa status | /fa target <id|link> | /fa clear")
    end
  end
end

RegisterSlash()

local eventFrame = CreateFrame("Frame", "FishingAssistEventFrame")
eventFrame:RegisterEvent("ADDON_LOADED")
eventFrame:RegisterEvent("PLAYER_LOGIN")
eventFrame:RegisterEvent("PLAYER_ENTERING_WORLD")
eventFrame:RegisterEvent("BAG_UPDATE")
eventFrame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
eventFrame:RegisterUnitEvent("UNIT_SPELLCAST_CHANNEL_START", "player")
eventFrame:RegisterUnitEvent("UNIT_SPELLCAST_CHANNEL_STOP", "player")
eventFrame:RegisterUnitEvent("UNIT_SPELLCAST_CHANNEL_UPDATE", "player")
eventFrame:RegisterUnitEvent("UNIT_SPELLCAST_INTERRUPTED", "player")

eventFrame:SetScript("OnEvent", function(_, event, arg1)
  if event == "ADDON_LOADED" and arg1 == "FishingAssist" then
    EnsureDB()
    RegisterSlash()
    BuildUI()
    Print("loaded. Try /fa status")
  elseif event == "PLAYER_LOGIN" or event == "PLAYER_ENTERING_WORLD" then
    RegisterSlash()
    BuildUI()
    UpdateFishingState()
    UpdateTargetState()
  elseif event == "BAG_UPDATE" or event == "PLAYER_EQUIPMENT_CHANGED" then
    UpdateTargetState()
  else
    UpdateFishingState()
  end
end)

eventFrame:SetScript("OnUpdate", function(self, elapsed)
  self.t = (self.t or 0) + elapsed
  if self.t < 0.25 then
    return
  end
  self.t = 0
  UpdateFishingState()
  UpdateTargetState()
end)
