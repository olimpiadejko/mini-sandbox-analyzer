import time
from sandbox.virtualbox import (
    check_vbox_available,
    get_vm_state,
    start_vm,
    shutdown_vm,
    poweroff_vm,      # <--- 1. Importujemy nową funkcję twardego wyłączenia
    restore_snapshot
)

def run_tests():
    print("TEST KOMUNIKACJI Z VIRTUALBOX")

    # 1. Sprawdzenie VBoxManage
    if not check_vbox_available():
        print("BŁĄD: Nie znaleziono VBoxManage.exe lub VirtualBox nie jest poprawnie zainstalowany.")
        return
    print("VBoxManage jest dostępny.")

    try:
        # 2. Sprawdzenie stanu maszyny
        state = get_vm_state()
        print(f"ℹAktualny stan maszyny wirtualnej: {state}")

        # 3. Test przywrócenia snapshotu (wymaga, aby maszyna była wyłączona)
        if state != "poweroff":
            print("Zamykam maszynę w celu przetestowania snapshotu...")
            print(poweroff_vm()) # Zmieniono na twarde wyłączenie dla pewności
        
        snapshot_name = "CzystyStan_Sysmon" # Dokładna nazwa snapshotu w VirtualBoxie
        print(f"Przywracam snapshot: '{snapshot_name}'...")
        res_snap = restore_snapshot(snapshot_name)
        print(f"{res_snap}")

        # 4. Test uruchomienia maszyny
        print("Uruchamiam maszynę wirtualną...")
        res_start = start_vm()
        print(f"{res_start}")

        # Dajemy jej chwilę na rozruch w tle
        time.sleep(10)

        # 5. Twarde zamknięcie po teście (odcięcie zasilania zamiast ACPI)
        print("Wyłączam twardo maszynę wirtualną (Power Off)...")
        res_stop = poweroff_vm()
        print(f"{res_stop}")

        print("\nWszystkie testy integracyjne VirtualBox przeszły pomyślnie!")

    except Exception as e:
        print(f"\nWystąpił błąd podczas testu: {str(e)}")

if __name__ == "__main__":
    run_tests()