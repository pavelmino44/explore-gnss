from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsSimpleTextItem
from PySide6.QtCore import Qt, QPointF, Signal, QLineF
from PySide6.QtGui import QPen, QBrush, QColor, QPolygonF, QFont, QTransform
import numpy as np

class BeaconItem(QGraphicsPolygonItem):
    def __init__(self, x, y, id, parent=None):
        size = 8
        triangle = QPolygonF([
            QPointF(0, -size),
            QPointF(-size*0.866, size*0.5),
            QPointF(size*0.866, size*0.5)
        ])
        super().__init__(triangle, parent)
        self.setPos(x, y)
        self.id = id
        self.setPen(QPen(Qt.black, 1))
        self.setBrush(QBrush(QColor("orange")))
        self.setFlag(QGraphicsPolygonItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsPolygonItem.ItemIsMovable, True)
        self.setZValue(1)

    def setEnabled(self, enabled):
        if enabled:
            self.setBrush(QBrush(QColor("orange")))
            self.setPen(QPen(Qt.black, 1))
        else:
            self.setBrush(QBrush(QColor("lightgray")))
            self.setPen(QPen(Qt.gray, 1))

class ReceiverItem(QGraphicsEllipseItem):
    def __init__(self, x, y, parent=None):
        super().__init__(-6, -6, 12, 12, parent)
        self.setPos(x, y)
        self.setPen(QPen(Qt.blue, 2))
        self.setBrush(QBrush(QColor("cyan")))
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable, True)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges, True)
        self.setZValue(2)

class GNSSScene(QGraphicsScene):
    receiverMoved = Signal(float, float)
    beaconMoved = Signal(int, float, float)
    beaconSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-3000, -3000, 6000, 6000)
        self.beacon_items = []
        self.receiver_item = None
        self.estimated_item = None
        self.ellipse_item = None
        self.iteration_items = []
        self.used_beacon_lines = []
        self.axis_labels = []   # храним ссылки на подписи, чтобы удалять при очистке
        self.drawGrid()

    def drawGrid(self):
        limit = 3000
        grid_step = 100  # Шаг линий сетки
        label_step = 200  # Шаг числовых подписей

        pen = QPen(QColor(220, 220, 220), 0.5)
        for i in range(-limit, limit + 1, grid_step):
            self.addLine(i, -limit, i, limit, pen)
            self.addLine(-limit, i, limit, i, pen)

        axis_pen = QPen(Qt.black, 1)
        self.addLine(-limit, 0, limit, 0, axis_pen)
        self.addLine(0, -limit, 0, limit, axis_pen)

        # Подписи осей
        font = QFont("Arial", 8)
        for i in range(-limit, limit + 1, label_step):
            if i == 0:
                continue

            label_x = QGraphicsSimpleTextItem(str(i))
            label_x.setFont(font)
            label_x.setPos(i, -10)
            label_x.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
            self.addItem(label_x)
            self.axis_labels.append(label_x)

            label_y = QGraphicsSimpleTextItem(str(i))
            label_y.setFont(font)
            # Сдвинуто на -40, чтобы четырехзначные числа не перекрывали саму ось
            label_y.setPos(-40, i)
            label_y.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
            self.addItem(label_y)
            self.axis_labels.append(label_y)

        # Подписи X и Y
        xl = QGraphicsSimpleTextItem("X")
        xl.setFont(QFont("Arial", 12, QFont.Bold))
        xl.setPos(limit - 100, -20)
        xl.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
        self.addItem(xl)
        self.axis_labels.append(xl)

        yl = QGraphicsSimpleTextItem("Y")
        yl.setFont(QFont("Arial", 12, QFont.Bold))
        yl.setPos(-20, -(limit - 100))
        yl.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
        self.addItem(yl)
        self.axis_labels.append(yl)

    def addBeacon(self, x, y, id, enabled=True):
        item = BeaconItem(x, y, id)
        item.setEnabled(enabled)
        self.addItem(item)
        self.beacon_items.append(item)
        return item

    def removeBeacon(self, id):
        for item in self.beacon_items:
            if item.id == id:
                self.removeItem(item)
                self.beacon_items.remove(item)
                break

    def setReceiver(self, x, y):
        if self.receiver_item is None:
            self.receiver_item = ReceiverItem(x, y)
            self.addItem(self.receiver_item)
        else:
            self.receiver_item.setPos(x, y)

    def clearAllObjects(self):
        for item in self.beacon_items:
            self.removeItem(item)
        self.beacon_items.clear()
        if self.receiver_item:
            self.removeItem(self.receiver_item)
            self.receiver_item = None
        self.clearEstimation()

    def clearEstimation(self):
        if self.estimated_item:
            self.removeItem(self.estimated_item)
            self.estimated_item = None
        if self.ellipse_item:
            self.removeItem(self.ellipse_item)
            self.ellipse_item = None
        for item in self.iteration_items:
            self.removeItem(item)
        self.iteration_items.clear()
        self.clearUsedBeaconLines()

    def setEstimation(self, est_x, est_y, cov_matrix, iterations):
        if self.estimated_item is None:
            self.estimated_item = self.addEllipse(-5, -5, 10, 10, QPen(Qt.red, 2), QBrush(Qt.red))
        self.estimated_item.setPos(est_x, est_y)
        self._draw_error_ellipse(est_x, est_y, cov_matrix)
        for it in iterations:
            dot = self.addEllipse(-2, -2, 4, 4, QPen(Qt.gray), QBrush(Qt.gray))
            dot.setPos(it["x"], it["y"])
            self.iteration_items.append(dot)

    def _draw_error_ellipse(self, cx, cy, cov):
        if self.ellipse_item:
            self.removeItem(self.ellipse_item)
        eigvals, eigvecs = np.linalg.eig(cov)
        a = 3 * np.sqrt(eigvals[0])
        b = 3 * np.sqrt(eigvals[1])
        angle = np.degrees(np.arctan2(eigvecs[1, 0], eigvecs[0, 0]))
        ellipse = QGraphicsEllipseItem(-a/2, -b/2, a, b)
        ellipse.setTransformOriginPoint(0, 0)
        ellipse.setRotation(angle)
        ellipse.setPen(QPen(Qt.red, 1, Qt.DashLine))
        ellipse.setBrush(QBrush(QColor(255, 0, 0, 30)))
        ellipse.setPos(cx, cy)
        self.addItem(ellipse)
        self.ellipse_item = ellipse

    def drawUsedBeaconLines(self, beacons, receiver_x, receiver_y):
        self.clearUsedBeaconLines()
        for b in beacons:
            line = QGraphicsLineItem(QLineF(b["x"], b["y"], receiver_x, receiver_y))
            line.setPen(QPen(Qt.green, 1, Qt.DashLine))
            self.addItem(line)
            self.used_beacon_lines.append(line)

    def clearUsedBeaconLines(self):
        for line in self.used_beacon_lines:
            self.removeItem(line)
        self.used_beacon_lines.clear()

    def mousePressEvent(self, event):
        # Снимаем выделение со всех маяков, если кликнули не на маяке
        items = self.items(event.scenePos())
        beacon_hit = any(isinstance(item, BeaconItem) for item in items)
        if not beacon_hit:
            for bi in self.beacon_items:
                bi.setSelected(False)
        super().mousePressEvent(event)