<div align="center">

#  Image Segmentation App

O aplicație modernă și intuitivă pentru **segmentarea manuală și semiautomată a imaginilor** cu un design ergonomic

</div>

---

##  Scopul aplicației

În procesele de **Computer Vision**, **Inteligență Artificială** și **Diagnostic Medical**, segmentarea imaginilor reprezintă pasul esențial prin care se izolează obiectele de interes de fundal  

**Scopul principal** al acestei aplicații este de a oferi un instrument precis, rapid și ușor de utilizat pentru **crearea și editarea măștilor binare** de segmentare:
* **Generare de mască binară (`Grayscale8`):** Pixelii selectați au valoarea 255 (Alb - Mască), iar fundalul ne-selectat are valoarea 0 (Negru)
* **Suprapunere vizuală (Overlay):** Oferă feedback vizual în timp real utilizând un strat roșu semitransparent peste imaginea originală pentru vizualizarea clară a regiunilor delimitate
* **Export direct:** Măștile pot fi salvate direct în formate standard (`PNG`, `BMP`, `JPG`) pentru a fi folosite în antrenarea modelelor de Machine Learning / Deep Learning

---

##  Tehnologii utilizate

* **Limbaj de programare:** `Python 3.10+`
* **Cadrul grafic UI:** `PyQt6` (`QGraphicsView`, `QGraphicsScene`, `QPainter`, `QImage`, `QSS`,etc.)
  * Implementare strictă prin cod Python (fără utilizarea designer-ului vizual Qt Designer sau fișiere .ui)
* **Procesare numerică și memorie:** `NumPy`
  * Utilizat pentru manipularea vectorizată ultra-rapidă a buffer-elor de imagini și aplicarea algoritmilor de umplere fără degradarea performanței C++
* **Styling și Design System:** `QSS` (Qt Style Sheets)
  * Design modular extern (styles.qss) cu butoane geometrice personalizate și stări vizuale dinamice

---

##  Interacțiunea cu utilizatorul și feedback-ul vizual

Aplicația pune accent pe un flux de lucru nativ,bazându-se pe ghidarea stărilor vizuale (*State-Driven UX*):

### 1. Acțiunile Utilizatorului
* **Încărcare imagine:**
  * Prin butonul `Load Image` din panoul lateral sau prin butonul circular central de **Upload** prezent în starea inițială (`Empty State`)
* **Selectare instrumente (Tools):**
  * Comutare exclusivă între instrumentele Rectangle, Ellipse, Lines, Freehand și Bucket Fill, folosind butoane interactive care își modifică dinamic forma colțurilor pentru a indica vizual starea de selecție (checked/unchecked)
* **Ajustare brush size:**
  * Modificare fluidă a grosimii de trasare prin slider-ul orizontal (1 px → 50 px)
* **Gestionare stări (Action Buttons):**
  * `Undo`: Anulează ultima acțiune desenată sau umplută
  * `Reset Canvas`: Golește complet masca binară curentă
  * `Save Mask`: Exportă masca creată într-un fișier imagine

### 2. Feedback-ul oferit Utilizatorului
* **Micro-interacțiuni și Hover:** Butoanele își schimbă culoarea, conturul și curbura bordurii la trecerea mouse-ului și la apăsare
* **Afișare dinamică a instrumentului activ :** Butonul uneltei selectate își inversează unghiurile rotunjite și primește un contur albastru aprins
* **Linii dinamice de previzualizare :**
  * *Dreptunghi / Elipsă:* Trasare cu linie punctată albă în timp ce utilizatorul poziționează cel de-al doilea click
  * *Poligon:* Linii de ghidare albe cu linii punctate către mouse și noduri roșii în fiecare punct fixat
  * *Freehand:* Linie contur Cyan în timpul desenării continue
* **Controlul stării butoanelor (Enabled/Disabled):**
  * Butoanele `Undo`, `Reset Canvas` și `Save Mask` sunt dezactivate vizual și funcțional atunci când acțiunile respective nu sunt posibile
* **Overlay Roșu Semitransparent:** Transparență calibrată la aprox. 40% , permițând utilizatorului să vadă concomitent detaliile imaginii originale și aria măștii generate

---

##  Logica din Spatele Instrumentelor (Tools Architecture)

Arhitectura este separată în două fișiere principale (`main.py` pentru UI/Control și `canvas.py` pentru grafică/procesare)

### 1. Dreptunghi și Elipsă 
* **Logică interacțiune:** Sistem de trasare în **2 click-uri** (Click 1: colț/punct de start, Click 2: colț opus / dimensiune finală)
* **Generare mască:** Calculul dreptunghiului normalizat și rasterizarea cu `QPainter` folosind `QBrush` alb pe mască

### 2. Poligon/Linii Frânte
* **Logică interacțiune:** Adăugare secvențială de puncte la fiecare click
* **Închidere automată:** Dacă un click este efectuat la o distanță mai mică de 12 px față de primul punct introdus (nodul de origine) și există cel puțin 3 puncte, poligonul se închide automat și umple interiorul
* **Generare mască:** Folosește `QPainterPath` pentru a crea o cale închisă umplută complet cu culoare albă

### 3. Desen Liber (Freehand)
* **Logică interacțiune:** Înregistrare continuă pe evenimentul `mouseMoveEvent` atâta timp cât butonul stânga al mouse-ului este menținut apăsat
* **Generare mască:** Reține traseul sub formă de vector de segmente `QPainterPath` și îl rasterizează folosind un penel cu capete și îmbinări rotunjite (`RoundCap`, `RoundJoin`) pentru evitarea fragmentării

### 4. Umplere Regiune (Bucket Fill)
* **Algoritm:** **Scanline Flood Fill** optimizat cu buffer `NumPy`
* **Cum funcționează:**
  1. La click, se citește valoarea pixelului apăsat direct din memorie
  2. Dacă pixelul este deja selectat (≥ 128), operația este ignorată
  3. Algoritmul parcurge liniile orizontale (Scanlines), extinzând secvențial limitele stânga-dreapta și introducând segmentele adiacente (sus/jos) într-o stivă
  4. Această tehnică evită apelurile recursive (care ar provoca Stack Overflow) și procesează regiuni masive în doar câteva milisecunde

