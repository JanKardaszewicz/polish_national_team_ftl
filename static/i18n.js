/* Przełącznik języka PL/EN (flagi w prawym górnym rogu).
 *
 * Strony są pisane po polsku. W trybie angielskim tłumaczymy teksty "w locie": słownik dokładnych zdań
 * (EXACT) i wzorce dla zdań składanych z liczb i nazw (PATTERNS). Obserwator DOM tłumaczy też to, co
 * strona dopisuje później (listy, komunikaty błędów, odpowiedzi serwera). Nieznany tekst zostaje po polsku.
 */
(function () {
  'use strict';

  var KEY = 'fencing.lang';

  var EXACT = {
    // ---------- wspólne ----------
    'Zawodnik': 'Fencer',
    'Zawodnicy': 'Fencers',
    'Grupa': 'Pool',
    'Grupy': 'Pools',
    'Klub': 'Club',
    'Ranking': 'Ranking',
    'Miejsce': 'Place',
    'Msc': 'Pl.',
    'Awans': 'Advances',
    'Imię *': 'First name *',
    'Nazwisko *': 'Last name *',
    'Imię': 'First name',
    'Nazwisko': 'Last name',
    'Kraj': 'Country',
    'Ty': 'You',
    'Ty vs': 'You vs',
    'Sędzia': 'Referee',
    'Zamknij': 'Close',
    'Szukaj': 'Search',
    'Ranking wszystkich grup': 'Ranking of all pools',
    'Pokaż ranking wszystkich grup': 'Show ranking of all pools',
    'Ukryj ranking wszystkich grup': 'Hide ranking of all pools',
    'Brak połączenia z serwerem. Sprawdź, czy jesteś w tej samej sieci Wi-Fi.': 'No connection to the server. Check that you are on the same Wi-Fi network.',
    'Brak połączenia z serwerem.': 'No connection to the server.',

    // ---------- panel organizatora: statyczne ----------
    'Panel organizatora': 'Organizer panel',
    'Logowanie': 'Login',
    'PIN organizatora (wypisany w oknie serwera)': 'Organizer PIN (printed in the server window)',
    'Zaloguj': 'Log in',
    'Nieprawidłowy PIN.': 'Wrong PIN.',
    'Lista jest zablokowana, bo grupy są utworzone. Odblokuj ją w karcie Grupy.': 'The list is locked because pools have been created. Unlock it in the Pools tab.',
    'Lista jest zablokowana, bo grupy są utworzone.': 'The list is locked because pools have been created.',
    'Zapisy przez telefon': 'Phone registration',
    'Zawodnicy skanują kod i wpisują imię oraz nazwisko. Telefony muszą być w tej samej sieci Wi-Fi co ten komputer.': 'Fencers scan the code and enter their first and last name. Phones must be on the same Wi-Fi network as this computer.',
    'Zamknij zapisy': 'Close registration',
    'Otwórz zapisy': 'Open registration',
    'Zapisy są otwarte.': 'Registration is open.',
    'Zapisy są zamknięte.': 'Registration is closed.',
    'Zapisy zamknęły się automatycznie po utworzeniu grup.': 'Registration closed automatically after the pools were created.',
    'Ranking PZSzerm': 'PZSzerm ranking',
    'Plik klasyfikacji (strona zapisana z przeglądarki jako „tylko HTML”)': 'Classification file (page saved from the browser as "HTML only")',
    'Importuj z pliku': 'Import from file',
    'Podgląd wczytanej klasyfikacji': 'Preview of the loaded classification',
    'Imię i nazwisko': 'First and last name',
    'Zapisany zawodnik': 'Registered fencer',
    'Osobisty kod QR zawodnika': 'Fencer personal QR code',
    'Zawodnik skanuje ten kod swoim telefonem, żeby odzyskać dostęp do swojego zapisu. Nie pokazuj go innym osobom.': 'The fencer scans this code with their phone to regain access to their registration. Do not show it to others.',
    'Dodaj zawodnika': 'Add fencer',
    'Ranking (puste = z klasyfikacji PZSzerm, 999 = bez rankingu)': 'Ranking (empty = from the PZSzerm classification, 999 = unranked)',
    'Anuluj edycję': 'Cancel editing',
    'Lista zawodników': 'Fencer list',
    'Źródło rankingu': 'Ranking source',
    'Brak zawodników. Dodaj pierwszego powyżej albo poczekaj na zapisy z telefonów.': 'No fencers. Add the first one above or wait for phone registrations.',
    'Nowy turniej': 'New tournament',
    'Zapisuje kopię bieżących danych (zawodnicy, grupy, wyniki) w folderze': 'Saves a copy of the current data (fencers, pools, results) in the folder',
    'obok serwera i czyści turniej. Wczytana klasyfikacja PZSzerm zostaje.': 'next to the server and clears the tournament. The loaded PZSzerm classification is kept.',
    'Ustawienia grup': 'Pool settings',
    'Rozmiar grupy': 'Pool size',
    'Górny limit plansz na grupę': 'Maximum boards per pool',
    'Utwórz grupy': 'Create pools',
    'Liczba awansujących (osób)': 'Number advancing (people)',
    'Grupy są utworzone, lista zawodników jest zablokowana, a zapisy zamknięte.': 'Pools have been created, the fencer list is locked and registration is closed.',
    'Usuń grupy i odblokuj listę': 'Delete pools and unlock the list',
    'Brak grup. Utwórz je powyżej.': 'No pools. Create them above.',
    'Kod QR do zapisu': 'QR code for registration',
    'nazwisko lub klub': 'last name or club',

    // ---------- panel organizatora: dynamiczne ----------
    'brak w PZSzerm': 'not in PZSzerm',
    'niejednoznaczny w PZSzerm': 'ambiguous in PZSzerm',
    'konflikt miejsc w PZSzerm': 'place conflict in PZSzerm',
    'ręcznie': 'manual',
    'Podaj nazwisko.': 'Enter the last name.',
    'Podaj imię.': 'Enter the first name.',
    'Ranking musi być liczbą całkowitą od 1 do 9999 albo pusty.': 'Ranking must be a whole number from 1 to 9999 or empty.',
    'Ranking musi być liczbą całkowitą od 1 do 9999.': 'Ranking must be a whole number from 1 to 9999.',
    'Edycja zawodnika': 'Edit fencer',
    'Zapisz zmiany': 'Save changes',
    'Edytuj': 'Edit',
    'Usuń': 'Delete',
    'Ranking nie jest wczytany. Zawodnicy zapisani przez telefon dostaną ranking 999.': 'The ranking is not loaded. Fencers who register by phone will get ranking 999.',
    'Wybierz plik z klasyfikacją.': 'Choose the classification file.',
    'Plik jest za duży (limit 30 MB).': 'The file is too large (limit 30 MB).',
    'Nie udało się odczytać pliku.': 'Could not read the file.',
    'Tabele w pliku są za duże (limit 1,5 MB).': 'The tables in the file are too large (limit 1.5 MB).',
    'Dodaj co najmniej dwóch zawodników.': 'Add at least two fencers.',
    'Rozpocząć nowy turniej? Zawodnicy, grupy i wyniki zostaną usunięte z panelu (kopia trafi do folderu archiwum). Telefony zawodników stracą dostęp do swoich meczów.': 'Start a new tournament? Fencers, pools and results will be removed from the panel (a copy goes to the archiwum folder). Fencers\' phones will lose access to their matches.',
    'Nowy turniej rozpoczęty (poprzedni był pusty, bez kopii).': 'New tournament started (the previous one was empty, no copy made).',
    'Usunąć wszystkie grupy i wyniki? Lista zawodników zostanie odblokowana (zapisy trzeba otworzyć ręcznie).': 'Delete all pools and results? The fencer list will be unlocked (registration must be opened manually).',
    'Wynik nie może być remisem, ktoś musi wygrać.': 'The result cannot be a draw, someone has to win.',
    'Przenieś do…': 'Move to…',
    '— brak —': '— none —',
    'Z tej grupy': 'From this pool',
    'Inni zawodnicy': 'Other fencers',
    'brak sędziego': 'no referee',
    'wpisał organizator': 'entered by the organizer',
    '⚠ zgłoszony błąd, decyduje organizator': '⚠ error reported, the organizer decides',
    'Potwierdź wynik': 'Confirm result',
    'Górny limit plansz': 'Maximum boards',
    'Ustaw limit plansz': 'Set board limit',
    'Otwórz grupę': 'Open pool',
    'Zamknij grupę': 'Close pool',
    'Zamknięta grupa nie przyjmuje wyników z telefonów': 'A closed pool does not accept results from phones',
    'Brak grup. Ustaw rozmiar grupy i kliknij „Utwórz grupy”.': 'No pools. Set the pool size and click "Create pools".',
    'Kolejność walk (wpisz wyniki, szachownica uaktualni się automatycznie)': 'Bout order (enter the results, the cross table updates automatically)',
    'Status awansu pojawi się po zakończeniu wszystkich grup.': 'The advancement status will appear when all pools are finished.',

    // ---------- zatwierdzenie grup, tura 2, drabinka ----------
    'Drabinka': 'Bracket',
    'Zatwierdzenie grup': 'Pool approval',
    'Wszystkie grupy zatwierdzone': 'All pools approved',
    'Opcja A: druga tura grup': 'Option A: second round of pools',
    'Wszyscy zawodnicy są ponownie dzieleni na grupy wężem według rankingu po grupach z pierwszej tury.': 'All fencers are divided into pools again in a snake pattern according to the ranking after the pools of the first round.',
    'Górny limit plansz na grupę': 'Maximum boards per pool',
    'Utwórz drugą turę grup': 'Create the second round of pools',
    'Opcja B: drabinka direct elimination': 'Option B: direct elimination bracket',
    'Zawodnicy są rozstawieni według rankingu po grupach. Gdy ich liczba nie jest potęgą dwójki, najniżej rozstawieni grają dobijaki, a najwyżej rozstawieni dostają wolny los.': 'Fencers are seeded according to the ranking after the pools. When their number is not a power of two, the lowest seeds fight preliminary bouts and the highest seeds get a bye.',
    'Liczba zawodników w drabince': 'Number of fencers in the bracket',
    'Utwórz drabinkę': 'Create bracket',
    'Drabinka została utworzona (karta Drabinka).': 'The bracket has been created (Bracket tab).',
    'Cofnij zatwierdzenie': 'Undo approval',
    'Drabinka direct elimination': 'Direct elimination bracket',
    'Usuń drabinkę': 'Delete bracket',
    'Przycisk będzie aktywny, gdy wszystkie walki w grupach mają wyniki.': 'The button will be active once all bouts in the pools have results.',
    'Rozstrzygnij zgłoszone błędy i prośby o poprawę wyniku.': 'Resolve the reported errors and correction requests.',
    'Wszystkie walki mają wyniki. Zatwierdź grupy, żeby przejść dalej.': 'All bouts have results. Approve the pools to continue.',
    'Zatwierdzić wszystkie grupy? Wyniki zostaną zamrożone (można cofnąć zatwierdzenie).': 'Approve all pools? The results will be frozen (the approval can be undone).',
    'Utworzyć drugą turę grup? Wyniki pierwszej tury zostaną zapisane jako ranking po 1. turze.': 'Create the second round of pools? The results of the first round will be saved as the ranking after round 1.',
    'Usunąć drabinkę wraz z wynikami?': 'Delete the bracket together with its results?',
    'Finał': 'Final',
    'Półfinały': 'Semifinals',
    'Ćwierćfinały': 'Quarterfinals',
    'Walka o 3. miejsce': 'Third place bout',
    'wolny los': 'bye',
    'Drabinka nie jest utworzona. Zatwierdź grupy w karcie Grupy i wybierz opcję drabinki.': 'The bracket has not been created. Approve the pools in the Pools tab and choose the bracket option.',
    'Grupy są zatwierdzone. Cofnij zatwierdzenie, żeby coś zmienić.': 'The pools are approved. Undo the approval to change anything.',
    'Grupy są zatwierdzone. Wynik poprawi organizator.': 'The pools are approved. The organizer will correct the result.',
    'Nie ma utworzonych grup.': 'No pools have been created.',
    'Oczekiwano pola approved (true/false).': 'The approved field (true/false) was expected.',
    'Nie wszystkie walki w grupach mają wyniki.': 'Not all bouts in the pools have results.',
    'Są walki ze zgłoszonym błędem lub prośbą o poprawę. Rozstrzygnij je przed zatwierdzeniem.': 'Some bouts have a reported error or a correction request. Resolve them before approving.',
    'Najpierw usuń drabinkę.': 'Delete the bracket first.',
    'Najpierw zatwierdź wszystkie grupy.': 'Approve all pools first.',
    'Druga tura grup już istnieje.': 'The second round of pools already exists.',
    'Drabinka już istnieje. Najpierw ją usuń.': 'The bracket already exists. Delete it first.',
    'Drabinka nie istnieje.': 'The bracket does not exist.',
    'W tej walce nie są jeszcze znani obaj zawodnicy.': 'Both fencers of this bout are not known yet.',
    'Walka następnej rundy ma już wynik. Najpierw usuń jej wynik.': 'The next round bout already has a result. Remove its result first.',

    'Mecze': 'Matches',
    'Wyniki poprzedniej tury grup.': 'Results of the previous round of pools.',
    'Nie brałeś udziału w tej turze grup.': 'You did not take part in this round of pools.',
    'Z repasażami (przegrani rundy grają o miejsca, np. 5–8, 9–16)': 'With repechage (the losers of a round play for places, e.g. 5–8, 9–16)',
    'Repasaże do miejsca': 'Repechage down to place',
    '8 (miejsca 5–8)': '8 (places 5–8)',
    '16 (miejsca 5–16)': '16 (places 5–16)',
    '32 (miejsca 5–32)': '32 (places 5–32)',
    '64 (miejsca 5–64)': '64 (places 5–64)',
    'wszystkie możliwe': 'all possible',
    'Repasaże do miejsca: podaj liczbę od 8 do 1024.': 'Repechage down to place: enter a number from 8 to 1024.',
    'Brak danych tej tury.': 'No data for this round.',
    'Mecze i grupa': 'Matches and pool',
    'Wszystkie grupy': 'All pools',
    'Podgląd składów i wyników wszystkich grup (odświeża się na żywo). Twoja grupa jest rozwinięta.': 'Rosters and results of all pools (updates live). Your pool is expanded.',
    'Grupy nie zostały jeszcze utworzone.': 'The pools have not been created yet.',
    'Od etapu:': 'From stage:',
    'Pomniejsz': 'Zoom out',
    'Dopasuj': 'Fit',
    'Dopasuj do ekranu': 'Fit to screen',
    'Powiększ': 'Zoom in',
    'albo procent zawodników (%)': 'or percentage of fencers (%)',
    'Procent zawodników musi być liczbą od 1 do 100.': 'The percentage of fencers must be a number from 1 to 100.',
    'Znajdź w drabince': 'Find in the bracket',
    'Twoja następna walka w drabince': 'Your next bout in the bracket',
    'Sędziujesz w drabince': 'You are refereeing in the bracket',
    'Czekasz na przeciwnika.': 'Waiting for your opponent.',
    'Sędzia: do ustalenia': 'Referee: to be decided',
    'Wynik wpisuje organizator.': 'The organizer enters the result.',
    'Odpadłeś z drabinki. Dziękujemy za udział!': 'You are out of the bracket. Thank you for taking part!',
    'Wygrałeś turniej! Gratulacje!': 'You won the tournament! Congratulations!',
    'Nie ma Cię w drabince.': 'You are not in the bracket.',
    'W walce z wolnym losem nie ma sędziego.': 'A bout with a bye has no referee.',
    // ---------- strona zawodnika ----------
    'Zapis na turniej': 'Tournament registration',
    'Ładowanie…': 'Loading…',
    'Zapisy są zamknięte': 'Registration is closed',
    'Zapytaj organizatora, jeśli chcesz wziąć udział w turnieju.': 'Ask the organizer if you want to take part in the tournament.',
    'Wpisz swoje dane': 'Enter your details',
    'Klub (opcjonalnie)': 'Club (optional)',
    'Zapisz mnie': 'Sign me up',
    'Ranking pobierzemy automatycznie z klasyfikacji PZSzerm. Jeśli Cię w niej nie ma, dostajesz ranking 999.': 'We fetch your ranking automatically from the PZSzerm classification. If you are not in it, you get ranking 999.',
    'Jesteś zapisany': 'You are registered',
    'Zapis przyjęty.': 'Registration accepted.',
    'Ten telefon jest Twoim kluczem do zapisu. Nie czyść danych przeglądarki. Jeśli stracisz dostęp, poproś organizatora o osobisty kod QR.': 'This phone is your key to the registration. Do not clear your browser data. If you lose access, ask the organizer for a personal QR code.',
    'Twój następny mecz': 'Your next match',
    'Twoje mecze': 'Your matches',
    'Pozostałe mecze': 'Remaining matches',
    'Wyniki Twojej grupy': 'Your pool results',
    'Sprawdź swoje wyniki. Jeśli coś się nie zgadza, zgłoś to organizatorowi.': 'Check your results. If something is wrong, report it to the organizer.',
    'Sędziujesz': 'You are refereeing',
    '999 (w klasyfikacji jest kilka osób o tym nazwisku, organizator to sprawdzi)': '999 (there are several people with this name in the classification, the organizer will check)',
    '999 (nie znaleziono Cię w klasyfikacji PZSzerm)': '999 (you were not found in the PZSzerm classification)',
    'Wpisałeś go Ty.': 'You entered it.',
    'Wpisał go przeciwnik.': 'Your opponent entered it.',
    'Wpisał go organizator.': 'The organizer entered it.',
    'Zalecana przerwa: walczysz zaraz po poprzedniej walce.': 'Rest recommended: you fight right after your previous bout.',
    'Zatwierdź poprawę': 'Approve correction',
    'poprawa zatwierdzona, czeka na zawodnika': 'correction approved, waiting for the fencer',
    'Prośba o poprawę wysłana. Czekasz na decyzję organizatora.': 'Correction request sent. Waiting for the organizer\'s decision.',
    'Organizator zatwierdził poprawę. Możesz zmienić wynik (jeden raz).': 'The organizer approved the correction. You can change the result (once).',
    'Poproś o zgodę na poprawę wyniku': 'Ask for permission to correct the result',
    'Wynik jest już wpisany. Poprawę musi zatwierdzić organizator.': 'The result has already been entered. The organizer must approve a correction.',
    'Poprawę możesz zgłosić tylko do wyniku, który sam wpisałeś.': 'You can only request a correction for a result you entered yourself.',
    'Do tej walki nie ma wyniku wpisanego przez zawodnika.': 'This bout has no result entered by a fencer.',
    'Do rozegrania': 'To be played',
    'Zgłoszono błąd w tym wyniku. Decyduje organizator.': 'An error was reported in this result. The organizer decides.',
    'Grupa jest zamknięta. Wynik wpisuje organizator.': 'The pool is closed. The organizer enters the result.',
    'Popraw wynik': 'Correct result',
    'Zapisz wynik': 'Save result',
    'Wpisz oba wyniki.': 'Enter both scores.',
    'Zgłoś błąd w wyniku': 'Report an error in the result',
    'Nie wszystkie grupy są jeszcze zakończone, ranking może się zmienić. Status awansu pojawi się po zakończeniu wszystkich grup.': 'Not all pools are finished yet, the ranking may change. The advancement status will appear when all pools are finished.',
    'Nie masz przydzielonych meczów.': 'You have no assigned matches.',
    'Mecze pojawią się tutaj, gdy organizator utworzy grupy. Ta strona odświeża się sama.': 'Matches will appear here when the organizer creates the pools. This page refreshes itself.',
    'Wszystkie Twoje mecze w grupie są rozegrane. Dziękujemy!': 'All your matches in the pool have been played. Thank you!',
    'Podaj imię i nazwisko.': 'Enter your first and last name.',
    'Jeśli to Ty, poproś organizatora o osobisty kod QR.': 'If this is you, ask the organizer for a personal QR code.',
    'Nie udało się połączyć': 'Could not connect',

    // ---------- komunikaty serwera ----------
    'Błąd można zgłosić tylko do wyniku wpisanego przez przeciwnika.': 'You can only report an error in a result entered by your opponent.',
    'Imię i nazwisko mogą mieć maksymalnie 60 znaków.': 'First and last name can have at most 60 characters.',
    'Kraj to kod do 3 liter.': 'Country is a code of up to 3 letters.',
    'Lista zawodników jest zablokowana, bo grupy są utworzone.': 'The fencer list is locked because pools have been created.',
    'Nazwa klubu może mieć maksymalnie 80 znaków.': 'The club name can have at most 80 characters.',
    'Nie ma takiego zawodnika.': 'No such fencer.',
    'Nie ma takiej grupy.': 'No such pool.',
    'Nie ma takiej walki.': 'No such bout.',
    'Nie rozpoznano tabeli w pliku. Zapisz stronę klasyfikacji jako „Strona internetowa, tylko HTML” (tabela musi mieć nagłówek „Miejsce”).': 'The table in the file was not recognized. Save the classification page as "Web page, HTML only" (the table must have a "Miejsce" header).',
    'Nie znaleziono pliku.': 'File not found.',
    'Nie znaleziono zapisu.': 'Registration not found.',
    'Nie znaleziono.': 'Not found.',
    'Nieprawidłowa grupa.': 'Invalid pool.',
    'Nieprawidłowe dane grup.': 'Invalid pool data.',
    'Nieprawidłowy JSON.': 'Invalid JSON.',
    'Nieprawidłowy nagłówek Content-Length.': 'Invalid Content-Length header.',
    'Nieprawidłowy rozmiar grupy.': 'Invalid pool size.',
    'Oczekiwano obiektu JSON.': 'A JSON object was expected.',
    'Oczekiwano pola closed (true/false).': 'The closed field (true/false) was expected.',
    'Oczekiwano pola open (true/false).': 'The open field (true/false) was expected.',
    'Osiągnięto limit zawodników.': 'The fencer limit has been reached.',
    'Plik jest pusty.': 'The file is empty.',
    'Podaj oba wyniki.': 'Enter both scores.',
    'Podaj poprawne imię i nazwisko.': 'Enter a valid first and last name.',
    'Podaj zawodnika.': 'Specify the fencer.',
    'Grupa jest zamknięta. Skontaktuj się z organizatorem.': 'The pool is closed. Contact the organizer.',
    'Grupa jest zamknięta. Wynik poprawi organizator.': 'The pool is closed. The organizer will correct the result.',
    'Grupa musi mieć co najmniej dwóch znanych, niepowtarzających się zawodników.': 'A pool must have at least two known, distinct fencers.',
    'Grupy już istnieją. Najpierw je usuń.': 'Pools already exist. Delete them first.',
    'Grupy są utworzone, zapisy nie mogą być otwarte.': 'Pools have been created, registration cannot be opened.',
    'Ranking będzie dostępny po zakończeniu Twojej grupy.': 'The ranking will be available after your pool is finished.',
    'Sędzią nie może być zawodnik walczący w tym meczu.': 'The referee cannot be a fencer fighting in this bout.',
    'Ten zawodnik nie jest w żadnej grupie.': 'This fencer is not in any pool.',
    'To nie jest Twoja walka.': 'This is not your bout.',
    'W grupie muszą zostać co najmniej dwie osoby.': 'At least two people must remain in the pool.',
    'W tej grupie są już wpisane wyniki. Zmiana plansz zmieniłaby kolejność walk.': 'This pool already has results. Changing boards would change the bout order.',
    'Wynik wpisał już ktoś inny. Jeśli jest błędny, zgłoś błąd.': 'Someone else has already entered the result. If it is wrong, report an error.',
    'Zawodnik jest już w tej grupie.': 'The fencer is already in this pool.',
    'Zbyt duże żądanie.': 'The request is too large.',
    'Zbyt wiele błędnych prób PIN-u. Spróbuj za minutę.': 'Too many wrong PIN attempts. Try again in a minute.',
    'Zbyt wiele grup.': 'Too many pools.'
  };

  // [wyrażenie na cały tekst, odpowiedź]; w odpowiedzi $1, $2... albo funkcja
  var PATTERNS = [
    [/^Tura (\d+): grupy zatwierdzone\. Wybierz, co dalej\.$/, 'Round $1: pools approved. Choose what happens next.'],
    [/^Ranking po (\d+)\. turze$/, 'Ranking after round $1'],
    [/^Dobijaki \(tabela (\d+)\)$/, 'Preliminary bouts (table of $1)'],
    [/^Tabela (\d+)$/, 'Table of $1'],
    [/^Drabinka: (\d+) zawodników, tabela (\d+)\.( Z repasażami\.)?(?: Zwycięzca: (.+)\.)?$/, function (m) {
      return 'Bracket: ' + m[1] + ' fencers, table of ' + m[2] + '.' + (m[3] ? ' With repechage.' : '') + (m[4] ? ' Winner: ' + m[4] + '.' : '');
    }],
    [/^Liczba zawodników w drabince musi być liczbą od 2 do (\d+)\.$/, 'The number of fencers in the bracket must be from 2 to $1.'],
    [/^Walka (\d+)$/, 'Bout $1'],
    [/^Walka o 3\. miejsce \(walka (\d+)\)$/, 'Third place bout (bout $1)'],
    [/^Zwycięzca walki (\d+)$/, 'Winner of bout $1'],
    [/^Przegrany walki (\d+)$/, 'Loser of bout $1'],
    [/^(.+) · walka (\d+)$/, function (m) { return translate(m[1]) + ' · bout ' + m[2]; }],
    [/^Przeciwnik wyjdzie ze zwycięzcy walki (\d+)\.$/, 'Your opponent will be the winner of bout $1.'],
    [/^Walka (\d+) \((.+)\): (.+) — (.+)$/, function (m) { return 'Bout ' + m[1] + ' (' + translate(m[2]) + '): ' + m[3] + ' — ' + m[4]; }],
    [/^Sędzia walki (.+)$/, function (m) { return 'Referee of ' + translate(m[1]); }],
    [/^W drabince: (\d+) z (\d+) zawodników \((\d+)%\), tabela (\d+)\.$/, 'In the bracket: $1 of $2 fencers ($3%), table of $4.'],
    [/^(.+) · (\d+) zawodników( · Twoja grupa)?( · zakończona)?$/, function (m) { return m[1] + ' · ' + m[2] + ' fencers' + (m[3] ? ' · Your pool' : '') + (m[4] ? ' · finished' : ''); }],
    [/^Repasaże: miejsca (\d+)–(\d+)$/, 'Repechage: places $1–$2'],
    [/^Repasaże: (.+)$/, function (m) { return 'Repechage: ' + translate(m[1]); }],
    [/^Miejsca (\d+)–(\d+)$/, 'Places $1–$2'],
    [/^Walka o (\d+)\. miejsce$/, 'Bout for place $1'],
    [/^Walka (\d+) · (.+)$/, function (m) { return 'Bout ' + m[1] + ' · ' + translate(m[2]); }],
    [/^Wszystkie grupy (\d+)$/, 'All pools $1'],
    [/^Wszystkie grupy \(tura (\d+)\)$/, 'All pools (round $1)'],
    [/^Ranking wszystkich grup \(tura (\d+)\)$/, 'Ranking of all pools (round $1)'],
    [/^Ranking po turze (\d+)\.$/, 'Ranking after round $1.'],
    [/^Zwycięzca → walka (\d+) · przegrany → walka (\d+)$/, 'Winner → bout $1 · loser → bout $2'],
    [/^Zwycięzca → walka (\d+)$/, 'Winner → bout $1'],
    [/^Przegrany → walka (\d+)$/, 'Loser → bout $1'],
    [/^Błąd serwera \((\d+)\)\.$/, 'Server error ($1).'],
    [/^Ranking (\d+) jest już przypisany do: (.+)\.$/, 'Ranking $1 is already assigned to: $2.'],
    [/^Zawodnik (.+) jest już na liście \(ranking (\d+)\)\.$/, 'Fencer $1 is already on the list (ranking $2).'],
    [/^Taki zawodnik jest już zapisany: (.+) \(ranking (\d+)\)\.$/, 'This fencer is already registered: $1 (ranking $2).'],
    [/^Usunąć zawodnika (.+)\?$/, 'Delete fencer $1?'],
    [/^Liczba zawodników: (\d+)$/, 'Number of fencers: $1'],
    [/^Wczytano (\d+) zawodników \((.+?), (.+)\)\.$/, function (m) { return 'Loaded ' + m[1] + ' fencers (' + m[2].replace(/^plik /, 'file ') + ', ' + m[3] + ').'; }],
    [/^Wczytano (\d+) zawodników, widocznych (\d+)\.$/, 'Loaded $1 fencers, $2 visible.'],
    [/^Pominięte wiersze \((\d+)\): nie rozpoznano miejsca lub nazwiska$/, 'Skipped rows ($1): place or name not recognized'],
    [/^Wczytano (\d+) zawodników z klasyfikacji(?: \(pominięto wierszy: (\d+), zobacz podgląd\))?\. Zaktualizowano ranking (\d+) zapisanych zawodników\.$/, function (m) {
      return 'Loaded ' + m[1] + ' fencers from the classification' + (m[2] ? ' (skipped rows: ' + m[2] + ', see preview)' : '') +
        '. Updated the ranking of ' + m[3] + ' registered fencers.';
    }],
    [/^Rozmiar grupy musi być liczbą całkowitą od 2 do (\d+)\.$/, 'Pool size must be a whole number from 2 to $1.'],
    [/^Rozmiar grupy nie może być większy niż liczba zawodników \((\d+)\)\.$/, 'Pool size cannot be larger than the number of fencers ($1).'],
    [/^Liczba awansujących musi być liczbą od 0 do (\d+)\.$/, 'The number advancing must be from 0 to $1.'],
    [/^Nieprawidłowa liczba awansujących \(maksymalnie (\d+)\)\.$/, 'Invalid number advancing (maximum $1).'],
    [/^Górny limit plansz na grupę musi być liczbą od 1 do (\d+)\.$/, 'The maximum boards per pool must be a number from 1 to $1.'],
    [/^Górny limit plansz musi być liczbą od 1 do (\d+)\.$/, 'The maximum boards must be a number from 1 to $1.'],
    [/^Wynik musi być liczbą całkowitą od 0 do (\d+)\.$/, 'The score must be a whole number from 0 to $1.'],
    [/^Nowy turniej rozpoczęty\. Kopia poprzedniego: archiwum\/(.+)\.$/, 'New tournament started. Copy of the previous one: archiwum/$1.'],
    [/^Nie udało się zapisać archiwum: (.+)$/, 'Could not save the archive: $1'],
    [/^W grupie "(.+)" są już wpisane wyniki\. Przeniesienie zmieniłoby kolejność walk\.$/, 'Pool "$1" already has results. Moving would change the bout order.'],
    [/^Przenieś (.+) do innej grupy$/, 'Move $1 to another pool'],
    [/^T(\d+) · pl\. (\d+)$/, 'R$1 · b. $2'],
    [/^Tura (\d+), plansza (\d+)$/, 'Round $1, board $2'],
    [/^Trafienia: (.+)$/, 'Hits: $1'],
    [/^wpisał: (.+)$/, 'entered by: $1'],
    [/^✎ prośba o poprawę wyniku: (.+)$/, '✎ correction requested by: $1'],
    [/^zalecana przerwa: (.+)$/, 'rest recommended: $1'],
    [/^(.+) \((\d+) zawodników\)( — zakończona)?( — zamknięta)?$/, function (m) {
      return m[1] + ' (' + m[2] + ' fencers)' + (m[3] ? ' — finished' : '') + (m[4] ? ' — closed' : '');
    }],
    [/^Górny limit plansz w (.+)$/, 'Maximum boards in $1'],
    [/^Użyte plansze: ([^.]+)\.$/, 'Boards used: $1.'],
    [/^Górny limit: (\d+) plansz\. Używam (\d+), bo każda walka potrzebuje sędziego z grupy\.$/, 'Board limit: $1. Using $2, because every bout needs a referee from the pool.'],
    [/^Walk bez przerwy: (\d+) \(oznaczone przy walkach\)\.$/, 'Bouts without a rest: $1 (marked at the bouts).'],
    [/^Walk bez sędziego: (\d+) \(wskaż sędziego ręcznie, także z innych grup\)\.$/, 'Bouts without a referee: $1 (assign a referee manually, also from other pools).'],
    [/^Awansuje (\d+) z (\d+) zawodników\.$/, '$1 of $2 fencers advance.'],
    [/^Liczba grup: (\d+)$/, 'Number of pools: $1'],
    [/^miejsce (\d+) w klasyfikacji PZSzerm$/, 'place $1 in the PZSzerm classification'],
    [/^(.+) · tura (\d+) · plansza (\d+)$/, '$1 · round $2 · board $3'],
    [/^Sędzia: (.+)$/, 'Referee: $1'],
    [/^Wynik: (\d+):(\d+) \(wygrana\)$/, 'Result: $1:$2 (win)'],
    [/^Wynik: (\d+):(\d+) \(porażka\)$/, 'Result: $1:$2 (loss)'],
    [/^(.+) \(zamknięta\)$/, '$1 (closed)'],
    [/^Wyniki Twojej grupy \((.+)\)$/, 'Your pool results ($1)'],
    [/^(.+) · tura (\d+) · plansza (\d+): (.+) — (.+?)( \(rozegrana\))?$/, function (m) {
      return m[1] + ' · round ' + m[2] + ' · board ' + m[3] + ': ' + m[4] + ' — ' + m[5] + (m[6] ? ' (played)' : '');
    }],
    [/^Wszystkie grupy zakończone\. Awansuje (\d+) zawodników\.$/, 'All pools are finished. $1 fencers advance.']
  ];

  function norm(text) { return text.replace(/\s+/g, ' ').trim(); }

  function translateCore(key) {
    if (Object.prototype.hasOwnProperty.call(EXACT, key)) return EXACT[key];
    for (var i = 0; i < PATTERNS.length; i++) {
      var m = PATTERNS[i][0].exec(key);
      if (!m) continue;
      var out = PATTERNS[i][1];
      if (typeof out === 'function') return out(m);
      return out.replace(/\$(\d)/g, function (_, n) { return m[Number(n)] === undefined ? '' : m[Number(n)]; });
    }
    return null;
  }

  // Zdania sklejone z kilku (np. komunikat serwera + dopisek) tłumaczymy po jednym.
  function translateKey(key) {
    var whole = translateCore(key);
    if (whole !== null) return whole;
    var parts = [];
    var start = 0;
    var cut = /[.!?] (?=[A-ZĄĆĘŁŃÓŚŹŻ])/g;
    var hit;
    while ((hit = cut.exec(key))) {
      parts.push(key.slice(start, hit.index + 1));
      start = hit.index + 2;
    }
    parts.push(key.slice(start));
    if (parts.length < 2) return null;
    var changed = false;
    var out = [];
    var i = 0;
    while (i < parts.length) {
      var matched = false;
      for (var k = Math.min(3, parts.length - i); k >= 1 && !matched; k--) {
        var t = translateCore(parts.slice(i, i + k).join(' '));
        if (t !== null) {
          out.push(t);
          i += k;
          changed = matched = true;
        }
      }
      if (!matched) out.push(parts[i++]);
    }
    return changed ? out.join(' ') : null;
  }

  function poolNames(text) { return text.replace(/\b(?:Pula|Grupa) (\d+)\b/g, 'Pool $1'); }

  function translate(text) {
    if (typeof text !== 'string' || !/\S/.test(text)) return text;
    var lead = text.match(/^\s*/)[0];
    var trail = text.match(/\s*$/)[0];
    var key = norm(text);
    var t = translateKey(key);
    var out = poolNames(t === null ? key : t);
    if (t === null && out === key) return text;
    return lead + out + trail;
  }

  var api = { translate: translate, lang: 'pl' };
  if (typeof window !== 'undefined') window.I18N = api;
  if (typeof document === 'undefined') {
    if (typeof module !== 'undefined') module.exports = api;
    return;
  }

  // ---------- DOM ----------

  var ATTRS = ['placeholder', 'aria-label', 'title', 'alt'];
  var SKIP = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1 };
  var textState = new WeakMap();   // węzeł tekstowy -> { pl, en }
  var attrState = new WeakMap();   // element -> { attr: { pl, en } }
  var current = 'pl';
  var observer = null;

  function readLang() {
    try {
      var fromUrl = new URLSearchParams(location.search).get('lang');
      if (fromUrl === 'en' || fromUrl === 'pl') {
        localStorage.setItem(KEY, fromUrl);
        return fromUrl;
      }
      return localStorage.getItem(KEY) === 'en' ? 'en' : 'pl';
    } catch (e) { return 'pl'; }
  }

  function skipped(node) {
    for (var el = node.nodeType === 1 ? node : node.parentElement; el; el = el.parentElement) {
      if (SKIP[el.tagName] || el.hasAttribute('data-no-i18n')) return true;
    }
    return false;
  }

  function doText(node) {
    if (skipped(node)) return;
    var st = textState.get(node);
    if (st && node.data === st.en) return;           // to nasz własny zapis
    var pl = node.data;
    var en = translate(pl);
    textState.set(node, { pl: pl, en: en });
    if (en !== pl) node.data = en;
  }

  function doAttr(el, name) {
    if (!el.hasAttribute(name) || skipped(el)) return;
    var map = attrState.get(el) || {};
    var value = el.getAttribute(name);
    if (map[name] && map[name].en === value) return;
    var en = translate(value);
    map[name] = { pl: value, en: en };
    attrState.set(el, map);
    if (en !== value) el.setAttribute(name, en);
  }

  function walk(root) {
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11) return;
    if (root.nodeType === 1) ATTRS.forEach(function (a) { doAttr(root, a); });
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    var n;
    while ((n = tw.nextNode())) {
      if (n.nodeType === 3) doText(n); else ATTRS.forEach(function (a) { doAttr(n, a); });
    }
  }

  function restoreAll() {
    var tw = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    var n;
    while ((n = tw.nextNode())) {
      if (n.nodeType === 3) {
        var st = textState.get(n);
        if (st && n.data === st.en && st.en !== st.pl) n.data = st.pl;
        textState.delete(n);
      } else {
        var map = attrState.get(n);
        if (map) {
          Object.keys(map).forEach(function (a) {
            if (n.getAttribute(a) === map[a].en && map[a].en !== map[a].pl) n.setAttribute(a, map[a].pl);
          });
          attrState.delete(n);
        }
      }
    }
  }

  function startObserver() {
    if (observer) return;
    observer = new MutationObserver(function (records) {
      records.forEach(function (r) {
        if (r.type === 'childList') {
          r.addedNodes.forEach(function (n) { walk(n); });
        } else if (r.type === 'characterData') {
          doText(r.target);
        } else if (r.type === 'attributes') {
          doAttr(r.target, r.attributeName);
        }
      });
    });
    observer.observe(document.documentElement, {
      childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS
    });
  }

  function stopObserver() {
    if (observer) { observer.disconnect(); observer = null; }
  }

  function setLang(lang) {
    current = lang === 'en' ? 'en' : 'pl';
    api.lang = current;
    try { localStorage.setItem(KEY, current); } catch (e) { /* tryb prywatny */ }
    document.documentElement.lang = current;
    stopObserver();
    restoreAll();
    if (current === 'en') {
      walk(document.documentElement);
      startObserver();
    }
    updateSwitch();
  }

  // Potwierdzenia (window.confirm) też tłumaczymy.
  var originalConfirm = window.confirm;
  window.confirm = function (message) {
    return originalConfirm.call(window, current === 'en' ? translate(String(message)) : message);
  };

  // ---------- przełącznik z flagami ----------

  var FLAGS = {
    pl: '<svg viewBox="0 0 24 16" width="28" height="19" aria-hidden="true"><rect width="24" height="8" fill="#fff"/><rect y="8" width="24" height="8" fill="#dc143c"/></svg>',
    en: '<svg viewBox="0 0 60 30" width="28" height="19" aria-hidden="true"><clipPath id="i18n-s"><path d="M0,0 v30 h60 v-30 z"/></clipPath><clipPath id="i18n-t"><path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z"/></clipPath><g clip-path="url(#i18n-s)"><path d="M0,0 v30 h60 v-30 z" fill="#012169"/><path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6"/><path d="M0,0 L60,30 M60,0 L0,30" clip-path="url(#i18n-t)" stroke="#c8102e" stroke-width="4"/><path d="M30,0 v30 M0,15 h60" stroke="#fff" stroke-width="10"/><path d="M30,0 v30 M0,15 h60" stroke="#c8102e" stroke-width="6"/></g></svg>'
  };
  var buttons = {};

  function buildSwitch() {
    var style = document.createElement('style');
    style.textContent =
      '.lang-switch{position:fixed;top:10px;right:12px;z-index:1000;display:flex;gap:6px;}' +
      '.lang-switch button{all:unset;box-sizing:border-box;cursor:pointer;line-height:0;padding:3px;border-radius:6px;' +
      'border:2px solid transparent;opacity:.55;}' +
      '.lang-switch button:hover{opacity:1;}' +
      '.lang-switch button[aria-pressed="true"]{opacity:1;border-color:#60a5fa;}' +
      '.lang-switch button:focus-visible{outline:2px solid #60a5fa;outline-offset:1px;}' +
      '.lang-switch svg{display:block;border-radius:3px;box-shadow:0 0 0 1px rgba(128,128,128,.5);}';
    document.head.appendChild(style);
    var box = document.createElement('div');
    box.className = 'lang-switch';
    box.setAttribute('data-no-i18n', '');
    [['pl', 'Polski'], ['en', 'English']].forEach(function (pair) {
      var b = document.createElement('button');
      b.type = 'button';
      b.innerHTML = FLAGS[pair[0]];
      b.setAttribute('aria-label', pair[1]);
      b.title = pair[1];
      b.addEventListener('click', function () { setLang(pair[0]); });
      buttons[pair[0]] = b;
      box.appendChild(b);
    });
    document.body.appendChild(box);
  }

  function updateSwitch() {
    Object.keys(buttons).forEach(function (k) { buttons[k].setAttribute('aria-pressed', String(k === current)); });
  }

  buildSwitch();
  setLang(readLang());
})();
