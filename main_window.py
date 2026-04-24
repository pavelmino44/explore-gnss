from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QLineEdit, QCheckBox,
                               QComboBox, QGroupBox, QFormLayout,
                               QGraphicsView, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QMessageBox,
                               QFileDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtGui import QTransform
from gnss_canvas import GNSSScene
from presets_manager import list_presets, load_preset, save_preset, delete_preset
from gnss_solver import solve_gnss

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GNSS Solver")
        self.setGeometry(100, 100, 1300, 850)
        self.setWindowIcon(QIcon("icon.jpg"))
        self.beacons_data = []
        self.receiver_data = {"x": 0.0, "y": 0.0}
        self.noise_std = 5.0
        self.measurement_error = 0.0
        self.next_beacon_id = 1
        self.current_preset_name = ""

        self._init_ui()
        self._connect_signals()

        presets = list_presets()
        if presets:
            self.load_preset_by_name(presets[0])
        else:
            self._update_view_from_data()

        self.add_mode = "beacon"
        # Флаг для отслеживания, было ли перетаскивание (чтобы не создавать объект при двойном клике после перемещения)
        self._dragging = False

        self._current_zoom = 1.0          
        self._min_zoom = 0.2              
        self._max_zoom = 5.0 

        self._panning = False
        self._pan_start = None          

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Сцена с перевёрнутой осью Y
        self.scene = GNSSScene()
        # Устанавливаем поле с диапазоном от -3000 до 3000 (x, y, ширина, высота)
        self.scene.setSceneRect(-3000, -3000, 6000, 6000)

        self.view = QGraphicsView(self.scene)
        self.view.setMouseTracking(True)
        # Инвертируем ось Y, чтобы положительные Y были вверх
        self.view.setTransform(QTransform().scale(1, -1))
        # Настройки для плавного зума и скроллинга
        self.view.setDragMode(QGraphicsView.NoDrag)
        main_layout.addWidget(self.view, stretch=3)

        # Панель управления
        panel = QWidget()
        panel.setFixedWidth(400)
        panel_layout = QVBoxLayout(panel)
        main_layout.addWidget(panel)

        # Режим
        mode_group = QGroupBox("Режим")
        mode_layout = QHBoxLayout()
        self.btn_add_beacon = QPushButton("Добавить маяк")
        self.btn_add_beacon.setCheckable(True)
        self.btn_add_beacon.setChecked(True)
        self.btn_set_receiver = QPushButton("Установить приёмник")
        self.btn_set_receiver.setCheckable(True)
        mode_layout.addWidget(self.btn_add_beacon)
        mode_layout.addWidget(self.btn_set_receiver)
        mode_group.setLayout(mode_layout)
        panel_layout.addWidget(mode_group)

        # Маяки
        beacon_group = QGroupBox("Маяки")
        beacon_layout = QVBoxLayout()
        self.beacon_table = QTableWidget(0, 4)
        self.beacon_table.setHorizontalHeaderLabels(["ID", "X", "Y", "Вкл"])
        self.beacon_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.beacon_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.beacon_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.beacon_table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        beacon_layout.addWidget(self.beacon_table)
        btn_beacon_layout = QHBoxLayout()
        self.btn_delete_beacon = QPushButton("Удалить маяк")
        btn_beacon_layout.addWidget(self.btn_delete_beacon)
        btn_beacon_layout.addStretch()
        beacon_layout.addLayout(btn_beacon_layout)
        beacon_group.setLayout(beacon_layout)
        panel_layout.addWidget(beacon_group)

        # Приёмник
        rx_group = QGroupBox("Приёмник (истинное положение)")
        rx_form = QFormLayout()
        self.edit_rx_x = QLineEdit()
        self.edit_rx_y = QLineEdit()
        rx_form.addRow("X:", self.edit_rx_x)
        rx_form.addRow("Y:", self.edit_rx_y)
        self.btn_apply_rx = QPushButton("Применить")
        rx_form.addRow(self.btn_apply_rx)
        rx_group.setLayout(rx_form)
        panel_layout.addWidget(rx_group)

        # Шумы
        noise_group = QGroupBox("Параметры измерений")
        noise_form = QFormLayout()
        self.edit_noise_std = QLineEdit(str(self.noise_std))
        self.edit_meas_error = QLineEdit(str(self.measurement_error))
        noise_form.addRow("σ шума (r):", self.edit_noise_std)
        noise_form.addRow("τ (ошибка часов):", self.edit_meas_error)
        noise_group.setLayout(noise_form)
        panel_layout.addWidget(noise_group)

        # Действия
        action_layout = QHBoxLayout()
        self.btn_calculate = QPushButton("Рассчитать")
        self.btn_clear_all = QPushButton("Очистить всё")
        action_layout.addWidget(self.btn_calculate)
        action_layout.addWidget(self.btn_clear_all)
        panel_layout.addLayout(action_layout)

        # Результаты
        result_group = QGroupBox("Результат оценки")
        result_form = QFormLayout()
        self.lbl_corr = QLabel("—")
        self.lbl_res_x = QLabel("—")
        self.lbl_res_y = QLabel("—")
        self.lbl_res_err = QLabel("—")
        result_form.addRow("Статус:", self.lbl_corr)
        result_form.addRow("Оценка X:", self.lbl_res_x)
        result_form.addRow("Оценка Y:", self.lbl_res_y)
        result_form.addRow("Ошибка:", self.lbl_res_err)
        result_group.setLayout(result_form)
        panel_layout.addWidget(result_group)

        # Пресеты
        preset_group = QGroupBox("Пресеты")
        preset_layout = QVBoxLayout()
        self.combo_presets = QComboBox()
        self.combo_presets.setEditable(True)
        btn_preset_layout = QHBoxLayout()
        self.btn_save = QPushButton("Сохранить")
        self.btn_load = QPushButton("Загрузить")
        self.btn_delete_preset = QPushButton("Удалить")
        btn_preset_layout.addWidget(self.btn_save)
        btn_preset_layout.addWidget(self.btn_load)
        btn_preset_layout.addWidget(self.btn_delete_preset)
        preset_layout.addWidget(self.combo_presets)
        preset_layout.addLayout(btn_preset_layout)
        preset_group.setLayout(preset_layout)
        panel_layout.addWidget(preset_group)

        self._refresh_presets_list()

    def _connect_signals(self):
        self.btn_add_beacon.clicked.connect(lambda: self._set_mode("beacon"))
        self.btn_set_receiver.clicked.connect(lambda: self._set_mode("receiver"))
        self.btn_calculate.clicked.connect(self._calculate)
        self.btn_clear_all.clicked.connect(self._clear_all)
        self.btn_apply_rx.clicked.connect(self._apply_rx_coords)
        self.btn_delete_beacon.clicked.connect(self._delete_selected_beacon)
        self.btn_save.clicked.connect(self._save_preset)
        self.btn_load.clicked.connect(lambda: self.load_preset_by_name(self.combo_presets.currentText()))
        self.btn_delete_preset.clicked.connect(self._delete_preset)

        self.scene.receiverMoved.connect(self._on_receiver_moved)
        self.scene.beaconMoved.connect(self._on_beacon_moved)
        self.scene.beaconSelected.connect(self._on_beacon_selected)

        self.beacon_table.cellChanged.connect(self._on_table_cell_changed)
        self.beacon_table.itemSelectionChanged.connect(self._on_table_selection_changed)

        # Переопределяем события view для реализации двойного клика и зума
        self.view.mouseDoubleClickEvent = self._view_mouse_double_click_event
        self.view.mousePressEvent = self._view_mouse_press_event
        self.view.mouseReleaseEvent = self._view_mouse_release_event
        self.view.mouseMoveEvent = self._view_mouse_move_event
        self.view.wheelEvent = self._view_wheel_event  # Добавлен обработчик колеса мыши

    # ---------- Обработка мыши ----------
    def _view_wheel_event(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor

        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
        else:
            factor = zoom_out_factor

        new_zoom = self._current_zoom * factor
        if new_zoom < self._min_zoom or new_zoom > self._max_zoom:
            return   # не применяем зум, если выходим за границы

        self._current_zoom = new_zoom
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.scale(factor, factor)

    def _view_mouse_press_event(self, event):
        if event.button() == Qt.RightButton:
            self._panning = True
            self._pan_start = event.pos()
            self.view.setCursor(Qt.ClosedHandCursor)
            return
        self._dragging = False
        pos = self.view.mapToScene(event.pos())
        items = self.scene.items(pos)
        from gnss_canvas import BeaconItem, ReceiverItem
        if any(isinstance(i, (BeaconItem, ReceiverItem)) for i in items):
            # Не создаём объект, разрешаем стандартное поведение
            QGraphicsView.mousePressEvent(self.view, event)
        else:
            # На пустом месте – просто запоминаем, что кликнули, но ничего не делаем (добавление по двойному)
            QGraphicsView.mousePressEvent(self.view, event)

    def _view_mouse_move_event(self, event):
            if self._panning:
                # Вычисляем смещение курсора с момента последнего события
                delta = event.pos() - self._pan_start
                self._pan_start = event.pos()
                # Прокручиваем view на величину смещения
                self.view.horizontalScrollBar().setValue(
                    self.view.horizontalScrollBar().value() - delta.x()
            )
                self.view.verticalScrollBar().setValue(
                    self.view.verticalScrollBar().value() - delta.y()
            )
                return
        # Если двигаем мышь с зажатой кнопкой, считаем это перетаскиванием
            if event.buttons() != Qt.NoButton:
                self._dragging = True
            QGraphicsView.mouseMoveEvent(self.view, event)

    def _view_mouse_release_event(self, event):
        if self._panning:
            self._panning = False
            self.view.setCursor(Qt.ArrowCursor)   # или Qt.OpenHandCursor, если хотите намекнуть
            return
        # После отпускания маяка или приёмника обновляем координаты
        QGraphicsView.mouseReleaseEvent(self.view, event)
        # Если перетаскивали, ничего не создаём (двойной клик не сработает после drag)
        # Здесь принудительно обновим данные из позиций
        for bi in self.scene.beacon_items:
            pos = bi.pos()
            # обновим соответствующую запись в beacons_data и таблицу
            for b in self.beacons_data:
                if b["id"] == bi.id:
                    b["x"], b["y"] = pos.x(), pos.y()
                    break
        self._refresh_beacon_table()
        if self.scene.receiver_item:
            rpos = self.scene.receiver_item.pos()
            self.receiver_data["x"], self.receiver_data["y"] = rpos.x(), rpos.y()
            self.edit_rx_x.setText(f"{rpos.x():.2f}")
            self.edit_rx_y.setText(f"{rpos.y():.2f}")

    def _view_mouse_double_click_event(self, event):
        # Добавление маяка или перемещение приёмника по двойному клику
        pos = self.view.mapToScene(event.pos())
        items = self.scene.items(pos)
        from gnss_canvas import BeaconItem, ReceiverItem
        if any(isinstance(i, (BeaconItem, ReceiverItem)) for i in items):
            # Двойной клик по объекту – не добавляем новый
            QGraphicsView.mouseDoubleClickEvent(self.view, event)
            return
        # Пустое место
        if self.add_mode == "beacon":
            self._add_beacon(pos.x(), pos.y())
        elif self.add_mode == "receiver":
            self.scene.setReceiver(pos.x(), pos.y())
            self.receiver_data["x"] = pos.x()
            self.receiver_data["y"] = pos.y()
            self.edit_rx_x.setText(f"{pos.x():.2f}")
            self.edit_rx_y.setText(f"{pos.y():.2f}")

    # ---------- Остальные методы ----------
    def _set_mode(self, mode):
        self.add_mode = mode
        self.btn_add_beacon.setChecked(mode == "beacon")
        self.btn_set_receiver.setChecked(mode == "receiver")

    def _add_beacon(self, x, y):
        id = self.next_beacon_id
        self.next_beacon_id += 1
        beacon = {"x": x, "y": y, "enabled": True, "id": id}
        self.beacons_data.append(beacon)
        self.scene.addBeacon(x, y, id, True)
        self._refresh_beacon_table()
        self.beacon_table.selectRow(len(self.beacons_data)-1)

    def _delete_selected_beacon(self):
        row = self.beacon_table.currentRow()
        if row < 0:
            return
        beacon = self.beacons_data[row]
        self.scene.removeBeacon(beacon["id"])
        del self.beacons_data[row]
        # Пересчитываем next_beacon_id, чтобы не было бесконечного роста
        if self.beacons_data:
            self.next_beacon_id = max(b["id"] for b in self.beacons_data) + 1
        else:
            self.next_beacon_id = 1
        self._refresh_beacon_table()

    def _on_receiver_moved(self, x, y):
        self.receiver_data["x"] = x
        self.receiver_data["y"] = y
        self.edit_rx_x.setText(f"{x:.2f}")
        self.edit_rx_y.setText(f"{y:.2f}")
        # Снимаем выделение со всех маяков при перемещении приёмника
        for bi in self.scene.beacon_items:
            bi.setSelected(False)
        self.beacon_table.clearSelection()

    def _on_beacon_moved(self, id, x, y):
        for b in self.beacons_data:
            if b["id"] == id:
                b["x"] = x
                b["y"] = y
                self._refresh_beacon_table()
                break

    def _on_beacon_selected(self, id):
        for i, b in enumerate(self.beacons_data):
            if b["id"] == id:
                self.beacon_table.selectRow(i)
                break
        # Снимаем выделение с приёмника
        if self.scene.receiver_item:
            self.scene.receiver_item.setSelected(False)

    def _on_table_cell_changed(self, row, col):
        if row >= len(self.beacons_data):
            return
        beacon = self.beacons_data[row]
        item = self.beacon_table.item(row, col)
        if item is None:
            return
        try:
            if col == 1:  # X
                val = float(item.text())
                beacon["x"] = val
                for bi in self.scene.beacon_items:
                    if bi.id == beacon["id"]:
                        bi.setPos(val, beacon["y"])
                        break
            elif col == 2:  # Y
                val = float(item.text())
                beacon["y"] = val
                for bi in self.scene.beacon_items:
                    if bi.id == beacon["id"]:
                        bi.setPos(beacon["x"], val)
                        break
            elif col == 3:  # Вкл
                enabled = item.checkState() == Qt.Checked
                beacon["enabled"] = enabled
                for bi in self.scene.beacon_items:
                    if bi.id == beacon["id"]:
                        bi.setEnabled(enabled)
                        break
        except ValueError:
            pass

    def _on_table_selection_changed(self):
        row = self.beacon_table.currentRow()
        if row < 0 or row >= len(self.beacons_data):
            return
        beacon = self.beacons_data[row]
        for item in self.scene.beacon_items:
            item.setSelected(item.id == beacon["id"])
        if self.scene.receiver_item:
            self.scene.receiver_item.setSelected(False)

    def _apply_rx_coords(self):
        try:
            x = float(self.edit_rx_x.text())
            y = float(self.edit_rx_y.text())
        except ValueError:
            return
        self.receiver_data["x"] = x
        self.receiver_data["y"] = y
        self.scene.setReceiver(x, y)

    def _refresh_beacon_table(self):
        self.beacon_table.blockSignals(True)
        self.beacon_table.setRowCount(0)
        for b in self.beacons_data:
            row = self.beacon_table.rowCount()
            self.beacon_table.insertRow(row)
            id_item = QTableWidgetItem(str(b["id"]))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.beacon_table.setItem(row, 0, id_item)
            self.beacon_table.setItem(row, 1, QTableWidgetItem(f"{b['x']:.2f}"))
            self.beacon_table.setItem(row, 2, QTableWidgetItem(f"{b['y']:.2f}"))
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked if b["enabled"] else Qt.Unchecked)
            self.beacon_table.setItem(row, 3, chk_item)
        self.beacon_table.blockSignals(False)

    def _update_view_from_data(self):
        self.scene.clearAllObjects()
        for b in self.beacons_data:
            self.scene.addBeacon(b["x"], b["y"], b["id"], b["enabled"])
        self.scene.setReceiver(self.receiver_data["x"], self.receiver_data["y"])
        self._refresh_beacon_table()
        self.edit_rx_x.setText(f"{self.receiver_data['x']:.2f}")
        self.edit_rx_y.setText(f"{self.receiver_data['y']:.2f}")

    def _clear_all(self):
        reply = QMessageBox.question(self, "Подтверждение",
                                     "Удалить все маяки и сбросить положение приёмника?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.beacons_data.clear()
            self.receiver_data = {"x": 0.0, "y": 0.0}
            self.next_beacon_id = 1
            self.scene.clearAllObjects()
            self._refresh_beacon_table()
            self.edit_rx_x.setText("0.00")
            self.edit_rx_y.setText("0.00")

    def _calculate(self):
        try:
            noise_std = float(self.edit_noise_std.text())
            meas_error = float(self.edit_meas_error.text())
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Введите корректные числа для шума и τ")
            return
        data = {
            "beacons": [{"x": b["x"], "y": b["y"], "enabled": b["enabled"]} for b in self.beacons_data],
            "receiver": {"x": self.receiver_data["x"], "y": self.receiver_data["y"]},
            "noise_std": noise_std,
            "measurement_error": meas_error
        }
        result = solve_gnss(data)
        self._display_result(result)

    def _display_result(self, result):
        self.scene.clearEstimation()

        if result['CalculationError'] == False:
            calc_err = 'Ошибок на этапе вычислений нет'
            est = result["estimated"]
            cov = result["covariance"]
            iters = result["iterations"]
            self.scene.setEstimation(est["x"], est["y"], cov, iters)

            self.lbl_corr.setText(calc_err)
            self.lbl_res_x.setText(f"{est['x']:.3f}")
            self.lbl_res_y.setText(f"{est['y']:.3f}")
            self.lbl_res_err.setText(f"{result['error']:.3f}")
        else:
            calc_err = 'Вырожденная обратная матрица при вычислениях'
            self.lbl_corr.setText(calc_err)
            self.lbl_res_x.setText(f"0")
            self.lbl_res_y.setText(f"0")
            self.lbl_res_err.setText(f"0")


        used = result["used_beacons"]
        self.scene.drawUsedBeaconLines(used, self.receiver_data["x"], self.receiver_data["y"])

    # ---------- Пресеты ----------
    def _refresh_presets_list(self):
        self.combo_presets.blockSignals(True)
        self.combo_presets.clear()
        self.combo_presets.addItems(list_presets())
        self.combo_presets.blockSignals(False)

    def _save_preset(self):
        name = self.combo_presets.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите имя пресета")
            return
        data = {
            "beacons": self.beacons_data,
            "receiver": self.receiver_data,
            "noise_std": float(self.edit_noise_std.text()),
            "measurement_error": float(self.edit_meas_error.text())
        }
        save_preset(data, name)
        self._refresh_presets_list()
        self.combo_presets.setCurrentText(name)

    def load_preset_by_name(self, name):
        try:
            data = load_preset(name)
            self.beacons_data = data.get("beacons", [])
            self.receiver_data = data.get("receiver", {"x": 0, "y": 0})
            self.edit_noise_std.setText(str(data.get("noise_std", 5.0)))
            self.edit_meas_error.setText(str(data.get("measurement_error", 0.0)))
            if self.beacons_data:
                self.next_beacon_id = max(b.get("id", 0) for b in self.beacons_data) + 1
            else:
                self.next_beacon_id = 1
            self._update_view_from_data()
            self.current_preset_name = name
            self._refresh_presets_list()
            self.combo_presets.setCurrentText(name)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить пресет: {e}")

    def _delete_preset(self):
        name = self.combo_presets.currentText()
        if not name:
            return
        delete_preset(name)
        self._refresh_presets_list()
        if self.current_preset_name == name:
            self.current_preset_name = ""