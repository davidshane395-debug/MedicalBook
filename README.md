# Medical Book Shop

A responsive Flask + MySQL bookstore with searchable customer pages, WhatsApp ordering and a secure admin dashboard for books, categories, featured titles, images and business details.

## Local setup (XAMPP)

1. Start **MySQL** in XAMPP.
2. In phpMyAdmin, import `database.sql` (or create a database named `medical_book_shop`).
3. Open PowerShell in this folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

4. Edit `.env`. Set a long random `SECRET_KEY`, your database credentials, `ADMIN_EMAIL`, and a strong `ADMIN_PASSWORD`.
5. Initialize and start:

```powershell
flask --app app init-db
flask --app app run --debug
```

Website: `http://127.0.0.1:5000`  
Admin: `http://127.0.0.1:5000/admin/login`

The starter catalog is inserted by `init-db`. Admin credentials are created from `.env`; the command will not create an admin if `ADMIN_PASSWORD` is blank.

## Images

The admin can either upload PNG/JPG/WEBP files (up to 5 MB) or save a public image URL. Local uploads go to `static/uploads` and only the path is stored in MySQL—never Base64.

Vercel's filesystem is temporary at runtime. For production, use the image URL field with a persistent image host (such as Cloudinary, S3 or Vercel Blob). Local uploads are intended for XAMPP/local hosting.

## Vercel

1. Create a hosted MySQL database; XAMPP MySQL cannot be reached by Vercel.
2. Initialize the hosted database once with `flask --app app init-db` while `DATABASE_URL` points to it.
3. Add these Vercel environment variables:
   - `DATABASE_URL`
   - `SECRET_KEY`
   - `ADMIN_EMAIL`
   - `ADMIN_PASSWORD`
   - `WHATSAPP_NUMBER`
4. Deploy the repository. `vercel.json` already points Vercel to the Flask app.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
