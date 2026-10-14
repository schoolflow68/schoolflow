import os
import sys
import time
import sqlite3
import fcntl
from datetime import datetime
from pyfingerprint.pyfingerprint import PyFingerprint

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SCHOOL_DB_PATH", os.path.join(ROOT, "school.db"))
PORT = os.environ.get("R307S_PORT", "/dev/serial0")
BAUD = int(os.environ.get("R307S_BAUD", "57600"))
LOCK_PATH = "/tmp/school-r307s-shared.lock"
POLL_INTERVAL = 0.35


def close_finger(finger):
    if finger is not None:
        try:
            finger._PyFingerprint__serial.close()
        except Exception:
            pass




def record_attendance(slot):
    now = datetime.now()
    day = now.date().isoformat()
    clock = now.strftime("%H:%M:%S")

    with sqlite3.connect(DB_PATH, timeout=10) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("""
            CREATE TABLE IF NOT EXISTS scanner_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
        """)

        columns = {
            row["name"] for row in db.execute("PRAGMA table_info(attendance)")
        }
        if "attendance_status" not in columns:
            db.execute(
                "ALTER TABLE attendance ADD COLUMN attendance_status "
                "TEXT NOT NULL DEFAULT 'present'"
            )

        student = db.execute(
            "SELECT * FROM students WHERE fingerprint_id=? AND active=1",
            (int(slot),),
        ).fetchone()
        if not student:
            print(f"???????????????????????????????? {slot}", flush=True)
            return

        settings = {
            row["setting_key"]: row["setting_value"]
            for row in db.execute(
                "SELECT setting_key, setting_value FROM scanner_settings"
            ).fetchall()
        }
        subject_id = settings.get("active_subject_id")
        phase = settings.get("scan_phase")
        start_time = settings.get("class_start_time")
        grace_text = settings.get("late_grace_minutes")

        if not subject_id or not phase:
            print("??????????????????????? ???????????????????????", flush=True)
            return

        subject = db.execute(
            "SELECT name FROM subjects WHERE id=?", (int(subject_id),)
        ).fetchone()
        if not subject:
            print("?????????????????? ??????????????????", flush=True)
            return

        row = db.execute(
            """SELECT * FROM attendance
               WHERE student_id=? AND attendance_date=? AND subject_id=?
               ORDER BY id DESC LIMIT 1""",
            (student["id"], day, int(subject_id)),
        ).fetchone()

        if phase == "in":
            if row and row["check_in"]:
                print(
                    f"??????????????????: {student['full_name']} [{subject['name']}]",
                    flush=True,
                )
                return

            try:
                start = datetime.strptime(start_time, "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day
                )
                grace_minutes = int(grace_text)
                late_after = start.timestamp() + grace_minutes * 60
                status = "late" if now.timestamp() > late_after else "present"
            except (TypeError, ValueError):
                print("???????????????????????? ????????????????", flush=True)
                return

            if row:
                db.execute(
                    """UPDATE attendance
                       SET check_in=?, method='fingerprint', attendance_status=?
                       WHERE id=?""",
                    (clock, status, row["id"]),
                )
            else:
                db.execute(
                    """INSERT INTO attendance
                       (student_id,class_id,subject_id,attendance_date,check_in,
                        method,attendance_status)
                       VALUES(?,?,?,?,?,'fingerprint',?)""",
                    (
                        student["id"], student["class_id"], int(subject_id),
                        day, clock, status,
                    ),
                )

            label = "???" if status == "late" else "???????"
            print(
                f"????????? {student['full_name']} [{subject['name']}] "
                f"{clock} ({label})",
                flush=True,
            )

        elif phase == "out":
            if not row or not row["check_in"]:
                print(
                    f"????????????????: {student['full_name']} [{subject['name']}]",
                    flush=True,
                )
                return
            if row["check_out"]:
                print(
                    f"?????????????????: {student['full_name']} [{subject['name']}]",
                    flush=True,
                )
                return

            db.execute(
                "UPDATE attendance SET check_out=?, method='fingerprint' WHERE id=?",
                (clock, row["id"]),
            )
            print(
                f"????????? {student['full_name']} [{subject['name']}] {clock}",
                flush=True,
            )
        else:
            print("?????????????????? ?????????????????", flush=True)
            return

        db.commit()


def scan_poll():
    """One short sensor poll. Release shared lock immediately when no finger is present."""
    lock_file = open(LOCK_PATH, "a")
    finger = None
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        finger = PyFingerprint(PORT, BAUD, 0xFFFFFFFF, 0x00000000)
        if not finger.verifyPassword():
            raise RuntimeError("R307S password verification failed")
        if not finger.readImage():
            return False

        finger.convertImage(0x01)
        slot, accuracy = finger.searchTemplate()
        if slot < 0:
            print("Fingerprint not registered", flush=True)
        else:
            record_attendance(slot)

        # Debounce: retain sensor ownership until the finger is removed.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if not finger.readImage():
                break
            time.sleep(0.15)
        else:
            print("Finger removal timeout; waiting for removal before next scan", flush=True)
            # Do not allow a held finger to become a second attendance event.
            while True:
                try:
                    if not finger.readImage():
                        break
                except Exception:
                    break
                time.sleep(0.25)
        time.sleep(0.8)
        return True
    finally:
        close_finger(finger)
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
        finally:
            lock_file.close()


def main():
    print("R307S automatic attendance scanner starting", flush=True)
    while True:
        try:
            found = scan_poll()
            if not found:
                time.sleep(POLL_INTERVAL)
        except Exception as exc:
            print(f"Scanner error: {exc}", file=sys.stderr, flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
