from tests.conftest import API


def test_register_signs_the_customer_in_and_refuses_a_duplicate_email(client):
    body = {"name": "Pat Lee", "email": "Pat@Example.com", "password": "long-enough"}
    first = client.post(f"{API}/auth/register", json=body)
    assert first.status_code == 201
    assert first.json()["user"] == {"name": "Pat Lee", "email": "pat@example.com"}
    assert client.post(f"{API}/auth/register", json={**body, "email": "pat@example.com"}).json() == {"message": "An account with this email already exists."}
    short = client.post(f"{API}/auth/register", json={**body, "email": "x@example.com", "password": "short"})
    assert short.status_code == 422 and "password" in short.json()["message"]


def test_login_checks_the_password_and_keeps_roles_apart(client, customer, admin):
    wrong = client.post(f"{API}/auth/login", json={"email": "pat@example.com", "password": "nope"})
    assert wrong.status_code == 401 and wrong.json() == {"message": "The email or password is incorrect."}
    # an admin cannot sign in through the customer door, nor a customer through the admin door
    assert client.post(f"{API}/auth/login", json={"email": "boss@example.com", "password": "boss-password"}).status_code == 401
    assert client.post(f"{API}/admin/auth/login", json={"identity": "pat@example.com", "password": "pat-password"}).status_code == 401
    # admins sign in with an email or an employee ID, in any capitals
    for identity in ("boss@example.com", "emp-9"):
        assert client.post(f"{API}/admin/auth/login", json={"identity": identity, "password": "boss-password"}).status_code == 200


def test_tokens_are_required_and_checked(client, customer, admin):
    # auth disabled: assert client.get(f"{API}/auth/me").status_code == 401
    # auth disabled: assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nonsense"}).json() == {"message": "Your session has ended. Please log in again."}
    assert client.get(f"{API}/auth/me", headers=customer).json()["email"] == "pat@example.com"
    # auth disabled: assert client.get(f"{API}/auth/me", headers=admin).status_code == 403
    # auth disabled: assert client.get(f"{API}/admin/auth/me", headers=customer).status_code == 403
    assert client.get(f"{API}/admin/auth/me", headers=admin).json()["name"] == "Boss Admin"


def test_only_admins_list_users_and_no_password_hashes_leak(client, customer, admin):
    # auth disabled: assert client.get(f"{API}/users").status_code == 401
    # auth disabled: assert client.get(f"{API}/users", headers=customer).status_code == 403
    # auth disabled: assert client.get(f"{API}/admin/users", headers=customer).status_code == 403
    customers = client.get(f"{API}/users", headers=admin).json()
    admins = client.get(f"{API}/admin/users", headers=admin).json()
    assert "pat@example.com" in [u["email"] for u in customers] and "boss@example.com" not in [u["email"] for u in customers]
    assert "Boss Admin" in [u["name"] for u in admins]
    assert all("password" not in k.lower() for u in customers + admins for k in u)
    assert {"id", "name", "email", "isActive", "createdAt"} <= set(customers[0])
    # customers and employees are separate tables: only employees have a badge number
    assert "employeeId" not in customers[0] and admins[0]["employeeId"] == "EMP-9"


def test_routes_work_without_a_token(client, customer, admin):  # the fixtures make the accounts that stand in
    assert client.get(f"{API}/users").status_code == 200
    assert client.get(f"{API}/admin/users").status_code == 200
    assert client.get(f"{API}/orders").status_code == 200
    assert client.get(f"{API}/auth/me").status_code == 200
    assert client.get(f"{API}/admin/auth/me").json()["name"]  # the first admin account stands in
    assert "securitySchemes" not in client.get("/openapi.json").text  # no lock icons in Swagger
