# -*- coding: utf-8 -*-
"""Local API/data layer for the knee rehabilitation demo.

Run:
  python knee_rehab_local_app.py
  python knee_rehab_local_app.py --init-demo
  python knee_rehab_local_app.py --serve
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import json
import os
import random
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "rehab_local_data"
DB_PATH = DATA_DIR / "rehab_local.sqlite3"
KEY_PATH = DATA_DIR / "secret.key"
SEED_PATH = DATA_DIR / "demo_seed.json"
EXPORT_DIR = DATA_DIR / "exported_sessions"
RUNTIME_DIR = DATA_DIR / "runtime"

STREAM_PROFILES: dict[str, dict[str, float | int]] = {
    "smooth": {"fps": 18.0, "width": 720, "jpeg_quality": 62, "flask_poll_sleep": 0.02},
    "balanced": {"fps": 15.0, "width": 800, "jpeg_quality": 68, "flask_poll_sleep": 0.025},
    "quality": {"fps": 12.0, "width": 960, "jpeg_quality": 72, "flask_poll_sleep": 0.04},
}
DEFAULT_STREAM_PROFILE = "balanced"
DEFAULT_WEBRTC_WIDTH = 960
DEFAULT_WEBRTC_FPS = 30
DEFAULT_WEBRTC_CODEC = "vp8"
DEFAULT_STREAM_TYPE = "webrtc"

DEMO_START_DATE = date(2026, 6, 1)
DEMO_END_DATE = date(2026, 6, 28)
SIMULATED_RECORD_END_DATE = date(2026, 6, 14)
_SYSTEM_TODAY = date.today()
DEMO_TODAY = _SYSTEM_TODAY if DEMO_START_DATE <= _SYSTEM_TODAY <= DEMO_END_DATE else date(2026, 6, 11)
PASSWORD_ITERATIONS = 200_000

ACTION_ORDER = [
    "ankle_pump",
    "quadriceps_isometric",
    "hamstring_isometric",
    "supine_straight_leg_raise",
    "side_lying_hip_abduction",
    "prone_hip_extension",
    "supine_knee_flexion",
    "bed_knee_flexion",
]

REMOVED_ACTION_IDS = {
    "sandbag_knee_extension_press",
    "side_lying_hip_adduction",
    "straight_leg_knee_bend",
}


ACTION_LIBRARY: dict[str, dict[str, Any]] = {
    "ankle_pump": {
        "id": "ankle_pump",
        "name": "主动踝泵练习",
        "shortName": "踝泵运动",
        "type": "quantity",
        "mode": "quantity",
        "metric": "completed_count",
        "category": "控水肿、预防血栓",
        "default_target_count": 600,
    },
    "quadriceps_isometric": {
        "id": "quadriceps_isometric",
        "name": "股四头肌等长收缩",
        "shortName": "股四头肌收缩",
        "type": "quantity",
        "mode": "quantity",
        "metric": "completed_count",
        "category": "伸膝控制、早期力量",
        "default_target_count": 300,
    },
    "hamstring_isometric": {
        "id": "hamstring_isometric",
        "name": "腘绳肌等长收缩",
        "shortName": "腘绳肌收缩",
        "type": "quantity",
        "mode": "quantity",
        "metric": "completed_count",
        "category": "膝后方控制、稳定性",
        "default_target_count": 300,
    },
    "supine_straight_leg_raise": {
        "id": "supine_straight_leg_raise",
        "name": "仰卧位直抬腿",
        "shortName": "直腿抬高",
        "type": "quality",
        "mode": "endurance_raise",
        "category": "股四头肌力量、伸膝控制",
        "target_angle_deg": 15,
        "target_hold_s": 1.5,
        "min_valid_hold_s": 1.0,
        "target_reps": 5,
    },
    "side_lying_hip_abduction": {
        "id": "side_lying_hip_abduction",
        "name": "侧抬腿练习",
        "shortName": "侧抬腿",
        "type": "quality",
        "mode": "endurance_raise",
        "category": "髋外展力量、步态稳定",
        "target_angle_deg": 12,
        "target_hold_s": 1.5,
        "min_valid_hold_s": 1.0,
        "target_reps": 5,
    },
    "prone_hip_extension": {
        "id": "prone_hip_extension",
        "name": "后抬腿练习",
        "shortName": "后抬腿",
        "type": "quality",
        "mode": "endurance_raise",
        "category": "臀肌力量、避免腰部代偿",
        "target_angle_deg": 12,
        "target_hold_s": 1.0,
        "min_valid_hold_s": 0.8,
        "target_reps": 5,
    },
    "supine_knee_flexion": {
        "id": "supine_knee_flexion",
        "name": "仰卧屈膝",
        "shortName": "仰卧屈膝",
        "type": "quality",
        "mode": "flexion",
        "category": "膝关节屈曲活动度",
        "target_flexion_deg": 120,
        "target_hold_s": 6,
    },
    "bed_knee_flexion": {
        "id": "bed_knee_flexion",
        "name": "床上弯腿",
        "shortName": "床上弯腿",
        "type": "quality",
        "mode": "bed_flexion",
        "category": "髋膝综合屈曲控制",
        "target_flexion_deg": 120,
        "target_thigh_raise_deg": 60,
        "target_hold_s": 10,
    },
}


def q_goal(action_id: str, target_count: int) -> dict[str, Any]:
    return {
        "id": action_id,
        "target_count": target_count,
        "target": target_count,
        "label": f"目标 {target_count} 次",
    }


def raise_goal(action_id: str, target_angle: int, hold_s: float, reps: int = 5) -> dict[str, Any]:
    return {
        "id": action_id,
        "target_angle_deg": target_angle,
        "target_hold_s": hold_s,
        "target_reps": reps,
        "min_valid_hold_s": ACTION_LIBRARY[action_id]["min_valid_hold_s"],
        "target": target_angle,
        "label": f"目标抬腿 {target_angle}°，保持 {hold_s:g} 秒，完成 {reps} 次",
    }


def flexion_goal(target_flexion: int = 120, hold_s: float = 6) -> dict[str, Any]:
    return {
        "id": "supine_knee_flexion",
        "target_flexion_deg": target_flexion,
        "target_hold_s": hold_s,
        "target": target_flexion,
        "label": f"目标屈膝 {target_flexion}°，保持 {hold_s:g} 秒",
    }


def bed_flexion_goal(target_flexion: int = 120, thigh_raise: int = 60, hold_s: float = 10) -> dict[str, Any]:
    return {
        "id": "bed_knee_flexion",
        "target_flexion_deg": target_flexion,
        "target_thigh_raise_deg": thigh_raise,
        "target_hold_s": hold_s,
        "target": hold_s,
        "label": f"大腿抬高约 {thigh_raise}°，屈膝接近 {target_flexion}°，最大位保持 {hold_s:g} 秒",
    }


PRESCRIPTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "week1_basic": {
        "id": "week1_basic",
        "name": "第 1 周基础消肿与等长收缩模板",
        "description": "踝泵逐日增加，配合股四头肌和腘绳肌等长收缩。",
        "week": 1,
    },
    "week2_straight_raise": {
        "id": "week2_straight_raise",
        "name": "第 2 周直腿抬高入门模板",
        "description": "保留基础数量动作，加入仰卧位直抬腿。",
        "week": 2,
    },
    "week3_flexion_progress": {
        "id": "week3_flexion_progress",
        "name": "第 3 周屈膝活动度进阶模板",
        "description": "在直腿抬高基础上加入仰卧屈膝。",
        "week": 3,
    },
    "week4_comprehensive": {
        "id": "week4_comprehensive",
        "name": "第 4 周综合力量与活动度模板",
        "description": "加入侧抬腿、后抬腿和床上弯腿，覆盖 8 个动作。",
        "week": 4,
    },
}


DEMO_USERS = [
    {
        "username": "therapist",
        "password": "123456",
        "role": "therapist",
        "name": "王康复师",
        "therapist_id": "t001",
    },
    {
        "username": "liming",
        "password": "123456",
        "role": "patient",
        "name": "李明",
        "patient_id": "p001",
    },
    {
        "username": "zhangmin",
        "password": "123456",
        "role": "patient",
        "name": "张敏",
        "patient_id": "p002",
    },
    {
        "username": "chenhao",
        "password": "123456",
        "role": "patient",
        "name": "陈浩",
        "patient_id": "p003",
    },
]

DEMO_PATIENTS = [
    {
        "id": "p001",
        "name": "李明",
        "age": 62,
        "diagnosis": "左膝关节置换术后早期",
        "therapist_id": "t001",
        "therapist": "王康复师",
        "score_range": (75, 105),
        "seed": 11,
    },
    {
        "id": "p002",
        "name": "张敏",
        "age": 57,
        "diagnosis": "右膝半月板术后康复期",
        "therapist_id": "t001",
        "therapist": "王康复师",
        "score_range": (85, 115),
        "seed": 23,
    },
    {
        "id": "p003",
        "name": "陈浩",
        "age": 68,
        "diagnosis": "膝关节置换术后早期",
        "therapist_id": "t001",
        "therapist": "王康复师",
        "score_range": (55, 95),
        "seed": 37,
    },
]


def today_str() -> str:
    return DEMO_TODAY.isoformat()


def dt_now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    EXPORT_DIR.mkdir(exist_ok=True)
    RUNTIME_DIR.mkdir(exist_ok=True)


def connect() -> sqlite3.Connection:
    ensure_data_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def json_loads(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return default
    return json.loads(raw)


def load_or_create_key(reset: bool = False) -> bytes:
    ensure_data_dirs()
    if reset and KEY_PATH.exists():
        KEY_PATH.unlink()
    if not KEY_PATH.exists():
        KEY_PATH.write_bytes(Fernet.generate_key())
    return KEY_PATH.read_bytes()


def fernet(reset_key: bool = False) -> Fernet:
    return Fernet(load_or_create_key(reset_key))


def encrypt_json(data: Any, cipher: Fernet | None = None) -> str:
    cipher = cipher or fernet()
    return cipher.encrypt(json_dumps(data).encode("utf-8")).decode("utf-8")


def decrypt_json(raw: str | None, cipher: Fernet | None = None) -> Any:
    if not raw:
        return None
    cipher = cipher or fernet()
    return json.loads(cipher.decrypt(raw.encode("utf-8")).decode("utf-8"))


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return base64.b64encode(digest).decode("ascii"), base64.b64encode(salt).decode("ascii")


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    salt = base64.b64decode(stored_salt.encode("ascii"))
    expected_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(expected_hash, stored_hash)


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS therapists (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              encrypted_profile TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patients (
              id TEXT PRIMARY KEY,
              therapist_id TEXT,
              name TEXT NOT NULL,
              age INTEGER,
              diagnosis TEXT,
              encrypted_profile TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(therapist_id) REFERENCES therapists(id)
            );
            CREATE TABLE IF NOT EXISTS users (
              username TEXT PRIMARY KEY,
              role TEXT NOT NULL CHECK(role IN ('patient','therapist')),
              password_hash TEXT NOT NULL,
              salt TEXT NOT NULL,
              display_name TEXT NOT NULL,
              patient_id TEXT,
              therapist_id TEXT,
              encrypted_profile TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(patient_id) REFERENCES patients(id),
              FOREIGN KEY(therapist_id) REFERENCES therapists(id)
            );
            CREATE TABLE IF NOT EXISTS prescriptions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              patient_id TEXT NOT NULL,
              date TEXT NOT NULL,
              template_id TEXT NOT NULL,
              template_name TEXT NOT NULL,
              actions_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(patient_id, date),
              FOREIGN KEY(patient_id) REFERENCES patients(id)
            );
            CREATE TABLE IF NOT EXISTS training_sessions (
              id TEXT PRIMARY KEY,
              patient_id TEXT NOT NULL,
              action_id TEXT NOT NULL,
              date TEXT NOT NULL,
              source TEXT NOT NULL CHECK(source IN ('prescribed','extra')),
              started_at TEXT NOT NULL,
              ended_at TEXT NOT NULL,
              metrics_json TEXT NOT NULL,
              score REAL,
              quantity_score REAL,
              quality_score REAL,
              stability_score REAL,
              summary_text TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(patient_id) REFERENCES patients(id)
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_patient_date ON training_sessions(patient_id, date);
            CREATE TABLE IF NOT EXISTS daily_scores (
              patient_id TEXT NOT NULL,
              date TEXT NOT NULL,
              score REAL,
              qty REAL,
              quality REAL,
              stability REAL,
              prescribed_scores_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(patient_id, date),
              FOREIGN KEY(patient_id) REFERENCES patients(id)
            );
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_meta(key, value) VALUES(?, ?)",
            ("schema_version", "1"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_meta(key, value) VALUES(?, ?)",
            ("demo_today", today_str()),
        )


def reset_demo_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM daily_scores;
        DELETE FROM training_sessions;
        DELETE FROM prescriptions;
        DELETE FROM users;
        DELETE FROM patients;
        DELETE FROM therapists;
        """
    )


def date_range(start: date, end: date) -> list[date]:
    total = (end - start).days
    return [start + timedelta(days=i) for i in range(total + 1)]


def week_index(day: date) -> int:
    return ((day - DEMO_START_DATE).days // 7) + 1


def template_for_date(day: date) -> str:
    week = week_index(day)
    if week <= 1:
        return "week1_basic"
    if week == 2:
        return "week2_straight_raise"
    if week == 3:
        return "week3_flexion_progress"
    return "week4_comprehensive"


def prescription_actions_for_date(day: date) -> list[dict[str, Any]]:
    day_no = (day - DEMO_START_DATE).days + 1
    week = week_index(day)
    if week <= 1:
        ankle = int(round(600 + (day_no - 1) * (300 / 6)))
        return [
            q_goal("ankle_pump", ankle),
            q_goal("quadriceps_isometric", 300),
            q_goal("hamstring_isometric", 300),
        ]
    if week == 2:
        ankle = int(round(800 + ((day_no - 8) * (200 / 6))))
        return [
            q_goal("ankle_pump", ankle),
            q_goal("quadriceps_isometric", 400),
            q_goal("hamstring_isometric", 400),
            raise_goal("supine_straight_leg_raise", 15, 1.5),
        ]
    if week == 3:
        return [
            q_goal("ankle_pump", 1000),
            q_goal("quadriceps_isometric", 500),
            q_goal("hamstring_isometric", 500),
            raise_goal("supine_straight_leg_raise", 15, 1.5),
            flexion_goal(120, 6),
        ]
    return [
        q_goal("ankle_pump", 1000),
        q_goal("quadriceps_isometric", 500),
        q_goal("hamstring_isometric", 500),
        raise_goal("supine_straight_leg_raise", 15, 1.5),
        raise_goal("side_lying_hip_abduction", 12, 1.5),
        raise_goal("prone_hip_extension", 12, 1.0),
        flexion_goal(120, 6),
        bed_flexion_goal(120, 60, 10),
    ]


def insert_user(conn: sqlite3.Connection, user: dict[str, Any], cipher: Fernet) -> None:
    pwd_hash, salt = hash_password(user["password"])
    profile = {
        "demo_password_hint": "123456",
        "seeded": True,
        "role": user["role"],
    }
    conn.execute(
        """
        INSERT INTO users(username, role, password_hash, salt, display_name, patient_id,
                          therapist_id, encrypted_profile, created_at)
        VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            user["username"],
            user["role"],
            pwd_hash,
            salt,
            user["name"],
            user.get("patient_id"),
            user.get("therapist_id"),
            encrypt_json(profile, cipher),
            dt_now_iso(),
        ),
    )


def seed_users_and_patients(conn: sqlite3.Connection, cipher: Fernet) -> None:
    conn.execute(
        "INSERT INTO therapists(id, name, encrypted_profile, created_at) VALUES(?,?,?,?)",
        (
            "t001",
            "王康复师",
            encrypt_json({"department": "运动康复演示组", "phone": "demo-only"}, cipher),
            dt_now_iso(),
        ),
    )
    for patient in DEMO_PATIENTS:
        conn.execute(
            """
            INSERT INTO patients(id, therapist_id, name, age, diagnosis, encrypted_profile, created_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                patient["id"],
                patient["therapist_id"],
                patient["name"],
                patient["age"],
                patient["diagnosis"],
                encrypt_json(
                    {
                        "surgery_side": "left" if patient["id"] == "p001" else "right",
                        "notes": "demo patient profile",
                    },
                    cipher,
                ),
                dt_now_iso(),
            ),
        )
    for user in DEMO_USERS:
        insert_user(conn, user, cipher)


def upsert_prescription(conn: sqlite3.Connection, patient_id: str, day: str, template_id: str, actions: list[dict[str, Any]]) -> None:
    template_name = PRESCRIPTION_TEMPLATES[template_id]["name"]
    now = dt_now_iso()
    conn.execute(
        """
        INSERT INTO prescriptions(patient_id, date, template_id, template_name, actions_json, created_at, updated_at)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(patient_id, date) DO UPDATE SET
          template_id=excluded.template_id,
          template_name=excluded.template_name,
          actions_json=excluded.actions_json,
          updated_at=excluded.updated_at
        """,
        (patient_id, day, template_id, template_name, json_dumps(actions), now, now),
    )


def seed_prescriptions(conn: sqlite3.Connection) -> None:
    for patient in DEMO_PATIENTS:
        for day in date_range(DEMO_START_DATE, DEMO_END_DATE):
            upsert_prescription(
                conn,
                patient["id"],
                day.isoformat(),
                template_for_date(day),
                prescription_actions_for_date(day),
            )


def clamp(value: float, low: float = 0, high: float = 130) -> float:
    return max(low, min(high, value))


def round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


@dataclass
class ActionScore:
    score: float
    quantity_score: float | None
    quality_score: float | None
    stability_score: float | None
    summary: str
    details: dict[str, Any]


def goal_for_action(patient_id: str, day: str, action_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    own_conn = conn is None
    conn = conn or connect()
    try:
        row = conn.execute(
            "SELECT actions_json FROM prescriptions WHERE patient_id=? AND date=?",
            (patient_id, day),
        ).fetchone()
        if not row:
            return None
        for goal in json_loads(row["actions_json"], []):
            if goal["id"] == action_id:
                return goal
        return None
    finally:
        if own_conn:
            conn.close()


def score_quantity(action_id: str, goal: dict[str, Any], metrics: dict[str, Any]) -> ActionScore:
    target = float(goal.get("target_count") or ACTION_LIBRARY[action_id].get("default_target_count") or 1)
    completed = float(metrics.get("completed_count") or 0)
    score = 100 * completed / max(target, 1)
    summary = f"完成 {int(completed)} / {int(target)} 次"
    return ActionScore(
        score=score,
        quantity_score=score,
        quality_score=None,
        stability_score=metrics.get("stability_score"),
        summary=summary,
        details={"completed_count": completed, "target_count": target},
    )


def score_endurance_raise(action_id: str, goal: dict[str, Any], metrics: dict[str, Any]) -> ActionScore:
    target_angle = float(goal.get("target_angle_deg") or ACTION_LIBRARY[action_id]["target_angle_deg"])
    target_hold = float(goal.get("target_hold_s") or ACTION_LIBRARY[action_id]["target_hold_s"])
    min_valid_hold = float(goal.get("min_valid_hold_s") or ACTION_LIBRARY[action_id]["min_valid_hold_s"])
    target_reps = int(goal.get("target_reps") or ACTION_LIBRARY[action_id]["target_reps"])
    reps = metrics.get("reps") or []
    rep_scores: list[float] = []
    valid_reps = 0
    best_angle = 0.0
    best_hold = 0.0
    stabilities: list[float] = []
    scored_reps = []
    for rep in reps:
        angle = float(rep.get("max_angle_deg") or 0)
        hold = float(rep.get("hold_s") or 0)
        stability = float(rep.get("stability_score") if rep.get("stability_score") is not None else 80)
        valid = angle >= target_angle * 0.95 and hold >= min_valid_hold
        if valid:
            valid_reps += 1
        best_angle = max(best_angle, angle)
        best_hold = max(best_hold, hold)
        stabilities.append(stability)
        rep_score = (
            0.75 * clamp(100 * hold / max(target_hold, 0.1), 0, 120)
            + 0.15 * clamp(100 * angle / max(target_angle, 0.1), 0, 120)
            + 0.10 * clamp(stability, 0, 120)
        )
        rep_scores.append(rep_score)
        scored_reps.append({**rep, "valid": valid, "score": round(rep_score, 1)})
    best_five = sorted(rep_scores, reverse=True)[:target_reps]
    while len(best_five) < target_reps:
        best_five.append(0.0)
    score = sum(best_five) / max(target_reps, 1)
    stability_score = sum(stabilities) / len(stabilities) if stabilities else None
    summary = f"有效 {valid_reps}/{target_reps} 次，最大 {best_angle:.0f}°，最长保持 {best_hold:.1f} 秒"
    return ActionScore(
        score=score,
        quantity_score=None,
        quality_score=score,
        stability_score=stability_score,
        summary=summary,
        details={
            "target_angle_deg": target_angle,
            "target_hold_s": target_hold,
            "target_reps": target_reps,
            "min_valid_hold_s": min_valid_hold,
            "valid_reps": valid_reps,
            "best_angle_deg": best_angle,
            "best_hold_s": best_hold,
            "reps": scored_reps,
        },
    )


def score_supine_flexion(action_id: str, goal: dict[str, Any], metrics: dict[str, Any]) -> ActionScore:
    max_flexion = float(metrics.get("max_flexion_deg") or 0)
    hold_s = float(metrics.get("hold_s") or 0)
    stability = float(metrics.get("stability_score") if metrics.get("stability_score") is not None else 80)
    score = (
        0.80 * clamp(100 * max_flexion / 120, 0, 130)
        + 0.10 * clamp(100 * hold_s / 6, 0, 130)
        + 0.10 * clamp(stability, 0, 120)
    )
    summary = f"最大屈膝 {max_flexion:.0f}°，保持 {hold_s:.1f} 秒"
    return ActionScore(
        score=score,
        quantity_score=None,
        quality_score=score,
        stability_score=stability,
        summary=summary,
        details={
            "max_flexion_deg": max_flexion,
            "target_flexion_deg": goal.get("target_flexion_deg", 120),
            "hold_s": hold_s,
        },
    )


def score_bed_flexion(action_id: str, goal: dict[str, Any], metrics: dict[str, Any]) -> ActionScore:
    max_flexion = float(metrics.get("max_flexion_deg") or 0)
    max_thigh = float(metrics.get("max_thigh_raise_deg") or 0)
    hold_s = float(metrics.get("hold_s") or 0)
    stability = float(metrics.get("stability_score") if metrics.get("stability_score") is not None else 80)
    score = (
        0.65 * clamp(100 * max_flexion / 120, 0, 130)
        + 0.15 * clamp(100 * max_thigh / 60, 0, 130)
        + 0.10 * clamp(100 * hold_s / 10, 0, 130)
        + 0.10 * clamp(stability, 0, 120)
    )
    summary = f"大腿最大 {max_thigh:.0f}°，屈膝最大 {max_flexion:.0f}°，保持 {hold_s:.1f} 秒"
    return ActionScore(
        score=score,
        quantity_score=None,
        quality_score=score,
        stability_score=stability,
        summary=summary,
        details={
            "max_flexion_deg": max_flexion,
            "max_thigh_raise_deg": max_thigh,
            "hold_s": hold_s,
            "thigh_wave_deg": metrics.get("thigh_wave_deg"),
            "flexion_wave_deg": metrics.get("flexion_wave_deg"),
        },
    )


def score_action(action_id: str, goal: dict[str, Any] | None, metrics: dict[str, Any]) -> ActionScore:
    if action_id in REMOVED_ACTION_IDS:
        raise ValueError(f"removed action is not supported: {action_id}")
    action = ACTION_LIBRARY[action_id]
    goal = goal or copy.deepcopy(action)
    mode = action["mode"]
    if mode == "quantity":
        return score_quantity(action_id, goal, metrics)
    if mode == "endurance_raise":
        return score_endurance_raise(action_id, goal, metrics)
    if mode == "flexion":
        return score_supine_flexion(action_id, goal, metrics)
    if mode == "bed_flexion":
        return score_bed_flexion(action_id, goal, metrics)
    raise ValueError(f"unsupported action mode: {mode}")


def insert_training_session(
    conn: sqlite3.Connection,
    patient_id: str,
    action_id: str,
    day: str,
    metrics: dict[str, Any],
    source: str = "prescribed",
) -> dict[str, Any]:
    goal = goal_for_action(patient_id, day, action_id, conn)
    source = "prescribed" if goal else source
    scored = score_action(action_id, goal, metrics)
    row = {
        "id": uuid.uuid4().hex,
        "patient_id": patient_id,
        "action_id": action_id,
        "date": day,
        "source": source,
        "started_at": metrics.get("started_at") or dt_now_iso(),
        "ended_at": metrics.get("ended_at") or dt_now_iso(),
        "metrics_json": json_dumps({**metrics, "score_details": scored.details}),
        "score": scored.score,
        "quantity_score": scored.quantity_score,
        "quality_score": scored.quality_score,
        "stability_score": scored.stability_score,
        "summary_text": scored.summary,
        "created_at": dt_now_iso(),
    }
    conn.execute(
        """
        INSERT INTO training_sessions(id, patient_id, action_id, date, source, started_at, ended_at,
                                      metrics_json, score, quantity_score, quality_score,
                                      stability_score, summary_text, created_at)
        VALUES(:id,:patient_id,:action_id,:date,:source,:started_at,:ended_at,:metrics_json,
               :score,:quantity_score,:quality_score,:stability_score,:summary_text,:created_at)
        """,
        row,
    )
    return row


def get_prescription(conn: sqlite3.Connection, patient_id: str, day: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM prescriptions WHERE patient_id=? AND date=?",
        (patient_id, day),
    ).fetchone()
    if not row:
        return None
    return {
        "date": row["date"],
        "templateId": row["template_id"],
        "template": row["template_name"],
        "actions": json_loads(row["actions_json"], []),
    }


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def sessions_for_day(conn: sqlite3.Connection, patient_id: str, day: str, prescribed_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM training_sessions WHERE patient_id=? AND date=?"
    args: list[Any] = [patient_id, day]
    if prescribed_only:
        sql += " AND source='prescribed'"
    sql += " ORDER BY created_at"
    rows = rows_to_dicts(conn.execute(sql, args).fetchall())
    for row in rows:
        row["metrics"] = json_loads(row.pop("metrics_json"), {})
    return rows


def action_score_from_sessions(action_id: str, goal: dict[str, Any], sessions: list[dict[str, Any]]) -> ActionScore | None:
    action = ACTION_LIBRARY[action_id]
    if not sessions:
        return None
    if action["mode"] == "quantity":
        completed = sum(float(s["metrics"].get("completed_count") or 0) for s in sessions)
        stability_values = [s.get("stability_score") for s in sessions if s.get("stability_score") is not None]
        metrics = {"completed_count": completed}
        if stability_values:
            metrics["stability_score"] = sum(stability_values) / len(stability_values)
        return score_action(action_id, goal, metrics)
    if action["mode"] == "endurance_raise":
        reps: list[dict[str, Any]] = []
        for session in sessions:
            reps.extend(session["metrics"].get("reps") or [])
        return score_action(action_id, goal, {"reps": reps})
    scored = [score_action(action_id, goal, s["metrics"]) for s in sessions]
    return max(scored, key=lambda x: x.score)


def recalculate_daily_score(conn: sqlite3.Connection, patient_id: str, day: str) -> dict[str, Any]:
    plan = get_prescription(conn, patient_id, day)
    if not plan:
        conn.execute("DELETE FROM daily_scores WHERE patient_id=? AND date=?", (patient_id, day))
        return {"patient_id": patient_id, "date": day, "score": None}
    sessions = sessions_for_day(conn, patient_id, day, prescribed_only=True)
    scores: list[float] = []
    quantity_scores: list[float] = []
    quality_scores: list[float] = []
    stability_scores: list[float] = []
    details: list[dict[str, Any]] = []
    for goal in plan["actions"]:
        action_id = goal["id"]
        action_sessions = [s for s in sessions if s["action_id"] == action_id]
        scored = action_score_from_sessions(action_id, goal, action_sessions)
        if scored is None:
            scores.append(0.0)
            details.append({"id": action_id, "score": 0, "missing": True, "summary": "尚未训练"})
            continue
        scores.append(scored.score)
        if scored.quantity_score is not None:
            quantity_scores.append(scored.quantity_score)
        if scored.quality_score is not None:
            quality_scores.append(scored.quality_score)
        if scored.stability_score is not None:
            stability_scores.append(scored.stability_score)
        details.append(
            {
                "id": action_id,
                "score": round(scored.score, 1),
                "quantity_score": round_or_none(scored.quantity_score),
                "quality_score": round_or_none(scored.quality_score),
                "stability_score": round_or_none(scored.stability_score),
                "summary": scored.summary,
                "details": scored.details,
            }
        )
    daily = {
        "patient_id": patient_id,
        "date": day,
        "score": round(sum(scores) / len(plan["actions"]), 1) if plan["actions"] else None,
        "qty": round(sum(quantity_scores) / len(quantity_scores), 1) if quantity_scores else None,
        "quality": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else None,
        "stability": round(sum(stability_scores) / len(stability_scores), 1) if stability_scores else None,
        "prescribed_scores": details,
        "updated_at": dt_now_iso(),
    }
    conn.execute(
        """
        INSERT INTO daily_scores(patient_id, date, score, qty, quality, stability, prescribed_scores_json, updated_at)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(patient_id, date) DO UPDATE SET
          score=excluded.score,
          qty=excluded.qty,
          quality=excluded.quality,
          stability=excluded.stability,
          prescribed_scores_json=excluded.prescribed_scores_json,
          updated_at=excluded.updated_at
        """,
        (
            patient_id,
            day,
            daily["score"],
            daily["qty"],
            daily["quality"],
            daily["stability"],
            json_dumps(details),
            daily["updated_at"],
        ),
    )
    return daily


def desired_score_for(patient: dict[str, Any], day: date, rng: random.Random) -> float:
    low, high = patient["score_range"]
    span_days = max(1, (SIMULATED_RECORD_END_DATE - DEMO_START_DATE).days)
    progress = (day - DEMO_START_DATE).days / span_days
    trend = low + (high - low) * progress
    return clamp(trend + rng.uniform(-8, 8), low - 4, high + 4)


def mock_metrics_for(action_id: str, goal: dict[str, Any] | None, target_score: float, rng: random.Random) -> dict[str, Any]:
    score_ratio = max(0.2, target_score / 100)
    action = ACTION_LIBRARY[action_id]
    if action["mode"] == "quantity":
        target = goal.get("target_count") if goal else action.get("default_target_count", 300)
        return {
            "completed_count": int(round(target * score_ratio * rng.uniform(0.92, 1.08))),
            "stability_score": clamp(target_score + rng.uniform(-6, 6), 40, 115),
        }
    if action["mode"] == "endurance_raise":
        target_angle = goal.get("target_angle_deg", action["target_angle_deg"]) if goal else action["target_angle_deg"]
        target_hold = goal.get("target_hold_s", action["target_hold_s"]) if goal else action["target_hold_s"]
        reps = []
        for _ in range(goal.get("target_reps", 5) if goal else 5):
            reps.append(
                {
                    "max_angle_deg": round(target_angle * score_ratio * rng.uniform(0.90, 1.12), 1),
                    "hold_s": round(target_hold * score_ratio * rng.uniform(0.85, 1.18), 2),
                    "stability_score": round(clamp(target_score + rng.uniform(-10, 8), 45, 115), 1),
                }
            )
        return {"reps": reps}
    if action["mode"] == "flexion":
        return {
            "max_flexion_deg": round(120 * score_ratio * rng.uniform(0.92, 1.06), 1),
            "hold_s": round(6 * score_ratio * rng.uniform(0.85, 1.15), 2),
            "stability_score": round(clamp(target_score + rng.uniform(-8, 8), 45, 115), 1),
        }
    if action["mode"] == "bed_flexion":
        return {
            "max_flexion_deg": round(120 * score_ratio * rng.uniform(0.9, 1.05), 1),
            "max_thigh_raise_deg": round(60 * score_ratio * rng.uniform(0.9, 1.1), 1),
            "hold_s": round(10 * score_ratio * rng.uniform(0.82, 1.12), 2),
            "thigh_wave_deg": round(max(1, 8 / score_ratio) * rng.uniform(0.7, 1.3), 1),
            "flexion_wave_deg": round(max(1, 10 / score_ratio) * rng.uniform(0.7, 1.3), 1),
            "stability_score": round(clamp(target_score + rng.uniform(-8, 8), 45, 115), 1),
        }
    return {}


def seed_training_records(conn: sqlite3.Connection) -> None:
    for patient in DEMO_PATIENTS:
        rng = random.Random(patient["seed"])
        for day in date_range(DEMO_START_DATE, SIMULATED_RECORD_END_DATE):
            day_key = day.isoformat()
            plan = get_prescription(conn, patient["id"], day_key)
            if not plan:
                continue
            desired = desired_score_for(patient, day, rng)
            for goal in plan["actions"]:
                action_score_target = clamp(desired + rng.uniform(-10, 10), 40, 125)
                metrics = mock_metrics_for(goal["id"], goal, action_score_target, rng)
                insert_training_session(conn, patient["id"], goal["id"], day_key, metrics, "prescribed")
            if day.day in (5, 10, 14):
                extra_id = "side_lying_hip_abduction" if day.day != 14 else "bed_knee_flexion"
                extra_goal = copy.deepcopy(ACTION_LIBRARY[extra_id])
                metrics = mock_metrics_for(extra_id, extra_goal, clamp(desired - 5, 40, 120), rng)
                insert_training_session(conn, patient["id"], extra_id, day_key, metrics, "extra")
            recalculate_daily_score(conn, patient["id"], day_key)


def seed_demo(reseed: bool = False, reset_key: bool = False) -> None:
    ensure_data_dirs()
    if reseed and DB_PATH.exists():
        DB_PATH.unlink()
    if reset_key and KEY_PATH.exists():
        KEY_PATH.unlink()
    cipher = fernet(reset_key)
    init_db()
    with connect() as conn:
        existing = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        if existing and not reseed:
            return
        if existing:
            reset_demo_tables(conn)
        seed_users_and_patients(conn, cipher)
        seed_prescriptions(conn)
        seed_training_records(conn)
        conn.execute("INSERT OR REPLACE INTO app_meta(key, value) VALUES(?, ?)", ("seeded_at", dt_now_iso()))
    SEED_PATH.write_text(
        json_dumps(
            {
                "seeded_at": dt_now_iso(),
                "demo_start_date": DEMO_START_DATE.isoformat(),
                "demo_today": DEMO_TODAY.isoformat(),
                "default_password_note": "演示账号默认密码为 123456；SQLite users 表仅保存 PBKDF2-HMAC-SHA256 哈希和盐。",
                "accounts": [
                    {"username": u["username"], "role": u["role"], "name": u["name"]}
                    for u in DEMO_USERS
                ],
                "patients": [
                    {k: p[k] for k in ("id", "name", "age", "diagnosis", "therapist")}
                    for p in DEMO_PATIENTS
                ],
                "templates": list(PRESCRIPTION_TEMPLATES.keys()),
            }
        ),
        encoding="utf-8",
    )


def public_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "username": row["username"],
        "role": row["role"],
        "name": row["display_name"],
        "patientId": row["patient_id"],
        "therapistId": row["therapist_id"],
        "avatar": "🧑‍🦱" if row["role"] == "patient" else "👩‍⚕️",
    }


def legacy_goal(goal: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(goal)
    if "target" not in out:
        out["target"] = out.get("target_count") or out.get("target_angle_deg") or out.get("target_flexion_deg")
    if "label" not in out:
        out["label"] = str(out["target"])
    return out


def legacy_result(action_id: str, scored: dict[str, Any] | None, counted: bool = True, session: dict[str, Any] | None = None) -> dict[str, Any]:
    if scored:
        score = scored.get("score", 0)
        actual = scored.get("summary", "已记录")
        note = "已按本动作关注指标计入当天总分" if counted else "额外训练记录，不计入当天总分"
    else:
        score = session.get("score", 0) if session else 0
        actual = session.get("summary_text", "已记录") if session else "已记录"
        note = "额外训练记录，不计入当天总分"
    return {
        "id": action_id,
        "percent": int(round(score or 0)),
        "actual": actual,
        "note": note,
        "counted": counted,
    }


def daily_score_row(conn: sqlite3.Connection, patient_id: str, day: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM daily_scores WHERE patient_id=? AND date=?",
        (patient_id, day),
    ).fetchone()
    if not row:
        return None
    return {
        "date": row["date"],
        "score": row["score"],
        "qty": row["qty"],
        "quality": row["quality"],
        "stability": row["stability"],
        "prescribed_scores": json_loads(row["prescribed_scores_json"], []),
    }


def legacy_patient_state(conn: sqlite3.Connection, patient_row: sqlite3.Row) -> dict[str, Any]:
    patient = {
        "id": patient_row["id"],
        "name": patient_row["name"],
        "avatar": "🧑‍🦱",
        "age": patient_row["age"],
        "diagnosis": patient_row["diagnosis"],
        "therapist": "王康复师",
        "prescriptions": {},
        "records": {},
        "extraRecords": {},
    }
    plans = conn.execute(
        "SELECT * FROM prescriptions WHERE patient_id=? ORDER BY date",
        (patient_row["id"],),
    ).fetchall()
    for plan in plans:
        patient["prescriptions"][plan["date"]] = {
            "date": plan["date"],
            "template": plan["template_name"],
            "actions": [legacy_goal(g) for g in json_loads(plan["actions_json"], [])],
        }
    score_rows = conn.execute(
        "SELECT * FROM daily_scores WHERE patient_id=? ORDER BY date",
        (patient_row["id"],),
    ).fetchall()
    for row in score_rows:
        scored = json_loads(row["prescribed_scores_json"], [])
        patient["records"][row["date"]] = {
            "date": row["date"],
            "score": int(round(row["score"])) if row["score"] is not None else None,
            "qty": int(round(row["qty"])) if row["qty"] is not None else 0,
            "quality": int(round(row["quality"])) if row["quality"] is not None else 0,
            "stability": int(round(row["stability"])) if row["stability"] is not None else 0,
            "results": [legacy_result(item["id"], item, True) for item in scored],
        }
    extras = conn.execute(
        "SELECT * FROM training_sessions WHERE patient_id=? AND source='extra' ORDER BY date, created_at",
        (patient_row["id"],),
    ).fetchall()
    for row in extras:
        day = row["date"]
        patient["extraRecords"].setdefault(day, [])
        patient["extraRecords"][day].append(
            legacy_result(row["action_id"], None, False, dict(row))
        )
    return patient


def build_demo_state() -> dict[str, Any]:
    with connect() as conn:
        user_rows = conn.execute("SELECT * FROM users ORDER BY role DESC, username").fetchall()
        patient_rows = conn.execute("SELECT * FROM patients ORDER BY id").fetchall()
        users = {}
        for row in user_rows:
            item = public_user(row)
            users[row["username"]] = {**item, "password": None}
        patients = {row["id"]: legacy_patient_state(conn, row) for row in patient_rows}
    return {
        "demoStartDate": DEMO_START_DATE.isoformat(),
        "demoToday": DEMO_TODAY.isoformat(),
        "defaultPatientId": "p001",
        "actions": {k: ACTION_LIBRARY[k] for k in ACTION_ORDER},
        "prescriptionTemplates": PRESCRIPTION_TEMPLATES,
        "users": users,
        "patients": patients,
    }


def patient_today(patient_id: str) -> dict[str, Any]:
    with connect() as conn:
        patient = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
        if not patient:
            raise KeyError(patient_id)
        day = DEMO_TODAY.isoformat()
        return {
            "patient": dict(patient),
            "date": day,
            "plan": get_prescription(conn, patient_id, day),
            "score": daily_score_row(conn, patient_id, day),
            "sessions": sessions_for_day(conn, patient_id, day),
        }


def patient_calendar(patient_id: str, year: int, month: int) -> dict[str, Any]:
    first = date(year, month, 1)
    next_month = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    last = next_month - timedelta(days=1)
    days = []
    with connect() as conn:
        for day in date_range(first, last):
            day_key = day.isoformat()
            days.append(
                {
                    "date": day_key,
                    "plan": get_prescription(conn, patient_id, day_key),
                    "score": daily_score_row(conn, patient_id, day_key),
                }
            )
    return {"patientId": patient_id, "year": year, "month": month, "days": days}


def patient_daily_detail(patient_id: str, day: str) -> dict[str, Any]:
    with connect() as conn:
        return {
            "patientId": patient_id,
            "date": day,
            "plan": get_prescription(conn, patient_id, day),
            "score": daily_score_row(conn, patient_id, day),
            "sessions": sessions_for_day(conn, patient_id, day),
        }


def register_user(username: str, password: str, role: str) -> dict[str, Any]:
    if role not in {"patient", "therapist"}:
        raise ValueError("role must be patient or therapist")
    cipher = fernet()
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
        if exists:
            raise ValueError("username exists")
        now = dt_now_iso()
        patient_id = None
        therapist_id = None
        if role == "patient":
            count = conn.execute("SELECT COUNT(*) AS n FROM patients").fetchone()["n"] + 1
            patient_id = f"p{count:03d}"
            conn.execute(
                "INSERT INTO patients(id, therapist_id, name, age, diagnosis, encrypted_profile, created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    patient_id,
                    "t001",
                    username,
                    None,
                    "新注册患者",
                    encrypt_json({"registered_from": "local_demo"}, cipher),
                    now,
                ),
            )
            for day in date_range(DEMO_TODAY, DEMO_END_DATE):
                upsert_prescription(conn, patient_id, day.isoformat(), "week2_straight_raise", prescription_actions_for_date(day))
        else:
            therapist_id = f"t{secrets.randbelow(900) + 100}"
            conn.execute(
                "INSERT INTO therapists(id, name, encrypted_profile, created_at) VALUES(?,?,?,?)",
                (therapist_id, username, encrypt_json({"registered_from": "local_demo"}, cipher), now),
            )
        pwd_hash, salt = hash_password(password)
        conn.execute(
            """
            INSERT INTO users(username, role, password_hash, salt, display_name, patient_id,
                              therapist_id, encrypted_profile, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                username,
                role,
                pwd_hash,
                salt,
                username,
                patient_id,
                therapist_id,
                encrypt_json({"registered": True}, cipher),
                now,
            ),
        )
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return public_user(row)


def apply_template(patient_id: str, template_id: str, start_date: str, days: int) -> dict[str, Any]:
    if template_id not in PRESCRIPTION_TEMPLATES:
        raise ValueError(f"unknown template: {template_id}")
    start = date.fromisoformat(start_date)
    with connect() as conn:
        affected = []
        for idx in range(days):
            day = start + timedelta(days=idx)
            actions = actions_for_template(template_id, day)
            upsert_prescription(conn, patient_id, day.isoformat(), template_id, actions)
            recalculate_daily_score(conn, patient_id, day.isoformat())
            affected.append(day.isoformat())
    return {"patientId": patient_id, "templateId": template_id, "startDate": start_date, "days": affected}


def actions_for_template(template_id: str, day: date | None = None) -> list[dict[str, Any]]:
    day = day or DEMO_TODAY
    day_no = max(1, (day - DEMO_START_DATE).days + 1)
    if template_id == "week1_basic":
        ankle = int(round(600 + min(6, max(0, day_no - 1)) * (300 / 6)))
        return [q_goal("ankle_pump", ankle), q_goal("quadriceps_isometric", 300), q_goal("hamstring_isometric", 300)]
    if template_id == "week2_straight_raise":
        return [
            q_goal("ankle_pump", 800),
            q_goal("quadriceps_isometric", 400),
            q_goal("hamstring_isometric", 400),
            raise_goal("supine_straight_leg_raise", 15, 1.5),
        ]
    if template_id == "week3_flexion_progress":
        return [
            q_goal("ankle_pump", 1000),
            q_goal("quadriceps_isometric", 500),
            q_goal("hamstring_isometric", 500),
            raise_goal("supine_straight_leg_raise", 15, 1.5),
            flexion_goal(120, 6),
        ]
    if template_id == "week4_comprehensive":
        return prescription_actions_for_date(date(2026, 6, 22))
    raise ValueError(template_id)


def unfinished_actions(conn: sqlite3.Connection, patient_id: str, day: str) -> list[dict[str, Any]]:
    plan = get_prescription(conn, patient_id, day)
    if not plan:
        return []
    pending = []
    for goal in plan["actions"]:
        progress = compute_action_progress(conn, patient_id, day, goal["id"], goal)
        if not progress.get("completed"):
            pending.append(goal)
    return pending


def compute_action_progress(
    conn: sqlite3.Connection,
    patient_id: str,
    day: str,
    action_id: str,
    goal: dict[str, Any] | None,
) -> dict[str, Any]:
    action = ACTION_LIBRARY[action_id]
    sessions = sessions_for_day(conn, patient_id, day, prescribed_only=True)
    action_sessions = [s for s in sessions if s["action_id"] == action_id]
    mode = action["mode"]
    if mode == "quantity":
        target = int(goal.get("target_count") if goal else action.get("default_target_count", 1))
        completed = int(round(sum(float(s["metrics"].get("completed_count") or 0) for s in action_sessions)))
        return {
            "score_type": "quantity",
            "completed_count": completed,
            "target_count": target,
            "remaining_count": max(target - completed, 0),
            "completed": completed >= target,
            "allow_over_target": True,
        }
    if mode == "endurance_raise":
        target_reps = int((goal or {}).get("target_reps") or action.get("target_reps", 5))
        valid_reps = 0
        best_scores: list[float] = []
        best_angle = 0.0
        best_hold = 0.0
        for session in action_sessions:
            scored = score_action(action_id, goal, session["metrics"])
            details = scored.details
            valid_reps += int(details.get("valid_reps") or 0)
            best_angle = max(best_angle, float(details.get("best_angle_deg") or 0))
            best_hold = max(best_hold, float(details.get("best_hold_s") or 0))
            for rep in details.get("reps") or []:
                best_scores.append(float(rep.get("score") or 0))
        best_scores = sorted(best_scores, reverse=True)[:target_reps]
        return {
            "score_type": "endurance_raise",
            "valid_reps": valid_reps,
            "target_reps": target_reps,
            "remaining_reps": max(target_reps - valid_reps, 0),
            "best_five_scores": best_scores,
            "best_angle_deg": round(best_angle, 1),
            "best_hold_s": round(best_hold, 1),
            "completed": valid_reps >= target_reps,
        }
    if mode == "flexion":
        target = float((goal or {}).get("target_flexion_deg") or action.get("target_flexion_deg", 120))
        best = 0.0
        best_hold = 0.0
        for session in action_sessions:
            metrics = session["metrics"]
            best = max(best, float(metrics.get("max_flexion_deg") or 0))
            best_hold = max(best_hold, float(metrics.get("hold_s") or 0))
        completed = best >= target * 0.95
        return {
            "score_type": "flexion",
            "target_units": 1,
            "best_flexion_deg": round(best, 1),
            "target_flexion_deg": target,
            "best_hold_s": round(best_hold, 1),
            "remaining_units": 0 if completed else 1,
            "completed": completed,
        }
    if mode == "bed_flexion":
        best_flexion = 0.0
        best_thigh = 0.0
        best_hold = 0.0
        for session in action_sessions:
            metrics = session["metrics"]
            best_flexion = max(best_flexion, float(metrics.get("max_flexion_deg") or 0))
            best_thigh = max(best_thigh, float(metrics.get("max_thigh_raise_deg") or 0))
            best_hold = max(best_hold, float(metrics.get("hold_s") or 0))
        completed = best_flexion >= 114 and best_hold >= 8
        return {
            "score_type": "bed_flexion",
            "target_units": 1,
            "best_flexion_deg": round(best_flexion, 1),
            "best_thigh_raise_deg": round(best_thigh, 1),
            "best_hold_s": round(best_hold, 1),
            "remaining_units": 0 if completed else 1,
            "completed": completed,
        }
    return {"score_type": mode, "completed": False}


def action_run_target_units(action_id: str, goal: dict[str, Any] | None, progress: dict[str, Any], mode: str) -> int:
    action_mode = ACTION_LIBRARY[action_id]["mode"]
    if action_mode == "quantity":
        remaining = int(progress.get("remaining_count") or 0)
        target = int((goal or {}).get("target_count") or ACTION_LIBRARY[action_id].get("default_target_count", 1))
        return max(1, remaining if mode == "one_click" else max(remaining, min(target, 10)))
    if action_mode == "endurance_raise":
        remaining = int(progress.get("remaining_reps") or 0)
        target = int((goal or {}).get("target_reps") or ACTION_LIBRARY[action_id].get("target_reps", 5))
        return max(1, remaining if mode == "one_click" else target)
    return 1


def build_training_action_config(
    conn: sqlite3.Connection,
    patient_id: str,
    day: str,
    action_id: str,
    goal: dict[str, Any] | None,
    mode: str,
) -> dict[str, Any]:
    action = ACTION_LIBRARY[action_id]
    progress = compute_action_progress(conn, patient_id, day, action_id, goal)
    source = "prescribed" if goal else "extra"
    run_target_units = action_run_target_units(action_id, goal, progress, mode)
    display: dict[str, Any] = {"score_type": progress["score_type"]}
    if action["mode"] == "quantity":
        display.update(
            {
                "base_completed": int(progress.get("completed_count") or 0),
                "total_target": int(progress.get("target_count") or (goal or {}).get("target_count") or 1),
                "allow_over_target": True,
            }
        )
    elif action["mode"] == "endurance_raise":
        display.update(
            {
                "base_valid_reps": int(progress.get("valid_reps") or 0),
                "target_reps": int(progress.get("target_reps") or (goal or {}).get("target_reps") or 5),
                "best_angle_deg": progress.get("best_angle_deg"),
                "best_hold_s": progress.get("best_hold_s"),
            }
        )
    elif action["mode"] == "flexion":
        display.update(
            {
                "best_flexion_deg": progress.get("best_flexion_deg"),
                "target_flexion_deg": progress.get("target_flexion_deg") or (goal or {}).get("target_flexion_deg") or 120,
            }
        )
    elif action["mode"] == "bed_flexion":
        display.update(
            {
                "best_flexion_deg": progress.get("best_flexion_deg"),
                "best_thigh_raise_deg": progress.get("best_thigh_raise_deg"),
                "target_flexion_deg": (goal or {}).get("target_flexion_deg") or 120,
                "target_thigh_raise_deg": (goal or {}).get("target_thigh_raise_deg") or 60,
            }
        )
    return {
        "id": action_id,
        "name": action["name"],
        "source": source,
        "score_type": progress["score_type"],
        "goal": goal or copy.deepcopy(action),
        "progress": progress,
        "run_target_units": run_target_units,
        "display": display,
    }


def build_training_session_config(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    patient_id: str,
    day: str,
    mode: str,
    action_id: str | None,
) -> dict[str, Any]:
    plan = get_prescription(conn, patient_id, day)
    goals = {goal["id"]: goal for goal in (plan or {}).get("actions", [])}
    action_configs: list[dict[str, Any]] = []
    if mode == "one_click":
        for goal in (plan or {}).get("actions", []):
            progress = compute_action_progress(conn, patient_id, day, goal["id"], goal)
            if not progress.get("completed"):
                action_configs.append(
                    build_training_action_config(conn, patient_id, day, goal["id"], goal, mode)
                )
    else:
        if not action_id:
            raise ValueError("single mode requires action_id")
        action_configs.append(
            build_training_action_config(conn, patient_id, day, action_id, goals.get(action_id), mode)
        )
    return {
        "session_id": session_id,
        "patient_id": patient_id,
        "date": day,
        "mode": mode,
        "source_policy": "prescribed_or_extra",
        "created_at": dt_now_iso(),
        "actions": action_configs,
    }


def stream_session_dir(session_id: str) -> Path:
    safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in {"_", "-"})
    if not safe_id:
        raise ValueError("invalid session id")
    path = RUNTIME_DIR / "training_stream" / safe_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_stream_profile(profile: str | None) -> str:
    if profile in STREAM_PROFILES:
        return profile
    return DEFAULT_STREAM_PROFILE


def stream_profile_settings(profile: str | None) -> dict[str, float | int]:
    return STREAM_PROFILES[normalize_stream_profile(profile)]


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def default_training_status(session_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = normalize_stream_profile((config or {}).get("stream_profile"))
    settings = stream_profile_settings(profile)
    stream_type = (config or {}).get("stream_type") or DEFAULT_STREAM_TYPE
    return {
        "session_id": session_id,
        "created_at": dt_now_iso(),
        "patient_id": (config or {}).get("patient_id"),
        "date": (config or {}).get("date"),
        "mode": (config or {}).get("mode"),
        "frame_seq": 0,
        "last_frame_at": None,
        "fps": 0,
        "encode_ms": None,
        "write_ms": None,
        "jpeg_size_kb": None,
        "dropped_frames": 0,
        "publisher_queue_lag_ms": None,
        "stream_profile": profile,
        "web_stream_width": settings["width"],
        "web_jpeg_quality": settings["jpeg_quality"],
        "streamType": stream_type,
        "webrtcReady": False,
        "webrtcPort": (config or {}).get("webrtc_port"),
        "webrtcClients": 0,
        "webrtcWidth": (config or {}).get("webrtc_width") or DEFAULT_WEBRTC_WIDTH,
        "webrtcFpsTarget": (config or {}).get("webrtc_fps") or DEFAULT_WEBRTC_FPS,
        "webrtcConnectionState": None,
        "webrtcIceConnectionState": None,
        "webrtcIceGatheringState": None,
        "webrtcSignalingState": None,
        "webrtcOfferReceivedAt": None,
        "webrtcOfferForwardStartedAt": None,
        "webrtcAnswerSentAt": None,
        "webrtcAnswerForwardedAt": None,
        "webrtcLastError": None,
        "hasFrame": False,
        "processedFps": 0,
        "webrtcTrackFps": 0,
        "command": None,
        "paused": False,
        "stale": True,
        "exited": False,
        "completed": False,
        "failed": False,
        "returncode": None,
        "message": "训练进程准备启动。",
        "error": None,
        "active_action": None,
        "logTail": "",
    }


def write_status_file(session_dir: Path, status: dict[str, Any]) -> None:
    status["updated_at"] = dt_now_iso()
    tmp = session_dir / "status.tmp"
    tmp.write_text(json_dumps(status), encoding="utf-8")
    tmp.replace(session_dir / "status.json")


def tail_text(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[-limit:] if path.exists() else ""
    except OSError:
        return ""


def read_status_file(session_id: str) -> dict[str, Any]:
    session_dir = stream_session_dir(session_id)
    status_path = session_dir / "status.json"
    status = json_loads(status_path.read_text(encoding="utf-8"), {}) if status_path.exists() else default_training_status(session_id)
    profile = normalize_stream_profile(status.get("stream_profile"))
    settings = stream_profile_settings(profile)
    status.setdefault("stream_profile", profile)
    status.setdefault("web_stream_width", settings["width"])
    status.setdefault("web_jpeg_quality", settings["jpeg_quality"])
    status.setdefault("encode_ms", None)
    status.setdefault("write_ms", None)
    status.setdefault("jpeg_size_kb", None)
    status.setdefault("dropped_frames", 0)
    status.setdefault("publisher_queue_lag_ms", None)
    status.setdefault("streamType", DEFAULT_STREAM_TYPE)
    status.setdefault("webrtcReady", False)
    status.setdefault("webrtcClients", 0)
    status.setdefault("webrtcWidth", DEFAULT_WEBRTC_WIDTH)
    status.setdefault("webrtcFpsTarget", DEFAULT_WEBRTC_FPS)
    status.setdefault("webrtcConnectionState", None)
    status.setdefault("webrtcIceConnectionState", None)
    status.setdefault("webrtcIceGatheringState", None)
    status.setdefault("webrtcSignalingState", None)
    status.setdefault("webrtcOfferReceivedAt", None)
    status.setdefault("webrtcOfferForwardStartedAt", None)
    status.setdefault("webrtcAnswerSentAt", None)
    status.setdefault("webrtcAnswerForwardedAt", None)
    status.setdefault("webrtcLastError", None)
    status.setdefault("hasFrame", False)
    status.setdefault("processedFps", 0)
    status.setdefault("webrtcTrackFps", 0)
    status.setdefault("command", None)
    latest = session_dir / "latest.jpg"
    now = time.time()
    if status.get("streamType") == "webrtc":
        last_frame_at = status.get("last_frame_at")
        age = None
        if last_frame_at:
            try:
                age = max(0.0, (datetime.now() - datetime.fromisoformat(str(last_frame_at))).total_seconds())
            except ValueError:
                age = status.get("latestFrameAgeSeconds")
        status["latestFrameAgeSeconds"] = round(float(age), 2) if age is not None else None
        status["stale"] = bool(status.get("paused")) is False and (age is None or float(age) > 2.0)
    else:
        try:
            latest_mtime = latest.stat().st_mtime if latest.exists() else None
        except OSError:
            latest_mtime = None
        status["latestFrameAgeSeconds"] = round(now - latest_mtime, 2) if latest_mtime else None
        status["stale"] = bool(status.get("paused")) is False and (latest_mtime is None or now - latest_mtime > 2.0)
    stderr_path = session_dir / "stderr.log"
    stdout_path = session_dir / "stdout.log"
    stdout_tail = tail_text(stdout_path)
    stderr_tail = tail_text(stderr_path)
    status["stdoutTail"] = stdout_tail
    status["stderrTail"] = stderr_tail
    if stderr_tail:
        status["logTail"] = stderr_tail[-2000:]
    return status


def normalize_real_result_metrics(action_id: str, result: dict[str, Any], config_action: dict[str, Any]) -> dict[str, Any]:
    metrics = result.get("metrics") or {}
    action_mode = ACTION_LIBRARY[action_id]["mode"]
    if action_mode == "quantity":
        completed = metrics.get("完成次数", result.get("completed_units", 0))
        return {"completed_count": int(round(float(completed or 0)))}
    if action_mode == "endurance_raise":
        target_angle = float((config_action.get("goal") or {}).get("target_angle_deg") or ACTION_LIBRARY[action_id].get("target_angle_deg", 12))
        hold = float(metrics.get("最长连续达标保持_s") or metrics.get("达标保持总时长_s") or 0)
        angle = float(metrics.get("最大抬腿角度_deg") or target_angle)
        completed = int(result.get("completed_units") or metrics.get("完成回合数") or 1)
        reps = [
            {
                "hold_s": round(hold, 2),
                "max_angle_deg": round(angle, 1),
                "stability_score": 85,
            }
            for _ in range(max(1, completed))
        ]
        return {"reps": reps}
    if action_mode == "flexion":
        return {
            "max_flexion_deg": float(metrics.get("最大屈膝角度_deg") or 0),
            "hold_s": float(metrics.get("保持目标时长_s") or (config_action.get("goal") or {}).get("target_hold_s") or 6),
            "stability_score": 85,
        }
    if action_mode == "bed_flexion":
        records = metrics.get("保持记录") or []
        best_record = records[-1] if records else {}
        return {
            "max_flexion_deg": float(metrics.get("最大屈膝角_deg") or metrics.get("最大屈膝角度_deg") or best_record.get("最大屈膝角_deg") or 0),
            "max_thigh_raise_deg": float(metrics.get("大腿最大上抬角_deg") or best_record.get("大腿最大上抬角_deg") or 0),
            "hold_s": float(metrics.get("保持目标时长_s") or 10),
            "thigh_wave_deg": float(metrics.get("最大保持期大腿角波动_deg") or 0),
            "flexion_wave_deg": float(metrics.get("最大保持期屈膝角波动_deg") or 0),
            "stability_score": 90 if int(metrics.get("稳定保持回合数") or 0) > 0 else 75,
        }
    return {}


def import_real_training_results(session_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    result_path = session_dir / "result" / "summary.json"
    if not result_path.exists():
        return {"imported": 0, "message": "未找到 summary.json，未导入 SQLite。"}
    payload = json_loads(result_path.read_text(encoding="utf-8"), {})
    config_by_id = {item["id"]: item for item in config.get("actions", [])}
    imported = 0
    with connect() as conn:
        for result in payload.get("results", []):
            action_id = result.get("exercise_id")
            config_action = config_by_id.get(action_id)
            if not action_id or not config_action:
                continue
            metrics = normalize_real_result_metrics(action_id, result, config_action)
            if not metrics:
                continue
            metrics["desktop_summary"] = result.get("metrics") or {}
            metrics["started_at"] = payload.get("created_at") or dt_now_iso()
            metrics["ended_at"] = dt_now_iso()
            insert_training_session(
                conn,
                config["patient_id"],
                action_id,
                config["date"],
                metrics,
                config_action.get("source", "prescribed"),
            )
            imported += 1
        recalculate_daily_score(conn, config["patient_id"], config["date"])
    return {"imported": imported, "message": f"已导入 {imported} 条真实训练记录。"}


def run_mock_training(patient_id: str, day: str, action_id: str | None, mock_all: bool) -> dict[str, Any]:
    rng = random.Random(f"{patient_id}-{day}-{action_id}-{datetime.now().isoformat(timespec='seconds')}")
    with connect() as conn:
        if mock_all or not action_id:
            goals = unfinished_actions(conn, patient_id, day)
            if not goals:
                plan = get_prescription(conn, patient_id, day)
                goals = plan["actions"] if plan else []
        else:
            goal = goal_for_action(patient_id, day, action_id, conn)
            goals = [goal or {"id": action_id}]
        inserted = []
        for goal in goals:
            aid = goal["id"]
            target = rng.uniform(86, 108)
            metrics = mock_metrics_for(aid, goal, target, rng)
            source = "prescribed" if goal_for_action(patient_id, day, aid, conn) else "extra"
            inserted.append(insert_training_session(conn, patient_id, aid, day, metrics, source))
        daily = recalculate_daily_score(conn, patient_id, day)
    return {"inserted": inserted, "dailyScore": daily, "detail": patient_daily_detail(patient_id, day)}


def http_json_request(url: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> dict[str, Any]:
    data = None if payload is None else json_dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json_loads(resp.read().decode("utf-8"), {})


def wait_for_webrtc_health(port: int, timeout_seconds: float = 3.0) -> tuple[bool, dict[str, Any] | None, str | None]:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        try:
            data = http_json_request(url, timeout=0.5)
            if data.get("ok"):
                return True, data, None
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.1)
    return False, None, last_error or "WebRTC health check timed out"


def launch_real_training(
    patient_id: str,
    day: str,
    action_id: str | None,
    run_all_pending: bool,
    session_id: str,
    stream_profile: str = DEFAULT_STREAM_PROFILE,
    stream_type: str = DEFAULT_STREAM_TYPE,
) -> dict[str, Any]:
    script = ROOT / "knee_rehab_desktop_session.py"
    if not script.exists():
        raise FileNotFoundError("knee_rehab_desktop_session.py 不存在")
    mode = "one_click" if run_all_pending or not action_id else "single"
    session_dir = stream_session_dir(session_id)
    result_dir = session_dir / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        config = build_training_session_config(
            conn,
            session_id=session_id,
            patient_id=patient_id,
            day=day,
            mode=mode,
            action_id=action_id,
        )
    requested_stream_type = stream_type if stream_type in {"webrtc", "mjpeg_fallback"} else DEFAULT_STREAM_TYPE
    stream_profile = "quality"
    stream_settings = stream_profile_settings(stream_profile)
    webrtc_port = find_free_port() if requested_stream_type == "webrtc" else None
    config["stream_profile"] = stream_profile
    config["stream_settings"] = {
        "fps": stream_settings["fps"],
        "width": stream_settings["width"],
        "jpegQuality": stream_settings["jpeg_quality"],
    }
    config["stream_type"] = requested_stream_type
    config["webrtc_port"] = webrtc_port
    config["webrtc_width"] = DEFAULT_WEBRTC_WIDTH
    config["webrtc_fps"] = DEFAULT_WEBRTC_FPS
    config["webrtc_codec"] = DEFAULT_WEBRTC_CODEC
    if not config["actions"]:
        return {
            "mode": "already_completed",
            "sessionId": session_id,
            "patientId": patient_id,
            "date": day,
            "exerciseIds": [],
            "message": "今日处方已完成。",
        }
    config_path = session_dir / "session_config.json"
    config_path.write_text(json_dumps(config), encoding="utf-8")
    write_status_file(session_dir, default_training_status(session_id, config))
    for stale_name in ("latest.jpg", "command.txt", "pause.flag"):
        stale = session_dir / stale_name
        if stale.exists():
            stale.unlink()
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(script),
        "--session-config",
        str(config_path),
        "--web-stream-dir",
        str(session_dir),
        "--output-dir",
        str(result_dir),
        "--web-stream-fps",
        str(stream_settings["fps"]),
        "--web-stream-width",
        str(stream_settings["width"]),
        "--web-jpeg-quality",
        str(stream_settings["jpeg_quality"]),
        "--web-stream-profile",
        stream_profile,
    ]
    if requested_stream_type == "webrtc" and webrtc_port is not None:
        cmd.extend(
            [
                "--webrtc-host",
                "127.0.0.1",
                "--webrtc-port",
                str(webrtc_port),
                "--webrtc-width",
                str(DEFAULT_WEBRTC_WIDTH),
                "--webrtc-fps",
                str(DEFAULT_WEBRTC_FPS),
                "--webrtc-codec",
                DEFAULT_WEBRTC_CODEC,
            ]
        )
    else:
        cmd.append("--disable-webrtc")
    status = read_status_file(session_id)
    status["command"] = cmd
    status["streamType"] = requested_stream_type
    status["webrtcPort"] = webrtc_port
    write_status_file(session_dir, status)
    stdout_file = (session_dir / "stdout.log").open("w", encoding="utf-8")
    stderr_file = (session_dir / "stderr.log").open("w", encoding="utf-8")
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=stdout_file,
        stderr=stderr_file,
        text=True,
        env=child_env,
    )
    start_training_watcher(process, session_dir, config, stdout_file, stderr_file)
    stream_type_result = "mjpeg_fallback"
    webrtc_health: dict[str, Any] | None = None
    webrtc_error: str | None = None
    if requested_stream_type == "webrtc" and webrtc_port is not None:
        ok, webrtc_health, webrtc_error = wait_for_webrtc_health(webrtc_port)
        stream_type_result = "webrtc" if ok else "mjpeg_fallback"
        if not ok:
            status = read_status_file(session_id)
            status["streamType"] = "mjpeg_fallback"
            status["webrtcReady"] = False
            status["webrtcError"] = webrtc_error or "WebRTC signaling server 未就绪"
            status["message"] = "WebRTC 实时画面不可用，已切换到 MJPEG 备用流。"
            write_status_file(session_dir, status)
    exercise_ids = [item["id"] for item in config["actions"]]
    return {
        "mode": "real_process",
        "sessionId": session_id,
        "pid": process.pid,
        "command": cmd,
        "patientId": patient_id,
        "date": day,
        "exerciseIds": exercise_ids,
        "streamUrl": f"/api/training-stream/{session_id}",
        "fallbackStreamUrl": f"/api/training-stream/{session_id}",
        "statusUrl": f"/api/training/status/{session_id}",
        "controlUrl": f"/api/training/control/{session_id}",
        "streamType": stream_type_result,
        "webrtcOfferUrl": f"/api/training/webrtc-offer/{session_id}" if webrtc_port is not None else None,
        "webrtc": {
            "width": DEFAULT_WEBRTC_WIDTH,
            "fps": DEFAULT_WEBRTC_FPS,
            "codec": DEFAULT_WEBRTC_CODEC,
            "port": webrtc_port,
            "ready": stream_type_result == "webrtc",
            "health": webrtc_health,
        },
        "webrtcError": webrtc_error if stream_type_result != "webrtc" else None,
        "note": "已启动网页内嵌动作识别进程。",
    }


def start_training_watcher(
    process: subprocess.Popen,
    session_dir: Path,
    config: dict[str, Any],
    stdout_file,
    stderr_file,
) -> None:
    def watch() -> None:
        returncode = process.wait()
        stdout_file.close()
        stderr_file.close()
        status = read_status_file(config["session_id"])
        status["exited"] = True
        status["returncode"] = returncode
        try:
            import_result = import_real_training_results(session_dir, config)
            status["completed"] = returncode == 0
            status["failed"] = returncode != 0
            status["message"] = import_result["message"] if returncode == 0 else "训练进程异常退出。"
            status["imported"] = import_result.get("imported", 0)
            if returncode != 0:
                status["error"] = status.get("logTail") or "训练进程异常退出。"
        except Exception as exc:
            status["completed"] = False
            status["failed"] = True
            status["error"] = str(exc)
            status["message"] = "训练结果导入失败。"
        write_status_file(session_dir, status)

    threading.Thread(target=watch, daemon=True).start()


def patient_summary(patient_id: str) -> dict[str, Any]:
    with connect() as conn:
        patient = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
        rows = conn.execute(
            "SELECT * FROM daily_scores WHERE patient_id=? ORDER BY date",
            (patient_id,),
        ).fetchall()
        scores = [row["score"] for row in rows if row["score"] is not None]
        last = dict(rows[-1]) if rows else None
        return {
            "patient": dict(patient) if patient else None,
            "daysRecorded": len(scores),
            "averageScore": round(sum(scores) / len(scores), 1) if scores else None,
            "bestScore": round(max(scores), 1) if scores else None,
            "latest": last,
            "trend": [
                {
                    "date": row["date"],
                    "score": row["score"],
                    "qty": row["qty"],
                    "quality": row["quality"],
                    "stability": row["stability"],
                }
                for row in rows[-14:]
            ],
        }


SESSIONS: dict[str, dict[str, Any]] = {}


def make_app(mock_training: bool = False):
    try:
        from flask import Flask, Response, jsonify, redirect, request, send_from_directory
    except ModuleNotFoundError as exc:
        raise SystemExit("缺少 Flask，请先运行 pip install -r requirements.txt") from exc

    init_db()
    if not DB_PATH.exists() or not connect().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]:
        seed_demo(reseed=False)

    app = Flask(__name__)
    runtime_state: dict[str, Any] = {
        "shutdown_requested": False,
        "shutdown_reason": None,
        "shutdown_requested_at": None,
        "close_deadline": None,
        "last_heartbeat": None,
        "active_session_id": None,
    }
    app.config["RUNTIME_STATE"] = runtime_state

    def api_ok(data: Any = None, **kwargs):
        payload = {"ok": True}
        if data is not None:
            payload["data"] = data
        payload.update(kwargs)
        return jsonify(payload)

    def api_error(message: str, status: int = 400):
        return jsonify({"ok": False, "error": message}), status

    def current_user() -> dict[str, Any] | None:
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        token = token or request.headers.get("X-Session-Token", "").strip()
        return SESSIONS.get(token)

    def mark_browser_active() -> None:
        runtime_state["last_heartbeat"] = time.monotonic()
        if not runtime_state["shutdown_requested"]:
            runtime_state["close_deadline"] = None

    def request_server_shutdown(reason: str, delay_seconds: float = 2.0) -> None:
        runtime_state["shutdown_requested"] = True
        runtime_state["shutdown_reason"] = reason
        runtime_state["shutdown_requested_at"] = runtime_state["shutdown_requested_at"] or time.monotonic()
        runtime_state["close_deadline"] = time.monotonic() + delay_seconds

    def active_training_status() -> dict[str, Any] | None:
        session_id = runtime_state.get("active_session_id")
        if not session_id:
            return None
        try:
            status = read_status_file(session_id)
        except Exception:
            return None
        if status.get("exited") or status.get("completed") or status.get("failed"):
            runtime_state["active_session_id"] = None
            return None
        return status

    def write_training_command(session_id: str, command: str) -> None:
        stream_dir = stream_session_dir(session_id)
        if command == "pause":
            (stream_dir / "pause.flag").write_text("pause", encoding="utf-8")
            return
        if command == "resume":
            pause_flag = stream_dir / "pause.flag"
            if pause_flag.exists():
                pause_flag.unlink()
            return
        if command not in {"q", "n", "r"}:
            raise ValueError("unsupported training command")
        pause_flag = stream_dir / "pause.flag"
        if pause_flag.exists():
            pause_flag.unlink()
        (stream_dir / "command.txt").write_text(command, encoding="utf-8")

    @app.get("/")
    def index():
        return redirect("/knee_rehab_full_demo_v1.html")

    @app.post("/api/browser-opened")
    def browser_opened():
        mark_browser_active()
        return api_ok({"status": "active"})

    @app.post("/api/browser-heartbeat")
    def browser_heartbeat():
        mark_browser_active()
        return api_ok({"status": "active"})

    @app.post("/api/browser-closed")
    def browser_closed():
        runtime_state["close_deadline"] = time.monotonic() + 2.0
        return api_ok({"status": "closing"})

    @app.get("/api/runtime-status")
    def runtime_status():
        active = active_training_status()
        return api_ok(
            {
                "shutdownRequested": runtime_state["shutdown_requested"],
                "shutdownReason": runtime_state["shutdown_reason"],
                "activeTraining": active,
            }
        )

    @app.get("/api/app-state")
    def app_state():
        return api_ok(
            {
                "demoStartDate": DEMO_START_DATE.isoformat(),
                "demoToday": DEMO_TODAY.isoformat(),
                "actions": {k: ACTION_LIBRARY[k] for k in ACTION_ORDER},
                "templates": PRESCRIPTION_TEMPLATES,
            }
        )

    @app.get("/api/demo-state")
    def demo_state():
        return api_ok(build_demo_state())

    @app.post("/api/login")
    def login():
        payload = request.get_json(force=True, silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        with connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"], row["salt"]):
            return api_error("账号或密码不正确", 401)
        user = public_user(row)
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = user
        return api_ok({"token": token, "user": user})

    @app.post("/api/register")
    def register():
        payload = request.get_json(force=True, silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        role = payload.get("role") or "patient"
        if not username or not password:
            return api_error("账号和密码不能为空")
        try:
            user = register_user(username, password, role)
        except ValueError as exc:
            return api_error(str(exc))
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = user
        return api_ok({"token": token, "user": user, "state": build_demo_state()})

    @app.get("/api/me")
    def me():
        user = current_user()
        if not user:
            return api_error("未登录", 401)
        return api_ok(user)

    @app.get("/api/actions")
    def actions():
        return api_ok([ACTION_LIBRARY[k] for k in ACTION_ORDER])

    @app.get("/api/patients")
    def patients():
        with connect() as conn:
            rows = conn.execute("SELECT * FROM patients ORDER BY id").fetchall()
        return api_ok([dict(row) for row in rows])

    @app.get("/api/patients/<patient_id>/today")
    def today(patient_id: str):
        try:
            return api_ok(patient_today(patient_id))
        except KeyError:
            return api_error("患者不存在", 404)

    @app.get("/api/patients/<patient_id>/calendar")
    def calendar_api(patient_id: str):
        year = int(request.args.get("year", DEMO_TODAY.year))
        month = int(request.args.get("month", DEMO_TODAY.month))
        return api_ok(patient_calendar(patient_id, year, month))

    @app.get("/api/patients/<patient_id>/daily-detail")
    def daily_detail_api(patient_id: str):
        day = request.args.get("date") or DEMO_TODAY.isoformat()
        return api_ok(patient_daily_detail(patient_id, day))

    def stream_response_for_session(session_id: str, poll_sleep: float | None = None):
        stream_dir = stream_session_dir(session_id)
        latest = stream_dir / "latest.jpg"
        status_path = stream_dir / "status.json"
        profile = DEFAULT_STREAM_PROFILE
        if status_path.exists():
            try:
                profile = normalize_stream_profile(json_loads(status_path.read_text(encoding="utf-8"), {}).get("stream_profile"))
            except OSError:
                profile = DEFAULT_STREAM_PROFILE
        sleep_seconds = float(poll_sleep if poll_sleep is not None else stream_profile_settings(profile)["flask_poll_sleep"])

        def generate():
            last_mtime = None
            while not runtime_state["shutdown_requested"]:
                try:
                    if latest.exists():
                        mtime = latest.stat().st_mtime_ns
                        if mtime != last_mtime:
                            last_mtime = mtime
                            frame = latest.read_bytes()
                            yield (
                                b"--frame\r\n"
                                b"Content-Type: image/jpeg\r\n"
                                b"Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n"
                                b"Pragma: no-cache\r\n"
                                b"X-Accel-Buffering: no\r\n\r\n"
                                + frame
                                + b"\r\n"
                            )
                except OSError:
                    pass
                time.sleep(sleep_seconds)

        response = Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @app.get("/api/training-stream/<session_id>")
    def training_stream_session(session_id: str):
        return stream_response_for_session(session_id)

    @app.get("/api/training-stream/current")
    def training_stream_current():
        session_id = runtime_state.get("active_session_id")
        if not session_id:
            return api_error("当前没有正在运行的训练。", 404)
        return stream_response_for_session(session_id)

    @app.get("/api/training/status/<session_id>")
    def training_status(session_id: str):
        try:
            return api_ok(read_status_file(session_id))
        except Exception as exc:
            return api_error(str(exc), 404)

    @app.post("/api/training/webrtc-offer/<session_id>")
    def training_webrtc_offer(session_id: str):
        payload = request.get_json(force=True, silent=True) or {}
        session_dir = stream_session_dir(session_id)
        try:
            status = read_status_file(session_id)
            status["webrtcOfferForwardStartedAt"] = dt_now_iso()
            status["webrtcLastError"] = None
            write_status_file(session_dir, status)
            port = status.get("webrtcPort") or status.get("webrtc_port")
            if not port:
                status["webrtcLastError"] = "该训练 session 没有可用的 WebRTC signaling 端口。"
                write_status_file(session_dir, status)
                return api_error("该训练 session 没有可用的 WebRTC signaling 端口。", 404)
            target_url = f"http://127.0.0.1:{int(port)}/offer"
            answer = http_json_request(target_url, payload, timeout=6.0)
            status = read_status_file(session_id)
            status["webrtcAnswerForwardedAt"] = dt_now_iso()
            if not answer.get("sdp"):
                status["webrtcLastError"] = "WebRTC signaling 返回的 answer 缺少 SDP。"
                write_status_file(session_dir, status)
                return api_error(status["webrtcLastError"], 502)
            status["webrtcAnswerSentAt"] = status.get("webrtcAnswerSentAt") or dt_now_iso()
            status["webrtcLastError"] = None
            write_status_file(session_dir, status)
            return jsonify({"ok": True, **answer})
        except urllib.error.URLError as exc:
            status = read_status_file(session_id)
            status["webrtcLastError"] = f"WebRTC signaling 转发失败：{exc}"
            write_status_file(session_dir, status)
            return api_error(f"WebRTC signaling 转发失败：{exc}", 502)
        except Exception as exc:
            status = read_status_file(session_id)
            status["webrtcLastError"] = str(exc)
            write_status_file(session_dir, status)
            return api_error(str(exc), 500)

    @app.post("/api/training/control/<session_id>")
    def training_control_session(session_id: str):
        payload = request.get_json(force=True, silent=True) or {}
        command = payload.get("command")
        try:
            write_training_command(session_id, command)
        except ValueError as exc:
            return api_error(str(exc))
        return api_ok({"sessionId": session_id, "command": command})

    @app.post("/api/training/control")
    def training_control():
        session_id = runtime_state.get("active_session_id")
        if not session_id:
            return api_error("当前没有正在运行的训练。", 404)
        return training_control_session(session_id)

    @app.post("/api/training/start")
    def training_start():
        payload = request.get_json(force=True, silent=True) or {}
        patient_id = payload.get("patient_id") or payload.get("patientId") or "p001"
        day = payload.get("date") or DEMO_TODAY.isoformat()
        action_id = payload.get("action_id") or payload.get("actionId")
        mock_all = payload.get("mode") in {"today", "one_click", "all"}
        use_mock = bool(payload.get("mock", mock_training))
        stream_profile = normalize_stream_profile(payload.get("stream_profile") or payload.get("streamProfile"))
        stream_type = payload.get("stream_type") or payload.get("streamType") or DEFAULT_STREAM_TYPE
        if not use_mock:
            active = active_training_status()
            if active:
                return api_error("已有训练正在进行，请先退出当前训练或等待完成。", 409)
            try:
                session_id = uuid.uuid4().hex
                result = launch_real_training(patient_id, day, action_id, mock_all, session_id, stream_profile, stream_type)
                if result.get("mode") == "real_process":
                    runtime_state["active_session_id"] = session_id
            except Exception as exc:
                return api_error(str(exc))
            return api_ok(result)
        result = run_mock_training(patient_id, day, action_id, mock_all)
        result["state"] = build_demo_state()
        return api_ok(result)

    @app.post("/api/therapist/assign-template")
    def assign_template():
        payload = request.get_json(force=True, silent=True) or {}
        patient_id = payload.get("patient_id") or payload.get("patientId") or "p001"
        template_id = payload.get("template_id") or payload.get("templateId") or "week2_straight_raise"
        start_date = payload.get("start_date") or payload.get("startDate") or DEMO_TODAY.isoformat()
        days = int(payload.get("days") or 7)
        try:
            result = apply_template(patient_id, template_id, start_date, days)
        except ValueError as exc:
            return api_error(str(exc))
        result["state"] = build_demo_state()
        return api_ok(result)

    @app.get("/api/therapist/patient-summary")
    def therapist_patient_summary():
        patient_id = request.args.get("patient_id") or "p001"
        return api_ok(patient_summary(patient_id))

    @app.get("/api/training/webrtc-debug/<session_id>")
    def training_webrtc_debug(session_id: str):
        session_dir = stream_session_dir(session_id)
        status = read_status_file(session_id)
        port = status.get("webrtcPort") or status.get("webrtc_port")
        health = None
        health_error = None
        if port:
            try:
                health = http_json_request(f"http://127.0.0.1:{int(port)}/health", timeout=1.0)
            except Exception as exc:
                health_error = str(exc)
        return api_ok(
            {
                "sessionId": session_id,
                "sessionDir": str(session_dir),
                "status": status,
                "stdoutTail": tail_text(session_dir / "stdout.log"),
                "stderrTail": tail_text(session_dir / "stderr.log"),
                "command": status.get("command"),
                "health": health,
                "healthError": health_error,
                "offerEndpoint": f"/api/training/webrtc-offer/{session_id}",
                "fallbackStreamUrl": f"/api/training-stream/{session_id}",
            }
        )

    @app.get("/<path:filename>")
    def static_files(filename: str):
        allowed_suffixes = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".md"}
        target = (ROOT / filename).resolve()
        if ROOT not in target.parents and target != ROOT:
            return api_error("invalid path", 404)
        if target.suffix.lower() not in allowed_suffixes:
            return api_error("unsupported file type", 404)
        return send_from_directory(ROOT, filename)

    return app


def print_summary() -> None:
    init_db()
    with connect() as conn:
        patient_count = conn.execute("SELECT COUNT(*) AS n FROM patients").fetchone()["n"]
        user_count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        prescription_count = conn.execute("SELECT COUNT(*) AS n FROM prescriptions").fetchone()["n"]
        session_count = conn.execute("SELECT COUNT(*) AS n FROM training_sessions").fetchone()["n"]
        score_count = conn.execute("SELECT COUNT(*) AS n FROM daily_scores").fetchone()["n"]
        rows = conn.execute(
            """
            SELECT p.name, ROUND(AVG(d.score), 1) AS avg_score, ROUND(MAX(d.score), 1) AS best_score
            FROM patients p
            LEFT JOIN daily_scores d ON d.patient_id = p.id
            GROUP BY p.id
            ORDER BY p.id
            """
        ).fetchall()
    print(f"数据目录: {DATA_DIR}")
    print(f"Demo today: {DEMO_TODAY.isoformat()}")
    print(f"用户: {user_count}, 患者: {patient_count}, 处方: {prescription_count}, 训练记录: {session_count}, 日评分: {score_count}")
    for row in rows:
        print(f"- {row['name']}: 平均 {row['avg_score']}, 最好 {row['best_score']}")
    print("Demo 账号: therapist / 123456, liming / 123456, zhangmin / 123456, chenhao / 123456")


def print_active_training() -> None:
    stream_root = RUNTIME_DIR / "training_stream"
    if not stream_root.exists():
        print("当前没有训练 session。")
        return
    sessions = sorted((p for p in stream_root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
    if not sessions:
        print("当前没有训练 session。")
        return
    for session_dir in sessions[:5]:
        status_path = session_dir / "status.json"
        status = json_loads(status_path.read_text(encoding="utf-8"), {}) if status_path.exists() else {}
        print(f"- {session_dir.name}: exited={status.get('exited')} completed={status.get('completed')} failed={status.get('failed')} fps={status.get('fps')} stale={status.get('stale')}")
        print(f"  path: {session_dir}")
        print(f"  message: {status.get('message')}")


def port_is_available(host: str, port: int) -> bool:
    bind_host = "127.0.0.1" if host in {"localhost", "0.0.0.0"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.bind((bind_host, port))
        except OSError:
            return False
    return True


def choose_available_port(host: str, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 20):
        if port_is_available(host, port):
            return port
    return preferred_port


def run_local_server(app: Any, *, host: str, port: int, url: str, open_browser: bool) -> None:
    try:
        from werkzeug.serving import make_server
    except ModuleNotFoundError as exc:
        raise SystemExit("缺少 Werkzeug，请先运行 pip install -r requirements.txt") from exc

    runtime_state: dict[str, Any] = app.config["RUNTIME_STATE"]
    server = make_server(host, port, app, threaded=True)
    server.timeout = 0.5
    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def request_shutdown_from_signal(signum, _frame) -> None:
        runtime_state["shutdown_requested"] = True
        runtime_state["shutdown_reason"] = "ctrl_c" if signum == signal.SIGINT else "signal"
        runtime_state["shutdown_requested_at"] = time.monotonic()
        runtime_state["close_deadline"] = time.monotonic() + 2.0
        print("收到退出信号，正在通知网页关闭...")

    signal.signal(signal.SIGINT, request_shutdown_from_signal)
    signal.signal(signal.SIGTERM, request_shutdown_from_signal)
    if open_browser:
        webbrowser.open(url)
    try:
        while True:
            server.handle_request()
            now = time.monotonic()
            close_deadline = runtime_state.get("close_deadline")
            if close_deadline and now >= close_deadline:
                break
            if runtime_state.get("shutdown_requested"):
                requested_at = runtime_state.get("shutdown_requested_at") or now
                if now - requested_at >= 2.0:
                    break
    finally:
        server.server_close()
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local knee rehabilitation demo API")
    parser.add_argument("--init-demo", action="store_true", help="initialize demo data if it is missing")
    parser.add_argument("--reseed-demo", action="store_true", help="recreate demo data")
    parser.add_argument("--reset-key", action="store_true", help="also recreate the Fernet key when reseeding")
    parser.add_argument("--print-summary", action="store_true", help="print local demo data summary")
    parser.add_argument("--print-active-training", action="store_true", help="print recent real training session status")
    parser.add_argument("--serve", action="store_true", help="serve the local API and frontend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="serve without opening the browser automatically")
    parser.add_argument("--mock-training", action="store_true", help="force API training calls to use mock data")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    raw_args = argv if argv is not None else sys.argv[1:]
    args = parse_args(raw_args)
    no_command = not any([args.init_demo, args.reseed_demo, args.print_summary, args.print_active_training, args.serve])
    if no_command:
        args.serve = True
        print("未传入命令行参数，默认启动本地网页端。")
    if args.reseed_demo:
        if args.reset_key and DATA_DIR.exists() and DB_PATH.exists():
            backup = EXPORT_DIR / f"backup_before_reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DB_PATH, backup)
        seed_demo(reseed=True, reset_key=args.reset_key)
        print("Demo 数据已重新生成。")
    elif args.init_demo:
        seed_demo(reseed=False, reset_key=False)
        print("Demo 数据已初始化。")
    if args.print_summary:
        print_summary()
    if args.print_active_training:
        print_active_training()
    if args.serve:
        seed_demo(reseed=False, reset_key=False)
        app = make_app(mock_training=args.mock_training)
        port = choose_available_port(args.host, args.port)
        if port != args.port:
            print(f"端口 {args.port} 已被占用，自动改用 {port}。")
        url_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
        url = f"http://{url_host}:{port}/knee_rehab_full_demo_v1.html"
        print(f"本地服务已启动: {url}")
        run_local_server(
            app,
            host=args.host,
            port=port,
            url=url,
            open_browser=not args.no_browser and url_host in {"127.0.0.1", "localhost"},
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
