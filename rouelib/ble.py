"""Gestion Bluetooth BLE : home trainer FTMS, cardiomètre, capteur de cadence.

bleak fonctionne en asyncio ; ici la boucle tourne dans un thread dédié et
communique avec l'interface graphique via des simples callbacks.
"""

import asyncio
import threading
import struct

FTMS_SERVICE = "00001826-0000-1000-8000-00805f9b34fb"
HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
CSC_SERVICE = "00001816-0000-1000-8000-00805f9b34fb"

CHAR_INDOOR_BIKE_DATA = "00002ad2-0000-1000-8000-00805f9b34fb"
CHAR_HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"
CHAR_CSC_MEASUREMENT = "00002a5b-0000-1000-8000-00805f9b34fb"
CHAR_CONTROL_POINT = "00002ad9-0000-1000-8000-00805f9b34fb"

KIND_TRAINER = "trainer"
KIND_HR = "heart_rate"
KIND_CSC = "cadence"


def parse_indoor_bike_data(data: bytearray) -> dict:
    """Décode une notification « Indoor Bike Data » (FTMS)."""
    if len(data) < 4:
        return {}
    flags = struct.unpack_from("<H", data, 0)[0]
    offset = 2
    out = {}
    if not flags & 0x0001 and offset + 2 <= len(data):
        (speed_raw,) = struct.unpack_from("<H", data, offset)
        out["speed_ms"] = speed_raw / 100.0
        offset += 2
    if flags & 0x0002 and offset + 2 <= len(data):
        offset += 2
    if flags & 0x0004 and offset + 2 <= len(data):
        (cad_raw,) = struct.unpack_from("<H", data, offset)
        out["cadence"] = cad_raw / 2.0
        offset += 2
    if flags & 0x0008 and offset + 2 <= len(data):
        offset += 2
    if flags & 0x0010 and offset + 3 <= len(data):
        offset += 3
    if flags & 0x0020 and offset + 1 <= len(data):
        offset += 1
    if flags & 0x0040 and offset + 2 <= len(data):
        (power_raw,) = struct.unpack_from("<h", data, offset)
        out["power"] = float(power_raw) if power_raw > 0 else 0.0
        offset += 2
    return out


def parse_heart_rate(data: bytearray):
    """Heart Rate Measurement : octet 0 = flags, puis valeur (uint8 ou uint16)."""
    if len(data) < 2:
        return None
    if data[0] & 0x01:
        if len(data) < 3:
            return None
        return data[1] + (data[2] << 8)
    return data[1]


def parse_csc(data: bytearray):
    """CSC Measurement : révolutions de pédalier si le drapeau bit 1 est actif."""
    if not data or not data[0] & 0x02:
        return None
    offset = 1
    if data[0] & 0x01:
        offset += 4
    if len(data) < offset + 4:
        return None
    revs, evt = struct.unpack_from("<HH", data, offset)
    return revs, evt


def classify(names, uuids):
    uuids = getattr(uuids, "_set_value", uuids) or []
    lower = [str(u).lower() for u in uuids]
    if FTMS_SERVICE in lower:
        return KIND_TRAINER
    if HR_SERVICE in lower:
        return KIND_HR
    if CSC_SERVICE in lower:
        return KIND_CSC
    name = " ".join(names).lower()
    if any(k in name for k in ("kickr", "wahoo", "elite", "tacx", "zwift",
                               "direto", "qubo", "saros", "h3", "h2",
                               "magnus", "nil", "drivo", "kura", "flux",
                               "tuf", "悟空")):
        return KIND_TRAINER
    if any(k in name for k in ("heart", "hrm", "polar", "cardio")):
        return KIND_HR
    if "cadence" in name or "csc" in name:
        return KIND_CSC
    return None


class BLETrainer:
    """Home trainer connecté avec contrôle de la résistance (FTMS)."""

    is_simulated = False
    kind = KIND_TRAINER

    def __init__(self, address, name, on_state=None):
        self.address = address
        self.name = name or "Home trainer"
        self._on_state = on_state
        self._lock = threading.Lock()
        self._power = 0.0
        self._cadence = None
        self._heart_rate = None
        self._speed = None
        self._client = None
        self._loop = None
        self._thread = None
        self._connected = False
        self._control_ok = False
        self._last_csc = None

    # -- état consultable depuis l'interface -------------------------------
    @property
    def power(self):
        return self._power

    @property
    def cadence(self):
        return self._cadence

    @property
    def heart_rate(self):
        return self._heart_rate

    @property
    def speed_ms(self):
        return self._speed

    @property
    def connected(self):
        return self._connected

    def supports_power_target(self):
        return True

    # -- opérations asynchrones, lancées depuis le thread Qt ---------------
    def _run_async(self, coro_factory):
        self._thread = threading.Thread(target=self._thread_main, args=(coro_factory,),
                                        daemon=True)
        self._thread.start()

    def _thread_main(self, coro_factory):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(coro_factory(loop))
        finally:
            loop.close()

    def connect(self):
        self._run_async(self._connect_async)

    async def _connect_async(self, loop):
        try:
            from bleak import BleakClient
            self._client = BleakClient(self.address)
            await self._client.connect()
            if not self._client.is_connected:
                raise ConnectionError("Connexion impossible")
            await self._client.start_notify(CHAR_INDOOR_BIKE_DATA,
                                            self._on_bike_data)
            try:
                await self._client.start_notify(CHAR_HR_MEASUREMENT,
                                                self._on_hr_data)
            except Exception:
                pass
            self._connected = True
            self._notify_state("connecté")
            await self._write_control(bytes([0x00]))
            await self._write_control(bytes([0x07, 0x01]))
        except Exception as exc:
            self._notify_state(f"échec : {exc}")
            await self._cleanup()

    async def _write_control(self, payload: bytes):
        if self._client is None or not self._connected:
            return False
        char = self._find_char(CHAR_CONTROL_POINT)
        if char is None:
            return False
        try:
            await self._client.write_gatt_char(char, payload, response=True)
            return True
        except Exception:
            try:
                await self._client.write_gatt_char(char, payload, response=False)
                return True
            except Exception:
                return False

    def _find_char(self, uuid):
        if self._client is None:
            return None
        for service in self._client.services:
            for char in service.characteristics:
                if str(char.uuid).lower().startswith(uuid[:8]):
                    return char
        return None

    def _on_bike_data(self, _char, data: bytearray):
        values = parse_indoor_bike_data(data)
        with self._lock:
            if "power" in values:
                self._power = values["power"]
            if "cadence" in values:
                self._cadence = values["cadence"]
            if "speed_ms" in values:
                self._speed = values["speed_ms"]

    def _on_hr_data(self, _char, data: bytearray):
        hr = parse_heart_rate(data)
        if hr:
            self._heart_rate = float(hr)

    def set_target_power(self, watts: float):
        if watts is None:
            return
        payload = bytes([0x04]) + struct.pack("<h", max(0, min(2000, int(round(watts)))))
        self._submit(payload)

    def set_target_inclination(self, grade: float):
        value = int(round(max(-40.0, min(40.0, grade)) * 100))
        payload = bytes([0x05]) + struct.pack("<h", value)
        self._submit(payload)

    def set_resistance_level(self, level: float):
        payload = bytes([0x11, max(-127, min(127, int(round(level * 10)))) & 0xFF])
        self._submit(payload)

    def _submit(self, payload: bytes):
        if self._loop is not None and self._connected:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._write_control(payload)))

    def disconnect(self):
        if self._loop is not None and self._connected:
            fut = asyncio.run_coroutine_threadsafe(self._cleanup(), self._loop)
            try:
                fut.result(timeout=3)
            except Exception:
                pass
        self._loop = None

    async def _cleanup(self):
        self._connected = False
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._notify_state("déconnecté")

    def _notify_state(self, message: str):
        if self._on_state:
            try:
                self._on_state(self.name, message)
            except Exception:
                pass


class BLEHeartMonitor:
    """Cardiomètre ou capteur de fréquence cardiaque standard (0x180D)."""

    is_simulated = False

    def __init__(self, address, name):
        self.address = address
        self.name = name or "Cardiomètre"
        self._heart_rate = None
        self._client = None
        self._loop = None
        self._connected = False

    @property
    def heart_rate(self):
        return self._heart_rate

    @property
    def power(self):
        return 0.0

    @property
    def cadence(self):
        return None

    def connect(self):
        threading.Thread(target=self._thread_main, daemon=True).start()

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._connect_async())
        finally:
            loop.close()

    async def _connect_async(self):
        try:
            from bleak import BleakClient
            self._client = BleakClient(self.address)
            await self._client.connect()
            await self._client.start_notify(CHAR_HR_MEASUREMENT, self._on_hr)
            self._connected = True
        except Exception:
            await self._safe_disconnect()

    def _on_hr(self, _char, data: bytearray):
        hr = parse_heart_rate(data)
        if hr:
            self._heart_rate = float(hr)

    def disconnect(self):
        if self._loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._safe_disconnect(),
                                                 self._loop).result(timeout=3)
            except Exception:
                pass
        self._loop = None

    async def _safe_disconnect(self):
        self._connected = False
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass


def scan_devices(timeout: float = 6.0):
    """Renvoie [(adresse, nom, type)] ; bloquant, à appeler hors thread Qt."""
    async def _scan():
        from bleak import BleakScanner
        advs = await BleakScanner.discover(timeout=timeout, return_adv=True)
        found = []
        for address, (device, adv) in advs.items():
            kind = classify([device.name or "", adv.local_name or ""],
                            adv.service_uuids)
            if kind and (device.name or adv.local_name):
                found.append((address, device.name or adv.local_name, kind))
        return found
    return asyncio.run(_scan())
