# Local Postgres on Windows

This API needs an **empty** Postgres database. This guide sets one up on a Windows machine, first with the normal installer and then without an installer (for locked-down devices). It uses the `postgres` superuser and pgAdmin, so `psql` is not needed.

There are no migrations to run. On first start the API creates the tables and, if the database is empty, loads the demo data (see the main README).

## Option A: the installer

1. Download the Windows installer from https://www.postgresql.org/download/windows/ (EDB) and run it.
2. Keep **PostgreSQL Server** and **pgAdmin 4**. Skip Stack Builder.
3. Keep the default data directory and port `5432`. Set a password for the `postgres` superuser and save it.
4. Check the server is running: `Get-Service postgresql*` (status `Running`).

Then go to [Connect pgAdmin](#connect-pgadmin).

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

   `pg_ctl` only manages the server. Check it with `.\pg_ctl.exe -D "$HOME\pgdata" status`; stop it with the same command and `stop`. It does **not** start by itself after a reboot, so run the start command again each time.

If port `5432` is taken ("address already in use"), start with `-o "-p 5433"` and use `5433` everywhere below.

If `initdb` fails with a missing DLL, install the Microsoft Visual C++ Redistributable.

## Connect pgAdmin

Right-click **Servers → Register → Server**:

| Field | Value |
|---|---|
| Name | `storefront-local` |
| Host | `localhost` |
| Port | `5432` (or `5433`) |
| Maintenance database | `postgres` |
| Username | `postgres` |
| Password | the one you set |

## Create the database

1. In pgAdmin, expand `storefront-local`, right-click **Databases → Create → Database**.
2. Name it `storefront`, leave the owner as `postgres`, and click **Save**.

Or open the **Query Tool** on the `postgres` database and run:

```sql
CREATE DATABASE storefront;
```

## Point the API at it

Copy `.env.example` to `.env` and set:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/storefront
```

Use the `postgres` password you set earlier. URL-encode special characters in it (`@` becomes `%40`, `/` becomes `%2F`, `#` becomes `%23`). Use `5433` instead of `5432` if you changed the port.

Then start the API. In PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
fastapi run
```

## Check it works

In a second PowerShell window:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

- `status: ok` and `database: up`: the API reached the database.
- A 503 with `database: down`: it could not connect. The log in the window running `fastapi run` says why.

Open http://localhost:8000/docs for the API. In pgAdmin, `storefront → Schemas → public → Tables` should now list the tables, with rows in `products` and `orders` if the demo seed ran.

For the frontend, set `VITE_API_URL=http://localhost:8000/api/v1` in its `.env.local` and restart `npm run dev`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Password authentication failed | wrong password in `.env`, or special characters in it need URL-encoding |
| Connection refused | server not running (Option A: `Start-Service postgresql-x64-<version>`; Option B: run the `pg_ctl start` command) or wrong port |
| `database "storefront" does not exist` | create it in pgAdmin (see above) |
| Address already in use | another Postgres owns `5432`; use a different port |
| `/health` is ok but no tables | `AUTO_CREATE_SCHEMA` is `false` in `.env` |
| API starts but seeds nothing | the database was not empty; the API never seeds one that already has products or orders |

## If both options are blocked

- **WSL2:** `wsl --install`, then `sudo apt install postgresql` and `sudo service postgresql start` in Ubuntu. Windows apps reach it at `localhost:5432`.
- **Docker:** `docker run -d --name pg -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:17`.
- **Hosted Postgres** (Neon, Supabase, free tiers): use its connection string as `DATABASE_URL`, adding `?sslmode=require`. The data is not on the device.
