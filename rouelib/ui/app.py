"""Fenêtre principale et pages : connexion, bibliothèque, résumé, historique."""

import shutil
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMainWindow, QMessageBox,
                             QPushButton, QStackedWidget, QTabWidget,
                             QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from .. import ble, storage
from ..routes import Route, load_builtin_routes, load_gpx
from ..trainers import SimTrainer, TrainerBase
from ..workouts import Workout, load_builtin_workouts
from .ride_screen import RidePage
from .theme import APP_QSS, format_distance, format_duration

USER_ROUTES_DIR = storage.DATA_DIR / "parcours"

KIND_LABELS = {ble.KIND_TRAINER: "Home trainer (contrôlable)",
               ble.KIND_HR: "Cardiomètre",
               ble.KIND_CSC: "Capteur cadence/vitesse"}


class CompositeTrainer:
    """Réunit le home trainer et le cardiomètre derrière une seule interface."""

    is_simulated = False

    def __init__(self, trainer, hr_monitor=None):
        self.trainer = trainer
        self.hr_monitor = hr_monitor
        self.name = trainer.name

    @property
    def power(self):
        return self.trainer.power

    @property
    def cadence(self):
        return self.trainer.cadence

    @property
    def heart_rate(self):
        if self.hr_monitor is not None:
            return self.hr_monitor.heart_rate
        return getattr(self.trainer, "heart_rate", None)

    @property
    def speed_ms(self):
        return getattr(self.trainer, "speed_ms", None)

    def set_target_power(self, watts):
        self.trainer.set_target_power(watts)

    def set_target_inclination(self, grade):
        self.trainer.set_target_inclination(grade)

    def set_resistance_level(self, level):
        self.trainer.set_resistance_level(level)

    def disconnect_all(self):
        for device in (self.trainer, self.hr_monitor):
            disconnect = getattr(device, "disconnect", None)
            if disconnect:
                disconnect()


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vos réglages")
        self.settings = dict(settings)

        form = QFormLayout(self)
        self.name_edit = QLineEdit(str(settings.get("rider", "")))
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(25.0, 200.0)
        self.weight_spin.setValue(float(settings.get("weight_kg", 78.0)))
        self.weight_spin.setSuffix(" kg")
        self.ftp_spin = QDoubleSpinBox()
        self.ftp_spin.setRange(50.0, 600.0)
        self.ftp_spin.setValue(float(settings.get("ftp_w", 200.0)))
        self.ftp_spin.setSuffix(" W")
        self.jersey_btn = QPushButton("Choisir une couleur…")
        self._set_swatch(self.jersey_btn,
                         settings.get("jersey_color", "#d95f2b"))
        self.jersey_btn.clicked.connect(
            lambda: self._pick_color("jersey_color", self.jersey_btn))
        self.bike_btn = QPushButton("Choisir une couleur…")
        self._set_swatch(self.bike_btn,
                         settings.get("bike_color", "#22262c"))
        self.bike_btn.clicked.connect(
            lambda: self._pick_color("bike_color", self.bike_btn))
        form.addRow("Prénom", self.name_edit)
        form.addRow("Votre poids", self.weight_spin)
        form.addRow("Votre FTP (puissance de référence)", self.ftp_spin)
        form.addRow("Couleur du maillot", self.jersey_btn)
        form.addRow("Couleur du vélo", self.bike_btn)
        note = QLabel("Le FTP est votre puissance de référence. Il est fourni par "
                      "la plupart des home trainers après un test, sinon prenez "
                      "la puissance que vous pouvez tenir 20 minutes.")
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _set_swatch(button, color_hex):
        button.setStyleSheet(
            f"QPushButton {{ background: {color_hex}; color: white; }}")
        button.setText(color_hex)

    def _pick_color(self, key, button):
        from PyQt6.QtGui import QColor
        current = QColor(self.settings.get(key, "#d95f2b"))
        color = QColorDialog.getColor(current, self,
                                      "Choisissez une couleur")
        if color.isValid():
            self.settings[key] = color.name()
            self._set_swatch(button, color.name())

    def accept(self):
        self.settings["rider"] = self.name_edit.text().strip() or "Cycliste"
        self.settings["weight_kg"] = self.weight_spin.value()
        self.settings["ftp_w"] = self.ftp_spin.value()
        storage.save_settings(self.settings)
        super().accept()


class ConnectPage(QWidget):
    ready = pyqtSignal(object)
    devices_found = pyqtSignal(list)
    state_changed = pyqtSignal(str, str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.devices = []

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        title = QLabel("Roue Libre")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Cyclisme virtuel sur votre home trainer — "
                          "connectez votre matériel ou essayez le mode démo.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        scan_row = QHBoxLayout()
        self.scan_btn = QPushButton("Rechercher mon matériel Bluetooth")
        self.scan_btn.setObjectName("primary")
        scan_row.addWidget(self.scan_btn)
        scan_row.addStretch(1)
        layout.addLayout(scan_row)

        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(200)
        layout.addWidget(self.device_list)

        hr_row = QHBoxLayout()
        hr_row.addWidget(QLabel("Cardiomètre à connecter aussi :"))
        self.hr_combo = QComboBox()
        self.hr_combo.addItem("Aucun")
        hr_row.addWidget(self.hr_combo, 1)
        layout.addLayout(hr_row)

        self.status_label = QLabel("Bluetooth éteint ou aucun appareil : utilisez "
                                   "le mode démo pour découvrir l'application.")
        self.status_label.setObjectName("subtitle")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.connect_btn = QPushButton("Se connecter et continuer")
        self.connect_btn.setObjectName("primary")
        self.demo_btn = QPushButton("Mode démo (sans matériel)")
        self.demo_btn.setEnabled(True)
        self.settings_btn = QPushButton("Réglages…")
        actions.addWidget(self.connect_btn)
        actions.addWidget(self.demo_btn)
        actions.addWidget(self.settings_btn)
        layout.addLayout(actions)

        self.scan_btn.clicked.connect(self.start_scan)
        self.connect_btn.clicked.connect(self.connect_selected)
        self.demo_btn.clicked.connect(self._start_demo)
        self.settings_btn.clicked.connect(self._open_settings)
        self.state_changed.connect(self._on_state)
        self.devices_found.connect(self._on_devices)

    # ------------------------------------------------------------------
    def start_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Recherche… (mettez le matériel en appairage)")
        self.status_label.setText("Recherche Bluetooth en cours, 6 secondes…")
        thread = threading.Thread(target=self._scan_blocking, daemon=True)
        thread.start()

    def _scan_blocking(self):
        try:
            devices = ble.scan_devices(timeout=6.0)
        except Exception as exc:
            devices = []
            self.state_changed.emit("scan", f"Bluetooth indisponible : {exc}")
        self.devices_found.emit(devices)

    def _on_devices(self, devices):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Relancer la recherche")
        self.devices = devices
        self.device_list.clear()
        self.hr_combo.clear()
        self.hr_combo.addItem("Aucun")
        self._hr_rows = []
        for address, name, kind in devices:
            label = f"{name} — {KIND_LABELS.get(kind, kind)}"
            QListWidgetItem(label, self.device_list)
            if kind == ble.KIND_HR:
                self.hr_combo.addItem(name, address)
        if devices:
            self.device_list.setCurrentRow(0)
            self.status_label.setText(
                f"{len(devices)} appareil(s) trouvé(s). Sélectionnez votre home "
                "trainer puis « Se connecter et continuer ».")
        else:
            self.status_label.setText(
                "Aucun home trainer détecté. Vérifiez qu'il est allumé et en mode "
                "appairage, activez le Bluetooth de l'ordinateur, puis relancez. "
                "Vous pouvez aussi essayer le mode démo.")

    def connect_selected(self):
        row = self.device_list.currentRow()
        if row < 0 or row >= len(self.devices):
            self.status_label.setText("Choisissez d'abord un appareil dans la liste.")
            return
        address, name, kind = self.devices[row]
        if kind != ble.KIND_TRAINER:
            self.status_label.setText(
                "Sélectionnez un home trainer (contrôlable). Les cardiomètres se "
                "rattachent via le menu ci-dessus.")
            return
        hr_monitor = None
        hr_address = self.hr_combo.currentData()
        if hr_address:
            for haddress, hname, hkind in self.devices:
                if haddress == hr_address and hkind == ble.KIND_HR:
                    hr_monitor = ble.BLEHeartMonitor(hr_address, hname)
                    hr_monitor.connect()
                    break
        self.status_label.setText(f"Connexion à {name}…")
        self.connect_btn.setEnabled(False)
        trainer = ble.BLETrainer(address, name,
                                 on_state=lambda n, m: self.state_changed.emit(n, m))
        trainer.connect()
        self._pending = (trainer, hr_monitor)

    def _on_state(self, _name, message):
        if message.startswith("échec"):
            self.status_label.setText("Échec de connexion Bluetooth — "
                                      "relancez la recherche et réessayez.")
            self.connect_btn.setEnabled(True)
        elif message == "connecté":
            trainer, hr_monitor = self._pending
            composite = CompositeTrainer(trainer, hr_monitor)
            self.settings["trainer_name"] = trainer.name
            storage.save_settings(self.settings)
            self.ready.emit(composite)
        else:
            self.status_label.setText(f"Bluetooth : {message}")

    def _start_demo(self):
        self.ready.emit(SimTrainer(float(self.settings.get("ftp_w", 200.0))))

    def _open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings.update(dialog.settings)


class BrowsePage(QWidget):
    start_ride = pyqtSignal(object, object)
    back_requested = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.routes = []
        self.workouts = []

        layout = QVBoxLayout(self)
        self.hello = QLabel("")
        self.hello.setObjectName("title")
        layout.addWidget(self.hello)

        self.tabs = QTabWidget()
        self.route_list = QListWidget()
        self.workout_list = QListWidget()
        self.tabs.addTab(self.route_list, "Parcours")
        self.tabs.addTab(self.workout_list, "Entraînements guidés")
        layout.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        self.import_btn = QPushButton("Importer un GPX…")
        self.start_btn = QPushButton("Commencer la séance")
        self.start_btn.setObjectName("primary")
        self.back_btn = QPushButton("Changer de matériel")
        actions.addWidget(self.import_btn)
        actions.addStretch(1)
        actions.addWidget(self.back_btn)
        actions.addWidget(self.start_btn)
        layout.addLayout(actions)

        self.import_btn.clicked.connect(self._import_gpx)
        self.start_btn.clicked.connect(self._start)
        self.back_btn.clicked.connect(self.back_requested.emit)
        self.route_list.itemDoubleClicked.connect(lambda _i: self._start())
        self.workout_list.itemDoubleClicked.connect(lambda _i: self._start())
        self.refresh()

    def refresh(self):
        self.routes = load_builtin_routes()
        self.routes.extend(self._user_routes())
        self.workouts = load_builtin_workouts()
        rider = self.settings.get("rider", "Cycliste")
        self.hello.setText(f"Bonjour {rider}, où voulez-vous rouler ?")

        self.route_list.clear()
        for route in self.routes:
            gain = route.elevation_gain()
            item = QListWidgetItem(
                f"{route.name}\n{format_distance(route.length_m)} · "
                f"+{gain:.0f} m · {route.description}")
            item.setData(Qt.ItemDataRole.UserRole, ("route", route))
            self.route_list.addItem(item)
        if self.routes:
            self.route_list.setCurrentRow(0)

        self.workout_list.clear()
        for workout in self.workouts:
            minutes = int(workout.total_duration // 60)
            item = QListWidgetItem(
                f"{workout.name}\n{minutes} min · {workout.description}")
            item.setData(Qt.ItemDataRole.UserRole, ("workout", workout))
            self.workout_list.addItem(item)
        if self.workouts:
            self.workout_list.setCurrentRow(0)

    def _user_routes(self):
        routes = []
        if USER_ROUTES_DIR.exists():
            for path in sorted(USER_ROUTES_DIR.glob("*.gpx")):
                try:
                    routes.append(load_gpx(path))
                except (ValueError, RuntimeError, OSError):
                    continue
        return routes

    def _import_gpx(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir un fichier GPX",
                                              str(Path.home()), "GPX (*.gpx)")
        if not path:
            return
        try:
            route = load_gpx(path)
        except (ValueError, RuntimeError, OSError) as exc:
            QMessageBox.warning(self, "Import GPX",
                                f"Ce fichier n'a pas pu être lu :\n{exc}")
            return
        USER_ROUTES_DIR.mkdir(parents=True, exist_ok=True)
        destination = USER_ROUTES_DIR / (route.name.replace("/", "_") + ".gpx")
        if not destination.exists():
            shutil.copyfile(path, destination)
        self.refresh()
        QMessageBox.information(
            self, "Import GPX",
            f"Parcours « {route.name} » importé ({format_distance(route.length_m)}).")

    def _start(self):
        current = self.tabs.currentWidget()
        item = current.currentItem()
        if item is None:
            return
        kind, payload = item.data(Qt.ItemDataRole.UserRole)
        if kind == "route":
            self.start_ride.emit(payload, None)
        else:
            route = self.routes[0] if self.routes else None
            if route is None:
                return
            self.start_ride.emit(route, payload)


class SummaryPage(QWidget):
    continue_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        title = QLabel("Séance terminée, bravo !")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.saved_label = QLabel("")
        self.saved_label.setObjectName("subtitle")
        self.saved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.saved_label)
        self.grid_box = QGroupBox("Résumé")
        self.grid = QGridLayout(self.grid_box)
        layout.addWidget(self.grid_box)
        button = QPushButton("Nouvelle séance")
        button.setObjectName("primary")
        button.clicked.connect(self.continue_requested.emit)
        layout.addWidget(button)
        layout.addStretch(1)
        self._rows = []

    def set_summary(self, summary: dict):
        rows = [
            ("Activité", summary.get("activity", "")),
            ("Parcours", summary.get("route_name", "")),
            ("Durée", format_duration(summary.get("duration_s", 0))),
            ("Distance", format_distance(summary.get("distance_m", 0))),
            ("Puissance moyenne", f"{summary.get('avg_power') or 0} W"),
            ("Puissance max", f"{summary.get('max_power') or 0} W"),
            ("Cardio moyenne", f"{summary.get('avg_hr')} bpm"
             if summary.get("avg_hr") else "—"),
            ("Cadence moyenne", f"{summary.get('avg_cadence')} rpm"
             if summary.get("avg_cadence") else "—"),
            ("Dénivelé positif", f"+{summary.get('elev_gain') or 0} m"),
        ]
        for text, label in self._rows:
            label.deleteLater()
        self._rows = []
        for i, (label_text, value) in enumerate(rows):
            key = QLabel(label_text)
            key.setStyleSheet("color:#8b95a7;")
            value_label = QLabel(str(value))
            value_label.setObjectName("big_value" if i == 0 else "hud_value")
            self.grid.addWidget(key, i, 0)
            self.grid.addWidget(value_label, i, 1)
            self._rows.extend([key, value_label])
        self.saved_label.setText("Séance enregistrée dans l'historique.")


class HistoryPage(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Historique des séances")
        title.setObjectName("title")
        layout.addWidget(title)
        self.totals_label = QLabel("")
        self.totals_label.setObjectName("subtitle")
        layout.addWidget(self.totals_label)
        self.table = QTableWidget()
        layout.addWidget(self.table, 1)
        back = QPushButton("Retour")
        back.clicked.connect(self.back_requested.emit)
        layout.addWidget(back)
        self.refresh()

    def refresh(self):
        sessions = storage.list_sessions()
        totals = storage.totals()
        self.totals_label.setText(
            f"{totals['sessions']} séance(s) · {format_duration(totals['duration_s'])}"
            f" cumulées · {format_distance(totals['distance_m'])} ·"
            f" +{totals['elev_gain']:.0f} m de dénivelé")
        columns = ["Date", "Activité", "Parcours", "Durée", "Distance",
                   "Puiss. moy.", "Puiss. max", "Cardio", "D+ "]
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(sessions))
        self.table.setHorizontalHeaderLabels(columns)
        import time as _time
        for r, row in enumerate(sessions):
            values = [
                _time.strftime("%d/%m/%Y %H:%M", _time.localtime(row["ts"])),
                row.get("activity") or "",
                row.get("route_name") or "",
                format_duration(row.get("duration_s") or 0),
                format_distance(row.get("distance_m") or 0),
                f"{row.get('avg_power')} W" if row.get("avg_power") else "—",
                f"{row.get('max_power')} W" if row.get("max_power") else "—",
                f"{row.get('avg_hr')} bpm" if row.get("avg_hr") else "—",
                f"+{row.get('elev_gain') or 0} m",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Roue Libre — cyclisme virtuel")
        self.settings = storage.load_settings(self._default_settings())
        self.composite = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.connect_page = ConnectPage(self.settings)
        self.browse_page = BrowsePage(self.settings)
        self.summary_page = SummaryPage()
        self.history_page = HistoryPage()
        self.ride_page = None

        for page in (self.connect_page, self.browse_page, self.summary_page,
                     self.history_page):
            self.stack.addWidget(page)

        self.connect_page.ready.connect(self._trainer_ready)
        self.browse_page.start_ride.connect(self._start_ride)
        self.browse_page.back_requested.connect(
            lambda: self.stack.setCurrentWidget(self.connect_page))
        self.summary_page.continue_requested.connect(self._back_to_browse)
        self.history_page.back_requested.connect(self._back_to_browse)
        self.history_btn = None

    def _trainer_ready(self, trainer):
        self.composite = trainer
        self.browse_page.refresh()
        self.stack.setCurrentWidget(self.browse_page)

    @staticmethod
    def _default_settings():
        return {"rider": "Cycliste", "weight_kg": 78.0, "ftp_w": 200.0,
                "bike_kg": 10.0, "trainer_name": "",
                "jersey_color": "#d95f2b", "bike_color": "#22262c"}

    def _start_ride(self, route, workout):
        ftp = float(self.settings.get("ftp_w", 200.0))
        if self.composite is not None and not self.composite.is_simulated:
            ftp = ftp
        rider = {**{"rider": "Cycliste", "weight_kg": 78.0, "bike_kg": 10.0,
                    "ftp_w": 200.0}, **self.settings}
        from ..physics import RiderSettings
        settings = RiderSettings.from_dict(rider)
        session = _RideSessionFactory().create(route, self.composite, settings,
                                               workout)
        if self.ride_page is not None:
            self.stack.removeWidget(self.ride_page)
            self.ride_page.deleteLater()
        self.ride_page = RidePage(
            session,
            jersey_color=self.settings.get("jersey_color", "#d95f2b"),
            bike_color=self.settings.get("bike_color", "#22262c"))
        self.ride_page.finished.connect(self._ride_finished)
        self.stack.addWidget(self.ride_page)
        self.stack.setCurrentWidget(self.ride_page)
        self.ride_page.setFocus()

    def _ride_finished(self, summary):
        storage.save_session(summary)
        self.summary_page.set_summary(summary)
        if self.ride_page is not None:
            self.stack.removeWidget(self.ride_page)
            self.ride_page.deleteLater()
            self.ride_page = None
        self.stack.setCurrentWidget(self.summary_page)

    def _back_to_browse(self):
        self.history_page.refresh()
        self.browse_page.refresh()
        self.stack.setCurrentWidget(self.browse_page)

    def closeEvent(self, event):
        if self.composite is not None:
            self.composite.set_target_power(0)
            self.composite.disconnect_all()
        super().closeEvent(event)


class _RideSessionFactory:
    def create(self, route, trainer, settings, workout):
        from ..session import RideSession
        return RideSession(route, trainer, settings, workout)
