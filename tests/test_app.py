import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import app  # noqa: E402
from models import Admin, Book, Category, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


class StoreSmokeTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            category = Category(name="USMLE", slug="usmle")
            db.session.add(category)
            db.session.flush()
            db.session.add(Book(title="Step Review", slug="step-review", author="Faculty", description="Focused review material.", price=2500, image_url="/static/images/cover-usmle.svg", category_id=category.id, featured=True, in_stock=True))
            db.session.add(Admin(email="admin@test.com", password_hash=generate_password_hash("secret123")))
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def csrf(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "test-token"
        return "test-token"

    def test_public_pages(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/books?q=Step").status_code, 200)
        response = self.client.get("/books/step-review")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Order via WhatsApp", response.data)

    def test_admin_login_and_create_book(self):
        token = self.csrf()
        response = self.client.post("/admin/login", data={"csrf_token": token, "email": "admin@test.com", "password": "secret123"})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = token
        response = self.client.post("/admin/books/new", data={"csrf_token": token, "title": "New Clinical Guide", "author": "Dr Test", "description": "A useful clinical guide.", "price": "1900", "category_id": "1", "image_url": "/static/images/cover-fcps.svg", "featured": "on", "in_stock": "on"})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertIsNotNone(Book.query.filter_by(title="New Clinical Guide").first())


if __name__ == "__main__":
    unittest.main()

