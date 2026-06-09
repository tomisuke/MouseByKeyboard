import keyboard, time, sys

log = open("debug_hotkey.txt", "w", encoding="utf-8")

def on_active():
    log.write("HOTKEY ACTIVE FIRED\n")
    log.flush()

def on_all():
    log.write("HOTKEY ALL FIRED\n")
    log.flush()

keyboard.add_hotkey("ctrl+shift+q", on_active)
keyboard.add_hotkey("ctrl+q", on_all)

log.write("Hotkeys registered. Waiting 10s...\n")
log.flush()
time.sleep(10)
log.write("Done\n")
log.close()
