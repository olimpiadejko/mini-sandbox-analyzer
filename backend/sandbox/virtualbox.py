
import subprocess
from pathlib import Path


VBOXMANAGE = Path(
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
)

VM_NAME = "MiniSandbox-Windows"


class VirtualBoxError(Exception):
    """Błąd komunikacji z VirtualBox."""


def run_vbox_command(*args: str) -> str:
    """Wykonuje dozwolone polecenie VBoxManage."""

    if not VBOXMANAGE.is_file():
        raise VirtualBoxError("Nie znaleziono VBoxManage.exe")

    try:
        result = subprocess.run(
            [str(VBOXMANAGE), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        return result.stdout

    except subprocess.TimeoutExpired as exc:
        raise VirtualBoxError(
            "Przekroczono czas oczekiwania na VirtualBox."
        ) from exc

    except subprocess.CalledProcessError as exc:
        raise VirtualBoxError(
            exc.stderr.strip() or "Polecenie VirtualBox nie powiodło się."
        ) from exc


def get_vm_state() -> str:
    """Zwraca aktualny stan maszyny."""

    output = run_vbox_command(
        "showvminfo",
        VM_NAME,
        "--machinereadable"
    )

    for line in output.splitlines():
        if line.startswith("VMState="):
            return line.split("=", 1)[1].strip('"')

    raise VirtualBoxError("Nie udało się odczytać stanu VM.")
