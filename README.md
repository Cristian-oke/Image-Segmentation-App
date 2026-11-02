<div align="center">

# Image Segmentation App

O aplicație modernă și intuitivă pentru **segmentarea manuală și semiautomată a imaginilor** cu un design ergonomic

</div>

---

## Scopul aplicației

În procesele de **Computer Vision**, **Inteligență Artificială** și **Diagnostic Medical**, segmentarea imaginilor reprezintă pasul esențial prin care se izolează obiectele de interes față de fundal sau se diferențiază mai multe clase de obiecte dintr-o scenă

**Aplicația oferă două moduri principale de lucru:**
- **Modul Classic (Single-class):** Generarea unei măști binare clasice (`Grayscale8`). Pixelii selectați au valoarea 255 (Alb - Mască), iar fundalul ne-selectat are valoarea 0 (Negru)
- **Modul Multi-class:** Segmentarea pe clase multiple. Fiecare clasă primește o culoare unică de suprapunere (overlay) și un ID unic în mască (1..255)

---

## Tehnologii utilizate

- **Limbaj de programare:** `Python 3.10+`
- **Cadrul grafic UI:** `PyQt6` (`QGraphicsView`, `QGraphicsScene`, `QPainter`, `QImage`, `QListWidget`, `QColorDialog`, `QSS` etc)
  - Implementare strictă prin cod Python (fără utilizarea designer-ului vizual Qt Designer sau fișiere `.ui`)
- **Procesare numerică și memorie:** `NumPy`
  - Utilizat pentru manipularea vectorizată ultra-rapidă a buffer-elor de imagini, alinierea liniilor (`bytesPerLine`), Look-Up Tables pentru overlay-uri și aplicarea algoritmilor de umplere fără degradarea performanței C++
- **Styling și Design System:** `QSS` (Qt Style Sheets)
  - Design modular extern (`styles.qss`) cu butoane geometrice personalizate și stări vizuale dinamice

---

## Interacțiunea cu utilizatorul și feedback-ul vizual

Aplicația pune accent pe un flux de lucru nativ, bazându-se pe ghidarea stărilor vizuale (*State-Driven UX*):

### 1. Acțiunile Utilizatorului

- **Încărcare imagine:**
  - Prin butonul `Load Image` din panoul lateral, prin butonul circular central de **Upload** prezent în starea inițială (`Empty State`), sau prin **Drag and Drop** direct peste fereastră
- **Comutare Mod de Lucru (Classic / Multi-class):**
  - Comutare din panoul lateral între modul binar (Classic) și modul pe clase (Multi-class), ultimul activând panoul lateral drept pentru gestiunea claselor
- **Gestiunea Claselor (Modul Multi-class):**
  - **Add:** Adaugă o clasă nouă cu o culoare automată din paletă
  - **Remove:** Șterge clasa selectată și elimină pixelii ei de pe mască
  - **Redenumire:** Dublu-click pe nume în listă
  - **Change Color:** Schimbă culoarea clasei prin `QColorDialog`
  - **Vizibilitate:** Bifa/debifa checkbox-ului ascunde sau afișează clasa pe canvas
  - **Clear Class:** Șterge doar pixelii clasei active de pe mască
- **Selectare instrumente (Tools):**
  - Comutare exclusivă între instrumentele Rectangle, Ellipse, Lines, Freehand și Bucket Fill, folosind butoane interactive care își modifică dinamic forma colțurilor pentru a indica vizual starea de selecție
- **Ajustare brush size:**
  - Modificare fluidă a grosimii de trasare prin slider-ul orizontal (1 px → 50 px)
- **Gestionare stări (Action Buttons):**
  - `Undo`: Anulează ultima acțiune desenată sau umplută (restaurează inclusiv clasele șterse)
  - `Reset Canvas`: Golește complet masca curentă
  - `Save Mask`: Exportă masca creată în formatul ales

### 2. Feedback-ul oferit utilizatorului

- **Micro-interacțiuni și Hover:** Butoanele își schimbă culoarea, conturul și curbura bordurii la trecerea mouse-ului și la apăsare
- **Afișare dinamică a instrumentului activ:** Butonul uneltei selectate își inversează unghiurile rotunjite și primește un contur albastru aprins
- **Linii dinamice de previzualizare (în culoarea clasei active):**
  - *Dreptunghi / Elipsă:* Trasare cu linie punctată în culoarea clasei active în timp ce utilizatorul poziționează cel de-al doilea click
  - *Poligon:* Linii de ghidare punctate în culoarea clasei active către mouse și noduri de control în fiecare punct fixat
  - *Freehand:* Linie de contur în culoarea clasei active în timpul desenării continue
- **Controlul stării butoanelor (Enabled/Disabled):**
  - Butoanele `Undo`, `Reset Canvas`, `Save Mask` și acțiunile pe clase sunt dezactivate vizual și funcțional atunci când acțiunile respective nu sunt posibile
- **Overlay Semitransparent:** Transparență calibrată la aprox. 43% , permițând utilizatorului să vedă concomitent detaliile imaginii originale și aria măștilor colorate

---

## Formate de export ale măștii

În modul **Classic**, masca binară simplă (0/255) poate fi salvată în formatele standard `JPG`, `PNG` sau `BMP`

In modul **Multi-class**, aplicația oferă 3 opțiuni de export prin filtrarea dialogului de salvare (folosind doar formatele fără pierderi `PNG` și `BMP` pentru a nu altera valorile etichetelor):

1. **Color mask :** Imagine RGB în care fiecare clasă este reprezentată cu culoarea ei,ideală pentru prezentare și vizualizare
2. **Label mask :** Imagine `Grayscale8` în care valoarea fiecărui pixel este egală cu indexul clasei (1..N). Este generat automat și un fișier JSON companion (`<nume>_classes.json`) cu legenda numelor claselor, format standard pentru Machine Learning/Computer Vision
3. **Binary mask per clasă :** Generează fișiere separate de mască binară (0/255) pentru fiecare clasă existentă (`<nume>_<clasa>.png`)

---

## Logica din spatele instrumentelor (Tools Architecture)

Arhitectura este separată în două fișiere principale (`main.py` pentru UI/Control și `canvas.py` pentru grafică/procesare)

### 1. Stamp Rasterization (Modul Multi-class)
Pentru a permite aplicarea corectă a formelor pe clase diferite fără coliziuni, aplicația creează un strat temporar binar (*stamp*) pe care `QPainter` rasterizează forma, după care pixelii selectați sunt comitați pe masca principală direct cu ID-ul clasei active prin operații NumPy

### 2. Dreptunghi și Elipsă
- **Logică interacțiune:** Sistem de trasare în **2 click-uri** (Click 1: colț/punct de start, Click 2: colț opus / dimensiune finală)
- **Generare mască:** Calculul dreptunghiului normalizat și rasterizarea pe stamp cu `QPainter`

### 3. Poligon (Lines)
- **Logică interacțiune:** Adăugare secvențială de puncte la fiecare click
- **Închidere automată:** Dacă un click este efectuat la o distanță mai mică de 12 px față de primul punct introdus (nodul de origine) și există cel puțin 3 puncte, poligonul se închide automat și umple interiorul
- **Generare mască:** Folosește `QPainterPath` pentru a crea o cale închisă umplută complet

### 4. Desen liber (Freehand)
- **Logică interacțiune:** Înregistrare continuă pe evenimentul `mouseMoveEvent` atâta timp cât butonul stânga al mouse-ului este menținut apăsat
- **Generare mască:** Reține traseul sub formă de vector de segmente `QPainterPath` și îl rasterizează folosind un penel cu capete și îmbinări rotunjite (`RoundCap`, `RoundJoin`) pentru evitarea fragmentării

### 5. Umplere regiune (Bucket Fill)
- **Algoritm:** **Scanline Flood Fill** optimizat pe buffer `NumPy`
- **Cum funcționează:**
  1. La click, se citește eticheta pixelului apăsat direct din array-ul NumPy
  2. Dacă regiunea are deja ID-ul clasei active, operația este ignorată
  3. Algoritmul parcurge liniile orizontale (Scanlines), extinzând limitele stânga-dreapta prin operații pe vectori booleeni (`np.flatnonzero`) și adăugând segmentele adiacente (sus/jos) într-o stivă
  4. Această tehnică evită apelurile recursive (care ar provoca Stack Overflow) și procesează regiuni masive în doar câteva milisecunde
