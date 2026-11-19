# storefront-backend

The API behind **Everyday Market**: a [FastAPI](https://fastapi.tiangolo.com) backend with [SQLAlchemy](https://www.sqlalchemy.org) models, [Alembic](https://alembic.sqlalchemy.org) migrations and a Postgres database. It serves the customer storefront and the admin portal of [storefront-frontend](https://github.com/RaunakDasgupta/storefront-frontend).

- **Swagger UI** at `/docs` (and ReDoc at `/redoc`): every route is documented, with an **Authorize** button for the login token. (The Swagger page loads its script from a CDN, so the machine showing it needs internet; the API itself does not.)
- **Postgres anywhere**: point `DATABASE_URL` at a database on another machine. The schema is created by migrations, which the API runs on start.
- **CSV / Excel import with validation**: the catalog sheet (`SKU`, `Current Sales Price`, `Brand`, `quantity`...) is checked row by row on the server.

## Run it (Postgres on another machine)

You need Python 3.11+ and an **empty** Postgres database that this machine can reach (for example `createdb storefront`, or ask whoever runs the database server to create it and a user for you).

```bash
git clone https://github.com/RaunakDasgupta/storefront-backend.git
cd storefront-backend
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                   # then open .env and set DATABASE_URL (see below)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs**. On the first start the API creates every table (`alembic upgrade head`) and fills the empty database with the demo accounts, the sample catalog and a week of orders. It says so if it cannot reach the database, and it never seeds a database that already has products or orders. For development add `--reload` to the `uvicorn` command so it restarts when you change the code.

The backend is its own program: it needs nothing from the frontend, and the frontend needs nothing but its URL. Start, stop and restart them independently.

### `DATABASE_URL`

```
postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

`postgres://` and `postgresql://` URLs are accepted as they are (the psycopg 3 driver is used). Add `?sslmode=require` if the server insists on SSL. The server must accept connections from this machine (`listen_addresses` and `pg_hba.conf` on the database machine).

## Connect the frontend (a separate program)

The frontend is [storefront-frontend](https://github.com/RaunakDasgupta/storefront-frontend), started on its own in another terminal. It only needs the address of this API:

```bash
cd storefront-frontend
npm install
cp .env.example .env.local             # then set:  VITE_API_URL=http://localhost:8000/api/v1
npm run dev                            # storefront on http://localhost:5173, admin on /admin
```

(`VITE_API_URL` can also be set for one run: `VITE_API_URL=http://localhost:8000/api/v1 npm run dev`. Restart `npm run dev` after changing it.) Without `VITE_API_URL` the frontend runs on its own built-in sample data, so it works with the backend off.

- **API on another machine:** use that machine's address, for example `VITE_API_URL=http://192.168.1.20:8000/api/v1`, and add the frontend's address to `CORS_ORIGINS` in this repo's `.env` (or `*` while demoing), then restart the API.
- **Frontend shown from another machine:** `npm run dev -- --host` makes it reachable on your network. The browser then calls the API at `VITE_API_URL`, so that must be an address the browser can reach, not `localhost`.
- **A built frontend:** `VITE_API_URL=https://api.example.com/api/v1 npm run build`. The URL is baked in at build time.

## Demo logins

| Who | Sign in at | Email / ID | Password |
|---|---|---|---|
| Customer | storefront (login popup) | `customer@storefront.test` | `customer123` |
| Admin | `/admin/login` | `admin@storefront.test` or `EMP-1001` | `admin1234` |

Three more customers (`liam.chen@example.com`, `sofia.rossi@example.com`, `noah.williams@example.com`) use `customer123`. **Change or remove these before putting a server on the internet** (`SEED_DEMO_DATA=false`, and set your own `SECRET_KEY`).

Dummy payments: `4242 4242 4242 4242` is approved, `4000 0000 0000 0002` is declined, `4000 0000 0000 9995` has insufficient funds (any future expiry, any code). No money moves, and card numbers and codes are never stored.

## The API

All routes are under `/api/v1`. Errors are always `{ "message": "..." }`. Tokens come from a login and go in `Authorization: Bearer <token>`.

| Route | Who | What |
|---|---|---|
| `GET /health` | anyone | Is the API and its database up |
| `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | customers | Sign up (signs in), log in, who am I |
| `POST /admin/auth/login`, `GET /admin/auth/me` | admins | Log in with an email or employee ID |
| `GET /products` | anyone | The catalog |
| `POST /products` | admin | Add a product (409 if the SKU exists) |
| `PATCH /products/{id}` | admin | Edit (only the fields sent change; `null` clears `size`, `was`, `image`) |
| `DELETE /products/{id}`, `POST /products/{id}/restore` | admin | Soft delete and Undo |
| `POST /products/import/validate` | admin | Check a `.csv` / `.xlsx` file, nothing is saved |
| `POST /products/import/file` | admin | Check and import a file (rows with problems are skipped) |
| `POST /products/import` | admin | Import rows (what `validate` and `/import/connect` return) |
| `POST /import/connect` | admin | Read the catalog from PostgreSQL, AWS RDS (PostgreSQL) or SQLite |
| `POST /payments` | customer | The dummy card gateway, returns a payment `ref` |
| `POST /orders` | customer | Checkout: needs the `ref`, creates one order per channel |
| `GET /orders` | customer / admin | A customer's own orders, or all of them for an admin |
| `PATCH /orders/{id}` | admin | Change the status (step 0 to 3) |
| `DELETE /orders/{id}`, `POST /orders/{id}/restore` | admin | Soft delete and Undo |

### What the server decides

- **Prices and stock.** `POST /orders` ignores the names and prices the browser sends: it prices the cart from its own catalog, refuses what is out of stock, and takes the stock. The payment must belong to the customer, be successful, unused, and for exactly that total.
- **Soft deletes.** Deleting a product or an order hides it (the Undo buttons call `/restore`), so old orders keep their items. A deleted order's stock is not put back.
- **Roles.** Customers and admins share one `users` table with a `role`. Each can only use its own login route and routes.

## The catalog sheet (CSV or Excel)

`samples/Unilever_storefront_products.csv` is a complete example (40 SKUs: 20 products in a small pack, marked `retail`, and a larger pack, marked `bulk`, with stock in several locations). One row per SKU, or one row per SKU **and stock location**. Header names are not case sensitive, and spaces, dashes and underscores are interchangeable. Unknown columns are ignored.

| Column | Required | Notes |
|---|---|---|
| `SKU` | yes | Unique (any capitals). The product name and size come from it when there is no `Name` column: `10014-Bru Gold Coffee 100g` is *Bru Gold Coffee*, *100g*. |
| `Current Sales Price` | yes | A number, `249` or `₹1,249`. |
| `PID`, `Country`, `Business Group`, `Category`, `Brand`, `SubBrand`, `Segment`, `Form` | no | Descriptive. `Category` defaults to `General`. |
| `system_id`, `location_id` | no | Where the stock sits, for example `AUTOSTORE` and `AS_BIN_A`. Defaults to `DEFAULT`. |
| `quantity` | no | A whole number, blank means 0. |
| `uom` | no | Unit of measure, defaults to `EA` (each). |
| `status` | no | `AVAILABLE` (default), `BLOCKED`, `DAMAGED`, `HOLD` or `QUARANTINE`. **Only AVAILABLE stock can be sold.** |
| `Name`, `Size`, `Channel` (`retail` / `bulk`), `Compare At Price`, `Description`, `Logo URL`, `Stock` | no | Optional extras. `Stock` is used only when the sheet has no stock-location columns. |

Rules, checked row by row (a bad row is skipped and reported with its spreadsheet line number; a bad file comes back with `fatal` set):

- SKU present and at most 120 characters; price a number of 0 or more; `quantity` a whole number of 0 or more; `status` one of the list above; `channel` retail or bulk; `Logo URL` a full https link or a `/products/` file.
- The same SKU on several rows is **one product with several stock locations**; its stock is the AVAILABLE quantity added up. The same SKU and the same location twice, or the same SKU twice with no location, is reported.
- `.csv` (comma, semicolon or tab separated; UTF-8 or Excel's Windows encoding) and `.xlsx`. Old `.xls` is refused with a hint. At most 1000 rows and 5 MB.
- Importing adds new SKUs and updates existing ones (matched by SKU). It never deletes, and a blank description, size or logo never wipes what is there. Each import that saves something is recorded in `import_jobs`.

Importing from a database reads **one table** the same way: the column names are the same as the sheet's. PostgreSQL and AWS RDS (PostgreSQL) connect for real (read-only, 15 s limit, the password never appears in an error); SQLite reads a file inside `IMPORT_SQLITE_DIR`. S3, Google Cloud Storage, Cloud SQL and BigQuery answer `501` until they are added.

## The database and migrations

| Table | Holds |
|---|---|
| `users` | Customers and admins (`role`), password hashes (bcrypt), optional `employee_id` |
| `products` | One row per SKU: price, `stock`, channel, category and the sheet's Brand / SubBrand / Segment / Form / Country / Business Group / PID |
| `stock_locations` | The sheet's `system_id`, `location_id`, `quantity`, `uom`, `status` per product |
| `orders`, `order_items` | Orders (visible number `ORD_` + id, starting at 1001), the delivery address, and the lines with the name and price at the time |
| `payments` | Dummy gateway charges (last 4 digits only) |
| `import_jobs` | A record of every import that changed the catalog |

Migrations are in `migrations/versions`. They run on start (`AUTO_MIGRATE=true`), or by hand: `python -m app.db.migrate`. Change a model, then:

```bash
alembic revision --autogenerate -m "add a column"   # generates the migration from the models: read it before you commit it
python -m app.db.migrate                            # applies it (the API also does this on start)
python -m app.db.migrate --check                    # fails if the models and the migrations disagree
```

Alembic cannot see expression indexes, so the case-insensitive unique indexes (`lower(email)`, `lower(sku)`) are written by hand in the first migration.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                  # on SQLite, a few seconds
TEST_WITH_POSTGRES=1 pytest             # on a real Postgres (an embedded one, nothing to install)
```

Both build the database with the Alembic migrations and cover login and roles, the catalog, the import validation (CSV and Excel), checkout, payments and the database sources. `TEST_DATABASE_URL=postgresql://...` runs them on a Postgres you already have.

## Layout

```
app/
  main.py            the FastAPI app: CORS, Swagger text, startup (migrate + seed)
  core/              settings (.env), error shape, passwords and tokens
  db/                engine and session, migrate.py (alembic from code), seed.py (demo data)
  models/            SQLAlchemy tables
  schemas/           request and response models (camelCase JSON, validation)
  services/          the logic: products, orders, payments, users, catalog_sheet (the sheet rules), readers (CSV/Excel), importing/
  api/               routes (one file per area) and the sign-in dependencies
migrations/          Alembic
samples/             the sample catalog sheet
tests/
```

## Not done yet

No rate limiting on login, no email verification or password reset, no refresh tokens (a token lasts `ACCESS_TOKEN_MINUTES`), and the payment gateway is a dummy. Add those before real customers use it.
