import json
from pathlib import Path
import subprocess
import time
from .config import (
    VBOXMANAGE,
    VM_NAME,
    VM_START_TIMEOUT,
    VM_SHUTDOWN_TIMEOUT,
    VM_STATE_TIMEOUT,
    VBOX_COMMAND_TIMEOUT
)

# Dane logowania do systemu gościa
GUEST_USER = "SandboxUser"
GUEST_PASS = "DAO2026!"


class VirtualBoxError(Exception):
    """Błąd komunikacji z VirtualBox."""
    pass


class VirtualBoxCommandError(VirtualBoxError):
    """Polecenie VBoxManage zakończyło się błędem."""
    pass


class VirtualBoxTimeoutError(VirtualBoxError):
    """Przekroczono czas oczekiwania na polecenie."""
    pass


def check_vbox_available() -> bool:
    """Sprawdza, czy VBoxManage jest dostępny."""
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
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        return False


def run_vbox_command(*args: str) -> str:
    """Wykonuje polecenie VBoxManage i zwraca jego wyjście."""
    if not VBOXMANAGE.is_file():
        raise VirtualBoxError("Nie znaleziono VBoxManage.exe.")

    try:
        result = subprocess.run(
            [str(VBOXMANAGE), *args],
            capture_output=True,
            text=True,
            timeout=VBOX_COMMAND_TIMEOUT,
            check=True
        )
        return result.stdout

    except subprocess.TimeoutExpired as exc:
        raise VirtualBoxTimeoutError(
            "Przekroczono czas oczekiwania na VirtualBox."
        ) from exc

    except subprocess.CalledProcessError as exc:
        message = (
            exc.stderr.strip()
            or exc.stdout.strip()
            or "Polecenie VirtualBox nie powiodło się."
        )
        raise VirtualBoxCommandError(message) from exc

    except OSError as exc:
        raise VirtualBoxError(
            f"Nie udało się uruchomić VBoxManage: {exc}"
        ) from exc


def wait_for_guest_additions(timeout: int = 60) -> bool:
    """Czeka, aż Windows i Guest Additions będą gotowe na polecenia."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            run_vbox_command(
                "guestcontrol", VM_NAME, "run",
                "--username", GUEST_USER,
                "--password", GUEST_PASS,
                "--exe", "C:\\Windows\\System32\\cmd.exe",
                "--", "cmd.exe", "/c", "echo ready"
            )
            return True

        except VirtualBoxTimeoutError:
            time.sleep(2)

        except VirtualBoxCommandError as exc:
            # Błąd polecenia może być przejściowy podczas uruchamiania Windows.
            time.sleep(2)

        except VirtualBoxError:
            raise

    raise VirtualBoxError(
        "Usługi Guest Additions w VM nie uruchomiły się w wyznaczonym czasie."
    )


def copy_file_to_guest(host_path: str, guest_path: str = "C:\\Temp\\"):
    """Kopiuje badaną próbkę z hosta do maszyny wirtualnej."""
    source = Path(host_path)

    if not source.is_file():
        raise FileNotFoundError(f"Nie znaleziono pliku: {host_path}")

    wait_for_guest_additions(timeout=60)

    run_vbox_command(
        "guestcontrol", VM_NAME, "copyto",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--target-directory", guest_path,
        str(source.resolve())
    )


def run_sample_in_guest(guest_exe_path: str):
    """Uruchamia badaną próbkę wewnątrz VM."""
    if not guest_exe_path:
        raise ValueError("Ścieżka do pliku wykonywalnego w VM nie może być pusta.")

    run_vbox_command(
        "guestcontrol", VM_NAME, "start",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--exe", guest_exe_path
    )



def export_and_fetch_sysmon_json(host_dest_json: str):
    """Uruchamia Export-Sysmon.ps1 w VM i kopiuje wynikowy plik JSON na hosta."""
    
    destination = Path(host_dest_json)

    if not destination.exists():
        destination.mkdir(parents=True, exist_ok=True)

    if not destination.is_dir():
        raise NotADirectoryError(
            f"Ścieżka docelowa nie jest katalogiem: {host_dest_json}"
        )

    # 1. Uruchomienie skryptu eksportującego logi Sysmon
    run_vbox_command(
        "guestcontrol", VM_NAME, "run",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--exe", "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "--", "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "C:\\SandboxTools\\Export-Sysmon.ps1"
    )

    # 2. Sprawdzenie, czy istnieją pliki JSON, i wybranie najnowszego
    run_vbox_command(
        "guestcontrol", VM_NAME, "run",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--exe", "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "--", "powershell.exe", "-NoProfile", "-Command",
        """
        $files = Get-ChildItem 'E:\\AnalysisResults\\Sysmon\\*.json' |
            Where-Object { $_.Name -ne 'latest.json' }

        if (-not $files) {
            Write-Error 'Nie znaleziono plików JSON z logami Sysmon.'
            exit 1
        }

        $latest = $files |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        Copy-Item $latest.FullName `
            -Destination 'E:\\AnalysisResults\\Sysmon\\latest.json' -Force
        """
    )

    # 3. Pobranie latest.json z VM na komputer hosta
    run_vbox_command(
        "guestcontrol", VM_NAME, "copyfrom",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--target-directory", str(destination.resolve()),
        "E:\\AnalysisResults\\Sysmon\\latest.json"
    )

    # 4. Sprawdzenie, czy plik został pobrany
    downloaded_file = destination / "latest.json"

    if not downloaded_file.is_file():
        raise FileNotFoundError(
            f"Nie znaleziono pobranego pliku: {downloaded_file}"
        )

    return str(downloaded_file.resolve())



def get_vm_info() -> dict:
    """Pobiera informacje o maszynie wirtualnej."""
    output = run_vbox_command("showvminfo", VM_NAME, "--machinereadable")
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
    """Zwraca aktualny stan maszyny wirtualnej."""
    vm_info = get_vm_info()
    state = vm_info.get("VMState")
    if not state:
        raise VirtualBoxError("Nie udało się odczytać stanu maszyny wirtualnej.")
    return str(state)


def wait_for_vm_state(expected_state: str, timeout: int = VM_STATE_TIMEOUT) -> bool:
    """Czeka, aż maszyna osiągnie określony stan."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            if get_vm_state() == expected_state:
                return True
        except VirtualBoxError:
            pass

        time.sleep(2)

    return False


def start_vm(timeout: int = VM_START_TIMEOUT) -> str:
    """Uruchamia maszynę wirtualną."""
    state = get_vm_state()
    if state == "running":
        return "Maszyna jest już uruchomiona."
    if state != "poweroff":
        raise VirtualBoxError(f"Nie można uruchomić VM. Aktualny stan: {state}")

    run_vbox_command("startvm", VM_NAME, "--type", "gui")

    if not wait_for_vm_state("running", timeout):
        raise VirtualBoxError("VM nie osiągnęła stanu running w wyznaczonym czasie.")
    return "Maszyna wirtualna została uruchomiona."


def shutdown_vm(timeout: int = VM_SHUTDOWN_TIMEOUT) -> str:
    """Wysyła do VM sygnał ACPI (miękkie zamknięcie)."""
    state = get_vm_state()
    if state == "poweroff":
        return "Maszyna jest już wyłączona."
    if state != "running":
        raise VirtualBoxError(f"Nie można zamknąć VM. Aktualny stan: {state}")

    run_vbox_command("controlvm", VM_NAME, "acpipowerbutton")

    if not wait_for_vm_state("poweroff", timeout):
        raise VirtualBoxError("VM nie została wyłączona w wyznaczonym czasie.")
    return "Maszyna wirtualna została poprawnie wyłączona."


def poweroff_vm() -> str:
    """Natychmiastowo wyłącza maszynę wirtualną (twarde odcięcie zasilania)."""
    state = get_vm_state()
    if state == "poweroff":
        return "Maszyna jest już wyłączona."

    run_vbox_command("controlvm", VM_NAME, "poweroff")
    time.sleep(2)
    return "Maszyna wirtualna została twardo wyłączona."


def restore_snapshot(snapshot_name: str) -> str:
    """Przywraca maszynę do wskazanego snapshotu."""
    if not isinstance(snapshot_name, str) or not snapshot_name.strip():
        raise ValueError("Nazwa snapshotu nie może być pusta.")

    state = get_vm_state()
    if state != "poweroff":
        raise VirtualBoxError(f"Maszyna musi być wyłączona. Aktualny stan: {state}")

    run_vbox_command("snapshot", VM_NAME, "restore", snapshot_name.strip())
    return f"Przywrócono snapshot: {snapshot_name.strip()}."