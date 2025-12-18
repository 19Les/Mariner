import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import pyautogui
import time
import random
import keyboard
import winsound
import os
import sys
import json
os.environ['TCL_LIBRARY'] = r'C:\Python\tcl\tcl8.6'
os.environ['TK_LIBRARY'] = r'C:\Python\tcl\tk8.6'
import tkinter as tk
from tkinter import ttk
import threading
import traceback

# ==========================================
# KONFIGURACJA GLOBALNA
# ==========================================
USER_SETTINGS = {
    'RES': 'FHD',
    'MODE': 'CZAS',
    'TIME': 20
}


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


KONFIGURACJE = {
    'FHD': {
        'ryba_img': resource_path('ind2.png'), 'ryba_reg': (534, 1008, 32, 32),
        'spacja_img': resource_path('space2.png'), 'spacja_reg': (798, 973, 65, 16),
        'zero_img': resource_path('gotowy.png'), 'zero_reg': (606, 1027, 47, 12),
        'dno_img': resource_path('dno.png'), 'dno_reg': (536, 1024, 30, 12),
        'tension_reg': (943, 1047, 10, 11)
    },
    '2K': {
        'ryba_img': resource_path('indicator.png'), 'ryba_reg': (855, 1369, 30, 30),
        'spacja_img': resource_path('space.png'), 'spacja_reg': (1120, 1227, 62, 16),
        'zero_img': resource_path('ready.png'), 'zero_reg': (896, 1387, 34, 9),
        'dno_img': resource_path('movement.png'), 'dno_reg': (856, 1384, 65, 12),
        'tension_reg': (933, 1407, 10, 11)
    }
}

PLIK_STATYSTYK = 'stats.json'
KLAWISZ_START = 'F8'
KLAWISZ_KONIEC = 'F12'

PROG_DOPASOWANIA = 0.65
MAX_CZAS_HOLU = 900
TIMEOUT_OPADANIA = 600
MOC_RZUTU_CZAS = 0.1

# Zmienne stanu (Globalne)
running = False
kill_signal = False

# --- STATYSTYKI RYB ---
TOTAL_COUNTER = 0
SESSION_COUNTER = 0

# --- STATYSTYKI CZASU ---
TOTAL_TIME_SECONDS = 0.0
SESSION_TIME_SECONDS = 0.0

BOT_STATUS = "GOTOWY"
ACTIVE_CONFIG = {}

root = None
lbl_counter = None
lbl_status = None


# ==========================================
# OBSŁUGA KLAWISZY (ASYNCHRONICZNA)
# ==========================================
def toggle_reset():
    global running
    resetuj_klawisze()
    running = not running
    if running:
        set_status("START")
        winsound.Beep(600, 200)
    else:
        set_status("RESET")
        zapisz_statystyki()
        winsound.Beep(400, 200)


def kill_bot():
    global kill_signal
    print("\n!!! KILL SWITCH (F12) !!!")
    kill_signal = True
    resetuj_klawisze()
    zapisz_statystyki()
    winsound.Beep(200, 500)
    os._exit(0)


def resetuj_klawisze():
    pyautogui.mouseUp(button='right')
    pyautogui.mouseUp(button='left')
    pyautogui.keyUp('shift')


# ==========================================
# NARZĘDZIA SYSTEMOWE I POMOCNICZE
# ==========================================
def format_time(seconds):
    """Zamienia sekundy na format HH:MM:SS"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def wczytaj_statystyki():
    global TOTAL_COUNTER, TOTAL_TIME_SECONDS
    if os.path.exists(PLIK_STATYSTYK):
        try:
            with open(PLIK_STATYSTYK, 'r') as f:
                data = json.load(f)
                TOTAL_COUNTER = data.get('total_fish', 0)
                TOTAL_TIME_SECONDS = data.get('total_time', 0.0)
        except:
            TOTAL_COUNTER = 0
            TOTAL_TIME_SECONDS = 0.0


def zapisz_statystyki():
    try:
        data = {
            'total_fish': TOTAL_COUNTER,
            'total_time': TOTAL_TIME_SECONDS
        }
        with open(PLIK_STATYSTYK, 'w') as f:
            json.dump(data, f)
    except:
        pass


def pobierz_obraz_z_ekranu(region, gray=True):
    x, y, width, height = region
    hwnd = win32gui.GetDesktopWindow()
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)
    saveDC.BitBlt((0, 0), (width, height), mfcDC, (x, y), win32con.SRCCOPY)
    bmpstr = saveBitMap.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype='uint8')
    img.shape = (height, width, 4)
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    if gray:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    else:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def szukaj_wzorca(template_gray, region, prog=PROG_DOPASOWANIA):
    try:
        screen_gray = pobierz_obraz_z_ekranu(region, gray=True)
        if screen_gray.shape[0] < template_gray.shape[0] or screen_gray.shape[1] < template_gray.shape[1]:
            return False, 0.0
        res = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return (True, max_val) if max_val >= prog else (False, max_val)
    except:
        return False, 0.0


def czy_jest_czerwone(region):
    try:
        img_bgr = pobierz_obraz_z_ekranu(region, gray=False)
        blue, green, red = np.average(np.average(img_bgr, axis=0), axis=0)
        if red > 140 and green < 100 and blue < 100: return True
        return False
    except:
        return False


def set_status(text):
    global BOT_STATUS
    BOT_STATUS = text


# ==========================================
# SMART WAIT
# ==========================================
def wait(seconds):
    end_time = time.time() + seconds
    while time.time() < end_time:
        if kill_signal: os._exit(0)
        if not running: return False
        time.sleep(0.01)
    return True


# ==========================================
# LAUNCHER
# ==========================================
def show_launcher():
    launcher = tk.Tk()
    launcher.title("Konfiguracja")
    launcher.geometry("300x400")
    launcher.configure(bg='#1a1b26')
    launcher.attributes('-topmost', True)
    launcher.lift()

    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TRadiobutton', background='#1a1b26', foreground='white', font=('Segoe UI', 10))

    var_res = tk.StringVar(value='2K')
    var_mode = tk.StringVar(value='CZAS')
    var_time = tk.StringVar(value='20')

    tk.Label(launcher, text="MARINER SETUP", font=("Segoe UI", 16, "bold"), bg='#1a1b26', fg='#7aa2f7').pack(pady=15)

    tk.Label(launcher, text="Rozdzielczość:", bg='#1a1b26', fg='#a9b1d6').pack(anchor='w', padx=20)
    ttk.Radiobutton(launcher, text="FHD (1920x1080)", variable=var_res, value='FHD').pack(anchor='w', padx=30)
    ttk.Radiobutton(launcher, text="2K (2560x1440)", variable=var_res, value='2K').pack(anchor='w', padx=30)

    tk.Label(launcher, text="", bg='#1a1b26').pack()
    tk.Label(launcher, text="Tryb opadania:", bg='#1a1b26', fg='#a9b1d6').pack(anchor='w', padx=20)
    ttk.Radiobutton(launcher, text="Czasowy (Stały)", variable=var_mode, value='CZAS').pack(anchor='w', padx=30)

    f_time = tk.Frame(launcher, bg='#1a1b26')
    f_time.pack(anchor='w', padx=50)
    tk.Label(f_time, text="Sekundy:", bg='#1a1b26', fg='#565f89').pack(side='left')
    tk.Entry(f_time, textvariable=var_time, width=5).pack(side='left', padx=5)

    ttk.Radiobutton(launcher, text="Auto-Dno (Obraz)", variable=var_mode, value='DNO').pack(anchor='w', padx=30)

    def on_start():
        USER_SETTINGS['RES'] = var_res.get()
        USER_SETTINGS['MODE'] = var_mode.get()
        try:
            USER_SETTINGS['TIME'] = int(var_time.get())
        except:
            USER_SETTINGS['TIME'] = 20
        launcher.destroy()

    tk.Button(launcher, text="URUCHOM", command=on_start, bg='#00e676', font=("Segoe UI", 10, "bold"), width=15).pack(
        pady=25)
    launcher.mainloop()


# ==========================================
# LOGIKA BOTA
# ==========================================
def bot_logic():
    global running, SESSION_COUNTER, TOTAL_COUNTER, ACTIVE_CONFIG

    try:
        ACTIVE_CONFIG = KONFIGURACJE[USER_SETTINGS['RES']]

        for plik in ['ryba_img']:
            if not os.path.isfile(ACTIVE_CONFIG[plik]):
                set_status(f"BRAK: {ACTIVE_CONFIG[plik]}")
                return

        template_ryba = cv2.imread(ACTIVE_CONFIG['ryba_img'], 0)
        template_spacja = cv2.imread(ACTIVE_CONFIG['spacja_img'], 0) if os.path.isfile(
            ACTIVE_CONFIG['spacja_img']) else None
        template_zero = cv2.imread(ACTIVE_CONFIG['zero_img'], 0) if os.path.isfile(ACTIVE_CONFIG['zero_img']) else None

        tryb_dno = (USER_SETTINGS['MODE'] == 'DNO')
        czas_opadu = USER_SETTINGS['TIME']
        template_dno = None
        if tryb_dno and os.path.isfile(ACTIVE_CONFIG['dno_img']):
            template_dno = cv2.imread(ACTIVE_CONFIG['dno_img'], 0)

        keyboard.add_hotkey(KLAWISZ_START, toggle_reset)
        keyboard.add_hotkey(KLAWISZ_KONIEC, kill_bot)

        wymagany_rzut = True
        set_status(f"GOTOWY ({KLAWISZ_START})")

        while True:
            if not running:
                wymagany_rzut = True
                while not running:
                    if kill_signal: os._exit(0)
                    time.sleep(0.05)
                continue

            # ========================
            # FAZA 1: RZUT
            # ========================
            if wymagany_rzut:
                set_status("RZUT")

                pyautogui.mouseDown(button='left')
                if not wait(random.uniform(0.08, 0.12)):
                    pyautogui.mouseUp(button='left');
                    continue
                pyautogui.mouseUp(button='left')

                start_opadu = time.time()
                przerwano_opad = False
                set_status("OPADANIE...")

                while True:
                    if not running: break
                    if szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])[0]:
                        set_status("BRANIE (OPAD)!")
                        przerwano_opad = True
                        break
                    teraz = time.time()
                    if tryb_dno and template_dno is not None:
                        if szukaj_wzorca(template_dno, ACTIVE_CONFIG['dno_reg'], prog=0.7)[0]: break
                        if teraz - start_opadu > TIMEOUT_OPADANIA: break
                    else:
                        if teraz - start_opadu > czas_opadu: break
                    if not wait(random.uniform(0.015, 0.025)): break

                if not running: continue

                wymagany_rzut = False

                if not przerwano_opad:
                    pyautogui.mouseDown(button='left')
                    pyautogui.mouseUp(button='left');
                else:
                    set_status("ZAMYKANIE KABŁĄKA!")
                    pyautogui.mouseDown(button='left')
                    if not wait(random.uniform(0.08, 0.12)): continue
                    pyautogui.mouseUp(button='left')
                    if not wait(random.uniform(0.25, 0.35)): continue

            # ========================
            # FAZA 2: JIGOWANIE
            # ========================
            set_status("JIGOWANIE")
            pyautogui.mouseDown(button='right')
            if not wait(random.uniform(0.5, 0.8)):
                pyautogui.mouseUp(button='right');
                continue
            pyautogui.mouseUp(button='right')

            start_skan = time.time()
            ryba_znaleziona = False
            end_scan = start_skan + random.uniform(1.8, 2.2)

            while time.time() < end_scan:
                if not running: break
                if szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])[0]:
                    ryba_znaleziona = True
                    break
                if not wait(random.uniform(0.04, 0.06)): break

            if not running: continue

            # ========================
            # FAZA 3: HOLOWANIE
            # ========================
            if ryba_znaleziona:
                set_status(">>> HOLOWANIE <<<")
                winsound.Beep(1000, 200)

                pyautogui.keyDown('shift')
                pyautogui.mouseDown(button='left')
                pyautogui.mouseDown(button='right')

                start_holu = time.time()
                sukces = False
                spadla = False
                licznik_znikniec = 0

                while time.time() - start_holu < MAX_CZAS_HOLU:
                    if not running: break

                    if not szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])[0]:
                        licznik_znikniec += 1
                    else:
                        licznik_znikniec = 0

                    if licznik_znikniec > 12: spadla = True; break

                    if template_spacja is not None and szukaj_wzorca(template_spacja, ACTIVE_CONFIG['spacja_reg'])[0]:
                        sukces = True;
                        break

                    jest_czerwono = czy_jest_czerwone(ACTIVE_CONFIG['tension_reg'])

                    if jest_czerwono:
                        set_status("NAPIĘCIE! (29)")
                        pyautogui.scroll(-1)
                    else:
                        set_status("HOL (30)")
                        pyautogui.scroll(1)

                    if not wait(random.uniform(0.04, 0.06)): break

                resetuj_klawisze()
                if not running: continue

                if sukces:
                    set_status("ZŁOWIONO!")
                    if not wait(random.uniform(0.9, 1.1)): continue
                    pyautogui.press('space')
                    SESSION_COUNTER += 1;
                    TOTAL_COUNTER += 1
                    zapisz_statystyki()
                    if not wait(random.uniform(1.8, 2.2)): continue
                    wymagany_rzut = True

                elif spadla:
                    set_status("SPADŁA - ZWIJAM")

                    pyautogui.mouseDown(button='left')
                    pyautogui.keyDown('shift')
                    pyautogui.mouseUp(button='right')

                    start_zwijania = time.time()
                    nowe_branie = False

                    while time.time() - start_zwijania < 45:
                        if not running: break
                        if szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])[0]:
                            set_status("PONOWNY ATAK!")
                            ryba_znaleziona = True
                            nowe_branie = True
                            break
                        if template_zero is not None and \
                                szukaj_wzorca(template_zero, ACTIVE_CONFIG['zero_reg'], prog=0.75)[0]:
                            break
                        if not wait(random.uniform(0.04, 0.06)): break

                    if nowe_branie: continue

                    resetuj_klawisze()
                    if not wait(random.uniform(1.4, 1.6)): continue
                    wymagany_rzut = True
            else:
                if not wait(random.uniform(0.04, 0.06)): continue

    except Exception as e:
        print(f"BŁĄD: {e}")
        traceback.print_exc()


def press_4_after_5_minutes_task():
    while not running:
        if kill_signal: return
        time.sleep(0.5)

    wait_duration = 300
    time_waited = 0
    last_time = time.time()

    while time_waited < wait_duration:
        if kill_signal: return

        if running:
            current_time = time.time()
            time_waited += current_time - last_time
            last_time = current_time
        else:
            last_time = time.time()
            while not running:
                if kill_signal: return
                time.sleep(0.5)
            last_time = time.time()

        time.sleep(0.1)

    for _ in range(5):
        if kill_signal: return
        while not running:
            if kill_signal: return
            time.sleep(0.1)
        pyautogui.press('4')
        if not wait(random.uniform(0.2, 0.5)):
            return


# ==========================================
# GUI
# ==========================================
def main_gui():
    global root, lbl_counter, lbl_status
    root = tk.Tk()
    root.title("Mariner")
    root.geometry("460x170")
    root.configure(bg='#1a1b26')
    root.attributes('-topmost', True)

    bg_color = '#1a1b26'

    global last_tick
    last_tick = time.time()

    main_frame = tk.Frame(root, bg=bg_color)
    main_frame.pack(fill='both', expand=True, padx=10, pady=10)

    left_frame = tk.Frame(main_frame, bg=bg_color)
    left_frame.pack(side='left', fill='both', expand=True)
    tk.Label(left_frame, text="⚓ MARINER", font=("Segoe UI", 16, "bold"), bg=bg_color, fg='#7aa2f7').pack(anchor='w')
    lbl_status = tk.Label(left_frame, text="...", font=("Segoe UI", 12, "bold"), bg=bg_color, fg='#e0af68')
    lbl_status.pack(anchor='w', pady=(5, 0))
    lbl_counter = tk.Label(left_frame, text="...", font=("Segoe UI", 10), bg=bg_color, fg='#c0caf5', justify='left')
    lbl_counter.pack(anchor='w', pady=(5, 0))

    right_frame = tk.Frame(main_frame, bg=bg_color)
    right_frame.pack(side='right', fill='both', padx=(20, 0))
    tk.Label(right_frame, text="STEROWANIE", font=("Segoe UI", 9, "bold"), bg=bg_color, fg='#565f89').pack(anchor='e')
    tk.Label(right_frame, text=f"Start/Reset: {KLAWISZ_START}", bg=bg_color, fg='#c0caf5').pack(anchor='e')
    tk.Label(right_frame, text=f"Stop: {KLAWISZ_KONIEC}", bg=bg_color, fg='#c0caf5').pack(anchor='e')

    def update_gui():
        global last_tick, SESSION_TIME_SECONDS, TOTAL_TIME_SECONDS

        current_tick = time.time()
        if running:
            delta = current_tick - last_tick
            SESSION_TIME_SECONDS += delta
            TOTAL_TIME_SECONDS += delta
        last_tick = current_tick

        try:
            sesja_str = f"Sesja: {SESSION_COUNTER} ({format_time(SESSION_TIME_SECONDS)})"
            razem_str = f"Razem: {TOTAL_COUNTER} ({format_time(TOTAL_TIME_SECONDS)})"

            lbl_counter.config(text=f"{sesja_str}\n{razem_str}")
            lbl_status.config(text=BOT_STATUS)

            st = BOT_STATUS.upper()
            col = '#7dcfff'
            if "RESET" in st:
                col = '#f7768e'
            elif "HOL" in st:
                col = '#bb9af7'
            elif "ZŁOWIONO" in st:
                col = '#9ece6a'
            elif "NAPIĘCIE" in st:
                col = '#ff0000'
            lbl_status.config(fg=col)
        except:
            pass

        root.after(200, update_gui)

    update_gui()
    root.mainloop()


if __name__ == "__main__":
    wczytaj_statystyki()
    show_launcher()
    threading.Thread(target=bot_logic, daemon=True).start()
    threading.Thread(target=press_4_after_5_minutes_task, daemon=True).start()
    main_gui()
