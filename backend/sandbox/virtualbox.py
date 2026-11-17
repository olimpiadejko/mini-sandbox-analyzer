import json
import subprocess
import time
from pathlib import Path
import os

# Ścieżka do programu VBoxManage
VBOXMANAGE = Path(
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
)

# Nazwa maszyny wirtualnej oraz dane logowania do systemu gościa
VM_NAME = "MiniSandbox-Windows"
GUEST_USER = "SandboxUser"
GUEST_PASS = "DAO2026!"


class VirtualBoxError(Exception):
    """Błąd komunikacji z VirtualBox."""
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
            timeout=60,
            check=True
        )
        return result.stdout
    except subprocess.TimeoutExpired as exc:
        raise VirtualBoxError("Przekroczono czas oczekiwania na VirtualBox.") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "Polecenie VirtualBox nie powiodło się."
        raise VirtualBoxError(message) from exc
    except OSError as exc:
        raise VirtualBoxError(f"Nie udało się uruchomić VBoxManage: {exc}") from exc


def wait_for_guest_additions(timeout: int = 60) -> bool:
    """Czeka, aż Windows i usługa VirtualBox Guest Additions będą gotowe na polecenia."""
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
        except VirtualBoxError:
            time.sleep(2)
    raise VirtualBoxError("Usługi Guest Additions w VM nie uruchomiły się w wyznaczonym czasie.")


def copy_file_to_guest(host_path: str, guest_path: str = "C:\\Temp\\"):
    """Kopiuje badaną próbkę z hosta do maszyny wirtualnej."""
    wait_for_guest_additions(timeout=60)
    run_vbox_command(
        "guestcontrol", VM_NAME, "copyto",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--target-directory", guest_path,
        host_path
    )


def run_sample_in_guest(guest_exe_path: str):
    """Uruchamia badaną próbkę wewnątrz VM w tle."""
    cmd = [
        str(VBOXMANAGE), "guestcontrol", VM_NAME, "start",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--exe", guest_exe_path
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def export_and_fetch_sysmon_json(host_dest_json: str):
    """Uruchamia Export-Sysmon.ps1 w VM i kopiuje wynikowy plik JSON na hosta."""
    # 1. Uruchomienie skryptu PowerShell w VM (tworzy JSON w E:\AnalysisResults\Sysmon)
    run_vbox_command(
        "guestcontrol", VM_NAME, "run",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--exe", "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "--", "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "C:\\SandboxTools\\Export-Sysmon.ps1"
    )

    # 2. Skopiowanie najnowszego wygenerowanego pliku JSON pod stałą nazwę latest.json
    run_vbox_command(
        "guestcontrol", VM_NAME, "run",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--exe", "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "--", "powershell.exe", "-Command",
        "Get-ChildItem 'E:\\AnalysisResults\\Sysmon\\*.json' | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Copy-Item -Destination 'E:\\AnalysisResults\\Sysmon\\latest.json' -Force"
    )

    # 3. Pobranie latest.json z VM na komputer główny
    run_vbox_command(
        "guestcontrol", VM_NAME, "copyfrom",
        "--username", GUEST_USER,
        "--password", GUEST_PASS,
        "--target-directory", host_dest_json,
        "E:\\AnalysisResults\\Sysmon\\latest.json"
    )


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


def wait_for_vm_state(expected_state: str, timeout: int = 120) -> bool:
    """Czeka, aż maszyna osiągnie określony stan."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if get_vm_state() == expected_state:
            return True
        time.sleep(2)
    return get_vm_state() == expected_state


def start_vm(timeout: int = 180) -> str:
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


def shutdown_vm(timeout: int = 180) -> str:
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