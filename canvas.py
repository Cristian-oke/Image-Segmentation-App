import numpy as np
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QBrush, QColor, QPainterPath
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene


# paleta implicita de culori atribuita pe rand claselor noi
DEFAULT_CLASS_COLORS = [
    QColor(255, 0, 0), QColor(0, 200, 0), QColor(0, 120, 255), QColor(255, 210, 0),
    QColor(255, 0, 255), QColor(0, 230, 230), QColor(255, 128, 0), QColor(150, 60, 255),
    QColor(160, 255, 60), QColor(255, 110, 170)]

# numarul maxim de clase (valorile 1..255 din masca Grayscale8, 0=fundal)
MAX_CLASSES = 255

# classic =o singura clasa (masca binara alb/negru, overlay rosu)
# multi =mai multe clase, fiecare cu culoarea ei
MODE_CLASSIC = 'classic'
MODE_MULTI = 'multi'


def image_to_array(image):
    """returneaza un view NumPy (h, w) peste buffer-ul unei imagini Grayscale8
    tine cont de padding-ul de aliniere al fiecarei linii (bytesPerLine poate fi > width)"""
    h, w = image.height(), image.width()
    bpl = image.bytesPerLine()
    ptr = image.bits()
    ptr.setsize(h * bpl)
    return np.frombuffer(ptr, dtype=np.uint8).reshape((h, bpl))[:, :w]


def array_to_image(arr, image_format):
    """creeaza o imagine QImage (copie proprie) dintr-un array NumPy"""
    arr = np.ascontiguousarray(arr)
    h,w= arr.shape[:2]
    return QImage(arr.data, w, h, arr.strides[0], image_format).copy()


class SegmentationCanvas(QGraphicsView):
    """suprafaaa grafica interactiva pentru afisarea imaginii si segmentarea manuala a acesteia
    gestioneaza uneltele de desenare (Rectangle, Ellipse, Lines, Freehand, Bucket Fill),
    masca de etichete multi-clasa, suprapunerea (overlay) colorata si istoricul pentru operatiile Undo"""

    def __init__(self, parent=None):
        super().__init__(parent)

        #scena grafica Qt in care se randeaza imaginea si overlay-ul
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # referinte catre obiectele grafice si resursele de memorie
        self.pixmap_item = None
        self.image_pixmap = None
        self.mask_image = None         # masca de etichete Grayscale8 (0=fundal, 1..255=id-ul clasei)
        self.mask_overlay = None       # stratul RGBA colorat (fiecare clasa cu culoarea ei)
        self.image_size = (0, 0)

        # stiva de istoric pentru Undo si referinta catre fereastra principala
        self.history_stack = []
        self.main_window = None

        # lista claselor
        self.classes = []
        self.active_class_id = None
        self.add_class()

        # modul curent si starea salvata (masca, istoric, clase) a modului inactiv
        self.mode = MODE_CLASSIC
        self.mode_states = {}

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
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)



    def get_class(self, class_id):
        """returneaza clasa cu id-ul dat sau None"""
        for c in self.classes:
            if c['id'] == class_id:
                return c
        return None

    def active_color(self):
        """culoarea clasei active folosita si pentru previzualizari"""
        c = self.get_class(self.active_class_id)
        return QColor(c['color']) if c else QColor(255, 255, 255)

    def _free_class_id(self):
        """cel mai mic id nefolosit de clasele curente sau de cele din istoric
        o clasa stearsa poate fi readusa prin Undo, deci id-ul ei ramane rezervat"""
        used = {c['id'] for c in self.classes}
        for _, snapshot in self.history_stack:
            used.update(c['id'] for c in snapshot)
        for class_id in range(1, MAX_CLASSES + 1):
            if class_id not in used:
                return class_id
        return None

    def can_add_class(self):
        return len(self.classes) < MAX_CLASSES and self._free_class_id() is not None

    def add_class(self, name=None, color=None):
        """adauga o clasa noua si o face activa"""
        class_id = self._free_class_id()
        if class_id is None or len(self.classes) >= MAX_CLASSES:
            return None

        if color is None:
            color = DEFAULT_CLASS_COLORS[len(self.classes) % len(DEFAULT_CLASS_COLORS)]
        if not name:
            name = f"Class {len(self.classes) + 1}"

        new_class = {'id': class_id, 'name': name, 'color': QColor(color), 'visible': True}
        self.classes.append(new_class)
        self.active_class_id = class_id
        return new_class

    def remove_class(self, class_id):
        """sterge o clasa si pixelii ei din masca"""
        c = self.get_class(class_id)
        if c is None or len(self.classes) <= 1:
            return False

        if self.mask_image is not None:
            self.save_state_to_history()
            mask = image_to_array(self.mask_image)
            mask[mask == class_id] = 0

        index = self.classes.index(c)
        self.classes.remove(c)
        if self.active_class_id == class_id:
            self.active_class_id = self.classes[min(index, len(self.classes) - 1)]['id']

        self.rebuild_mask_overlay()
        self.update_canvas_overlay()
        if self.main_window:
            self.main_window.update_button_states()
        return True

    def clear_class(self, class_id):
        """goleste din masca doar pixelii clasei date"""
        if self.mask_image is None or not self.class_has_pixels(class_id):
            return
        self.save_state_to_history()
        mask = image_to_array(self.mask_image)
        mask[mask == class_id] = 0
        self.rebuild_mask_overlay()
        self.update_canvas_overlay()
        if self.main_window:
            self.main_window.update_button_states()

    def class_has_pixels(self, class_id):
        if self.mask_image is None or self.mask_image.isNull():
            return False
        return bool(np.any(image_to_array(self.mask_image) == class_id))

    def on_classes_changed(self):
        """reimprospateaza overlay-ul dupa schimbarea culorii/vizibilitatii unei clase"""
        self.rebuild_mask_overlay()
        self.update_canvas_overlay()

    def _snapshot_classes(self):
        return [dict(c, color=QColor(c['color'])) for c in self.classes]

    def _restore_missing_classes(self, snapshot):
        """la Undo readuce clasele sterse intre timp"""
        current_ids = {c['id'] for c in self.classes}
        for index, c in enumerate(snapshot):
            if c['id'] not in current_ids:
                self.classes.insert(min(index, len(self.classes)), dict(c, color=QColor(c['color'])))

    def set_mode(self, mode):
        """comuta intre modul clasic (binar) si cel multi-clasa
        fiecare mod isi pastreaza propria masca, propriul istoric Undo si propriile clase"""
        if mode == self.mode:
            return

        # anulare comenzi in desfasurare
        self.polygon_points.clear()
        self.click_count = 0
        self.is_freehand_drawing = False

        self.mode_states[self.mode] = (self.mask_image, self.history_stack, self.classes, self.active_class_id)
        state = self.mode_states.pop(mode, None)
        self.mode = mode

        if state is not None:
            self.mask_image, self.history_stack, self.classes, self.active_class_id = state
        else:
            self.mask_image, self.history_stack, self.classes = None, [], []
            if mode == MODE_CLASSIC:
                # o singura clasa fixa: rosu pe ecran, alb (255) la export
                self.add_class("Mask", QColor(255, 0, 0))
            else:
                self.add_class()

        # masca modului este recreata daca imaginea a fost schimbata intre timp
        if self.image_pixmap is not None and self.mask_image is None:
            self.mask_image = self.new_stamp()
            self.history_stack = []

        self.rebuild_mask_overlay()
        self.update_canvas_overlay()
        if self.main_window:
            self.main_window.update_button_states()


    def dragEnterEvent(self, event):
        """drag and drop"""
        if self.main_window:
            self.main_window.dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self.main_window:
            self.main_window.dragMoveEvent(event)

    def dropEvent(self, event):
        if self.main_window:
            self.main_window.dropEvent(event)

    def load_image(self, file_path):
        """incarca o imagine noua, creeaza masca de etichete initiala (neagra/goala)
        si reseteaza stiva de istoric si starile interne (clasele definite se pastreaza)"""
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            return False

        self.image_pixmap = pixmap
        self.scene.clear()

        # adaugare imagine in scena grafica
        self.pixmap_item = self.scene.addPixmap(self.image_pixmap)
        self.image_size = (pixmap.width(), pixmap.height())
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

        # initializare masca curata (Grayscale8, fill 0=complet fundal)
        self.mask_image = QImage(
            pixmap.width(),
            pixmap.height(),
            QImage.Format.Format_Grayscale8)
        self.mask_image.fill(0)

        # reconstruire strat colorat de acoperire
        self.rebuild_mask_overlay()

        #curatare istoric si stari temporare inclusiv masca modului inactiv, recreata la comutare
        self.history_stack = []
        for mode, (_, _, classes, active_id) in self.mode_states.items():
            self.mode_states[mode] = (None, [], classes, active_id)
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
        """salveaza o copie profunda (deep copy) a mastii curente si a listei de clase in stiva de Undo"""
        if self.mask_image:
            self.history_stack.append((self.mask_image.copy(), self._snapshot_classes()))
            if self.main_window:
                self.main_window.update_button_states()

    def undo_last_action(self):
        """anuleaza ultima actiune si restaureaza masca si eventualele clase sterse din stiva"""
        if self.history_stack:
            self.mask_image, snapshot = self.history_stack.pop()
            self._restore_missing_classes(snapshot)
            self.rebuild_mask_overlay()
            self.polygon_points.clear()
            self.click_count = 0
            self.update_canvas_overlay()
            if self.main_window:
                self.main_window.refresh_class_list()
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

        # instrumentul Lines
        elif self.current_tool == 'polygon':
            # verificare daca click-ul este aproape de primul punct pentru inchiderea poligonului
            if self.polygon_points:
                first = self.polygon_points[0]
                distance = ((scene_pos.x() - first.x()) ** 2 + (scene_pos.y() - first.y()) ** 2) ** 0.5

                if distance < 12 and len(self.polygon_points) >= 3:
                    # istoricul se salveaza doar cand poligonul chiar modifica masca
                    self.save_state_to_history()
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

    def new_stamp(self):
        """creeaza un strat temporar binar (0/255) pe care QPainter rasterizeaza forma curenta"""
        stamp = QImage(self.image_size[0], self.image_size[1], QImage.Format.Format_Grayscale8)
        stamp.fill(0)
        return stamp

    def commit_stamp(self, stamp):
        """copiaza forma rasterizata pe masca cu id-ul clasei active
        pixelii altor clase aflati sub forma sunt suprascrisi"""
        if self.get_class(self.active_class_id) is not None:
            mask = image_to_array(self.mask_image)
            mask[image_to_array(stamp) >= 128] = self.active_class_id

        self.rebuild_mask_overlay()
        if self.main_window:
            self.main_window.update_button_states()

    def apply_shape_to_mask(self, shape_type):
        """aplica un dreptunghi sau o elipsa pe masca, cu clasa activa"""
        rect = QRectF(self.start_point, self.current_point).normalized()

        stamp = self.new_stamp()
        painter = QPainter(stamp)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(Qt.PenStyle.NoPen)

        if shape_type == 'rectangle':
            painter.drawRect(rect)
        elif shape_type == 'ellipse':
            painter.drawEllipse(rect)

        painter.end()
        self.commit_stamp(stamp)

    def apply_polygon_to_mask(self):
        """aplica poligonul completat si inchis pe masca, cu clasa activa"""
        if len(self.polygon_points) < 3:
            return

        stamp = self.new_stamp()
        painter = QPainter(stamp)
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
        self.commit_stamp(stamp)

    def apply_freehand_to_mask(self):
        """aplica traseul desenat liber pe masca, cu clasa activa"""
        stamp = self.new_stamp()
        painter = QPainter(stamp)

        pen = QPen(
            QColor(255, 255, 255),
            self.brush_size,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(self.freehand_path)
        painter.end()
        self.commit_stamp(stamp)

    def rebuild_mask_overlay(self):
        """genereaza stratul RGBA de acoperire printr-un tabel de culori indexat cu id-ul clasei
        fiecare clasa vizibila primeste culoarea ei fundalul si clasele ascunse raman transparente"""
        if self.mask_image is None or self.mask_image.isNull():
            self.mask_overlay = None
            return

        lut = np.zeros((256, 4), dtype=np.uint8)
        for c in self.classes:
            if c['visible']:
                lut[c['id']] = (c['color'].red(), c['color'].green(), c['color'].blue(), 255)

        rgba = lut[image_to_array(self.mask_image)]
        self.mask_overlay = array_to_image(rgba, QImage.Format.Format_RGBA8888)

    def update_canvas_overlay(self):
        """randeaza peste imaginea originala masca colorata si ghidajele in timp real (linii intrerupte,noduri)
        ghidajele folosesc culoarea clasei active"""
        if self.image_pixmap is None or self.pixmap_item is None:
            return

        #clonare imagine originala pentru a nu i altera pixelii
        overlay = self.image_pixmap.copy()
        painter = QPainter(overlay)
        color = self.active_color()

        # randarea stratului colorat semitransparent peste imagine
        if self.mask_overlay is not None:
            painter.save()
            painter.setOpacity(110.0 / 255.0)  #transparentă de aprox 43%
            painter.drawImage(0, 0, self.mask_overlay)
            painter.restore()

        # previzualizare dreptunghi/elipsa in timpul trasarii
        if self.click_count == 1:
            rect = QRectF(self.start_point, self.current_point).normalized()

            painter.setPen(QPen(color, self.brush_size, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            if self.current_tool == 'rectangle':
                painter.drawRect(rect)
            elif self.current_tool == 'ellipse':
                painter.drawEllipse(rect)

        # previzualizare Freehand
        if self.is_freehand_drawing and self.current_tool == 'freehand':
            pen_fh = QPen(
                color,
                self.brush_size,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin)

            painter.setPen(pen_fh)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.freehand_path)

        # previzualizare poligon (linii punctate si noduri in culoarea clasei active)
        if self.polygon_points:
            pen_poly = QPen(
                color,
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
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255), 1))

            node_radius = max(4, self.brush_size //2 +2)

            for point in self.polygon_points:
                painter.drawEllipse(point, node_radius, node_radius)

        painter.end()

        # actualizare pixmap afisat in scena
        self.pixmap_item.setPixmap(overlay)

    def reset_mask(self):
        """goleste complet masca (toate clasele) si reimprospateaza afisarea"""
        if self.mask_image:
            self.save_state_to_history()
            self.mask_image.fill(0)
            self.rebuild_mask_overlay()
            self.polygon_points.clear()
            self.click_count = 0
            self.update_canvas_overlay()
            if self.main_window:
                self.main_window.update_button_states()

    def has_mask_content(self):
        """verifica daca masca curenta are cel putin un pixel etichetat (>0)"""
        if self.mask_image is None or self.mask_image.isNull():
            return False
        return bool(image_to_array(self.mask_image).any())

    def colored_mask_image(self):
        """masca RGB: fundal negru, fiecare clasa cu culoarea ei (indiferent de vizibilitate)"""
        lut = np.zeros((256, 3), dtype=np.uint8)
        for c in self.classes:
            lut[c['id']] = (c['color'].red(), c['color'].green(), c['color'].blue())
        return array_to_image(lut[image_to_array(self.mask_image)], QImage.Format.Format_RGB888)

    def label_mask_image(self):
        """masca de etichete Grayscale8 cu valori consecutive 0=fundal, 1..N = clasele in ordinea
        din lista (id-urile interne pot avea goluri dupa stergeri) returneaza (imagine, legenda)"""
        lut = np.zeros(256, dtype=np.uint8)
        legend = []
        for value, c in enumerate(self.classes, start=1):
            lut[c['id']] = value
            legend.append({'value': value, 'name': c['name'], 'color': c['color'].name()})
        return array_to_image(lut[image_to_array(self.mask_image)], QImage.Format.Format_Grayscale8), legend

    def class_binary_mask(self, class_id=None):
        """masca binara clasica (0/255): alb = pixelii clasei date,negru = fundal"""
        mask = image_to_array(self.mask_image)
        selected = mask > 0 if class_id is None else mask == class_id
        binary = np.where(selected, 255, 0).astype(np.uint8)
        return array_to_image(binary, QImage.Format.Format_Grayscale8)

    def apply_flood_fill(self, start_pos):
        """umple regiunea conectata care are aceeasi eticheta ca pixelul apasat (fundal sau alta clasa)
        cu clasa activa, folosind algoritmul Scanline Flood Fill pe un buffer NumPy
        extinderea stanga/dreapta si cautarea segmentelor vecine sunt vectorizate"""
        x = int(start_pos.x())
        y = int(start_pos.y())

        width, height = self.image_size
        if not (0 <= x < width and 0 <= y < height):
            return

        fill_value = self.active_class_id
        if self.get_class(fill_value) is None:
            return

        # dacă regiunea are deja clasa activa se ignora actiunea
        target = int(image_to_array(self.mask_image)[y, x])
        if target == fill_value:
            return
        self.save_state_to_history()

        # accesare masca prin NumPy
        mask = image_to_array(self.mask_image)

        #stiva ce retine segmentele orizontale:(x1, x2, y)
        stack = [(x, x, y)]

        while stack:
            x1, x2, cy = stack.pop()
            # segmentul a fost deja umplut de pe alt traseu
            if mask[cy, x1] != target:
                continue

            row_is_target = mask[cy] == target

            #extindere spre stanga (pana la primul pixel cu alta eticheta)
            blocked = np.flatnonzero(~row_is_target[:x1])
            lx = blocked[-1] + 1 if blocked.size else 0

            #extindere spre dreapta
            blocked = np.flatnonzero(~row_is_target[x2 + 1:])
            rx = x2 + blocked[0] if blocked.size else width - 1

            # umplerea segmentului detectat
            mask[cy, lx:rx + 1] = fill_value

            # verificarea liniilor adiacente (sus si jos): fiecare secventa continua de pixeli
            # cu eticheta tinta devine un segment nou in stiva
            for ny in (cy - 1, cy + 1):
                if 0 <= ny < height:
                    seg = (mask[ny, lx:rx + 1] == target).astype(np.int8)
                    edges = np.diff(np.concatenate(([0], seg, [0])))
                    starts = np.flatnonzero(edges == 1)
                    ends = np.flatnonzero(edges == -1) - 1
                    for s, e in zip(starts, ends):
                        stack.append((lx + s, lx + e, ny))

        self.rebuild_mask_overlay()
        if self.main_window:
            self.main_window.update_button_states()
