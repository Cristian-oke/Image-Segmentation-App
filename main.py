import sys
import os
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QColor,QPixmap, QPainter, QPen, QPainterPath
from PyQt6.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QButtonGroup, QSlider, QLabel, QFileDialog, QMessageBox, QGroupBox)
from canvas import SegmentationCanvas


class MainWindow(QMainWindow):
    """gestioneaza panoul lateral de control, starile butoanelor, incarcarea/salvarea
    imaginilor si comunicarea cu canvasul"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Segmentation")
        self.resize(1150, 780)
        self.canvas = SegmentationCanvas()
        self.canvas.main_window = self
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

        # adaugarea panoului de control si a canvasului in layout ul principal
        main_layout.addWidget(control_panel)
        main_layout.addWidget(self.canvas)

        #zona centrala /empty state (cand nu este incarcata o imagine)
        self.empty_state_widget = QWidget(self.canvas.viewport())
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(12)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        #label text central
        self.lbl_no_image = QLabel("No Image Loaded")
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
            if not self.canvas.load_image(file_path):
                QMessageBox.critical(self,"Eroare","Imaginea nu s-a putut încărca")

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

    def on_export_mask(self):
        """seschide dialogul de salvare si exporta masca binara curenta"""
        file_path, _ = QFileDialog.getSaveFileName(self,"Salvează Masca Binară","",
            "Imagine PNG (*.png);;Imagine BMP (*.bmp);;Imagine JPG (*.jpg)")

        if file_path:
            success = self.canvas.mask_image.save(file_path)
            if success:
                QMessageBox.information(
                    self,
                    "Succes",
                    "Masca a fost salvată cu succes!"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Eroare",
                    "Eroare la salvarea fișierului!"
                )

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