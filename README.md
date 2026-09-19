# Sonia Music Academy — Supabase version

Uses the existing website UI with Flask + Supabase PostgreSQL.

1. Create a Supabase project.
2. Open SQL Editor and run `backend/supabase_schema.sql`.
3. In Project Settings → API, copy the Project URL and service_role key.
4. Copy `backend/.env.example` to `backend/.env` and fill the values.
5. Run:
```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe app.py
```
6. Test `http://127.0.0.1:5000/api/health`.
7. Open `http://127.0.0.1:5000`.

Never put the Supabase service_role key in frontend code or GitHub.
