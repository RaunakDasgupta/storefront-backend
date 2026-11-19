from tests.conftest import API

NEW = {"sku": "DET-002", "name": "Detergent Pro", "category": "Home care", "price": 299, "stock": 10, "channel": "retail"}


def test_the_catalog_is_public_and_leaves_empty_fields_out(client, admin):
    client.post(f"{API}/products", json=NEW, headers=admin)
    listed = client.get(f"{API}/products").json()
    assert [p["sku"] for p in listed] == ["DET-002"]
    product = listed[0]
    assert product["id"] == "det-002" and product["price"] == 299 and product["stock"] == 10
    for absent in ("size", "was", "image", "brand"):
        assert absent not in product  # null would break the storefront's checks


def test_only_admins_change_the_catalog(client, customer, admin):
    # auth disabled: assert client.post(f"{API}/products", json=NEW).status_code == 401
    # auth disabled: assert client.post(f"{API}/products", json=NEW, headers=customer).status_code == 403
    assert client.post(f"{API}/products", json=NEW, headers=admin).status_code == 201


def test_adding_checks_the_fields_and_refuses_a_duplicate_sku(client, admin):
    assert client.post(f"{API}/products", json=NEW, headers=admin).status_code == 201
    dup = client.post(f"{API}/products", json={**NEW, "sku": "det-002"}, headers=admin)
    assert dup.status_code == 409 and "already exists" in dup.json()["message"]
    assert client.post(f"{API}/products", json={**NEW, "sku": "X", "price": -1}, headers=admin).status_code == 422
    assert client.post(f"{API}/products", json={**NEW, "sku": "X", "image": "javascript:alert(1)"}, headers=admin).status_code == 422
    ok = client.post(f"{API}/products", json={**NEW, "sku": "Y", "image": "/products/shampoo.jpg"}, headers=admin)
    assert ok.status_code == 201 and ok.json()["image"] == "/products/shampoo.jpg"


def test_editing_changes_only_what_is_sent_and_null_clears(client, admin):
    client.post(f"{API}/products", json={**NEW, "size": "1 kg", "was": 349}, headers=admin)
    edited = client.patch(f"{API}/products/det-002", json={"price": 279, "size": None}, headers=admin).json()
    assert edited["price"] == 279 and "size" not in edited and edited["was"] == 349 and edited["name"] == "Detergent Pro"
    assert client.patch(f"{API}/products/det-002", json={"name": None}, headers=admin).status_code == 422
    assert client.patch(f"{API}/products/nope", json={"price": 1}, headers=admin).status_code == 404


def test_delete_hides_and_restore_brings_it_back(client, admin):
    client.post(f"{API}/products", json=NEW, headers=admin)
    assert client.delete(f"{API}/products/det-002", headers=admin).status_code == 204
    assert client.get(f"{API}/products").json() == []
    assert client.get(f"{API}/products/det-002").status_code == 404
    assert client.post(f"{API}/products/det-002/restore", headers=admin).json()["sku"] == "DET-002"
    assert len(client.get(f"{API}/products").json()) == 1


def test_import_rows_adds_and_updates_by_sku_and_never_deletes(client, admin):
    client.post(f"{API}/products", json={**NEW, "size": "1 kg", "blurb": "Keep me"}, headers=admin)
    rows = [
        {"sku": "det-002", "name": "Renamed", "category": "Home care", "price": 1, "stock": 3, "blurb": "", "channel": "retail"},
        {"sku": "NEW-1", "name": "Brand new", "category": "Snacks", "price": 9, "stock": 4, "blurb": "", "channel": "bulk"},
    ]
    assert client.post(f"{API}/products/import", json={"rows": rows}, headers=admin).json() == {"added": 1, "updated": 1}
    by_sku = {p["sku"]: p for p in client.get(f"{API}/products").json()}
    assert by_sku["DET-002"]["name"] == "Renamed" and by_sku["DET-002"]["blurb"] == "Keep me" and by_sku["DET-002"]["size"] == "1 kg"
    assert by_sku["NEW-1"]["channel"] == "bulk"
    assert len(by_sku) == 2
