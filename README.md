# University Portal

## Run the Python backend

1. Install Python 3.10 or newer and MySQL.
2. Configure `.env` with the MySQL connection settings and a `SESSION_SECRET` of at least 32 characters. Make sure `DB_NAME` matches the database selected in `schema.sql` (`online_exam1` by default).
3. Install the Python dependencies and start the server:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

The backend serves the portal at <http://localhost:3000> and creates the `portal_students` and `exam_registrations` tables on startup. Exam form submissions are saved in `exam_registrations` in the database selected by `DB_NAME`.

Run the backend tests with:

```powershell
python -m unittest -v
```
