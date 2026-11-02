import sys
import os
import re
import json
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QColor,QPixmap, QPainter, QPen, QPainterPath
from PyQt6.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QButtonGroup, QSlider, QLabel, QFileDialog, QMessageBox, QGroupBox,
    QListWidget, QListWidgetItem, QColorDialog)
from canvas import SegmentationCanvas, MODE_CLASSIC, MODE_MULTI

# extensiile acceptate la incarcare
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp')


# formatele de export ale mastii
EXPORT_FILTERS = {
    "Color mask - fiecare clasa cu culoarea ei (*.png *.bmp)": 'color',
    "Label mask - pixel = indexul clasei (*.png *.bmp)": 'label',
    "Binary mask per clasa - cate un fisier 0/255 (*.png *.bmp)": 'binary'}


class MainWindow(QMainWindow):
    """gestioneaza panoul lateral de control, starile butoanelor, incarcarea/salvarea
    imaginilor si comunicarea cu canvasul"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Segmentation")
        self.resize(1400, 800)
        self.canvas = SegmentationCanvas()
        self.canvas.main_window = self
        self.setAcceptDrops(True)
        self.setup_ui()

    def setup_ui(self):
        """construiește structura layout principal si toate controalele UI"""

        # widget central care contine intreaga interfata
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        #layout orizontal principal (panou control stanga /canvas dreapta)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # panoul lateral de control
        control_panel = QWidget()
        control_panel.setFixedWidth(280)
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(20)

        # titlul aplicației
        title = QLabel("Image Segmentation")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("lbl_title")
        panel_layout.addWidget(title)

        # comutator de mod: Classic (masca binara alb/negru) / Multi-class (clase colorate)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.btn_mode_classic = QPushButton("Classic")
        self.btn_mode_multi = QPushButton("Multi-class")
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        for btn in [self.btn_mode_classic, self.btn_mode_multi]:
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setObjectName("btn_mode_option")
            self.mode_button_group.addButton(btn)
            mode_row.addWidget(btn)
        self.btn_mode_multi.setChecked(self.canvas.mode == MODE_MULTI)
        self.btn_mode_classic.setChecked(self.canvas.mode == MODE_CLASSIC)
        self.btn_mode_classic.clicked.connect(lambda: self.on_mode_changed(MODE_CLASSIC))
        self.btn_mode_multi.clicked.connect(lambda: self.on_mode_changed(MODE_MULTI))
        panel_layout.addLayout(mode_row)

        #buton incarcare imagine
        btn_load = QPushButton("Load Image")
        btn_load.setObjectName("btn_side_load")
        btn_load.setFixedHeight(40)
        btn_load.setFixedWidth(230)
        btn_load.clicked.connect(self.on_load_image)
        panel_layout.addWidget(btn_load, alignment=Qt.AlignmentFlag.AlignCenter)

        panel_layout.addStretch(1)

        # secțiunea Tools
        tools_group = QGroupBox("Tools")
        tools_layout = QVBoxLayout(tools_group)
        tools_layout.setSpacing(10)
        tools_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # crearea butoanelor pentru unelte
        self.btn_rect = QPushButton("Rectangle")
        self.btn_ellipse = QPushButton("Ellipse")
        self.btn_polygon = QPushButton("Lines")
        self.btn_freehand = QPushButton("Freehand")
        self.btn_fill = QPushButton("Bucket Fill")

        tools = [self.btn_rect, self.btn_ellipse, self.btn_polygon, self.btn_freehand, self.btn_fill]
        for btn in tools:
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setFixedWidth(210)
            btn.setObjectName("btn_tool_option")

        # selectare implicita pentru Rectangle
        self.btn_rect.setChecked(True)

        # gruparea exclusiva a butoanelor (doar o unealta poate fi activa la un moment dat)
        self.tool_button_group = QButtonGroup(self)
        self.tool_button_group.setExclusive(True)
        self.tool_button_group.addButton(self.btn_rect, 1)
        self.tool_button_group.addButton(self.btn_ellipse, 2)
        self.tool_button_group.addButton(self.btn_polygon, 3)
        self.tool_button_group.addButton(self.btn_freehand, 4)
        self.tool_button_group.addButton(self.btn_fill, 5)

        # conectarea schimbarii uneltei la metoda de tratare
        self.tool_button_group.idClicked.connect(self.on_tool_changed)

        # adaugarea butoanelor in layout ul grupului Tools
        for btn in tools:
            tools_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(tools_group)
        panel_layout.addStretch(1)

        # secțiunea Brush
        brush_group = QGroupBox("Brush")
        brush_layout = QVBoxLayout(brush_group)
        brush_layout.setSpacing(10)

        # label pentru afisarea dimensiunii curente a brushului
        self.lbl_brush = QLabel(f"Size: {self.canvas.brush_size} px")
        self.lbl_brush.setObjectName("lbl_brush")

        #slider orizontal pentru ajustarea grosimii brushului
        self.slider_brush = QSlider(Qt.Orientation.Horizontal)
        self.slider_brush.setMinimum(1)
        self.slider_brush.setMaximum(50)
        self.slider_brush.setValue(self.canvas.brush_size)
        self.slider_brush.valueChanged.connect(self.on_brush_size_changed)

        brush_layout.addWidget(self.lbl_brush)
        brush_layout.addWidget(self.slider_brush)
        panel_layout.addWidget(brush_group)
        panel_layout.addStretch(1)

        #butoanele de acțiune (Undo, Reset Canvas, Save Mask)
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.setObjectName("btn_undo")
        self.btn_undo.setFixedHeight(40)
        self.btn_undo.setFixedWidth(230)
        self.btn_undo.clicked.connect(self.on_undo)
        panel_layout.addWidget(self.btn_undo, alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_reset = QPushButton("Reset Canvas")
        self.btn_reset.setObjectName("btn_reset")
        self.btn_reset.setFixedHeight(40)
        self.btn_reset.setFixedWidth(230)
        self.btn_reset.clicked.connect(self.canvas.reset_mask)
        panel_layout.addWidget(self.btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_export = QPushButton("Save Mask")
        self.btn_export.setObjectName("btn_export")
        self.btn_export.setFixedHeight(40)
        self.btn_export.setFixedWidth(230)
        self.btn_export.clicked.connect(self.on_export_mask)
        panel_layout.addWidget(self.btn_export, alignment=Qt.AlignmentFlag.AlignCenter)

        panel_layout.addStretch(1)

        # panoul lateral drept pentru clase (etichete multiple, fiecare cu culoarea ei)
        self.class_panel = QWidget()
        self.class_panel.setFixedWidth(250)
        self.class_panel.setVisible(self.canvas.mode == MODE_MULTI)
        class_panel_layout = QVBoxLayout(self.class_panel)
        class_panel_layout.setContentsMargins(0, 0, 0, 0)

        classes_group = QGroupBox("Classes")
        classes_layout = QVBoxLayout(classes_group)
        classes_layout.setSpacing(10)

        # lista claselor
        self.class_list = QListWidget()
        self.class_list.setObjectName("class_list")
        self.class_list.setIconSize(QSize(18, 18))
        self.class_list.currentRowChanged.connect(self.on_class_selected)
        self.class_list.itemChanged.connect(self.on_class_item_changed)
        classes_layout.addWidget(self.class_list)

        lbl_hint = QLabel("Double-click to rename\nCheckbox = show / hide on canvas")
        lbl_hint.setObjectName("lbl_hint")
        classes_layout.addWidget(lbl_hint)

        # butoane de gestionare a claselor
        class_buttons_row = QHBoxLayout()
        self.btn_add_class = QPushButton("Add")
        self.btn_remove_class = QPushButton("Remove")
        class_buttons_row.addWidget(self.btn_add_class)
        class_buttons_row.addWidget(self.btn_remove_class)
        classes_layout.addLayout(class_buttons_row)

        self.btn_class_color = QPushButton("Change Color")
        self.btn_clear_class = QPushButton("Clear Class")
        classes_layout.addWidget(self.btn_class_color)
        classes_layout.addWidget(self.btn_clear_class)

        for btn in [self.btn_add_class, self.btn_remove_class, self.btn_class_color, self.btn_clear_class]:
            btn.setObjectName("btn_class_action")
            btn.setFixedHeight(34)

        self.btn_add_class.clicked.connect(self.on_add_class)
        self.btn_remove_class.clicked.connect(self.on_remove_class)
        self.btn_class_color.clicked.connect(self.on_change_class_color)
        self.btn_clear_class.clicked.connect(self.on_clear_class)

        class_panel_layout.addWidget(classes_group)

        # adaugarea panourilor si a canvasului in layout ul principal
        main_layout.addWidget(control_panel)
        main_layout.addWidget(self.canvas)
        main_layout.addWidget(self.class_panel)
        self.refresh_class_list()

        #zona centrala /empty state (cand nu este incarcata o imagine)
        self.empty_state_widget = QWidget(self.canvas.viewport())
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(12)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        #label text central
        self.lbl_no_image = QLabel("No Image Loaded\nDrag and drop an image or click Upload")
        self.lbl_no_image.setObjectName("lbl_no_image")
        self.lbl_no_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # butonul central de load image
        self.center_load_button = QPushButton()
        self.center_load_button.setObjectName("btn_center_load")
        self.center_load_button.setFixedSize(140, 44)

        #generare pictograma de Upload si atasare pe buton
        upload_icon = self.create_upload_icon(QColor(255, 255, 255), size=28)
        self.center_load_button.setIcon(upload_icon)
        self.center_load_button.setIconSize(QSize(28, 28))
        self.center_load_button.clicked.connect(self.on_load_image)

        empty_layout.addWidget(self.lbl_no_image)
        empty_layout.addWidget(self.center_load_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.empty_state_widget.adjustSize()
        self.empty_state_widget.show()

        # actualizarea starii initiale a butoanelor (dezactivare Undo,Reset,Save la pornire)
        self.update_button_states()

    def update_button_states(self):
        """actualizeaza starile (enabled/disabled) ale butoanelor si vizibilitatea starii empty state
        in functie de prezenta imaginii, istoricului de undo si continutului mastii"""
        image_loaded = self.canvas.image_pixmap is not None
        undo_available = len(self.canvas.history_stack) > 0
        has_content = self.canvas.has_mask_content()

        # Undo este activ doar daca este o imagine si stiva de istoric nu este goala
        self.btn_undo.setEnabled(image_loaded and undo_available)

        # Reset Canvas este activ doar daca exista pixeli selectati pe masca
        self.btn_reset.setEnabled(image_loaded and has_content)

        # Save Mask este activ cand avem o imagine incarcata
        self.btn_export.setEnabled(image_loaded)

        # doar daca clasa activa are pixeli pe masca
        self.btn_add_class.setEnabled(self.canvas.can_add_class())
        self.btn_remove_class.setEnabled(len(self.canvas.classes) > 1)
        self.btn_clear_class.setEnabled(image_loaded and self.canvas.class_has_pixels(self.canvas.active_class_id))

        # comutare vizibilitate pentru overlay-ul "No Image Loaded"
        if hasattr(self, "empty_state_widget"):
            self.empty_state_widget.setVisible(not image_loaded)

    def position_center_load_button(self):
        """pozitioneaza exact pe centrul suprafetei canvas widget-ul empty state"""
        self.empty_state_widget.adjustSize()
        x = (self.canvas.viewport().width() - self.empty_state_widget.width()) // 2
        y = (self.canvas.viewport().height() - self.empty_state_widget.height()) // 2
        self.empty_state_widget.move(x, y)

    def resizeEvent(self, event):
        """recalculeaza centrul widget-ului empty state la redimensionarea ferestrei"""
        super().resizeEvent(event)
        if hasattr(self, "empty_state_widget"):
            self.position_center_load_button()

    def showEvent(self, event):
        """aseaza widget-ul empty state pe centru imediat dupa prima afisare a ferestrei"""
        super().showEvent(event)
        if hasattr(self, "empty_state_widget"):
            QTimer.singleShot(0, self.position_center_load_button)

    def on_load_image(self):
        """deschide dialogul de selectare a fisierului si incarca imaginea pe canvas"""
        file_path, _ = QFileDialog.getOpenFileName(self,"Deschide Imagine","",
            "Imagini (*.png *.jpg *.jpeg *.bmp)")

        if file_path:
            self.load_image_file(file_path)

    def load_image_file(self, file_path):
        if not self.canvas.load_image(file_path):
            QMessageBox.critical(self,"Eroare","Imaginea nu s-a putut încărca")

    def dropped_image_path(self, event):
        """returneaza primul fisier imagine local din datele trase cu mouse-ul sau None"""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(IMAGE_EXTENSIONS):
                return path
        return None

    def dragEnterEvent(self, event):
        """accepta drag and drop doar pentru fisiere imagine"""
        if self.dropped_image_path(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        """incarca imaginea lasata (drop) peste fereastra"""
        path = self.dropped_image_path(event)
        if path:
            event.acceptProposedAction()
            self.load_image_file(path)

    def on_mode_changed(self, mode):
        """comuta modul de lucru Classic ascunde panoul de clase/ Multi-class il afiseaza"""
        self.canvas.set_mode(mode)
        self.class_panel.setVisible(mode == MODE_MULTI)
        self.refresh_class_list()

    def on_tool_changed(self, tool_id):
        """schimba instrumentul curent de segmentare in canvas la selectarea unui buton"""
        mapping = {
            1: 'rectangle',
            2: 'ellipse',
            3: 'polygon',
            4: 'freehand',
            5: 'fill'}

        self.canvas.current_tool = mapping.get(tool_id, 'rectangle')
        # resetare puncte temporare ale poligonului la schimbarea uneltei
        self.canvas.polygon_points.clear()
        self.canvas.click_count = 0
        self.canvas.update_canvas_overlay()

    def on_brush_size_changed(self, value):
        """actualizeaza dimensiunea brushului in canvas si textul labelului"""
        self.lbl_brush.setText(f"Size: {value} px")
        self.canvas.brush_size = value

    def on_undo(self):
        """apeleaza Undo din canvas"""
        self.canvas.undo_last_action()

    def create_color_icon(self, color, size=18):
        """deseneaza un patrat rotunjit plin cu culoarea clasei, folosit ca pictograma in lista"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
        painter.setBrush(color)
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 4, 4)
        painter.end()
        return QIcon(pixmap)

    def refresh_class_list(self):
        """reconstruieste lista de clase din canvas (nume, culoare, vizibilitate, clasa activa)"""
        self.class_list.blockSignals(True)
        self.class_list.clear()
        active_row = 0

        for row, c in enumerate(self.canvas.classes):
            item = QListWidgetItem(self.create_color_icon(c['color']), c['name'])
            item.setData(Qt.ItemDataRole.UserRole, c['id'])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if c['visible'] else Qt.CheckState.Unchecked)
            self.class_list.addItem(item)
            if c['id'] == self.canvas.active_class_id:
                active_row = row

        self.class_list.setCurrentRow(active_row)
        self.class_list.blockSignals(False)
        self.update_button_states()

    def on_class_selected(self, row):
        """seteaza clasa activa la selectarea unui rand din lista"""
        item = self.class_list.item(row)
        if item is None:
            return
        self.canvas.active_class_id = item.data(Qt.ItemDataRole.UserRole)
        self.canvas.update_canvas_overlay()
        self.update_button_states()

    def on_class_item_changed(self, item):
        """trateaza redenumirea si bifarea/debifarea vizibilitatii unei clase"""
        c = self.canvas.get_class(item.data(Qt.ItemDataRole.UserRole))
        if c is None:
            return

        name = item.text().strip()
        if name:
            c['name'] = name
        else:
            # numele gol nu este permis se revine la cel vechi
            self.class_list.blockSignals(True)
            item.setText(c['name'])
            self.class_list.blockSignals(False)

        visible = item.checkState() == Qt.CheckState.Checked
        if visible != c['visible']:
            c['visible'] = visible
            self.canvas.on_classes_changed()

    def on_add_class(self):
        """adauga o clasa noua cu urmatoarea culoare din paleta si o selecteaza pentru redenumire"""
        if self.canvas.add_class() is None:
            return
        self.refresh_class_list()
        self.canvas.update_canvas_overlay()
        self.class_list.editItem(self.class_list.currentItem())

    def on_remove_class(self):
        """sterge clasa activa impreuna cu pixelii ei """
        c = self.canvas.get_class(self.canvas.active_class_id)
        if c is None:
            return

        if self.canvas.class_has_pixels(c['id']):
            answer = QMessageBox.question(self, "Ștergere clasă",
                f"Ștergeți clasa „{c['name']}” și toți pixelii ei de pe mască?")
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.canvas.remove_class(c['id'])
        self.refresh_class_list()

    def on_change_class_color(self):
        """deschide selectorul de culoare pentru clasa activa"""
        c = self.canvas.get_class(self.canvas.active_class_id)
        if c is None:
            return

        color = QColorDialog.getColor(c['color'], self, f"Culoare pentru „{c['name']}”")
        if color.isValid():
            c['color'] = color
            self.refresh_class_list()
            self.canvas.on_classes_changed()

    def on_clear_class(self):
        """goleste de pe masca doar pixelii clasei active"""
        self.canvas.clear_class(self.canvas.active_class_id)

    def create_upload_icon(self, color, size=28):
        """deseneaza o pictograma vectoriala de Upload (baza + sageata sus)
        folosind QPainter si o returneaza ca QIcon"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # baza inferioara
        path_box = QPainterPath()
        path_box.moveTo(4, 17)
        path_box.lineTo(4, 23)
        path_box.lineTo(24, 23)
        path_box.lineTo(24, 17)
        painter.drawPath(path_box)

        #sageata orientata in sus
        path_arrow = QPainterPath()
        path_arrow.moveTo(14, 18)
        path_arrow.lineTo(14, 4)       #linia verticala
        path_arrow.moveTo(8, 10)
        path_arrow.lineTo(14, 4)       #varf stanga
        path_arrow.lineTo(20, 10)      #varf dreapta
        painter.drawPath(path_arrow)
        painter.end()
        return QIcon(pixmap)

    def export_classic_mask(self):
        """modul Classic: salveaza masca binara Grayscale8 (255 = selectat/alb, 0 = fundal/negru)"""
        file_path, _ = QFileDialog.getSaveFileName(self,"Salvează Masca Binară","",
            "Imagine PNG (*.png);;Imagine BMP (*.bmp)")

        if not file_path:
            return

        root, ext = os.path.splitext(file_path)
        if ext.lower() not in ('.png', '.bmp'):
            file_path = root + '.png'

        if self.canvas.class_binary_mask().save(file_path):
            QMessageBox.information(self, "Succes", "Masca a fost salvată cu succes")
        else:
            QMessageBox.critical(self, "Eroare", "Eroare la salvarea fișierului")

    def on_export_mask(self):
        """deschide dialogul de salvare si exporta masca in formatul ales
        color= Imagine RGB cu fiecare clasa in culoarea ei
        label= Valoarea pixelului - ID-ul clasei + JSON
        binary= Câte un fișier Alb/Negru pentru fiecare clasă
        formatul JPG nu este oferit deoarece compresia cu pierderi altereaza valorile mastii
        in modul Classic se exporta direct masca binara (alb = selectat, negru = fundal)"""
        if self.canvas.mode == MODE_CLASSIC:
            self.export_classic_mask()
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(self, "Salvează Masca", "",
            ";;".join(EXPORT_FILTERS))

        if not file_path:
            return

        mode = EXPORT_FILTERS.get(selected_filter, 'color')
        root, ext = os.path.splitext(file_path)
        if ext.lower() not in ('.png', '.bmp'):
            ext = '.png'

        try:
            if mode == 'color':
                saved = [root + ext] if self.canvas.colored_mask_image().save(root + ext) else []
                expected = 1

            elif mode == 'label':
                image, legend = self.canvas.label_mask_image()
                saved = [root + ext] if image.save(root + ext) else []
                expected = 1
                if saved:
                    with open(root + "_classes.json", "w", encoding="utf-8") as f:
                        json.dump(legend, f, ensure_ascii=False, indent=2)
                    saved.append(root + "_classes.json")

            else:
                saved = []
                expected = len(self.canvas.classes)
                for c in self.canvas.classes:
                    safe_name = re.sub(r'[^\w\-]+', '_', c['name']).strip('_') or f"class{c['id']}"
                    path = f"{root}_{safe_name}{ext}"
                    if self.canvas.class_binary_mask(c['id']).save(path):
                        saved.append(path)
        except OSError:
            saved, expected = [], 1

        if len(saved) >= expected:
            names = "\n".join(os.path.basename(p) for p in saved)
            QMessageBox.information(self, "Succes", f"Masca a fost salvată cu succes!\n\n{names}")
        else:
            QMessageBox.critical(self, "Eroare", "Eroare la salvarea fișierului!")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    #incarcare si aplicare stil extern QSS (styles.qss)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    qss_path = os.path.join(base_dir, "styles.qss")

    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()

    # rularea buclei principale de evenimente Qt
    sys.exit(app.exec())