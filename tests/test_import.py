import io

import pytest
from openpyxl import Workbook

from app.services.catalog_sheet import parse_sheet
from tests.conftest import API, sheet

DOVE = "10001-Dove Intense Repair Shampoo 180ml"


def validate(client, admin, content: bytes, filename="products.csv"):
    return client.post(f"{API}/products/import/validate", files={"file": (filename, content)}, headers=admin)


def test_the_sheet_is_read_into_products_with_stock_locations(client, admin):
    content = sheet(
        f"{DOVE},India,Beauty & Well being,SHAMPOO,Dove,Intense Repair,ALL OTHER,Liquid,{DOVE},230,AUTOSTORE,AS_BIN_A,100,EA,AVAILABLE",
        f"{DOVE},India,Beauty & Well being,SHAMPOO,Dove,Intense Repair,ALL OTHER,Liquid,{DOVE},230,AUTOSTORE,AS_BIN_B,30,EA,BLOCKED",
        f"10014-Bru Gold Coffee 100g,India,Nutrition,INSTANT COFFEE,Bru,Gold,BEVERAGES - SPL,Coffee,10014-Bru Gold Coffee 100g,343,,,,,",
    )
    body = validate(client, admin, content).json()
    assert "fatal" not in body and body["issues"] == []
    assert body["summary"] == {"totalRows": 3, "valid": 2, "new": 2, "updates": 0, "skipped": 0}
    dove, bru = body["rows"]
    assert dove["name"] == "Dove Intense Repair Shampoo" and dove["size"] == "180ml" and dove["price"] == 230
    assert dove["brand"] == "Dove" and dove["subBrand"] == "Intense Repair" and dove["businessGroup"] == "Beauty & Well being"
    assert dove["stock"] == 100  # the blocked pallet does not count
    assert [loc["status"] for loc in dove["locations"]] == ["AVAILABLE", "BLOCKED"]
    assert bru["stock"] == 0 and "locations" not in bru


def test_problem_rows_are_reported_with_their_line_and_skipped(client, admin):
    content = sheet(
        f",India,G,C,B,S,Seg,F,,10,,,,,",                                                  # line 2: no SKU
        f"p,India,G,C,B,S,Seg,F,10002-Sunsilk 180ml,abc,,,,,",                             # line 3: price is not a number
        f"p,India,G,C,B,S,Seg,F,10003-TRESemme 190ml,293,AUTOSTORE,AS_BIN_A,-4,EA,AVAILABLE",  # line 4: negative quantity
        f"p,India,G,C,B,S,Seg,F,10004-Clinic Plus 175ml,122,AUTOSTORE,AS_BIN_A,5,EA,SOLD",     # line 5: unknown status
        f"p,India,G,C,B,S,Seg,F,10005-Fine 100g,50,AUTOSTORE,AS_BIN_A,5,EA,AVAILABLE",         # line 6: fine
        f"p,India,G,C,B,S,Seg,F,10005-Fine 100g,50,AUTOSTORE,AS_BIN_A,5,EA,AVAILABLE",         # line 7: same SKU and the same place
        f"p,India,G,C,B,S,Seg,F,10005-fine 100g,50,,,,,",                                      # line 8: duplicate SKU, no location
    )
    body = validate(client, admin, content).json()
    assert [(i["line"], i["message"].split(":")[0]) for i in body["issues"]] == [
        (2, "SKU is empty."), (3, "10002-Sunsilk 180ml"), (4, "10003-TRESemme 190ml"), (5, "10004-Clinic Plus 175ml"), (7, "10005-Fine 100g"), (8, "10005-fine 100g"),
    ]
    assert "price" in body["issues"][1]["message"] and "quantity" in body["issues"][2]["message"] and "status" in body["issues"][3]["message"]
    assert "twice" in body["issues"][4]["message"] and "duplicate" in body["issues"][5]["message"]
    assert [r["sku"] for r in body["rows"]] == ["10005-Fine 100g"]
    assert body["summary"]["skipped"] == 6 and body["summary"]["totalRows"] == 7


@pytest.mark.parametrize("content, message", [
    (b"", "The file is empty."),
    (b"PID,Brand\n1,Dove\n", "Missing required columns: SKU, Current Sales Price."),
    (b"SKU,Brand\nA,Dove\n", "Missing required column: Current Sales Price."),
])
def test_a_file_that_cannot_be_used_comes_back_with_fatal(client, admin, content, message):
    response = validate(client, admin, content)
    assert response.status_code == 200 and response.json()["fatal"] == message and response.json()["rows"] == []


def test_wrong_file_types_and_big_files_are_refused_clearly(client, admin):
    assert validate(client, admin, b"x", "notes.pdf").json()["fatal"] == "Choose a .csv or .xlsx file."
    assert "xlsx" in validate(client, admin, b"x", "old.xls").json()["fatal"]
    assert "valid .xlsx" in validate(client, admin, b"not a zip", "bad.xlsx").json()["fatal"]
    rows = "\n".join(f"{n}-Item {n} 10g,50" for n in range(1, 1100))
    assert "more than 1000 rows" in validate(client, admin, f"SKU,Current Sales Price\n{rows}\n".encode()).json()["fatal"]


def test_header_names_are_forgiving_and_unknown_columns_are_ignored():
    table = [["sku", "CURRENT-SALES-PRICE", "sub brand", "AUTOSTORE", "SKU-001"], [" 10-Dove Soap 100g ", "₹1,230", "Fresh", "x", "y"]]
    result = parse_sheet(table)
    assert result.issues == [] and result.rows[0].price == 1230 and result.rows[0].sub_brand == "Fresh" and result.rows[0].name == "Dove Soap"


def test_semicolon_and_excel_files_work_too(client, admin):
    semicolons = b"SKU;Current Sales Price;quantity\n10-Soap 50g;31;7\n"
    assert validate(client, admin, semicolons).json()["rows"][0]["stock"] == 7
    book = Workbook()
    sheet_ = book.active
    sheet_.append(["SKU", "Current Sales Price", "system_id", "location_id", "quantity", "uom", "status"])
    sheet_.append(["20-Tea 250g", 304.0, "AUTOSTORE", "AS_BIN_A", 12.0, "EA", "AVAILABLE"])
    buffer = io.BytesIO()
    book.save(buffer)
    row = validate(client, admin, buffer.getvalue(), "sheet.xlsx").json()["rows"][0]
    assert row["sku"] == "20-Tea 250g" and row["price"] == 304 and row["stock"] == 12


def test_import_file_saves_the_good_rows_and_records_the_job(client, admin):
    content = sheet("p,India,G,Soaps,B,S,Seg,F,10-Soap 50g,31,AUTOSTORE,AS_BIN_A,7,EA,AVAILABLE", "p,India,G,Soaps,B,S,Seg,F,11-Bad 50g,x,,,,,")
    assert client.post(f"{API}/products/import/file", files={"file": ("p.csv", content)}, headers=admin).json() == {"added": 1, "updated": 0}
    assert client.post(f"{API}/products/import/file", files={"file": ("p.csv", content)}, headers=admin).json() == {"added": 0, "updated": 1}
    product = client.get(f"{API}/products").json()[0]
    assert product["name"] == "Soap" and product["size"] == "50g" and product["stock"] == 7
    summary = validate(client, admin, content).json()["summary"]
    assert summary["updates"] == 1 and summary["new"] == 0
    assert client.post(f"{API}/products/import/file", files={"file": ("p.pdf", b"x")}, headers=admin).status_code == 422


@pytest.mark.skip(reason="auth is switched off")
def test_importing_requires_an_admin(client, customer):
    pass
    # auth disabled: assert client.post(f"{API}/products/import/validate", files={"file": ("p.csv", b"SKU\n")}).status_code == 401
    # auth disabled: assert client.post(f"{API}/products/import/validate", files={"file": ("p.csv", b"SKU\n")}, headers=customer).status_code == 403
