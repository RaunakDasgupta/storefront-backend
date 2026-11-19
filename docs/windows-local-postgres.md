# Local Postgres on Windows

This API needs an **empty** Postgres database. This guide sets one up on a Windows machine, first with the normal installer and then without an installer (for locked-down devices).

There are no migrations to run. On first start the API creates the tables and, if the database is empty, loads the demo data (see the main README).

## Option A: the installer

1. Download the Windows installer from https://www.postgresql.org/download/windows/ (EDB) and run it.
2. Keep **PostgreSQL Server**, **Command Line Tools** and **pgAdmin 4**. Skip Stack Builder.
3. Keep the default data directory and port `5432`. Set a password for the `postgres` superuser and save it.
4. Add `C:\Program Files\PostgreSQL\<version>\bin` to the system `Path` (Environment Variables dialog), then open a **new** PowerShell window.
5. Check it runs: `psql --version` and `Get-Service postgresql*` (status `Running`).

Then go to [Create the user and database](#create-the-user-and-database).

## Option B: no installer (portable zip)

Use this when the installer is blocked. It needs no admin rights and no Windows service.

1. Download the Windows x86-64 **zip** from https://www.enterprisedb.com/download-postgresql-binaries and extract it to `C:\Users\<you>\pgsql`. The folder should contain `bin`, `lib` and `share` (if it extracts to `pgsql\pgsql`, move the inner folder up).
2. Initialize a data folder, once. It prompts for the `postgres` password; save it.

   ```powershell
   cd $HOME\pgsql\bin
   .\initdb.exe -D "$HOME\pgdata" -U postgres -A scram-sha-256 -W
   ```

3. Start the server:

   ```powershell
   .\pg_ctl.exe -D "$HOME\pgdata" -l "$HOME\pg.log" start
   ```

   Check it with `.\pg_ctl.exe -D "$HOME\pgdata" status`; stop it with the same command and `stop`. It does **not** start by itself after a reboot, so run the start command again each time.

If port `5432` is taken ("address already in use"), start with `-o "-p 5433"` and use `5433` everywhere below.

If `initdb` fails with a missing DLL, install the Microsoft Visual C++ Redistributable.

## Create the user and database

From the folder with `psql.exe` (Option B) or any terminal (Option A):

```powershell
psql -U postgres -h localhost
```

```sql
CREATE USER storefront WITH PASSWORD 'choose-a-password';
CREATE DATABASE storefront OWNER storefront;
\q
```

Test the new login (you should get a `storefront=>` prompt):

```powershell
psql -U storefront -d storefront -h localhost
```

## Connect pgAdmin

Right-click **Servers → Register → Server**:

| Field | Value |
|---|---|
| Name | `storefront-local` |
| Host | `localhost` |
| Port | `5432` (or `5433`) |
| Maintenance database | `postgres` |
| Username | `postgres`, or `storefront` for the app user |
| Password | the one you set |

## Point the API at it

In `.env` (copy `.env.example` first):

```
DATABASE_URL=postgresql://storefront:choose-a-password@localhost:5432/storefront
```

URL-encode special characters in the password (`@` becomes `%40`, `/` becomes `%2F`, `#` becomes `%23`).

Then start the API as the main README describes. On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs. `GET /health` reports whether the API can reach the database.

For the frontend, set `VITE_API_URL=http://localhost:8000/api/v1` in its `.env.local` and restart `npm run dev`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `psql` is not recognized | `bin` is not on `Path`, or the terminal is the old one |
| Password authentication failed | wrong user or password; `postgres` and `storefront` have separate passwords |
| Connection refused | server not running (Option A: `Start-Service postgresql-x64-<version>`; Option B: run the `pg_ctl start` command) |
| Address already in use | another Postgres owns `5432`; use a different port |
| API starts but seeds nothing | the database was not empty; the API never seeds one that already has products or orders |

## If both options are blocked

- **WSL2:** `wsl --install`, then `sudo apt install postgresql` and `sudo service postgresql start` in Ubuntu. Windows apps reach it at `localhost:5432`.
- **Docker:** `docker run -d --name pg -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:17`.
- **Hosted Postgres** (Neon, Supabase, free tiers): use its connection string as `DATABASE_URL`, adding `?sslmode=require`. The data is not on the device.
