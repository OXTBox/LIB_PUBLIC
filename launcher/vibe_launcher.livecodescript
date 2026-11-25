script "Vibecode3D_Launcher"
######################################################################################
## STACK SCRIPT: "Vibecode3D_Launcher"  (LIB_PUBLIC/launcher, 15 Nov 2026, Opus)
## The Vibecode3D library app for an installed PC (the V: simulation, LIB_PUBLIC/install/
## LAYOUT.md): Steam's library window, made in OXT-Beyond and saved as a standalone that sits
## beside Vibecode3D.exe in  Program Files (x86)\Vibecode3D\.
##
## Started with no arguments   the library: every title in every library folder, Play,
##                             Show Folder, Verify Files.
## Started with a game folder  that game in its own window (one game per program: the engine
##   ( -game <folder>  or       keeps its state in globals). Play starts a second copy of this
##     just <folder> )          program this way, so closing the library leaves games running.
##
## Where things are (all found from the program's own folder, never from one PC's paths):
##   <install>\vibeapps\                     the default library; more in libraryfolders.txt
##   <library>\common\<Game>\game.txt        what the folder holds (the truth; manifests are a cache)
##   <library>\appmanifest_<appid>.txt       last updated, size
##   <library>\common\Vibecode3D Common\Engine\   vibe_engine_xt3d, game_player, GameNotes
## Game errors go to %LOCALAPPDATA%\Vibecode3D\logs\game_errors.txt.
## The UI is made by VL.BuildUI the first time the stack opens, so the stack is just this script.
######################################################################################

constant kW = 960
constant kH = 600
constant kListW = 300
constant kCommonRel = "Vibecode3D Common/Engine"

local sRoot, sGames, sOrder, sFilter, sSel, sTestRoot

-------------------------------------------------------------------- start

on openStack
   -- only for this stack (game windows have their own scripts)
   if the short name of the owner of the target is not the short name of me then pass openStack
   VL.Start
end openStack

on closeStackRequest
   set the destroyStack of me to true
   pass closeStackRequest
end closeStackRequest

command VL.Start
   local tFolder, tWhy
   put VL.GameArg() into tFolder
   if the environment is "standalone application" then VL.Log "started:" && $# && "arguments: [" & $1 & "] [" & $2 & "] game folder: [" & tFolder & "]"
   if tFolder is not empty then
      hide me
      put VL.Play(tFolder, true) into tWhy
      if tWhy is not empty then
         VL.Log "could not start" && tFolder & ":" && tWhy
         if the environment is "standalone application" then
            answer "Vibecode3D could not start this game:" & return & tWhy
            quit
         end if
      end if
      -- this copy only plays the game: once its window is open, the library stack goes
      -- (destroyStack true); if no game window opened, this copy closes and quits
      if the environment is "standalone application" then send "VL.CloseSelf" to me in 3 seconds
      exit VL.Start
   end if
   VL.BuildUI
   VL.Refresh
end VL.Start

-- the game folder from the command line: -game <folder>, or a folder holding game.txt
function VL.GameArg
   local tA, tB, tErr
   try
      put $1 into tA
      put $2 into tB
   catch tErr
      return empty
   end try
   if tA is "-game" then return tB
   if tA is not empty and there is a file (tA & "/game.txt") then return tA
   return empty
end VL.GameArg

-- the install folder: beside the program (standalone), else the simulated PC's V: drive
function VL.Root
   if sTestRoot is not empty then return sTestRoot
   if sRoot is not empty then return sRoot
   if the environment is "standalone application" then
      put specialFolderPath("engine") into sRoot
   else
      put "V:/Program Files (x86)/Vibecode3D" into sRoot
   end if
   replace "\" with "/" in sRoot
   return sRoot
end VL.Root

-------------------------------------------------------------------- reading the libraries

function VL.ReadText pPath
   local tText
   if there is not a file pPath then return empty
   put textDecode(URL ("binfile:" & pPath), "UTF-8") into tText
   replace numToChar(13) & numToChar(10) with return in tText
   replace numToChar(13) with return in tText
   return tText
end VL.ReadText

-- game.txt: key TAB value lines
function VL.ReadKV pPath
   local tA, tLine
   set the itemDelimiter to tab
   repeat for each line tLine in VL.ReadText(pPath)
      if tLine is empty or char 1 of tLine is "#" then next repeat
      put item 2 to -1 of tLine into tA[item 1 of tLine]
   end repeat
   return tA
end VL.ReadKV

-- an appmanifest: "Key"   "Value" lines (Steam's KeyValues look)
function VL.ReadManifest pPath
   local tA, tLine, tParts
   repeat for each line tLine in VL.ReadText(pPath)
      put empty into tParts
      if matchText(tLine, "^\s*" & quote & "([^" & quote & "]+)" & quote & "\s+" & quote & "([^" & quote & "]*)" & quote, tParts["k"], tParts["v"]) then
         put tParts["v"] into tA[tParts["k"]]
      end if
   end repeat
   return tA
end VL.ReadManifest

-- every library's vibeapps folder: beside the program first, then the others in its
-- libraryfolders.txt (relative to the program, or with a drive letter)
function VL.Libraries
   local tList, tLine, tPath, tParts, tSeen
   put VL.Root() & "/vibeapps" into tList
   put true into tSeen[toLower(tList)]
   repeat for each line tLine in VL.ReadText(VL.Root() & "/vibeapps/libraryfolders.txt")
      put empty into tParts
      if not matchText(tLine, "(?i)" & quote & "path" & quote & "\s+" & quote & "([^" & quote & "]+)" & quote, tParts) then next repeat
      put tParts into tPath
      replace "\\" with "/" in tPath
      replace "\" with "/" in tPath
      -- on the program's own drive a library is written relative to it (a USB stick that
      -- comes up as another letter still works)
      if not (matchText(tPath, "^[A-Za-z]:") or tPath begins with "/") then put VL.Root() & "/" & tPath into tPath
      put tPath & "/vibeapps" into tPath
      if tSeen[toLower(tPath)] is true then next repeat
      put true into tSeen[toLower(tPath)]
      if there is a folder tPath then put return & tPath after tList
   end repeat
   return tList
end VL.Libraries

-- read every game folder into sGames[id]
command VL.Scan
   local tLib, tDir, tG, tM, tId, tFolders
   put empty into sGames
   repeat for each line tLib in VL.Libraries()
      if there is not a folder (tLib & "/common") then next repeat
      put folders(tLib & "/common") into tFolders
      repeat for each line tDir in tFolders
         if tDir is "." or tDir is ".." or tDir is empty then next repeat
         put VL.ReadKV(tLib & "/common/" & tDir & "/game.txt") into tG
         if tG["name"] is empty then next repeat
         if tG["kind"] is "redist" then next repeat
         put tG["appid"] into tId
         if tId is empty then put tDir into tId
         if sGames[tId]["name"] is not empty then next repeat   -- the first library wins
         put tG into sGames[tId]
         put tLib & "/common/" & tDir into sGames[tId]["folder"]
         put tLib into sGames[tId]["library"]
         put VL.ReadManifest(tLib & "/appmanifest_" & tId & ".txt") into tM
         put tM["LastUpdated"] into sGames[tId]["updated"]
         put tM["SizeOnDisk"] into sGames[tId]["size"]
         put (tM["installdir"] is not empty) into sGames[tId]["manifest"]
      end repeat
   end repeat
end VL.Scan

-- the ids shown for the filter (All, Games, Betas, Tools), by name
function VL.Ordered pFilter
   local tId, tOut
   repeat for each key tId in sGames
      if pFilter is "Games" and sGames[tId]["kind"] is not "game" then next repeat
      if pFilter is "Tools" and sGames[tId]["kind"] is not "tool" then next repeat
      if pFilter is "Betas" and sGames[tId]["branch"] is not "beta" then next repeat
      -- a title marked "listed last" in its game.txt goes after the rest (p1-26: the old Dot Maze)
      if sGames[tId]["listed"] is "last" then put "2" after tOut else put "1" after tOut
      put sGames[tId]["name"] & tab & tId & return after tOut
   end repeat
   delete last char of tOut
   sort lines of tOut by item 1 of each
   set the itemDelimiter to tab
   put empty into sOrder
   repeat for each line tId in tOut
      put item 2 of tId & return after sOrder
   end repeat
   delete last char of sOrder
   return sOrder
end VL.Ordered

-- what a game's script header says (as LIB_DEV's GL.Info): about, keys, rules
function VL.Info pId
   local tScript, tInfo, tLine, tText, tMode
   put VL.ReadText(sGames[pId]["folder"] & "/" & sGames[pId]["script"]) into tScript
   repeat for each line tLine in line 1 to 30 of tScript
      if not (tLine begins with "##") then
         if tLine is not empty then exit repeat
         next repeat
      end if
      if char 3 to 5 of tLine is "###" or tLine is "##" then next repeat
      put char 4 to -1 of tLine into tText
      if word 1 of tText is "CARD" and word 2 of tText is "SCRIPT:" then next repeat
      if word 1 of tText is "CONTROLS" then
         put "keys" into tMode
         delete word 1 of tText
      else if word 1 of tText is "RULES" then
         put "rules" into tMode
         delete word 1 of tText
      end if
      if tMode is empty then put "about" into tMode
      put word 1 to -1 of tText & return after tInfo[tMode]
   end repeat
   return tInfo
end VL.Info

-- what is wrong with a game's folder (empty: nothing)
function VL.Check pId
   local tOut, tF, tD
   put sGames[pId]["folder"] into tF
   if there is not a file (tF & "/game.txt") then put "no game.txt" & return after tOut
   if sGames[pId]["script"] is empty then
      put "game.txt names no script" & return after tOut
   else if VL.ReadText(tF & "/" & sGames[pId]["script"]) is empty then
      put "missing: " & sGames[pId]["script"] & return after tOut
   end if
   set the itemDelimiter to comma
   repeat for each item tD in sGames[pId]["data"]
      if tD is not empty and there is not a folder (tF & "/" & tD) then put "missing data folder: " & tD & return after tOut
   end repeat
   if sGames[pId]["manifest"] is not true then put "no appmanifest (the library will rebuild it)" & return after tOut
   if VL.EngineFile(tF, "vibe_engine_xt3d.livecodescript") is empty then put "Vibecode3D Common has no engine" & return after tOut
   delete last char of tOut
   return tOut
end VL.Check

-- a file of the engine, from the Vibecode3D Common beside the game's folder
function VL.EngineFile pFolder, pName
   local tPath
   put pFolder into tPath
   replace "\" with "/" in tPath
   set the itemDelimiter to "/"
   if item -1 of tPath is empty then delete item -1 of tPath
   delete item -1 of tPath
   put tPath & "/" & kCommonRel & "/" & pName into tPath
   if there is a file tPath then return tPath
   return empty
end VL.EngineFile

-- the hidden AUDIO stack (LIB_AUDIO in Vibecode3D Common/Engine), as LIB_DEV's GL.Audio: the
-- game's sounds fill one per tick and ... > Sounds... chooses them (and Edit... makes new ones).
-- The kit in Vibecode3D Common/Sounds goes into the player's Sounds folder the first time.
-- No lib_audio there (an older install): the engine's own sound kit, as before.
command VL.Audio pFolder, pName, pFile
   global bNoAudio
   local tLib, tErr, tCommon
   if bNoAudio is true then exit VL.Audio
   put VL.EngineFile(pFolder, "lib_audio.livecodescript") into tLib
   if tLib is empty then exit VL.Audio
   set the itemDelimiter to "/"
   put item 1 to -3 of tLib into tCommon
   set the itemDelimiter to comma
   try
      if not ("lib_audio" is among the lines of the stacksInUse) then start using stack tLib
      if not Audio.IsOpen() then
         Audio.Open
         Audio.Seed tCommon & "/Sounds", tCommon & "/Music"
      end if
      set the itemDelimiter to "/"
      Audio.Refresh item 1 to -2 of pFile
      set the itemDelimiter to comma
      Audio.Select pName, pFile
   catch tErr
   end try
end VL.Audio

-------------------------------------------------------------------- the window

command VL.BuildUI
   local tObj
   set the title of me to "Vibecode3D"
   set the resizable of me to false
   set the backgroundColor of me to "18,20,28"
   set the foregroundColor of me to "220,226,240"
   set the textFont of me to "Arial"
   set the textSize of me to 13
   set the width of me to kW
   set the height of me to kH
   if there is not a field "Header" of me then
      create field "Header" in card 1 of me
      set the lockText of it to true
      set the opaque of it to false
      set the showBorder of it to false
      set the textSize of it to 20
      set the textStyle of it to "bold"
      set the rect of it to 16, 10, 400, 44
      put "VIBECODE3D  LIBRARY" into it
   end if
   if there is not a button "Filter" of me then
      create button "Filter" in card 1 of me
      set the style of it to "menu"
      set the menuMode of it to "option"
      set the text of it to "All titles" & return & "Games" & return & "Betas" & return & "Tools"
      set the label of it to "All titles"
      set the rect of it to 16, 52, kListW, 76
   end if
   if there is not a field "Games" of me then
      create field "Games" in card 1 of me
      set the listBehavior of it to true
      set the dontWrap of it to true
      set the lockText of it to true
      set the vScrollbar of it to true
      set the backgroundColor of it to "28,31,42"
      set the hiliteColor of it to "60,110,200"
      set the borderWidth of it to 0
      set the textSize of it to 14
      set the rect of it to 16, 84, kListW, kH - 40
   end if
   if there is not a field "Title" of me then
      create field "Title" in card 1 of me
      set the lockText of it to true
      set the opaque of it to false
      set the showBorder of it to false
      set the textSize of it to 26
      set the textStyle of it to "bold"
      set the rect of it to kListW + 24, 48, kW - 16, 88
   end if
   repeat for each item tObj in "Play,Folder,Verify"
      if there is not a button tObj of me then
         create button tObj in card 1 of me
         set the style of it to "standard"
      end if
   end repeat
   set the label of button "Play" of me to "PLAY"
   set the textStyle of button "Play" of me to "bold"
   set the backgroundColor of button "Play" of me to "70,160,90"
   set the rect of button "Play" of me to kListW + 24, 96, kListW + 144, 128
   set the label of button "Folder" of me to "Show Folder"
   set the rect of button "Folder" of me to kListW + 156, 96, kListW + 276, 128
   set the label of button "Verify" of me to "Verify Files"
   set the rect of button "Verify" of me to kListW + 288, 96, kListW + 408, 128
   if there is not a field "Details" of me then
      create field "Details" in card 1 of me
      set the lockText of it to true
      set the vScrollbar of it to true
      set the backgroundColor of it to "28,31,42"
      set the borderWidth of it to 0
      set the rect of it to kListW + 24, 140, kW - 16, kH - 40
   end if
   if there is not a field "Status" of me then
      create field "Status" in card 1 of me
      set the lockText of it to true
      set the opaque of it to false
      set the showBorder of it to false
      set the textSize of it to 11
      set the rect of it to 16, kH - 32, kW - 16, kH - 8
   end if
end VL.BuildUI

command VL.Refresh
   local tList, tId, tSel, tN
   VL.Scan
   if sFilter is empty then put "All titles" into sFilter
   -- p1-07 (23 Nov): a number left of each name, so a tester can say "game 21", not "Thrmnlra"
   set the tabStops of field "Games" of me to 36
   put 0 into tN
   repeat for each line tId in VL.Ordered(sFilter)
      add 1 to tN
      put tN & tab & sGames[tId]["name"] into tSel
      if sGames[tId]["branch"] is "beta" then put "   (beta)" after tSel
      put tSel & return after tList
   end repeat
   delete last char of tList
   put tList into field "Games" of me
   if sOrder is empty then
      put empty into field "Title" of me
      put "No titles found in" && VL.Root() & "/vibeapps" into field "Details" of me
      VL.Say "0 titles"
      exit VL.Refresh
   end if
   put lineOffset(sSel, sOrder) into tSel
   if sSel is empty or tSel is 0 then put 1 into tSel
   VL.Select tSel
   VL.Say the number of lines of sOrder && "titles  |  " & the number of lines of VL.Libraries() && "library folder(s)  |  " & VL.Root()
end VL.Refresh

command VL.Select pLine
   local tId, tInfo, tText
   put line pLine of sOrder into tId
   if tId is empty then exit VL.Select
   put tId into sSel
   set the hilitedLine of field "Games" of me to pLine
   put pLine & "  " & sGames[tId]["name"] into field "Title" of me
   put VL.Info(tId) into tInfo
   if tInfo["about"] is not empty then put tInfo["about"] & return after tText
   if tInfo["keys"] is not empty then put "CONTROLS" & return & tInfo["keys"] & return after tText
   if tInfo["rules"] is not empty then put "RULES" & return & tInfo["rules"] & return after tText
   put "----" & return after tText
   put "App" && tId && "|" && sGames[tId]["kind"] after tText
   if sGames[tId]["branch"] is "beta" then put "  |  beta (" & sGames[tId]["ref"] & ")" after tText
   put return after tText
   if sGames[tId]["updated"] is not empty then put "Updated" && sGames[tId]["updated"] & return after tText
   if sGames[tId]["size"] is not empty then put "Size" && VL.Size(sGames[tId]["size"]) & return after tText
   put VL.WinPath(sGames[tId]["folder"]) after tText
   put tText into field "Details" of me
   set the enabled of button "Play" of me to (sGames[tId]["script"] is not empty)
end VL.Select

function VL.Size pBytes
   if pBytes is not a number then return pBytes
   if pBytes < 1024 then return pBytes && "bytes"
   if pBytes < 1048576 then return round(pBytes / 1024) && "KB"
   return round(pBytes / 1048576, 1) && "MB"
end VL.Size

function VL.WinPath pPath
   if the platform is "Win32" then replace "/" with "\" in pPath
   return pPath
end VL.WinPath

command VL.Say pText
   if there is a field "Status" of me then put pText into field "Status" of me
end VL.Say

on mouseUp
   local tName
   put the short name of the target into tName
   switch tName
      case "Games"
         if the hilitedLine of field "Games" of me is a number then VL.Select the hilitedLine of field "Games" of me
         break
      case "Play"
         VL.PlaySelected
         break
      case "Folder"
         VL.ShowFolder
         break
      case "Verify"
         VL.VerifyAll
         break
   end switch
end mouseUp

on mouseDoubleUp
   if the short name of the target is "Games" then VL.PlaySelected
end mouseDoubleUp

on arrowKey pDir
   local tL
   if the selectedField is not empty then pass arrowKey
   put the hilitedLine of field "Games" of me into tL
   if tL is not a number then put 0 into tL
   if pDir is "down" and tL < the number of lines of sOrder then VL.Select tL + 1
   if pDir is "up" and tL > 1 then VL.Select tL - 1
   if pDir is not "down" and pDir is not "up" then pass arrowKey
end arrowKey

on returnKey
   VL.PlaySelected
end returnKey

on menuPick pItem
   if the short name of the target is not "Filter" then pass menuPick
   put pItem into sFilter
   if sFilter is "All titles" then put "All titles" into sFilter
   VL.Refresh
end menuPick

-------------------------------------------------------------------- buttons

-- Play: a second copy of this program plays the game (one game per program)
command VL.PlaySelected
   local tWhy
   if sSel is empty then exit VL.PlaySelected
   if the environment is "standalone application" then
      put VL.LaunchCopy(sGames[sSel]["folder"]) into tWhy
   else
      put VL.Play(sGames[sSel]["folder"], false) into tWhy
   end if
   if tWhy is empty then
      VL.Say "Started" && sGames[sSel]["name"]
   else
      VL.Say "Could not start" && sGames[sSel]["name"] & ":" && tWhy
   end if
end VL.PlaySelected

-- the copy is started with Windows' start command (start "" "<exe>" -game "<folder>"), which
-- returns at once: this library is then free to answer the copy's relaunch message (a new copy
-- waits for that answer). 'launch ... with' kept the library busy, and the first Play only
-- opened another library (16 Nov).
function VL.LaunchCopy pFolder
   local tExe, tErr, tCmd, tOut
   put the effective filename of me into tExe
   if tExe is empty then return "this program's own file is unknown"
   replace "\" with "/" in pFolder
   if char -1 of pFolder is "/" then delete char -1 of pFolder
   if the platform is not "Win32" then
      try
         launch VL.WinPath(pFolder) with VL.WinPath(tExe)
      catch tErr
         return line 1 of tErr
      end try
      return empty
   end if
   put "start " & quote & quote & space & quote & VL.WinPath(tExe) & quote & " -game " & quote & VL.WinPath(pFolder) & quote into tCmd
   VL.Log "play:" && tCmd
   set the hideConsoleWindows to true
   try
      put shell(tCmd) into tOut
   catch tErr
      return line 1 of tErr
   end try
   if the result is not empty and the result is not 0 then return "start said:" && the result && tOut
   return empty
end VL.LaunchCopy

-- a game copy, 3 seconds after its start: the library stack closes (destroyStack true). When
-- no game window is open, the copy did nothing (owner, 16 Nov: the first Play's copy never
-- opened its game): it says so in the log and quits instead of lingering
command VL.CloseSelf
   local tStack, tOpen
   put false into tOpen
   repeat for each line tStack in the openStacks
      if tStack begins with "Play " and the visible of stack tStack then put true into tOpen
   end repeat
   if not tOpen then
      VL.Log "no game window 3 seconds after the start: this copy quits"
      set the destroyStack of me to true
      quit
   end if
   set the destroyStack of me to true
   close me
end VL.CloseSelf

-- a second copy of this program was started: let it run (it is a game, or another library)
on relaunch
   pass relaunch
end relaunch

command VL.ShowFolder
   local tErr
   if sSel is empty then exit VL.ShowFolder
   try
      launch document VL.WinPath(sGames[sSel]["folder"])
   catch tErr
      VL.Say "Could not open the folder:" && line 1 of tErr
   end try
end VL.ShowFolder

command VL.VerifyAll
   local tId, tBad, tN, tOut, tWhy
   VL.Scan
   put 0 into tN
   put 0 into tBad
   repeat for each key tId in sGames
      add 1 to tN
      put VL.Check(tId) into tWhy
      if tWhy is empty then next repeat
      add 1 to tBad
      replace return with "; " in tWhy
      put sGames[tId]["name"] & ":" && tWhy & return after tOut
   end repeat
   sort lines of tOut
   put "Verify Files" into field "Title" of me
   if tBad is 0 then
      put tN && "titles checked: every folder is complete." into field "Details" of me
   else
      put tN && "titles checked," && tBad && "with problems:" & return & return & tOut into field "Details" of me
   end if
   VL.Say "Verified" && tN && "titles," && tBad && "with problems"
end VL.VerifyAll

-------------------------------------------------------------------- playing

-- a game's folder in its own window (as LIB_DEV's GL.Open, from the install's own files).
-- pQuitOnClose: closing the window ends the program. Returns empty, or why it could not.
function VL.Play pFolder, pQuitOnClose
   local tG, tFile, tScript, tEngine, tPlayer, tNotes, tName, tStack, tInfo, tErr, tLevels, tAt
   global gV3DSkin
   replace "\" with "/" in pFolder
   if char -1 of pFolder is "/" then delete char -1 of pFolder
   put VL.ReadKV(pFolder & "/game.txt") into tG
   if tG["script"] is empty then return "not a game folder (no game.txt):" && pFolder
   put pFolder & "/" & tG["script"] into tFile
   put VL.ReadText(tFile) into tScript
   if tScript is empty then return "no game script:" && tFile
   put VL.EngineFile(pFolder, "vibe_engine_xt3d.livecodescript") into tEngine
   if tEngine is empty then return "Vibecode3D Common has no engine (Engine/vibe_engine_xt3d.livecodescript)"
   put VL.ReadText(VL.EngineFile(pFolder, "game_player.livecodescript")) into tPlayer
   if tPlayer is empty then return "Vibecode3D Common has no game player (Engine/game_player.livecodescript)"
   try
      if not ("VibeEngineXt3d" is among the lines of the stacksInUse) then start using stack tEngine
   catch tErr
      return "the engine did not load:" && line 1 of tErr
   end try
   put VL.EngineFile(pFolder, "GameNotes.livecodescript") into tNotes
   if tNotes is not empty and not ("GameNotes" is among the lines of the frontScripts) then
      try
         start using stack tNotes
         insert script of stack "GameNotes" into front
      catch tErr
      end try
   end if
   put empty into gV3DSkin
   -- Vibecode3D_Play_<Name>.livecodescript: the card is "Play.<Name>"
   put tG["script"] into tName
   if tName begins with "Vibecode3D_Play_" then delete char 1 to 16 of tName
   set the itemDelimiter to "."
   put item 1 of tName into tName
   VL.Audio pFolder, tName, tFile
   put "Play" && tName into tStack
   if there is a stack tStack then close stack tStack
   lock messages
   create invisible stack tStack
   unlock messages
   set the defaultStack to tStack
   set the script of stack tStack to tPlayer
   if the result is not empty then
      put the result into tErr
      delete stack tStack
      return "the game player does not compile:" && tErr
   end if
   set the name of card 1 of stack tStack to "Play." & tName
   set the script of card 1 of stack tStack to tScript
   if the result is not empty then
      put the result into tErr
      delete stack tStack
      return tName && "does not compile:" && tErr
   end if
   -- the level menu: <Prefix>.StartLevel, 5 levels unless the header says otherwise
   put 0 into tLevels
   repeat for each line tAt in tScript
      if word 1 of tAt is "on" and word 2 of tAt ends with ".StartLevel" then
         set the uPrefix of stack tStack to char 1 to -12 of word 2 of tAt
         put 5 into tLevels
         exit repeat
      end if
   end repeat
   if tLevels > 0 and matchText(line 1 to 30 of tScript, "(?i)\b([0-9]+) levels", tAt) then
      if tAt is an integer and tAt > 0 and tAt < 100 then put tAt into tLevels
   end if
   set the uGame of stack tStack to tName
   set the uScriptFile of stack tStack to tFile
   set the uLevels of stack tStack to tLevels
   set the uQuitOnClose of stack tStack to (pQuitOnClose is true)
   set the uErrorFile of stack tStack to VL.ErrorFile()
   set the backgroundColor of stack tStack to "0,0,0"
   set the resizable of stack tStack to false
   set the destroyStack of stack tStack to true
   if tG["name"] is not empty then put tG["name"] into tName
   set the title of stack tStack to tName && "|  Vibecode3D  |  Escape pauses, ... top right: Reset, Levels, Quit"
   set the rect of stack tStack to VL.WindowRect()
   try
      show stack tStack
      go stack tStack
   catch tErr
      return "the window did not open:" && line 1 of tErr
   end try
   send "Player.Start" to stack tStack in 50 milliseconds
   return empty
end VL.Play

function VL.WindowRect
   local tL, tT
   put max(0, (item 3 of the screenRect - 900) div 2) into tL
   put max(30, (item 4 of the screenRect - 600) div 2) into tT
   return tL, tT, tL + 900, tT + 600
end VL.WindowRect

-- %LOCALAPPDATA%\Vibecode3D\logs\ (this machine only, safe to lose), else the temporary folder
function VL.LogFolder
   local tDir, tErr
   put $LOCALAPPDATA into tDir
   if tDir is empty then
      put specialFolderPath("temporary") into tDir
   else
      replace "\" with "/" in tDir
      put "/Vibecode3D" after tDir
      try
         if there is not a folder tDir then create folder tDir
         put "/logs" after tDir
         if there is not a folder tDir then create folder tDir
      catch tErr
         put specialFolderPath("temporary") into tDir
      end try
   end if
   return tDir
end VL.LogFolder

function VL.ErrorFile
   return VL.LogFolder() & "/game_errors.txt"
end VL.ErrorFile

command VL.Log pText
   local tFile, tText, tErr
   try
      put VL.LogFolder() & "/launcher.txt" into tFile
      put VL.ReadText(tFile) into tText
      put the short date && the long time & tab & pText & return after tText
      put textEncode(tText, "UTF-8") into URL ("binfile:" & tFile)
   catch tErr
   end try
end VL.Log

-------------------------------------------------------------------- test hooks

command VL.TestRoot pPath
   put pPath into sTestRoot
end VL.TestRoot

function VL.Count
   return the number of lines of sOrder
end VL.Count

function VL.NameOf pId
   return sGames[pId]["name"]
end VL.NameOf

function VL.Field pName
   return field pName of me
end VL.Field

function VL.SelId
   return sSel
end VL.SelId

function VL.FolderOf pName
   local tId
   repeat for each key tId in sGames
      if sGames[tId]["name"] is pName then return sGames[tId]["folder"]
   end repeat
   return empty
end VL.FolderOf
