# JWT Auth Fullstack Project

A fullstack authentication demo using Django REST Framework (DRF) with JWT (JSON Web Token) authentication on the backend and a modern React + Vite + Tailwind frontend. This project demonstrates secure, stateless authentication using HTTP-only cookies, token refresh, and user registration.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Features](#features)
- [Backend Setup (Django)](#backend-setup-django)
- [Frontend Setup (React + Vite)](#frontend-setup-react--vite)
- [API Endpoints (Summary)](#api-endpoints-summary)
- [Development Notes & Tips](#development-notes--tips)
- [Security & Production Notes](#security--production-notes)

---

## Project Overview

This project provides a robust authentication system using JWTs, with secure cookie storage and token rotation. It is suitable as a starter for modern web apps requiring authentication.

## Architecture

- **Backend:** Django 5, Django REST Framework, SimpleJWT, custom user model, CORS, SQLite (default)
- **Frontend:** React 19, Vite, Tailwind CSS, shadcn/ui, axios
- **Auth Flow:**
  - Login/register via API
  - JWT tokens stored in HTTP-only cookies
  - Automatic token refresh
  - Logout and token blacklisting

## Features

- User registration & login
- JWT authentication (access & refresh tokens)
- Secure HTTP-only cookie storage
- Token rotation & blacklisting
- Protected API endpoints
- Modern, responsive UI

---

## Backend Setup (Django)

### Prerequisites

- Python 3.8+
- [pip](https://pip.pypa.io/en/stable/)
- Git

### Step-by-Step Local Setup

Follow these steps to set up the project locally without errors:

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd demo1
```

#### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

#### 3. Install Requirements

```bash
pip install -r requirements.txt
```

#### 4. Set Up Environment Variables

```bash
# Copy the sample environment file
cp .env.sample .env

# Edit .env with your preferred settings (optional for local development)
# The default values in .env.sample work for local development
```

#### 5. Create Static Directory

```bash
mkdir -p static
```

#### 6. Create Database Migrations

```bash
# Create initial migrations for the users app
python manage.py makemigrations users

# Apply all migrations
python manage.py migrate
```

#### 7. Create Superuser (Optional)

```bash
python manage.py createsuperuser
# Follow the prompts to create an admin user
```

#### 8. Run the Development Server

```bash
python manage.py runserver
```

The backend will be available at `http://localhost:8000/`

### Useful Commands

- `python manage.py makemigrations` — Create new migrations
- `python manage.py migrate` — Apply migrations
- `python manage.py flushexpiredtokens` — Remove expired JWT tokens (run periodically)

### Environment Variables

- By default, settings are in `config/settings.py`.
- For production, set `SECRET_KEY`, `DEBUG`, and JWT lifetimes via environment variables (see code comments in `settings.py`).

### Database

- Default: SQLite (file-based, no setup needed)
- For production, configure PostgreSQL or another DB in `config/settings.py`.

---

## Frontend Setup (React + Vite)

### Prerequisites

- Node.js 18+ (recommended)
- npm (comes with Node.js)

### Installation

```bash
cd frontend
npm install
```

### Running the App

```bash
npm run dev
```

- The app will be available at http://localhost:5173/
- The frontend is configured to talk to the backend at `http://localhost:8000/api/` by default (see `src/config/axiosInstance.js`).

---

## API Endpoints (Summary)

### Auth Endpoints

| Endpoint                   | Method | Description        |
| -------------------------- | ------ | ------------------ |
| `/api/auth/login/`         | POST   | User login         |
| `/api/auth/logout/`        | POST   | User logout        |
| `/api/auth/token/refresh/` | POST   | Refresh JWT tokens |

### User Endpoints

| Endpoint               | Method | Description          |
| ---------------------- | ------ | -------------------- |
| `/api/users/register/` | POST   | Register new user    |
| `/api/users/profile/`  | GET    | Get user info (auth) |

- All endpoints expect/return JSON.
- Auth endpoints use HTTP-only cookies for tokens.

---

## Development Notes & Tips

- **CORS:** Only `localhost:3000`, `localhost:5173`, and their `127.0.0.1` equivalents are allowed by default for frontend-backend communication.
- **Token Refresh:** The frontend automatically refreshes tokens when expired (see axios interceptors).
- **Admin Panel:** Visit `/admin/` on the backend to manage users (login with superuser credentials).
- **Custom User Model:** Email is used as the unique identifier.

---

## Security & Production Notes

- Set `DEBUG = False` and configure allowed hosts in production.
- Use HTTPS and set `JWT_AUTH_SECURE = True` for cookies.
- Store secrets and sensitive settings in environment variables.
- Regularly run `python manage.py flushexpiredtokens` to clean up expired tokens.
- For production DB, use PostgreSQL or another robust database.

---

## License

This project is provided for educational/demo purposes. Adapt and use as needed for your own projects.
