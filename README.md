# storefront-backend

The API behind **Everyday Market**, for the [storefront-frontend](https://github.com/RaunakDasgupta/storefront-frontend) customer storefront and admin portal. FastAPI, SQLAlchemy and Postgres.

- Swagger UI at `/docs` (ReDoc at `/redoc`) documents every route, with an **Authorize** button for the login token. The page loads its script from a CDN, so the browser needs internet; the API does not.
- SQLAlchemy creates and updates the tables on start. There is no migration tool.
- The catalog sheet (CSV or Excel) is validated row by row on the server.

## Quick start

You need Python 3.11+ and an **empty** Postgres database this machine can reach (it can be on another machine).

```bash
git clone https://github.com/RaunakDasgupta/storefront-backend.git
cd storefront-backend
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                   # set DATABASE_URL in it
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs**. On the first start the API creates the tables and, if the database is empty, loads the demo accounts, the sample catalog and a week of orders. It never seeds a database that already has products or orders, and it says so if it cannot reach the database. Add `--reload` while developing.

### Settings (`.env`)

| Setting | Default | |
|---|---|---|
| `DATABASE_URL` | local Postgres | `postgresql://USER:PASSWORD@HOST:5432/DATABASE`. `postgres://` works too, and `?sslmode=require` if the server wants SSL. The server must accept connections from this machine (`listen_addresses`, `pg_hba.conf`). |
| `CORS_ORIGINS` | the Vite dev URLs | Addresses allowed to call the API, comma separated, or `*`. |
| `SECRET_KEY` | a dev key | Signs login tokens. **Set your own.** |
| `ACCESS_TOKEN_MINUTES` | `720` | How long a login lasts. |
| `AUTO_CREATE_SCHEMA` | `true` | Create and update the tables on start. |
| `SEED_DEMO_DATA` | `true` | Fill an empty database with demo data on start. |
| `IMPORT_SQLITE_DIR` | `./data/import` | Folder the admin's "SQLite" import source may read from. |

`.env.example` has them all, and any of them can be a normal environment variable instead.

## Connect the frontend

The frontend is a separate program started in its own terminal. It only needs this API's address:

```bash
cd storefront-frontend
npm install
cp .env.example .env.local             # set VITE_API_URL=http://localhost:8000/api/v1
npm run dev                            # storefront on :5173, admin on /admin
```

Without `VITE_API_URL` the frontend uses its own sample data and works with the backend off. Restart `npm run dev` after changing it.

- **API on another machine:** use its address in `VITE_API_URL`, and add the frontend's address to `CORS_ORIGINS` here.
- **Frontend shown to other machines:** `npm run dev -- --host`. `VITE_API_URL` must then be an address their browsers can reach, not `localhost`.
- **Production build:** `VITE_API_URL=https://api.example.com/api/v1 npm run build` (the URL is baked in).

## Demo logins

The same accounts are in the descriptions of the two login routes in Swagger.

| Who | Email / ID | Password |
|---|---|---|
| Customer | `customer@storefront.test` | `customer123` |
| More customers | `liam.chen@example.com`, `sofia.rossi@example.com`, `noah.williams@example.com` | `customer123` |
| Admin (log in at `/admin/login`) | `admin@storefront.test` or `EMP-1001` | `admin1234` |

Dummy payments: card `4242 4242 4242 4242` is approved, `4000 0000 0000 0002` is declined, `4000 0000 0000 9995` has insufficient funds (any future expiry and code). No money moves and card numbers are never stored.

Before putting a server on the internet: set `SEED_DEMO_DATA=false` and your own `SECRET_KEY`, and remove the demo accounts.

## API

All routes are under `/api/v1`. Errors are always `{ "message": "..." }`. Send the token from a login as `Authorization: Bearer <token>`.

| Route | Who | What |
|---|---|---|
| `GET /health` | anyone | Is the API and its database up |
| `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | customers | Sign up (signs in), log in, who am I |
| `POST /admin/auth/login`, `GET /admin/auth/me` | admins | Log in with an email or employee ID |
| `GET /users` | admin | List customers |
| `GET /admin/users` | admin | List admin users |
| `GET /products` | anyone | The catalog |
| `POST /products` | admin | Add a product (409 if the SKU exists) |
| `PATCH /products/{id}` | admin | Edit; only the fields sent change, `null` clears `size`, `was`, `image` |
| `DELETE /products/{id}`, `POST /products/{id}/restore` | admin | Soft delete and Undo |
| `POST /products/import/validate` | admin | Check a `.csv` / `.xlsx` file, nothing is saved |
| `POST /products/import/file` | admin | Check and import a file (bad rows are skipped) |
| `POST /products/import` | admin | Import rows (what `validate` and `/import/connect` return) |
| `POST /import/connect` | admin | Read the catalog from PostgreSQL, AWS RDS (PostgreSQL) or SQLite |
| `POST /payments` | customer | The dummy card gateway, returns a payment `ref` |
| `POST /orders` | customer | Checkout: needs the `ref`, creates one order per channel |
| `GET /orders` | customer / admin | The customer's own orders, or everyone's for an admin |
| `PATCH /orders/{id}` | admin | Change the status (step 0 to 3) |
| `DELETE /orders/{id}`, `POST /orders/{id}/restore` | admin | Soft delete and Undo |

The server decides what matters:

- **Prices and stock.** `POST /orders` ignores the names and prices the browser sends. It prices the cart from its own catalog, refuses what is out of stock and takes the stock. The payment must belong to the customer, be successful, unused, and for exactly that total.
- **Soft deletes.** Deleting a product or order hides it, so old orders keep their items. A deleted order's stock is not put back.
- **Roles.** Customers and admins share one `users` table with a `role`. Each can only use its own login and routes. The user lists never include password hashes.

## The catalog sheet (CSV or Excel)

`samples/Unilever_storefront_products.csv` is a full example: 40 SKUs, 20 products in a small `retail` pack and a larger `bulk` pack, with stock in several locations. Use one row per SKU, or one row per SKU **and stock location**. Header names ignore capitals, and spaces, dashes and underscores are interchangeable. Unknown columns are ignored.

| Column | Required | Notes |
|---|---|---|
| `SKU` | yes | Unique, any capitals. Without a `Name` column the name and size come from it: `10014-Bru Gold Coffee 100g` is *Bru Gold Coffee*, *100g*. |
| `Current Sales Price` | yes | A number: `249` or `₹1,249`. |
| `PID`, `Country`, `Business Group`, `Category`, `Brand`, `SubBrand`, `Segment`, `Form` | no | Descriptive. `Category` defaults to `General`. |
| `system_id`, `location_id` | no | Where the stock sits, for example `AUTOSTORE` and `AS_BIN_A`. Default `DEFAULT`. |
| `quantity` | no | A whole number; blank is 0. |
| `uom` | no | Unit of measure, default `EA`. |
| `status` | no | `AVAILABLE` (default), `BLOCKED`, `DAMAGED`, `HOLD` or `QUARANTINE`. **Only AVAILABLE stock can be sold.** |
| `Name`, `Size`, `Channel` (`retail` / `bulk`), `Compare At Price`, `Description`, `Logo URL`, `Stock` | no | Optional. `Stock` is used only when the sheet has no stock-location columns. |

Checked row by row. A bad row is skipped and reported with its spreadsheet line number; a bad file comes back with `fatal` set.

- SKU present and at most 120 characters; price a number of 0 or more; `quantity` a whole number of 0 or more; `status` from the list; `channel` retail or bulk; `Logo URL` a full https link or a `/products/` file.
- The same SKU on several rows is **one product with several stock locations**, and its stock is the AVAILABLE quantity added up. The same SKU and location twice, or the same SKU twice with no location, is reported.
- `.csv` (comma, semicolon or tab; UTF-8 or Excel's Windows encoding) and `.xlsx`. Old `.xls` is refused. At most 1000 rows and 5 MB.
- Importing adds new SKUs and updates existing ones by SKU. It never deletes, and a blank description, size or logo never wipes what is there. Each import that saves something is recorded in `import_jobs`.

Importing from a database reads **one table** the same way, with the same column names. PostgreSQL and AWS RDS (PostgreSQL) connect for real (read-only, 15 s limit, the password never appears in an error). SQLite reads a file inside `IMPORT_SQLITE_DIR`. S3, Google Cloud Storage, Cloud SQL and BigQuery answer `501` until they are added.

## The database

| Table | Holds |
|---|---|
| `users` | Customers and admins (`role`), bcrypt password hashes, optional `employee_id` |
| `products` | One row per SKU: price, `stock`, channel, category and the sheet's descriptive columns |
| `stock_locations` | `system_id`, `location_id`, `quantity`, `uom`, `status` per product |
| `orders`, `order_items` | Orders (visible number `ORD_` + id, from 1001), the delivery address, and the lines with the name and price at the time |
| `payments` | Dummy gateway charges (last 4 digits only) |
| `import_jobs` | A record of every import that changed the catalog |

SQLAlchemy alone manages the schema. On start (`AUTO_CREATE_SCHEMA=true`) [`create_schema`](app/db/schema.py) creates every missing table with its indexes and constraints, then adds any column or index that a model has and the existing table lacks. So adding a column or table is: edit the model, restart. By hand:

```bash
python -m app.db.schema            # create / update the tables
python -m app.db.schema --check    # only report what is missing; exit code 1 if anything is
```

It does **not** rename, drop or retype columns, or touch data: do those in SQL. A new `NOT NULL` column with no `server_default` is added as nullable, with a warning in the log, because existing rows have no value for it; fill it in and set `NOT NULL` yourself. A database made by an earlier Alembic version works as it is; its leftover `alembic_version` table is harmless.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                  # on SQLite, a few seconds
TEST_WITH_POSTGRES=1 pytest             # on a real, embedded Postgres (nothing to install)
```

`TEST_DATABASE_URL=postgresql://...` runs them on a Postgres you already have. They cover login and roles, the user lists, the catalog, import validation (CSV and Excel), checkout, payments, the database sources and the schema sync.

## Layout

```
app/
  main.py        the FastAPI app: CORS, startup (create tables, seed)
  core/          settings, error shape, passwords and tokens
  db/            engine and session, schema.py (create/update tables), seed.py (demo data)
  models/        SQLAlchemy tables
  schemas/       request and response models (camelCase JSON, validation)
  services/      the logic: products, orders, payments, users, the sheet rules, CSV/Excel readers, importing/
  api/           routes (one file per area) and the sign-in dependencies
samples/         the sample catalog sheet
tests/
```

## Not done yet

No rate limiting on login, no email verification or password reset, no refresh tokens (a token lasts `ACCESS_TOKEN_MINUTES`), and the payment gateway is a dummy. Add those before real customers use it.
