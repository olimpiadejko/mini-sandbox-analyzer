from pathlib import Path

# Ścieżka do programu VBoxManage i nazwa maszyny
VBOXMANAGE = Path(r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe")
VM_NAME = "MiniSandbox-Windows"

VM_START_TIMEOUT = 180
VM_SHUTDOWN_TIMEOUT = 180
VM_STATE_TIMEOUT = 120
VBOX_COMMAND_TIMEOUT = 60