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
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nonsense"}).json() == {"message": "Your session has ended. Please log in again."}
    assert client.get(f"{API}/auth/me", headers=customer).json()["email"] == "pat@example.com"
    assert client.get(f"{API}/auth/me", headers=admin).status_code == 403
    assert client.get(f"{API}/admin/auth/me", headers=customer).status_code == 403
    assert client.get(f"{API}/admin/auth/me", headers=admin).json()["name"] == "Boss Admin"
