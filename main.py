import sys
import os
import re
import json
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QColor,QPixmap, QPainter, QPen, QPainterPath
from PyQt6.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QButtonGroup, QSlider, QLabel, QFileDialog, QGroupBox,
                             QListWidget, QListWidgetItem, QColorDialog, QDialog, QLineEdit,QToolButton)
from canvas import SegmentationCanvas, MODE_CLASSIC, MODE_MULTI

# extensiile acceptate la incarcare
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp')


# formatele de export ale mastii
EXPORT_FILTERS = {
    "Color mask - fiecare clasa cu culoarea ei (*.png *.bmp)": 'color',
    "Label mask - pixel = indexul clasei (*.png *.bmp)": 'label',
    "Binary mask per clasa - cate un fisier 0/255 (*.png *.bmp)": 'binary'}


class CustomMessageBox(QDialog):
    """MesageBox Custom"""

    def __init__(self, parent, title, message, mode="info"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(460)
        self.result_value = False

        # layout-ul radacina al dialogului
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 14, 0, 0)  # Spațiu sus pentru ca badge-ul titlului să iasă peste bordură

        # containerul principal cu bordura
        container = QWidget(self)
        container.setObjectName("dlg_container")
        root_layout.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 24)
        layout.setSpacing(18)

        # butonul X rosu din coltul dreapta-sus
        btn_x = QPushButton("✕", container)
        btn_x.setObjectName("btn_close_x")
        btn_x.setFixedSize(32, 32)
        btn_x.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_x.clicked.connect(self.reject)

        #badge-ul pentru titlu
        lbl_title = QLabel(title, self)
        lbl_title.setObjectName("dlg_title_badge")
        lbl_title.adjustSize()

        def position_overlays():
            # titlul centrat pe linia superioara
            lbl_title.adjustSize()
            tx = (self.width() - lbl_title.width()) // 2
            lbl_title.move(tx, 2)
            lbl_title.raise_()
            btn_x.move(container.width() - 40, 10)
            btn_x.raise_()

        QTimer.singleShot(0, position_overlays)
        layout.addSpacing(10)

        #mesajul text centrat
        lbl_msg = QLabel(message)
        lbl_msg.setObjectName("dlg_msg")
        lbl_msg.setWordWrap(True)
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_msg)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("btn_dialog_action")
        btn_ok.setFixedHeight(38)
        btn_ok.setFixedWidth(100)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        def on_ok_clicked():
            self.result_value = True
            self.accept()

        btn_ok.clicked.connect(on_ok_clicked)
        btn_layout.addWidget(btn_ok, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(btn_layout)

    @staticmethod
    def show_info(parent, title, message):
        dlg = CustomMessageBox(parent, title, message, mode="info")
        dlg.exec()

    @staticmethod
    def show_critical(parent, title, message):
        dlg = CustomMessageBox(parent, title, message, mode="critical")
        dlg.exec()

    @staticmethod
    def ask_question(parent, title, message):
        dlg = CustomMessageBox(parent, title, message, mode="question")
        dlg.exec()
        return dlg.result_value


class ClassItemWidget(QWidget):
    """widget personalizat pentru randurile din lista de clase cu bifa rotundă vectoriala"""
    def __init__(self, class_data, color_icon, parent_window):
        super().__init__()
        self.class_data = class_data
        self.parent_window = parent_window

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        #buton bifa rotunda
        self.btn_check = QToolButton()
        self.btn_check.setFixedSize(22, 22)
        self.btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check.setStyleSheet("background: transparent; border: none;")
        self.btn_check.clicked.connect(self.toggle_visibility)
        self.update_icon()
        layout.addWidget(self.btn_check)

        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(18, 18)
        self.lbl_icon.setPixmap(color_icon.pixmap(18, 18))
        layout.addWidget(self.lbl_icon)

        self.lbl_name = QLabel(class_data['name'])
        self.lbl_name.setStyleSheet("color: #e0e6ed; font-weight: 500;")
        layout.addWidget(self.lbl_name, stretch=1)

        #QLineEdit pentru editare
        self.txt_edit = QLineEdit(class_data['name'])
        self.txt_edit.setObjectName("txt_class_rename")
        self.txt_edit.setFixedHeight(26)
        self.txt_edit.setVisible(False)
        self.txt_edit.returnPressed.connect(self.commit_edit)
        layout.addWidget(self.txt_edit, stretch=1)

        #buton edit
        self.btn_pencil = QToolButton()
        self.btn_pencil.setObjectName("btn_class_pencil")
        self.btn_pencil.setFixedSize(24, 24)
        self.btn_pencil.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pencil.setStyleSheet("background: transparent; border: none; padding: 0px;")
        self.btn_pencil.setIcon(self.parent_window.create_pencil_icon(size=18))
        self.btn_pencil.setIconSize(QSize(18, 18))
        self.btn_pencil.clicked.connect(self.start_edit)
        layout.addWidget(self.btn_pencil)

    def update_icon(self):
        """schimba pictograma intre cerc alb si bifa albastra"""
        icon = self.parent_window.create_checkbox_icon(checked=self.class_data['visible'], size=18)
        self.btn_check.setIcon(icon)
        self.btn_check.setIconSize(QSize(22, 22))

    def toggle_visibility(self):
        self.class_data['visible'] = not self.class_data['visible']
        self.update_icon()
        self.parent_window.canvas.on_classes_changed()

    def start_edit(self):
        self.lbl_name.hide()
        self.btn_pencil.hide()
        self.txt_edit.setText(self.class_data['name'])
        self.txt_edit.show()
        self.txt_edit.setFocus()
        self.txt_edit.selectAll()

    def commit_edit(self):
        new_name = self.txt_edit.text().strip()
        if new_name:
            self.class_data['name'] = new_name
            self.lbl_name.setText(new_name)
        else:
            self.txt_edit.setText(self.class_data['name'])

        self.txt_edit.hide()
        self.lbl_name.show()
        self.btn_pencil.show()


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
            CustomMessageBox.show_critical(self, "Error", "The image could not be loaded")

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
        """reconstruieste lista de clase folosind widget-uri izolate ClassItemWidget cu dimensiune fixa per rand"""
        self.class_list.blockSignals(True)
        self.class_list.clear()
        active_row = 0

        for row, c in enumerate(self.canvas.classes):
            item = QListWidgetItem(self.class_list)
            item.setData(Qt.ItemDataRole.UserRole, c['id'])

            #instanțiere widget rand
            row_widget = ClassItemWidget(c, self.create_color_icon(c['color']), self)

            item.setSizeHint(QSize(0, 36))
            self.class_list.addItem(item)
            self.class_list.setItemWidget(item, row_widget)

            if c['id'] == self.canvas.active_class_id:
                active_row = row
        self.class_list.setCurrentRow(active_row)
        self.class_list.blockSignals(False)
        self.update_button_states()

    def on_add_class(self):
        """adauga o clasa noua si deschide automat editarea numelui"""
        new_class = self.canvas.add_class()
        if new_class is None:
            return
        self.refresh_class_list()
        self.canvas.update_canvas_overlay()

        #pornire automata redenumire pentru clasa adaugata
        last_item = self.class_list.item(self.class_list.count() - 1)
        if last_item:
            widget = self.class_list.itemWidget(last_item)
            if isinstance(widget, ClassItemWidget):
                widget.start_edit()

    def on_class_visibility_toggled(self, class_id, visible):
        """trateaza bifarea/debifarea vizibilitatii unei clase"""
        c = self.canvas.get_class(class_id)
        if c and c['visible'] != visible:
            c['visible'] = visible
            self.canvas.on_classes_changed()

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

    def on_remove_class(self):
        """sterge clasa activa impreuna cu pixelii ei"""
        c = self.canvas.get_class(self.canvas.active_class_id)
        if c is None:
            return

        if self.canvas.class_has_pixels(c['id']):
            confirmed = CustomMessageBox.ask_question(self, "Delete class",
                f"Delete class „{c['name']}” and all its pixels from the mask?")
            if not confirmed:
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

    def create_checkbox_icon(self, checked=False, size=22):
        """genereaza pictograma rotunda vectoriala:
        cerc alb cu bordura albastru pentru checked și pentru unchecked
        bifa fiind desenata doar la checked"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        main_color = QColor("#1e40af")

        #fond alb interior identic pentru ambele stari
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(1, 1, size - 2, size - 2)

        #inel exterior albastru inchis identic pentru ambele stari
        painter.setPen(QPen(main_color, 2.6))
        painter.drawEllipse(1, 1, size - 2, size - 2)

        # bifa din centru se desenează doar la Checked
        if checked:
            pen_check = QPen(main_color, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen_check)
            path = QPainterPath()
            path.moveTo(size * 0.28, size * 0.52)
            path.lineTo(size * 0.45, size * 0.70)
            path.lineTo(size * 0.75, size * 0.32)
            painter.drawPath(path)
        painter.end()
        return QIcon(pixmap)

    def create_pencil_icon(self, color=QColor("#4da6ff"), size=18):
        """genereaza o pictograma vectoriala de creion pt butonul de edit"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QColor(color))

        # varful triunghiular al creionului stanga jos
        tip_path = QPainterPath()
        tip_path.moveTo(3, 15)
        tip_path.lineTo(3, 11)
        tip_path.lineTo(7, 15)
        tip_path.closeSubpath()
        painter.drawPath(tip_path)

        # corpul dreptunghiular
        body_path = QPainterPath()
        body_path.moveTo(4.5, 9.5)
        body_path.lineTo(11.5, 2.5)
        body_path.lineTo(15.5, 6.5)
        body_path.lineTo(8.5, 13.5)
        body_path.closeSubpath()
        painter.drawPath(body_path)

        painter.setPen(QPen(QColor("#1e222b"), 1.2))
        painter.drawLine(10, 4, 14, 8)
        painter.end()
        return QIcon(pixmap)

    def export_classic_mask(self):
        """modul Classic: salveaza masca binara Grayscale8 (255 = selectat/alb, 0 = fundal/negru)"""
        file_path, _ = QFileDialog.getSaveFileName(self,"Save Mask","",
            "Image PNG (*.png);;Image BMP (*.bmp)")

        if not file_path:
            return

        root, ext = os.path.splitext(file_path)
        if ext.lower() not in ('.png', '.bmp'):
            file_path = root + '.png'

        if self.canvas.class_binary_mask().save(file_path):
            CustomMessageBox.show_info(self, "Success", "The mask was successfully saved")
        else:
            CustomMessageBox.show_critical(self, "Error", "Error saving file")

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

        file_path, selected_filter = QFileDialog.getSaveFileName(self, "Save Mask", "",
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
            CustomMessageBox.show_info(self, "Success", f"The mask was succesfully saved")
        else:
            CustomMessageBox.show_critical(self, "Erorr", "Error saving file")

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