import struct
import time
import unittest.mock as mock

from rouelib import storage
from rouelib.ble import (parse_csc, parse_heart_rate, parse_indoor_bike_data)


# --- parsing BLE -----------------------------------------------------------
def test_indoor_bike_data_speed_cadence_power():
    flags = 0x0044  # cadence + puissance (vitesse aussi présente car bit0 à 0)
    data = struct.pack("<H", flags)
    data += struct.pack("<H", 0)    # vitesse 0 m/s
    data += struct.pack("<H", 144)  # cadence 72.0 rpm
    data += struct.pack("<h", 250)  # 250 W
    values = parse_indoor_bike_data(data)
    assert values["cadence"] == 72.0
    assert values["power"] == 250.0


def test_indoor_bike_data_full():
    flags = 0x0000
    data = struct.pack("<H", flags)
    data += struct.pack("<H", 500)  # 5.00 m/s
    values = parse_indoor_bike_data(data)
    assert abs(values["speed_ms"] - 5.0) < 0.001
    assert "cadence" not in values
    assert "power" not in values


def test_heart_rate_formats():
    assert parse_heart_rate(bytearray([0x00, 120])) == 120
    assert parse_heart_rate(bytearray([0x01, 120, 0])) == 120


def test_csc_ignores_without_crank():
    assert parse_csc(bytearray([0x00, 1, 2])) is None
    values = parse_csc(bytearray([0x02, 10, 0, 0, 2]))
    assert values == (10, 512)


# --- stockage --------------------------------------------------------------
def test_save_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(storage, "DB_PATH", (tmp_path / "data") / "historique.db")
    storage.save_session({"ts": time.time(), "activity": "Sortie libre",
                          "route_name": "Boucle du Lac", "duration_s": 600.0,
                          "distance_m": 15000.0, "avg_power": 180,
                          "max_power": 340, "avg_hr": 145, "avg_cadence": 88,
                          "elev_gain": 120})
    sessions = storage.list_sessions()
    assert len(sessions) == 1
    row = sessions[0]
    assert row["route_name"] == "Boucle du Lac"
    assert row["distance_m"] == 15000.0
    totals = storage.totals()
    assert totals["sessions"] == 1
    assert totals["distance_m"] == 15000.0


def test_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "CONFIG_DIR", tmp_path / "conf")
    monkeypatch.setattr(storage, "CONFIG_PATH", (tmp_path / "conf") / "r.json")
    defaults = {"ftp_w": 200.0, "weight_kg": 78.0}
    storage.save_settings({**defaults, "ftp_w": 250.0})
    loaded = storage.load_settings(defaults)
    assert loaded["ftp_w"] == 250.0
    assert loaded["weight_kg"] == 78.0
