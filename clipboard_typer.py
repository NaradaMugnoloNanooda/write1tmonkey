""" ClipboardTyper — Reliable GlobalHotKeys + Tray
===============================================
Hotkey : Alt + Z + X
Uses pynput GlobalHotKeys (most reliable method on Windows)
"""

import time
import random
import threading
import sys
import atexit
import ctypes
import pyperclip
import pystray
from PIL import Image, ImageDraw
from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Controller, GlobalHotKeys

# ─────────────────────────────────────────
#  SINGLE-INSTANCE SANDBOX LOCK
#  Uses a Windows Named Mutex — resolves in <1ms.
#  Change SANDBOX_ID if you ever want two separate
#  variants to coexist independently.
# ─────────────────────────────────────────

SANDBOX_ID = "ClipboardTyper_SingleInstance_v1"  # ← unique app identity
_mutex_handle = None  # module-level handle so it stays alive for process lifetime


def enforce_single_instance():
    """
    Creates a named Windows mutex tied to SANDBOX_ID.
    If another process already owns it, this instance exits immediately.
    The first/highest-priority instance always wins — no election needed.
    """
    global _mutex_handle

    # Create or open the named mutex
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(
        None,       # default security attributes
        True,       # this process requests initial ownership
        SANDBOX_ID  # the shared sandbox name
    )

    last_error = ctypes.windll.kernel32.GetLastError()

    # ERROR_ALREADY_EXISTS = 183
    # Means another instance already owns this mutex → we are the duplicate
    if last_error == 183:
        print(
            f"[ClipboardTyper] Duplicate instance detected "
            f"(sandbox: '{SANDBOX_ID}'). Exiting in <1ms."
        )
        # Release our redundant handle before exiting
        if _mutex_handle:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        sys.exit(0)  # hard exit — millisecond-level termination

    # Register cleanup so the mutex is properly released on normal shutdown
    atexit.register(_release_mutex)
    print(f"[ClipboardTyper] Single-instance lock acquired (sandbox: '{SANDBOX_ID}').")


def _release_mutex():
    """Releases the named mutex on clean exit."""
    global _mutex_handle
    if _mutex_handle:
        ctypes.windll.kernel32.ReleaseMutex(_mutex_handle)
        ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None


# ─────────────────────────────────────────
CHARS_PER_MINUTE = 1200   # ~240 WPM — fastest human typist tier
VARIANCE_MS      = 30     # natural ±ms jitter kept
# ─────────────────────────────────────────

controller         = Controller()
is_typing          = False
stop_typing        = threading.Event()
tray_icon          = None
typing_started_at  = 0.0
INTERRUPT_COOLDOWN = 2.0

IGNORED_INTERRUPT_KEYS = {
    Key.alt, Key.alt_l, Key.alt_r,
    Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    Key.shift, Key.shift_l, Key.shift_r,
    Key.cmd, Key.cmd_l, Key.cmd_r,
    Key.caps_lock, Key.num_lock, Key.scroll_lock,
    Key.insert, Key.print_screen, Key.pause,
    Key.media_play_pause, Key.media_next, Key.media_previous,
    Key.media_volume_up, Key.media_volume_down, Key.media_volume_mute,
}

# ─────────────────────────────────────────
#  TRAY ICON
# ─────────────────────────────────────────

def make_icon(state="idle"):
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = {
        "idle":        ((50, 200, 100, 255),  (30, 150, 70, 255)),
        "typing":      ((255, 165, 0, 255),   (200, 120, 0, 255)),
        "interrupted": ((220, 50, 50, 255),   (160, 30, 30, 255)),
    }
    fill, outline = colors.get(state, colors["idle"])
    draw.ellipse([4, 4, 60, 60], fill=fill, outline=outline, width=4)
    for i in range(3):
        draw.rectangle([14+i*14, 26, 22+i*14, 34], fill=(255, 255, 255, 200))
    draw.rectangle([18, 38, 46, 44], fill=(255, 255, 255, 200))
    return img


def set_tray(state, tooltip=None):
    global tray_icon
    if tray_icon:
        tray_icon.icon = make_icon(state)
        if tooltip:
            tray_icon.title = tooltip
        tray_icon.menu = build_menu()


def on_stop_click(icon, item):
    if is_typing:
        stop_typing.set()


def on_quit(icon, item):
    stop_typing.set()
    icon.stop()


def build_menu():
    status = "● Typing..." if is_typing else "● Idle — Ready"
    return pystray.Menu(
        pystray.MenuItem(status,                            None, enabled=False),
        pystray.MenuItem("⌨  Hotkey: ALT+Z+X",             None, enabled=False),
        pystray.MenuItem(f"⚡ Speed: {CHARS_PER_MINUTE} CPM", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("⛔ Stop Typing", on_stop_click, enabled=lambda item: is_typing),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("✖ Quit", on_quit),
    )

# ─────────────────────────────────────────
#  TYPING ENGINE
# ─────────────────────────────────────────

def type_text(text):
    global is_typing, typing_started_at
    is_typing = True
    typing_started_at = time.time()
    stop_typing.clear()
    set_tray("typing", f"Typing {len(text)} chars...")
    delay = 60.0 / CHARS_PER_MINUTE
    for char in text:
        if stop_typing.is_set():
            print("[ClipboardTyper] Interrupted.")
            set_tray("interrupted", "ClipboardTyper — Interrupted")
            time.sleep(0.4)
            break
        try:
            controller.type(char)
        except Exception:
            pass
        jitter = random.uniform(VARIANCE_MS / 1000, VARIANCE_MS / 1000)
        time.sleep(max(0, delay + jitter))
    is_typing = False
    set_tray("idle", "ClipboardTyper — Idle (Alt+Z+X)")
    print("[ClipboardTyper] Done.")


def trigger_typing():
    """Called by hotkey — small delay so keys release before typing starts."""
    time.sleep(0.25)
    text = pyperclip.paste()
    if not text or not text.strip():
        print("[ClipboardTyper] Clipboard empty!")
        set_tray("interrupted", "ClipboardTyper — Clipboard empty!")
        time.sleep(1)
        set_tray("idle", "ClipboardTyper — Idle (Alt+Z+X)")
        return
    print(f"[ClipboardTyper] Hotkey fired! Typing {len(text)} chars...")
    threading.Thread(target=type_text, args=(text,), daemon=True).start()

# ─────────────────────────────────────────
#  INTERRUPT LISTENER
# ─────────────────────────────────────────

def on_any_key_press(key):
    """Only ESC interrupts typing."""
    if is_typing:
        if key == Key.esc:
            print("[ClipboardTyper] Interrupted by ESC.")
            stop_typing.set()


def start_interrupt_listener():
    with keyboard.Listener(on_press=on_any_key_press) as l:
        l.join()

# ─────────────────────────────────────────
#  GLOBAL HOTKEY LISTENER
# ─────────────────────────────────────────

def start_hotkey_listener():
    with GlobalHotKeys({
        '<alt>+z+x':   lambda: threading.Thread(target=trigger_typing, daemon=True).start(),
        '<alt_l>+z+x': lambda: threading.Thread(target=trigger_typing, daemon=True).start(),
        '<alt_r>+z+x': lambda: threading.Thread(target=trigger_typing, daemon=True).start(),
    }) as h:
        h.join()

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────

def main():
    global tray_icon

    # ── Single-instance guard — must be FIRST ──
    enforce_single_instance()
    # ───────────────────────────────────────────

    print("=" * 50)
    print("  ClipboardTyper — Running")
    print("  Hotkey   : Alt + Z + X")
    print("  Speed    : 1200 CPM")
    print("  Interrupt: ESC while typing")
    print("  Stop     : Tray → Quit or Ctrl+C")
    print("=" * 50)

    hk_thread = threading.Thread(target=start_hotkey_listener, daemon=True)
    hk_thread.start()

    int_thread = threading.Thread(target=start_interrupt_listener, daemon=True)
    int_thread.start()

    tray_icon = pystray.Icon(
        "ClipboardTyper",
        make_icon("idle"),
        "ClipboardTyper — Idle (Alt+Z+X)",
        build_menu()
    )
    try:
        tray_icon.run()
    except Exception as e:
        print(f"[Tray error] {e}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[ClipboardTyper] Stopped.")


if __name__ == "__main__":
    main()