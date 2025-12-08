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


# ==========================================
# FUNKCJA DLA ZASOBÓW (PyInstaller)
# ==========================================
def resource_path(relative_path):
    """ Zwraca absolutną ścieżkę do zasobu, działa dla dev i PyInstaller """
    try:
        # PyInstaller tworzy temp folder w _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# ==========================================
# KONFIGURACJA ROZDZIELCZOŚCI
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
        'dno_reg': (536, 1024, 30, 12),
        # 'tension_reg' dodane pro forma, na razie nieużywane w logice
        'tension_reg': (943, 1047, 10, 11)
    },
    '2K': {
        'ryba_img': resource_path('indicator.png'),
        'ryba_reg': (855, 1369, 30, 30),
        'spacja_img': resource_path('space.png'),
        'spacja_reg': (1120, 1227, 62, 16),
        'zero_img': resource_path('ready.png'),
        'zero_reg': (896, 1387, 34, 9),
        'dno_img': resource_path('movement.png'),
        'dno_reg': (856, 1384, 65, 12),
        'tension_reg': (933, 1407, 10, 11)
    }
}

# Plik statystyk
PLIK_STATYSTYK = 'stats.json'

# Klawisze
KLAWISZ_START = 'j'
KLAWISZ_KONIEC = 'k'

# Parametry
PROG_DOPASOWANIA = 0.65
MAX_CZAS_HOLU = 900  # 15 minut max holu
TIMEOUT_OPADANIA = 600  # Zabezpieczenie (10 min opadania)
MOC_RZUTU_CZAS = 0.1  # Krótki rzut

# Zmienne globalne
running = False
TOTAL_COUNTER = 0
SESSION_COUNTER = 0

# Zmienne aktywnej konfiguracji (zostaną nadpisane po wyborze)
ACTIVE_CONFIG = {}


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
        data = {'total_fish': TOTAL_COUNTER}
        with open(PLIK_STATYSTYK, 'w') as f:
            json.dump(data, f)
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
        if max_val >= prog:
            return True, max_val
        return False, max_val
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


def inteligentne_czekanie(sekundy):
    global running
    start = time.time()
    while time.time() - start < sekundy:
        if keyboard.is_pressed(KLAWISZ_KONIEC): wyjscie_awaryjne()
        if keyboard.is_pressed(KLAWISZ_START):
            resetuj_klawisze()
            running = not running
            if running:
                print(">>> WZNOWIONO <<<")
                winsound.Beep(600, 200)
            else:
                print(">>> PAUZA <<<")
                zapisz_statystyki()
                winsound.Beep(400, 200)
            time.sleep(0.5)
        if not running: return False
        time.sleep(0.02)
    return True


# ==========================================
# MAIN LOOP
# ==========================================

def main():
    global running, SESSION_COUNTER, TOTAL_COUNTER, ACTIVE_CONFIG

    # 1. Wczytaj licznik
    wczytaj_statystyki()

    print("--- RF4 PRO BOT (FAST + MULTI-RES) ---")
    print(f"Ryby łącznie: {TOTAL_COUNTER}")
    print("--------------------------------------")

    # 2. Wybór Rozdzielczości
    print("WYBIERZ ROZDZIELCZOŚĆ:")
    print("1. FHD (1920x1080)")
    print("2. 2K  (2560x1440)")
    res_wybor = input("Twój wybór (1/2): ").strip()

    if res_wybor == '1':
        print(">>> Wybrano: FHD")
        ACTIVE_CONFIG = KONFIGURACJE['FHD']
    else:
        print(">>> Wybrano: 2K")
        ACTIVE_CONFIG = KONFIGURACJE['2K']

    # 3. Ładowanie obrazów na podstawie wyboru
    if not os.path.isfile(ACTIVE_CONFIG['ryba_img']):
        print(f"BŁĄD: Brak pliku '{ACTIVE_CONFIG['ryba_img']}'")
        input("Naciśnij Enter aby wyjść...");
        return

    template_ryba = cv2.imread(ACTIVE_CONFIG['ryba_img'], 0)

    template_spacja = None
    if os.path.isfile(ACTIVE_CONFIG['spacja_img']):
        template_spacja = cv2.imread(ACTIVE_CONFIG['spacja_img'], 0)

    template_zero = None
    if os.path.isfile(ACTIVE_CONFIG['zero_img']):
        template_zero = cv2.imread(ACTIVE_CONFIG['zero_img'], 0)

    # 4. Wybór trybu opadania
    print("\nWYBIERZ TRYB OPADANIA:")
    print("1. Czasowy (np. 20s)")
    print("2. Do dna (szukanie obrazka)")
    opad_wybor = input("Twój wybór (1/2): ").strip()

    tryb_dno = False
    czas_opadu = 20
    template_dno = None

    if opad_wybor == '2':
        tryb_dno = True
        dno_path = ACTIVE_CONFIG['dno_img']
        if os.path.isfile(dno_path):
            template_dno = cv2.imread(dno_path, 0)
            print(">>> Tryb: Szukanie Dna")
        else:
            print(f"Brak pliku {dno_path}, przełączam na czasowy.")
            tryb_dno = False
    else:
        inp = input("Podaj czas (sekundy): ").strip()
        if inp.isdigit(): czas_opadu = int(inp)
        print(f">>> Tryb: Czasowy ({czas_opadu}s)")

    print(f"\nGOTOWY. {KLAWISZ_START}=Start/Pauza, {KLAWISZ_KONIEC}=Stop")
    keyboard.add_hotkey(KLAWISZ_KONIEC, wyjscie_awaryjne)

    wymagany_rzut = True

    while True:
        # Pętla obsługi start/stop w głównym wątku
        if keyboard.is_pressed(KLAWISZ_START):
            resetuj_klawisze()
            running = not running
            if running:
                print(">>> START <<<")
                winsound.Beep(600, 200)
            else:
                print(">>> PAUZA <<<")
                zapisz_statystyki()
                winsound.Beep(400, 200)
            time.sleep(0.5)

        if running:
            # -----------------------------------
            # ETAP 1: RZUT
            # -----------------------------------
            if wymagany_rzut:
                print("Rzut...")
                pyautogui.keyUp('shift')
                time.sleep(0.2)
                pyautogui.mouseDown(button='left')
                time.sleep(MOC_RZUTU_CZAS)
                pyautogui.mouseUp(button='left')

                start_opadu = time.time()
                przerwano_opad = False

                print("Opadanie...")
                while True:
                    if not running: break
                    if keyboard.is_pressed(KLAWISZ_KONIEC): wyjscie_awaryjne()

                    # 1. Sprawdź branie w locie
                    is_bite, _ = szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])
                    if is_bite:
                        print("!!! Branie z opadu !!!")
                        przerwano_opad = True
                        break

                    # 2. Sprawdź warunek końca
                    teraz = time.time()
                    if tryb_dno and template_dno is not None:
                        is_dno, _ = szukaj_wzorca(template_dno, ACTIVE_CONFIG['dno_reg'], prog=0.7)
                        if is_dno: break
                        if teraz - start_opadu > TIMEOUT_OPADANIA: break
                    else:
                        if teraz - start_opadu > czas_opadu: break

                    time.sleep(0.05)

                if not running: continue

                if not przerwano_opad:
                    # Zamknij kabłąk
                    pyautogui.mouseDown(button='left')
                    time.sleep(0.5)
                    pyautogui.mouseUp(button='left')
                    wymagany_rzut = False

            # -----------------------------------
            # ETAP 2: JIGOWANIE
            # -----------------------------------
            pyautogui.mouseDown(button='right')
            if not inteligentne_czekanie(random.uniform(0.5, 0.8)):
                pyautogui.mouseUp(button='right')
                continue
            pyautogui.mouseUp(button='right')

            # Skanuj czy jest branie
            start_skan = time.time()
            ryba_znaleziona = False
            while time.time() - start_skan < random.uniform(1.8, 2.2):
                if not running: break

                znaleziono, _ = szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])
                if znaleziono:
                    ryba_znaleziona = True
                    break
                time.sleep(0.1)

            if not running: continue

            # -----------------------------------
            # ETAP 3: HOLOWANIE
            # -----------------------------------
            if ryba_znaleziona:
                print("!!! RYBA !!! Holowanie...")
                winsound.Beep(1000, 200)

                # Trzymaj przyciski
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

                    # Sprawdź czy ryba siedzi
                    jest_ryba, _ = szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])
                    if not jest_ryba:
                        licznik_znikniec += 1
                    else:
                        licznik_znikniec = 0

                    if licznik_znikniec > 12:  # Ryba zerwana
                        spadla = True
                        break

                    # Sprawdź spację
                    if template_spacja is not None:
                        jest_spacja, _ = szukaj_wzorca(template_spacja, ACTIVE_CONFIG['spacja_reg'])
                        if jest_spacja:
                            sukces = True
                            break

                    time.sleep(0.05)

                # Resetuj po holu (ale jeśli spadła, zaraz obsłużymy zwijanie)
                resetuj_klawisze()

                if sukces:
                    print("Lądowanie ryby...")
                    time.sleep(1.0)
                    pyautogui.press('space')

                    SESSION_COUNTER += 1
                    TOTAL_COUNTER += 1
                    zapisz_statystyki()
                    print(f"Złowiono! (Sesja: {SESSION_COUNTER} | Razem: {TOTAL_COUNTER})")

                    time.sleep(2.0)
                    wymagany_rzut = True

                elif spadla and running:
                    print("Ryba spadła. Szybkie zwijanie ze skanowaniem...")

                    pyautogui.mouseUp(button='right')
                    pyautogui.keyDown('shift')
                    pyautogui.mouseDown(button='left')

                    start_zwijania = time.time()
                    nowe_branie = False

                    while time.time() - start_zwijania < 45:
                        if not running: break
                        if keyboard.is_pressed(KLAWISZ_KONIEC): wyjscie_awaryjne()

                        # 1. CZY JEST NOWY ATAK?
                        jest_ryba, p = szukaj_wzorca(template_ryba, ACTIVE_CONFIG['ryba_reg'])
                        if jest_ryba:
                            print(f"!!! ATAK PODCZAS ZWIJANIA !!! ({p:.2f})")
                            ryba_znaleziona = True
                            nowe_branie = True
                            break

                        # 2. Czy koniec żyłki?
                        if template_zero is not None:
                            jest_zero, _ = szukaj_wzorca(template_zero, ACTIVE_CONFIG['zero_reg'], prog=0.75)
                            if jest_zero: break

                        time.sleep(0.05)

                    if nowe_branie:
                        # Pętla while True wróci na początek, ryba_znaleziona jest True, więc zacznie hol
                        continue

                    resetuj_klawisze()
                    time.sleep(1.5)
                    wymagany_rzut = True


if __name__ == "__main__":
    main()