import numpy as np
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QBrush, QColor, QPainterPath
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene


class SegmentationCanvas(QGraphicsView):
    """suprafaaa grafica interactiva pentru afisarea imaginii si segmentarea manuala a acesteia
    gestioneaza uneltele de desenare (Rectangle, Ellipse, Lines, Freehand, Bucket Fill),
    masca binară asociata, suprapunerea (overlay) rosie si istoricul pentru operatiile Undo"""

    def __init__(self, parent=None):
        super().__init__(parent)

        #scena grafica Qt in care se randeaza imaginea si overlay-ul
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # referinte catre obiectele grafice si resursele de memorie
        self.pixmap_item = None
        self.image_pixmap = None
        self.mask_image = None         # masca binarz Grayscale8 (0=fundal, 255=selectat)
        self.red_mask_overlay = None   # stratul ARGB32 rosu semitransparent suprapus
        self.image_size = (0, 0)

        # stiva de istoric pentru Undo si referinta catre fereastra principala
        self.history_stack = []
        self.main_window = None

        # starile curente ale uneltelor
        self.current_tool = 'rectangle'
        self.brush_size = 10

        # stari pentru selectia bazata pe interactiune cu mouse
        self.click_count = 0
        self.start_point = QPointF()
        self.current_point = QPointF()

        #structuri de date temporare pentru poligon, Freehand
        self.polygon_points = []
        self.freehand_path = QPainterPath()
        self.is_freehand_drawing = False

        #optimizari de randare vizuala pentru anti-aliasing si scalare neteda a imaginii incarcate
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        # configurare ancorare pentru redimensionare si urmarire continua a cursorului
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)

    def load_image(self, file_path):
        """incarca o imagine noua, creeaza masca binara initiala (neagra/goala)
        si reseteaza stiva de istoric si starile interne"""
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            return False

        self.image_pixmap = pixmap
        self.scene.clear()

        # adaugare imagine in scena grafica
        self.pixmap_item = self.scene.addPixmap(self.image_pixmap)
        self.image_size = (pixmap.width(), pixmap.height())
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

        # initializare masca binara curata (Grayscale8, fill 0 =complet neagra)
        self.mask_image = QImage(
            pixmap.width(),
            pixmap.height(),
            QImage.Format.Format_Grayscale8)
        self.mask_image.fill(0)

        # reconstruire strat rosu de acoperire (initial gol)
        self.rebuild_red_mask_overlay()

        #curatare istoric si stari temporare
        self.history_stack.clear()
        self.polygon_points.clear()
        self.click_count = 0

        # potrivire imagine in fereastra pastrand raportul de aspect
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

        # notificare fereastra principala pentru actualizarea starii butoanelor
        if self.main_window:
            self.main_window.update_button_states()
        return True

    def resizeEvent(self, event):
        """ajusteaza zoom-ul imaginii la redimensionarea ferestrei"""
        super().resizeEvent(event)

        if self.image_pixmap is not None and not self.image_pixmap.isNull():
            if self.scene.sceneRect().width() > 0 and self.scene.sceneRect().height() > 0:
                self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def save_state_to_history(self):
        """salveaza o copie profunda (deep copy) a mastii curente in stiva de Undo"""
        if self.mask_image:
            self.history_stack.append(self.mask_image.copy())
            if self.main_window:
                self.main_window.update_button_states()

    def undo_last_action(self):
        """anuleaza ultima actiune si restaureaza masca din stiva"""
        if self.history_stack:
            self.mask_image = self.history_stack.pop()
            self.rebuild_red_mask_overlay()
            self.polygon_points.clear()
            self.click_count = 0
            self.update_canvas_overlay()
            if self.main_window:
                self.main_window.update_button_states()
            return True

        if self.main_window:
            self.main_window.update_button_states()
        return False

    def mousePressEvent(self, event):
        """gestioneaza interactiunea la apasarea click-ului stanga pe canvas"""
        if not self.image_pixmap or event.button() != Qt.MouseButton.LeftButton:
            return

        #transformare coordonate din ecran/view in coordonatele scenei (pixelii imaginii)
        scene_pos = self.mapToScene(event.pos())

        #verificare daca click-ul este in interiorul limitelor imaginii
        if not (0 <= scene_pos.x() < self.image_size[0] and 0 <= scene_pos.y() < self.image_size[1]):
            return

        # instrumentul Bucket Fill (umplere regiune conectata)
        if self.current_tool == 'fill':
            self.apply_flood_fill(scene_pos)
            self.update_canvas_overlay()
            return

        # instrumentul Freehand
        if self.current_tool == 'freehand':
            self.save_state_to_history()
            self.is_freehand_drawing = True
            self.freehand_path = QPainterPath()
            self.freehand_path.moveTo(scene_pos)
            return

        # instrumentele dreptunghi si elipsa (2 click-uri)
        if self.current_tool in ['rectangle', 'ellipse']:
            if self.click_count == 0:
                self.start_point = scene_pos
                self.current_point = scene_pos
                self.click_count = 1
                self.update_canvas_overlay()

            elif self.click_count == 1:
                self.save_state_to_history()
                self.current_point = scene_pos
                self.apply_shape_to_mask(self.current_tool)
                self.click_count = 0
                self.update_canvas_overlay()

        # instrumentul (Lines)
        elif self.current_tool == 'polygon':
            if not self.polygon_points:
                self.save_state_to_history()

            # verificare daca click-ul este aproape de primul punct pentru inchiderea poligonului
            if self.polygon_points:
                first = self.polygon_points[0]
                distance = ((scene_pos.x() - first.x()) ** 2 + (scene_pos.y() - first.y()) ** 2) ** 0.5

                if distance < 12 and len(self.polygon_points) >= 3:
                    self.apply_polygon_to_mask()
                    self.polygon_points.clear()
                    self.update_canvas_overlay()
                    return

            self.polygon_points.append(scene_pos)
            self.current_point = scene_pos
            self.update_canvas_overlay()

    def mouseMoveEvent(self, event):
        """actualizeaza previzualizarea grafica in timp ce cursorul se deplaseaza"""
        if not self.image_pixmap:
            return

        scene_pos = self.mapToScene(event.pos())
        self.current_point = scene_pos

        # desenare linii temporare de ghidaj daca este activa o comanda in desfasurare
        if self.click_count == 1 or self.polygon_points or self.is_freehand_drawing:
            if self.is_freehand_drawing:
                self.freehand_path.lineTo(scene_pos)

            self.update_canvas_overlay()

    def mouseReleaseEvent(self, event):
        """finalizeaza desenarea libera la eliberarea butonului de mouse"""
        if not self.image_pixmap or event.button() != Qt.MouseButton.LeftButton:
            return

        if self.current_tool == 'freehand' and self.is_freehand_drawing:
            self.apply_freehand_to_mask()
            self.is_freehand_drawing = False
            self.update_canvas_overlay()

    def apply_shape_to_mask(self, shape_type):
        """aplica un dreptunghi sau o elipsa direct pe masca binara"""
        rect = QRectF(self.start_point, self.current_point).normalized()

        painter = QPainter(self.mask_image)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(Qt.PenStyle.NoPen)

        if shape_type == 'rectangle':
            painter.drawRect(rect)
        elif shape_type == 'ellipse':
            painter.drawEllipse(rect)

        painter.end()

        self.rebuild_red_mask_overlay()
        if self.main_window:
            self.main_window.update_button_states()

    def apply_polygon_to_mask(self):
        """aplica poligonul completat si inchis pe masca binara"""
        if len(self.polygon_points) < 3:
            return

        painter = QPainter(self.mask_image)
        painter.setBrush(QBrush(QColor(255, 255, 255)))

        pen = QPen(
            QColor(255, 255, 255),
            self.brush_size,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(self.polygon_points[0])

        for point in self.polygon_points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)
        painter.end()

        self.rebuild_red_mask_overlay()
        if self.main_window:
            self.main_window.update_button_states()

    def apply_freehand_to_mask(self):
        """aplica traseul desenat liber pe masca binara"""
        painter = QPainter(self.mask_image)

        pen = QPen(
            QColor(255, 255, 255),
            self.brush_size,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(self.freehand_path)
        painter.end()

        self.rebuild_red_mask_overlay()
        if self.main_window:
            self.main_window.update_button_states()

    def rebuild_red_mask_overlay(self):
        """genereaza un strat ARGB32 de acoperire rosu
        canalul Alpha este extras direct din masca binara (alb=vizibil/rosu, negru=transparent)"""
        if self.mask_image is None or self.mask_image.isNull():
            self.red_mask_overlay = None
            return

        mask = self.mask_image.convertToFormat(QImage.Format.Format_Grayscale8)

        red_layer = QImage(mask.width(),mask.height(),QImage.Format.Format_ARGB32)
        red_layer.fill(QColor(255, 0, 0, 255))
        red_layer.setAlphaChannel(mask)
        self.red_mask_overlay = red_layer

    def update_canvas_overlay(self):
        """randeaza peste imaginea originala masca rosie si ghidajele in timp real (linii intrerupte,noduri)"""
        if self.image_pixmap is None or self.pixmap_item is None:
            return

        #clonare imagine originala pentru a nu i altera pixelii
        overlay = self.image_pixmap.copy()
        painter = QPainter(overlay)

        # randarea stratului rosu semitransparent peste imagine
        if self.red_mask_overlay is not None:
            painter.save()
            painter.setOpacity(110.0 / 255.0)  #transparentă de aprox 43%
            painter.drawImage(0, 0, self.red_mask_overlay)
            painter.restore()

        # previzualizare dreptunghi/elipsa in timpul trasarii
        if self.click_count == 1:
            rect = QRectF(self.start_point, self.current_point).normalized()

            painter.setPen(QPen(QColor(255, 255, 255),self.brush_size,Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            if self.current_tool == 'rectangle':
                painter.drawRect(rect)
            elif self.current_tool == 'ellipse':
                painter.drawEllipse(rect)

        # previzualizare Freehand
        if self.is_freehand_drawing and self.current_tool == 'freehand':
            pen_fh = QPen(
                QColor(0, 230, 230),
                self.brush_size,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin)

            painter.setPen(pen_fh)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.freehand_path)

        # previzualizare poligon (linii punctate albe si noduri rosii)
        if self.polygon_points:
            pen_poly = QPen(
                QColor(255, 255, 255),
                self.brush_size,
                Qt.PenStyle.DashLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin)

            painter.setPen(pen_poly)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for i in range(len(self.polygon_points) - 1):
                painter.drawLine(self.polygon_points[i], self.polygon_points[i + 1])

            #linie dinamica de la ultimul punct la pozitia curenta a mouse-ului
            painter.drawLine(self.polygon_points[-1], self.current_point)

            # randarea nodurilor (punctelor) de control
            painter.setBrush(QBrush(QColor(255, 77, 77)))
            painter.setPen(QPen(QColor(255, 77, 77), 1))

            node_radius = max(4, self.brush_size //2 +2)

            for point in self.polygon_points:
                painter.drawEllipse(point, node_radius, node_radius)

        painter.end()

        # actualizare pixmap afisat in scena
        self.pixmap_item.setPixmap(overlay)

    def reset_mask(self):
        """goleste complet masca binara is reimprospateaza afisarea"""
        if self.mask_image:
            self.save_state_to_history()
            self.mask_image.fill(0)
            self.rebuild_red_mask_overlay()
            self.polygon_points.clear()
            self.click_count = 0
            self.update_canvas_overlay()
            if self.main_window:
                self.main_window.update_button_states()

    def has_mask_content(self):
        """verifica daca masca binara curenta are cel putin un pixel selectat (>0)
        foloseste constBits() si conversie in bytes nativi Python pentru protecție impotriva
        erorilor de memorie C++"""
        if self.mask_image is None or self.mask_image.isNull():
            return False

        try:
            #acces read-only securizat la buffer-ul nativ
            ptr = self.mask_image.constBits()
            if ptr is None:
                return False
            ptr.setsize(self.image_size[0] * self.image_size[1])

            # conversie sigura in obiectul 'bytes' gestionat de Python
            raw_bytes = bytes(ptr)
            return any(raw_bytes)
        except Exception:
            return False

    def apply_flood_fill(self, start_pos):
        """executa umplerea unei regiuni conectate neselectate folosind
        algoritmul optimizat Scanline Flood Fill pe un buffer NumPy"""
        x = int(start_pos.x())
        y = int(start_pos.y())

        width, height = self.image_size
        if not (0 <= x < width and 0 <= y < height):
            return

        # accesare masca prin NumPy
        ptr = self.mask_image.bits()
        ptr.setsize(height * width)
        mask = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width))

        # dacă pixelul este deja selectat se ignora actiunea
        if mask[y, x] >= 128:
            return
        self.save_state_to_history()

        #stiva ce retine segmentele orizontale:(x1, x2, y)
        stack = [(x, x, y)]

        while stack:
            x1, x2, cy = stack.pop()
            if not (0 <= cy < height):
                continue

            #extindere spre stanga
            lx = x1
            while lx > 0 and mask[cy, lx - 1] < 128:
                lx -= 1

            #extindere spre dreapta
            rx = x2
            while rx < width - 1 and mask[cy, rx + 1] < 128:
                rx += 1

            # umplerea segmentului detectat
            mask[cy, lx:rx + 1] = 255

            # verificarea liniilor adiacente (sus si jos)
            for ny in (cy - 1, cy + 1):
                if 0 <= ny < height:
                    nx = lx
                    while nx <= rx:
                        if mask[ny, nx] < 128:
                            scan_start = nx
                            while nx <= rx and mask[ny, nx] < 128:
                                nx += 1
                            stack.append((scan_start, nx - 1, ny))
                        nx += 1

        self.rebuild_red_mask_overlay()
        if self.main_window:
            self.main_window.update_button_states()