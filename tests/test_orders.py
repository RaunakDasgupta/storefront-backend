from tests.conftest import API

ADDRESS = {"fullName": "Pat Lee", "phone": "98765 43210", "line1": "12 MG Road", "line2": "", "city": "Pune", "state": "Maharashtra", "pin": "411001"}
CARD = {"number": "4242 4242 4242 4242", "name": "Pat", "expiry": "12/39", "cvc": "123"}


def add_product(client, admin, sku, price, stock, channel="retail"):
    return client.post(f"{API}/products", headers=admin, json={"sku": sku, "name": f"Item {sku}", "category": "Snacks", "price": price, "stock": stock, "channel": channel}).json()


def pay(client, headers, amount, card=None):
    return client.post(f"{API}/payments", headers=headers, json={"amount": amount, "currency": "INR", "card": card or CARD})


def checkout(client, headers, items, ref, shipping=None):
    # the browser also sends names and prices; the server must not trust them
    groups = [{"channel": "retail", "items": [{"id": i, "qty": q, "name": "x", "price": 1} for i, q in items]}]
    return client.post(f"{API}/orders", headers=headers, json={"customer": {"name": "x", "email": "x@x.com"}, "shipping": shipping or ADDRESS, "paymentRef": ref, "groups": groups})


def test_checkout_prices_from_the_catalog_takes_stock_and_splits_channels(client, admin, customer):
    add_product(client, admin, "R-1", 100, 10)
    add_product(client, admin, "B-1", 1000, 5, "bulk")
    ref = pay(client, customer, 2 * 100 + 1000).json()["ref"]
    response = checkout(client, customer, [("r-1", 2), ("b-1", 1)], ref)
    assert response.status_code == 201
    made = response.json()
    assert [o["channel"] for o in made] == ["retail", "bulk"]
    assert [o["total"] for o in made] == [200, 1000]
    assert made[0]["id"].startswith("ORD_") and made[0]["step"] == 0 and made[0]["shipping"]["city"] == "Pune"
    assert made[0]["customer"] == {"name": "Pat Lee", "email": "pat@example.com"}
    assert made[0]["items"] == [{"id": "r-1", "name": "Item R-1", "qty": 2, "price": 100}]
    stock = {p["sku"]: p["stock"] for p in client.get(f"{API}/products").json()}
    assert stock == {"R-1": 8, "B-1": 4}


def test_a_payment_must_match_the_total_belong_to_the_customer_and_be_used_once(client, admin, customer, other_customer):
    add_product(client, admin, "R-1", 100, 10)
    wrong = pay(client, customer, 90).json()["ref"]
    assert checkout(client, customer, [("r-1", 1)], wrong).status_code == 409
    assert checkout(client, customer, [("r-1", 1)], "PAY_NOPE").status_code == 402
    ref = pay(client, customer, 100).json()["ref"]
    assert checkout(client, other_customer, [("r-1", 1)], ref).status_code == 402  # someone else's payment
    assert checkout(client, customer, [("r-1", 1)], ref).status_code == 201
    again = checkout(client, customer, [("r-1", 1)], ref)
    assert again.status_code == 409 and "already been used" in again.json()["message"]


def test_stock_and_missing_products_are_checked(client, admin, customer):
    add_product(client, admin, "R-1", 100, 2)
    ref = pay(client, customer, 300).json()["ref"]
    assert checkout(client, customer, [("r-1", 3)], ref).json() == {"message": "Only 2 of Item R-1 left."}
    assert checkout(client, customer, [("ghost", 1)], ref).status_code == 409
    assert client.post(f"{API}/orders", headers=customer, json={"shipping": ADDRESS, "paymentRef": ref, "groups": []}).json() == {"message": "Your cart is empty."}


def test_the_address_is_validated(client, admin, customer):
    add_product(client, admin, "R-1", 100, 2)
    ref = pay(client, customer, 100).json()["ref"]
    bad = checkout(client, customer, [("r-1", 1)], ref, shipping={**ADDRESS, "pin": "12", "phone": "123"})
    assert bad.status_code == 422 and "pin" in bad.json()["message"]


def test_declined_cards_and_bad_card_numbers(client, customer):
    declined = pay(client, customer, 100, {**CARD, "number": "4000 0000 0000 0002"})
    assert declined.status_code == 402 and "declined" in declined.json()["message"]
    assert "insufficient" in pay(client, customer, 100, {**CARD, "number": "4000000000009995"}).json()["message"]
    assert pay(client, customer, 100, {**CARD, "number": "4242 4242 4242 4243"}).status_code == 422  # fails the checksum
    assert pay(client, customer, 100, {**CARD, "expiry": "01/20"}).status_code == 422
    assert client.post(f"{API}/payments", json={"amount": 5, "card": CARD}).status_code == 401


def test_customers_see_their_own_orders_and_admins_see_all(client, admin, customer, other_customer):
    add_product(client, admin, "R-1", 100, 10)
    for headers in (customer, other_customer):
        checkout(client, headers, [("r-1", 1)], pay(client, headers, 100).json()["ref"])
    assert len(client.get(f"{API}/orders", headers=customer).json()) == 1
    everyone = client.get(f"{API}/orders", headers=admin).json()
    assert len(everyone) == 2 and everyone[0]["id"] > everyone[1]["id"]  # newest first
    assert client.get(f"{API}/orders").status_code == 401


def test_admins_change_status_and_delete_with_undo(client, admin, customer):
    add_product(client, admin, "R-1", 100, 10)
    order = checkout(client, customer, [("r-1", 1)], pay(client, customer, 100).json()["ref"]).json()[0]
    path = f"{API}/orders/{order['id']}"
    assert client.patch(path, json={"step": 2}, headers=customer).status_code == 403
    assert client.patch(path, json={"step": 9}, headers=admin).status_code == 422
    assert client.patch(path, json={"step": 2}, headers=admin).json()["step"] == 2
    assert client.get(f"{API}/orders", headers=customer).json()[0]["step"] == 2
    assert client.delete(path, headers=admin).status_code == 204
    assert client.get(f"{API}/orders", headers=customer).json() == []
    assert client.post(f"{path}/restore", headers=admin).json()["id"] == order["id"]
    assert len(client.get(f"{API}/orders", headers=customer).json()) == 1
    assert client.patch(f"{API}/orders/ORD_9999", json={"step": 1}, headers=admin).status_code == 404
    assert client.patch(f"{API}/orders/nonsense", json={"step": 1}, headers=admin).status_code == 404
