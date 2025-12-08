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
import tkinter as tk
from tkinter import ttk
import threading
import traceback

# ==========================================
# ZMIENNE KONFIGURACYJNE (Będą ustawione przez Launcher)
# ==========================================
USER_SETTINGS = {
    'RES': '2K',  # FHD / 2K
    'MODE': 'DNO',  # CZAS / DNO
    'TIME': 20  # Sekundy
}


# ==========================================
# NARZĘDZIA SYSTEMOWE
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ==========================================
# ZASOBY
# ==========================================
KONFIGURACJE = {
    'FHD': {
        'ryba_img': resource_path('ind2.png'),
        'ryba_reg': (534, 1008, 32, 32),
        'spacja_img': resource_path('space2.png'),
        'spacja_reg': (798, 973, 65, 16),
        'zero_img': resource_path('gotowy.png'),
        'zero_reg': (606, 1027, 47, 12),
        'dno_img': resource_path('dno.png'),
        'dno_reg': (536, 1024, 30, 12)
    },
    '2K': {
        'ryba_img': resource_path('indicator.png'),
        'ryba_reg': (855, 1369, 30, 30),
        'spacja_img': resource_path('space.png'),
        'spacja_reg': (1120, 1227, 62, 16),
        'zero_img': resource_path('ready.png'),
        'zero_reg': (896, 1387, 34, 9),
        'dno_img': resource_path('movement.png'),
        'dno_reg': (856, 1384, 65, 12)
    }
}

PLIK_STATYSTYK = 'stats.json'
KLAWISZ_START = 'F8'
KLAWISZ_KONIEC = 'F12'

PROG_DOPASOWANIA = 0.65
MAX_CZAS_HOLU = 900
TIMEOUT_OPADANIA = 600
MOC_RZUTU_CZAS = 0.1

running = False
TOTAL_COUNTER = 0
SESSION_COUNTER = 0
BOT_STATUS = "GOTOWY"
ACTIVE_CONFIG = {}

root = None
lbl_counter = None
lbl_status = None


# ==========================================
# FUNKCJE POMOCNICZE
# ==========================================
def wczytaj_statystyki():
    global TOTAL_COUNTER
    if os.path.exists(PLIK_STATYSTYK):
        try:
            with open(PLIK_STATYSTYK, 'r') as f:
                data = json.load(f)
                TOTAL_COUNTER = data.get('total_fish', 0)
        except:
            TOTAL_COUNTER = 0


def zapisz_statystyki():
    try:
        with open(PLIK_STATYSTYK, 'w') as f:
            json.dump({'total_fish': TOTAL_COUNTER}, f)
    except:
        pass


def pobierz_obraz_z_ekranu(region):
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
    return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)


def szukaj_wzorca(template_gray, region, prog=PROG_DOPASOWANIA):
    try:
        screen_gray = pobierz_obraz_z_ekranu(region)
        if screen_gray.shape[0] < template_gray.shape[0] or screen_gray.shape[1] < template_gray.shape[1]:
            return False, 0.0
        res = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return (True, max_val) if max_val >= prog else (False, max_val)
    except:
        return False, 0.0


def resetuj_klawisze():
    pyautogui.mouseUp(button='right')
    pyautogui.mouseUp(button='left')
    pyautogui.keyUp('shift')


def wyjscie_awaryjne():
    print("\n!!! ZAMYKANIE BOTA !!!")
    zapisz_statystyki()
    resetuj_klawisze()
    winsound.Beep(200, 500)
    os._exit(0)


def set_status(text):
    global BOT_STATUS
    BOT_STATUS = text


def inteligentne_czekanie(sekundy):
    global running
    start = time.time()
    while time.time() - start < sekundy:
        if keyboard.is_pressed(KLAWISZ_KONIEC): wyjscie_awaryjne()
        if keyboard.is_pressed(KLAWISZ_START):
            resetuj_klawisze()
            running = not running
            if running:
                set_status("WZNOWIONO")
                winsound.Beep(600, 200)
            else:
                set_status("PAUZA")
                zapisz_statystyki()
                winsound.Beep(400, 200)
            time.sleep(0.5)
        if not running: return False
        time.sleep(0.02)
    return True


# ==========================================
# LAUNCHER (OKNO KONFIGURACJI)
# ==========================================
def show_launcher():
    launcher = tk.Tk()
    launcher.title("Konfiguracja")
    launcher.geometry("300x400")
    launcher.configure(bg='#1a1b26')

    # Stylizacja
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TRadiobutton', background='#1a1b26', foreground='white', font=('Segoe UI', 10))
    style.configure('TLabel', background='#1a1b26', foreground='white', font=('Segoe UI', 10))

    # Zmienne
    var_res = tk.StringVar(value='2K')
    var_mode = tk.StringVar(value='CZAS')
    var_time = tk.StringVar(value='20')

    # UI
    tk.Label(launcher, text="MARINER SETUP", font=("Segoe UI", 16, "bold"), bg='#1a1b26', fg='#7aa2f7').pack(pady=15)

    # Rozdzielczość
    tk.Label(launcher, text="Rozdzielczość:", bg='#1a1b26', fg='#a9b1d6', font=("Segoe UI", 9, "bold")).pack(anchor='w',
                                                                                                             padx=20)
    ttk.Radiobutton(launcher, text="FHD (1920x1080)", variable=var_res, value='FHD').pack(anchor='w', padx=30)
    ttk.Radiobutton(launcher, text="2K (2560x1440)", variable=var_res, value='2K').pack(anchor='w', padx=30)

    tk.Label(launcher, text="", bg='#1a1b26').pack()  # Odstęp

    # Tryb
    tk.Label(launcher, text="Tryb opadania:", bg='#1a1b26', fg='#a9b1d6', font=("Segoe UI", 9, "bold")).pack(anchor='w',
                                                                                                             padx=20)
    ttk.Radiobutton(launcher, text="Czasowy (Stały)", variable=var_mode, value='CZAS').pack(anchor='w', padx=30)

    frame_time = tk.Frame(launcher, bg='#1a1b26')
    frame_time.pack(anchor='w', padx=50)
    tk.Label(frame_time, text="Sekundy:", bg='#1a1b26', fg='#565f89', font=("Segoe UI", 9)).pack(side='left')
    tk.Entry(frame_time, textvariable=var_time, width=5, bg='#24283b', fg='white', insertbackground='white').pack(
        side='left', padx=5)

    ttk.Radiobutton(launcher, text="Auto-Dno (Obraz)", variable=var_mode, value='DNO').pack(anchor='w', padx=30)

    # Przycisk Start
    def on_start():
        USER_SETTINGS['RES'] = var_res.get()
        USER_SETTINGS['MODE'] = var_mode.get()
        try:
            USER_SETTINGS['TIME'] = int(var_time.get())
        except:
            USER_SETTINGS['TIME'] = 20
        launcher.destroy()

    tk.Button(launcher, text="URUCHOM", command=on_start, bg='#00e676', fg='black', font=("Segoe UI", 10, "bold"),
              width=15).pack(pady=25)

    launcher.mainloop()


# ==========================================
# WĄTEK BOTA
# ==========================================
def bot_logic():
    global running, SESSION_COUNTER, TOTAL_COUNTER, ACTIVE_CONFIG

    try:
        # Inicjalizacja z ustawień Launchera
        active_res = USER_SETTINGS['RES']
        ACTIVE_CONFIG = KONFIGURACJE[active_res]

        # Sprawdzenie obrazków
        if not os.path.isfile(ACTIVE_CONFIG['ryba_img']):
            set_status(f"BŁĄD: BRAK {ACTIVE_CONFIG['ryba_img']}")
            return

        template_ryba = cv2.imread(ACTIVE_CONFIG['ryba_img'], 0)
        template_spacja = cv2.imread(ACTIVE_CONFIG['spacja_img'], 0) if os.path.isfile(
            ACTIVE_CONFIG['spacja_img']) else None
        template_zero = cv2.imread(ACTIVE_CONFIG['zero_img'], 0) if os.path.isfile(ACTIVE_CONFIG['zero_img']) else None

        # Konfiguracja trybu
        tryb_dno = (USER_SETTINGS['MODE'] == 'DNO')
        czas_opadu = USER_SETTINGS['TIME']
        template_dno = None
        if tryb_dno and os.path.isfile(ACTIVE_CONFIG['dno_img']):
            template_dno = cv2.imread(ACTIVE_CONFIG['dno_img'], 0)
        elif tryb_dno:
            set_status("BŁĄD: Brak dno.png!")
            time.sleep(2)

        wymagany_rzut = True
        set_status(f"GOTOWY ({KLAWISZ_START})")
        keyboard.add_hotkey(KLAWISZ_KONIEC, wyjscie_awaryjne)

        while True:
            # Obsługa przycisków
            if keyboard.is_pressed(KLAWISZ_START):
                resetuj_klawisze()
                running = not running
                if running:
                    set_status("START")
                    winsound.Beep(600, 200)
                else:
                    set_status("PAUZA")
                    zapisz_statystyki()
                    winsound.Beep(400, 200)
                time.sleep(0.5)

            if running:
                # --- RZUT ---
                if wymagany_rzut:
                    set_status("RZUT")
                    pyautogui.keyUp('shift')
                    time.sleep(0.2)
                    pyautogui.mouseDown(button='left')
                    time.sleep(MOC_RZUTU_CZAS)
                    pyautogui.mouseUp(button='left')

                    start_opadu = time.time()
                    przerwano_opad = False
                    set_status("OPADANIE...")

                    while True:
                        if not running: break
                        if keyboard.is_pressed(KLAWISZ_KONIEC): wyjscie_awaryjne()

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
                        time.sleep(0.05)

                    if not running: continue
                    if not przerwano_opad:
                        pyautogui.mouseDown(button='left')
                        time.sleep(0.5)
                        pyautogui.mouseUp(button='left')
                        wymagany_rzut = False

                # --- JIGOWANIE ---
                set_status("JIGOWANIE")
                pyautogui.mouseDown(button='right')
                if not inteligentne_czekanie(random.uniform(0.5, 0.8)):
                    pyautogui.mouseUp(button='right');
                    continue
                pyautogui.mouseUp(button='right')

                start_skan = time.time()
                ryba_znaleziona = False
                while time.time() - start_skan < random.uniform(1.8, 2.2):
                    if not running: break
                    if szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])[0]:
                        ryba_znaleziona = True
                        break
                    time.sleep(0.1)

                if not running: continue

                # --- HOLOWANIE ---
                if ryba_znaleziona:
                    set_status(">>> HOLOWANIE <<<")
                    winsound.Beep(1000, 200)
                    pyautogui.mouseDown(button='right')
                    pyautogui.keyDown('shift')
                    pyautogui.mouseDown(button='left')

                    start_holu = time.time()
                    sukces = False
                    spadla = False
                    licznik_znikniec = 0

                    while time.time() - start_holu < MAX_CZAS_HOLU:
                        if not running: break
                        if keyboard.is_pressed(KLAWISZ_KONIEC): wyjscie_awaryjne()

                        if not szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])[0]:
                            licznik_znikniec += 1
                        else:
                            licznik_znikniec = 0

                        if licznik_znikniec > 12:
                            spadla = True;
                            break

                        if template_spacja and szukaj_wzorca(template_spacja, ACTIVE_CONFIG['spacja_reg'])[0]:
                            sukces = True;
                            break
                        time.sleep(0.05)

                    resetuj_klawisze()

                    if sukces:
                        set_status("ZŁOWIONO!")
                        time.sleep(1.0)
                        pyautogui.press('space')
                        SESSION_COUNTER += 1
                        TOTAL_COUNTER += 1
                        zapisz_statystyki()
                        time.sleep(2.0)
                        wymagany_rzut = True

                    elif spadla and running:
                        set_status("SPADŁA - ZWIJAM")
                        pyautogui.mouseUp(button='right')
                        pyautogui.keyDown('shift')
                        pyautogui.mouseDown(button='left')

                        start_zwijania = time.time()
                        nowe_branie = False

                        while time.time() - start_zwijania < 45:
                            if not running: break
                            if keyboard.is_pressed(KLAWISZ_KONIEC): wyjscie_awaryjne()

                            if szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])[0]:
                                set_status("PONOWNY ATAK!")
                                ryba_znaleziona = True
                                nowe_branie = True
                                break

                            if template_zero and szukaj_wzorca(template_zero, ACTIVE_CONFIG['zero_reg'], prog=0.75)[0]:
                                break
                            time.sleep(0.05)

                        if nowe_branie: continue
                        resetuj_klawisze()
                        time.sleep(1.5)
                        wymagany_rzut = True
            else:
                time.sleep(0.1)  # ODPOCZYNEK CPU

    except Exception as e:
        print(f"BŁĄD WĄTKU: {e}")
        traceback.print_exc()


# ==========================================
# GUI GŁÓWNE
# ==========================================
def main_gui():
    global root, lbl_counter, lbl_status
    root = tk.Tk()
    root.title("Mariner")
    root.geometry("460x160")
    root.configure(bg='#1a1b26')
    root.attributes('-topmost', True)

    bg_color, accent_color, text_color = '#1a1b26', '#7aa2f7', '#c0caf5'

    # Etykiety informacyjne
    res_info = USER_SETTINGS['RES']
    mode_info = "Auto-Dno" if USER_SETTINGS['MODE'] == 'DNO' else f"Czas ({USER_SETTINGS['TIME']}s)"

    main_frame = tk.Frame(root, bg=bg_color)
    main_frame.pack(fill='both', expand=True, padx=10, pady=10)

    left_frame = tk.Frame(main_frame, bg=bg_color)
    left_frame.pack(side='left', fill='both', expand=True)
    tk.Label(left_frame, text="⚓ MARINER", font=("Segoe UI", 16, "bold"), bg=bg_color, fg=accent_color).pack(anchor='w')
    lbl_status = tk.Label(left_frame, text="ŁADOWANIE...", font=("Segoe UI", 12, "bold"), bg=bg_color, fg='#e0af68')
    lbl_status.pack(anchor='w', pady=(5, 0))
    lbl_counter = tk.Label(left_frame, text="Sesja: 0 | Razem: 0", font=("Segoe UI", 11), bg=bg_color, fg=text_color)
    lbl_counter.pack(anchor='w', pady=(5, 0))

    right_frame = tk.Frame(main_frame, bg=bg_color)
    right_frame.pack(side='right', fill='both', padx=(20, 0))
    tk.Frame(main_frame, bg='#414868', width=2).pack(side='right', fill='y', padx=5)
    tk.Label(right_frame, text="STEROWANIE", font=("Segoe UI", 9, "bold"), bg=bg_color, fg='#565f89').pack(anchor='e')
    tk.Label(right_frame, text=f"Start / Pauza: [{KLAWISZ_START}]", font=("Segoe UI", 9), bg=bg_color,
             fg=text_color).pack(anchor='e')
    tk.Label(right_frame, text=f"Wyjście: [{KLAWISZ_KONIEC}]", font=("Segoe UI", 9), bg=bg_color, fg=text_color).pack(
        anchor='e')
    tk.Label(right_frame, text="", bg=bg_color).pack()
    tk.Label(right_frame, text=f"Res: {res_info}", font=("Segoe UI", 8), bg=bg_color, fg='#565f89').pack(anchor='e')
    tk.Label(right_frame, text=f"Tryb: {mode_info}", font=("Segoe UI", 8), bg=bg_color, fg='#565f89').pack(anchor='e')

    def update_gui():
        try:
            lbl_counter.config(text=f"Sesja: {SESSION_COUNTER}  |  Razem: {TOTAL_COUNTER}")
            lbl_status.config(text=BOT_STATUS)
            st = BOT_STATUS.upper()
            color = '#7dcfff'
            if "PAUZA" in st:
                color = '#f7768e'
            elif "HOL" in st:
                color = '#bb9af7'
            elif "ZŁOWIONO" in st:
                color = '#9ece6a'
            elif "SPADŁA" in st:
                color = '#e0af68'
            lbl_status.config(fg=color)
        except:
            pass
        root.after(200, update_gui)

    update_gui()
    root.mainloop()


if __name__ == "__main__":
    try:
        wczytaj_statystyki()

        # 1. Pokaż Launcher (Blokuje aż do kliknięcia Start)
        show_launcher()

        # 2. Start Wątku Bota
        bot_thread = threading.Thread(target=bot_logic, daemon=True)
        bot_thread.start()

        # 3. Start Głównego GUI
        main_gui()

    except Exception as e:
        print(f"BŁĄD: {e}")
        traceback.print_exc()