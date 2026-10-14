SchoolFlow Premium UI - Flask + SQLite + R307S

This package updates the existing Flask application's HTML templates to a premium dashboard style.
It does not intentionally modify app.py, auto_scan.py, or any database file.

Important:
- The UI has not been tested on the Raspberry Pi hardware in this environment.
- Back up app.py, the templates directory, and school.db before installing.
- Copy the templates/ folder only; do NOT replace app.py, auto_scan.py, or school.db with this package.
- Existing Flask endpoint names are preserved in the templates.

Suggested Raspberry Pi installation:
  cd /home/suthipong/school-system
  cp -a templates templates.backup_premium_$(date +%Y%m%d_%H%M%S)
  # transfer and extract this archive somewhere temporary, then copy its templates folder:
  cp -a /path/to/extracted/school-system-code/templates/. /home/suthipong/school-system/templates/
  sudo systemctl restart school-system.service

Then open the existing web app and check dashboard, students, classes, subjects, attendance, fingerprint scan, sensor, and password pages.
If any page returns HTTP 500, restore the backup templates directory and restart the service.
