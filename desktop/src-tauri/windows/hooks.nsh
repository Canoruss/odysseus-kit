; Automatically terminates any running background/tray Odysseus instance before copying files,
; allowing 1-click in-place NSIS upgrades without manually uninstalling or losing user config.
!macro NSIS_HOOK_PREINSTALL
  SetOverwrite on
  nsExec::ExecToStack 'taskkill /IM "odysseus-desktop.exe"'
  nsExec::ExecToStack 'taskkill /IM "Odysseus.exe"'
  Sleep 400
  nsExec::ExecToStack 'taskkill /F /IM "odysseus-desktop.exe"'
  nsExec::ExecToStack 'taskkill /F /IM "Odysseus.exe"'
  Sleep 400
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  nsExec::ExecToStack 'taskkill /F /IM "odysseus-desktop.exe"'
  nsExec::ExecToStack 'taskkill /F /IM "Odysseus.exe"'
  Sleep 400
!macroend
