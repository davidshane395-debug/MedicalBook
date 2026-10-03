import os
import re
import secrets
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Flask, abort, flash, redirect, render_template, request, session, url_for
)
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config
from models import Admin, Book, Category, SiteSetting, db


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or secrets.token_hex(4)


def unique_slug(model, value, current_id=None):
    base = slugify(value)
    candidate, counter = base, 2
    while True:
        row = model.query.filter_by(slug=candidate).first()
        if not row or row.id == current_id:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    @app.context_processor
    def global_values():
        settings = {}
        try:
            settings = {item.key: item.value for item in SiteSetting.query.all()}
        except Exception:
            pass
        try:
            global_discount = min(100, max(0, int(float(settings.get("discount_percent", 0)))))
        except (TypeError, ValueError):
            global_discount = 0
        return {
            "site_settings": settings,
            "whatsapp": settings.get("whatsapp", os.getenv("WHATSAPP_NUMBER", "923002422099")),
            "global_discount": global_discount,
        }

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("admin_id"):
                flash("Please sign in to continue.", "error")
                return redirect(url_for("admin_login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(24)
        return session["csrf_token"]

    def validate_csrf():
        if not secrets.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "x")):
            abort(400, "Invalid security token")

    app.jinja_env.globals["csrf_token"] = csrf_token

    def save_image(file):
        if not file or not file.filename:
            return None
        extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError("Please upload a PNG, JPG, JPEG or WEBP image.")

        # Deployed/serverless environments need persistent object storage.
        # Cloudinary returns a permanent HTTPS URL which is stored in MySQL.
        if os.getenv("CLOUDINARY_URL"):
            try:
                import cloudinary
                import cloudinary.uploader

                cloudinary.config(secure=True)
                result = cloudinary.uploader.upload(
                    file.stream,
                    folder="medical-book-shop/books",
                    public_id=f"book-{uuid4().hex}",
                    resource_type="image",
                    overwrite=False,
                )
                return result["secure_url"]
            except Exception as exc:
                app.logger.exception("Cloud image upload failed")
                raise ValueError("Image upload failed. Please try again or use an image URL.") from exc

        if os.getenv("VERCEL"):
            raise ValueError("Online image storage is not configured. Add CLOUDINARY_URL in Vercel settings.")

        filename = secure_filename(f"{uuid4().hex}.{extension}")
        folder = Path(app.root_path) / app.config["UPLOAD_FOLDER"]
        try:
            folder.mkdir(parents=True, exist_ok=True)
            file.save(folder / filename)
        except OSError as exc:
            raise ValueError("This server cannot store uploaded files. Configure Cloudinary or use an image URL.") from exc
        return f"/static/uploads/{filename}"

    @app.get("/")
    def home():
        featured = Book.query.filter_by(featured=True).order_by(Book.created_at.desc()).limit(8).all()
        if len(featured) < 8:
            featured_ids = [book.id for book in featured]
            latest_query = Book.query.order_by(Book.created_at.desc())
            if featured_ids:
                latest_query = latest_query.filter(Book.id.notin_(featured_ids))
            featured.extend(latest_query.limit(8 - len(featured)).all())
        categories = Category.query.order_by(Category.name).all()
        return render_template("home.html", featured=featured, categories=categories)

    @app.get("/books")
    def books():
        search = request.args.get("q", "").strip()
        category_slug = request.args.get("category", "").strip()
        query = Book.query
        if search:
            term = f"%{search}%"
            query = query.filter(or_(Book.title.ilike(term), Book.author.ilike(term), Book.description.ilike(term)))
        if category_slug:
            query = query.join(Category).filter(Category.slug == category_slug)
        page = query.order_by(Book.featured.desc(), Book.created_at.desc()).paginate(
            page=request.args.get("page", 1, type=int), per_page=8, error_out=False
        )
        return render_template(
            "books.html", books=page, categories=Category.query.order_by(Category.name).all(),
            search=search, active_category=category_slug
        )

    @app.get("/categories")
    def category_list():
        page = Category.query.order_by(Category.name).paginate(
            page=request.args.get("page", 1, type=int), per_page=9, error_out=False
        )
        return render_template("categories.html", categories=page)

    @app.get("/books/<slug>")
    def book_detail(slug):
        book = Book.query.filter_by(slug=slug).first_or_404()
        related = Book.query.filter(Book.category_id == book.category_id, Book.id != book.id).limit(4).all()
        return render_template("book_detail.html", book=book, related=related)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if session.get("admin_id"):
            return redirect(url_for("admin_dashboard"))
        if request.method == "POST":
            validate_csrf()
            admin = Admin.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
            if admin and check_password_hash(admin.password_hash, request.form.get("password", "")):
                session.clear()
                session["admin_id"] = admin.id
                session.permanent = True
                flash("Welcome back.", "success")
                return redirect(url_for("admin_dashboard"))
            flash("Incorrect email or password.", "error")
        return render_template("admin/login.html")

    @app.post("/admin/logout")
    def admin_logout():
        validate_csrf()
        session.clear()
        return redirect(url_for("admin_login"))

    @app.get("/admin")
    @login_required
    def admin_dashboard():
        return render_template(
            "admin/dashboard.html", book_count=Book.query.count(),
            category_count=Category.query.count(), featured_count=Book.query.filter_by(featured=True).count(),
            recent=Book.query.order_by(Book.created_at.desc()).limit(6).all()
        )

    @app.get("/admin/books")
    @login_required
    def admin_books():
        return render_template("admin/books.html", books=Book.query.order_by(Book.created_at.desc()).all())

    @app.route("/admin/books/new", methods=["GET", "POST"])
    @app.route("/admin/books/<int:book_id>/edit", methods=["GET", "POST"])
    @login_required
    def admin_book_form(book_id=None):
        book = db.session.get(Book, book_id) if book_id else None
        if book_id and not book:
            abort(404)
        categories = Category.query.order_by(Category.name).all()
        if request.method == "POST":
            validate_csrf()
            try:
                image_url = request.form.get("image_url", "").strip()
                uploaded = save_image(request.files.get("image"))
                if uploaded:
                    image_url = uploaded
                if not image_url and book:
                    image_url = book.image_url
                if not image_url:
                    raise ValueError("Add an image URL or upload a cover image.")
                if not categories:
                    raise ValueError("Create a category first.")

                target = book or Book()
                title = request.form.get("title", "").strip()
                target.title = title
                target.slug = unique_slug(Book, title, target.id)
                target.author = request.form.get("author", "").strip()
                target.description = request.form.get("description", "").strip()
                target.price = float(request.form.get("price", 0))
                target.image_url = image_url
                target.category_id = int(request.form.get("category_id"))
                target.featured = request.form.get("featured") == "on"
                target.in_stock = request.form.get("in_stock") == "on"
                if not title or not target.description or target.price < 0:
                    raise ValueError("Title, description and a valid price are required.")
                if not book:
                    db.session.add(target)
                db.session.commit()
                flash("Book saved successfully.", "success")
                return redirect(url_for("admin_books"))
            except (ValueError, TypeError) as exc:
                db.session.rollback()
                flash(str(exc), "error")
        return render_template("admin/book_form.html", book=book, categories=categories)

    @app.post("/admin/books/<int:book_id>/delete")
    @login_required
    def admin_book_delete(book_id):
        validate_csrf()
        book = db.get_or_404(Book, book_id)
        db.session.delete(book)
        db.session.commit()
        flash("Book deleted.", "success")
        return redirect(url_for("admin_books"))

    @app.route("/admin/categories", methods=["GET", "POST"])
    @login_required
    def admin_categories():
        if request.method == "POST":
            validate_csrf()
            name = request.form.get("name", "").strip()
            if name and not Category.query.filter_by(name=name).first():
                db.session.add(Category(name=name, slug=unique_slug(Category, name), description=request.form.get("description", "").strip()))
                db.session.commit()
                flash("Category added.", "success")
            else:
                flash("Enter a unique category name.", "error")
        return render_template("admin/categories.html", categories=Category.query.order_by(Category.name).all())

    @app.post("/admin/categories/<int:category_id>/delete")
    @login_required
    def admin_category_delete(category_id):
        validate_csrf()
        category = db.get_or_404(Category, category_id)
        if category.books:
            flash("Move or delete this category's books first.", "error")
        else:
            db.session.delete(category)
            db.session.commit()
            flash("Category deleted.", "success")
        return redirect(url_for("admin_categories"))

    @app.route("/admin/settings", methods=["GET", "POST"])
    @login_required
    def admin_settings():
        keys = ["store_name", "tagline", "whatsapp", "phone", "address", "facebook_url", "discount_percent"]
        if request.method == "POST":
            validate_csrf()
            try:
                discount = int(float(request.form.get("discount_percent", 0) or 0))
                if not 0 <= discount <= 100:
                    raise ValueError
            except ValueError:
                flash("Discount must be between 0 and 100.", "error")
                values = {row.key: row.value for row in SiteSetting.query.all()}
                return render_template("admin/settings.html", values=values)
            for key in keys:
                row = SiteSetting.query.filter_by(key=key).first() or SiteSetting(key=key)
                row.value = str(discount) if key == "discount_percent" else request.form.get(key, "").strip()
                db.session.add(row)
            db.session.commit()
            flash("Website content updated.", "success")
            return redirect(url_for("admin_settings"))
        values = {row.key: row.value for row in SiteSetting.query.all()}
        return render_template("admin/settings.html", values=values)

    @app.errorhandler(413)
    def too_large(_):
        return "Image is too large. Maximum upload size is 5MB.", 413

    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        seed_data()
        print("Database initialized.")

    def seed_data():
        admin_email = os.getenv("ADMIN_EMAIL", "admin@medicalbookshop.pk").lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "")
        if admin_password and not Admin.query.filter_by(email=admin_email).first():
            db.session.add(Admin(email=admin_email, password_hash=generate_password_hash(admin_password)))

        if Category.query.count() == 0:
            names = ["MBBS", "FCPS", "USMLE", "MRCP", "Radiology", "International Exams"]
            cats = {name: Category(name=name, slug=slugify(name)) for name in names}
            db.session.add_all(cats.values())
            db.session.flush()
            samples = [
                ("Clinical Anatomy Essentials", "Dr. A. Rahman", "MBBS", 2450, "cover-anatomy.svg"),
                ("FCPS Medicine Review", "Medical Review Board", "FCPS", 3200, "cover-fcps.svg"),
                ("USMLE Step 1 Master Notes", "Exam Prep Faculty", "USMLE", 3850, "cover-usmle.svg"),
                ("MRCP Part 1 Practice", "Dr. Sarah Malik", "MRCP", 2950, "cover-mrcp.svg"),
                ("Diagnostic Radiology Cases", "Dr. H. Ahmed", "Radiology", 4250, "cover-radiology.svg"),
                ("PLAB & AMC Clinical Guide", "Global Medical Faculty", "International Exams", 2750, "cover-plab.svg"),
            ]
            for title, author, cat, price, image in samples:
                db.session.add(Book(
                    title=title, slug=slugify(title), author=author,
                    description=f"A focused, practical study resource for {cat} candidates with clear explanations, exam-oriented summaries and high-yield revision material.",
                    price=price, image_url=f"/static/images/{image}", category_id=cats[cat].id,
                    featured=True, in_stock=True,
                ))
        defaults = {
            "store_name": "Medical Book Shop", "tagline": "For doctors, students and every medical milestone",
            "whatsapp": "923002422099", "phone": "0321-8926985 / 0300-2422099",
            "address": "Pakistan — Nationwide delivery available", "facebook_url": "#",
            "discount_percent": "0",
        }
        for key, value in defaults.items():
            if not SiteSetting.query.filter_by(key=key).first():
                db.session.add(SiteSetting(key=key, value=value))
        db.session.commit()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")

