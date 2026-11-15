
import json
import subprocess
import time
from pathlib import Path


# Ścieżka do programu VBoxManage
VBOXMANAGE = Path(
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
)

# Nazwa maszyny wirtualnej
# Można ją zmienić po utworzeniu docelowej VM.
VM_NAME = "MiniSandbox-Windows"


class VirtualBoxError(Exception):
    """Błąd komunikacji z VirtualBox."""
    pass


def check_vbox_available() -> bool:
    """
    Sprawdza, czy VBoxManage jest dostępny
    i czy można wykonać polecenie.
    """

    if not VBOXMANAGE.is_file():
        return False

    try:
        subprocess.run(
            [str(VBOXMANAGE), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True
        )
        return True

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        OSError
    ):
        return False


def run_vbox_command(*args: str) -> str:
    """
    Wykonuje polecenie VBoxManage
    i zwraca jego standardowe wyjście.
    """

    if not VBOXMANAGE.is_file():
        raise VirtualBoxError(
            "Nie znaleziono VBoxManage.exe."
        )

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
        message = (
            exc.stderr.strip()
            or exc.stdout.strip()
            or "Polecenie VirtualBox nie powiodło się."
        )

        raise VirtualBoxError(message) from exc

    except OSError as exc:
        raise VirtualBoxError(
            f"Nie udało się uruchomić VBoxManage: {exc}"
        ) from exc


def get_vm_info() -> dict:
    """
    Pobiera informacje o maszynie wirtualnej
    i zwraca je jako słownik.
    """

    output = run_vbox_command(
        "showvminfo",
        VM_NAME,
        "--machinereadable"
    )

    vm_info = {}

    for line in output.splitlines():
        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        try:
            vm_info[key] = json.loads(value)
        except json.JSONDecodeError:
            vm_info[key] = value.strip('"')

    return vm_info


def get_vm_state() -> str:
    """
    Zwraca aktualny stan maszyny wirtualnej.
    Przykładowe stany: running, poweroff, paused.
    """

    vm_info = get_vm_info()
    state = vm_info.get("VMState")

    if not state:
        raise VirtualBoxError(
            "Nie udało się odczytać stanu maszyny wirtualnej."
        )

    return str(state)


def wait_for_vm_state(
    expected_state: str,
    timeout: int = 120
) -> bool:
    """
    Czeka, aż maszyna osiągnie określony stan.
    """

    if timeout <= 0:
        raise ValueError(
            "Timeout musi być większy od zera."
        )

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if get_vm_state() == expected_state:
            return True

        time.sleep(2)

    return get_vm_state() == expected_state


def start_vm(timeout: int = 180) -> str:
    """
    Uruchamia maszynę wirtualną
    i czeka na stan running.
    """

    state = get_vm_state()

    if state == "running":
        return "Maszyna jest już uruchomiona."

    if state != "poweroff":
        raise VirtualBoxError(
            f"Nie można uruchomić VM. Aktualny stan: {state}"
        )

    run_vbox_command(
        "startvm",
        VM_NAME,
        "--type",
        "gui"
    )

    if not wait_for_vm_state("running", timeout):
        raise VirtualBoxError(
            "VM nie osiągnęła stanu running w wyznaczonym czasie."
        )

    return "Maszyna wirtualna została uruchomiona."


def shutdown_vm(timeout: int = 180) -> str:
    """
    Wysyła do VM sygnał ACPI
    i czeka na jej poprawne wyłączenie.
    """

    state = get_vm_state()

    if state == "poweroff":
        return "Maszyna jest już wyłączona."

    if state != "running":
        raise VirtualBoxError(
            f"Nie można zamknąć VM. Aktualny stan: {state}"
        )

    run_vbox_command(
        "controlvm",
        VM_NAME,
        "acpipowerbutton"
    )

    if not wait_for_vm_state("poweroff", timeout):
        raise VirtualBoxError(
            "VM nie została wyłączona w wyznaczonym czasie."
        )

    return "Maszyna wirtualna została poprawnie wyłączona."


def restore_snapshot(snapshot_name: str) -> str:
    """
    Przywraca maszynę do wskazanego snapshotu.

    Maszyna musi być całkowicie wyłączona.
    Snapshot musi już istnieć.
    """

    if not isinstance(snapshot_name, str) or not snapshot_name.strip():
        raise ValueError(
            "Nazwa snapshotu nie może być pusta."
        )

    state = get_vm_state()

    if state != "poweroff":
        raise VirtualBoxError(
            "Nie można przywrócić snapshotu. "
            f"Maszyna musi być wyłączona. Aktualny stan: {state}"
        )

    run_vbox_command(
        "snapshot",
        VM_NAME,
        "restore",
        snapshot_name.strip()
    )

    if get_vm_state() != "poweroff":
        raise VirtualBoxError(
            "Po przywróceniu snapshotu VM nie jest wyłączona."
        )

    return (
        f"Przywrócono snapshot: {snapshot_name.strip()}."
    )
