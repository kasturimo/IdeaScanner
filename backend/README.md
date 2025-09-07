# IdeaScanner Backend

This is the Flask backend for the **IdeaScanner** app.  
It handles user authentication (email + Google login), idea analysis using OpenAI, subscription management, and billing integration.

---

## 🚀 Features
- User registration & login (email/password + Google OAuth)
- Email verification & password reset
- Idea analysis powered by OpenAI
- Freemium model:
  - First 2 analyses free
  - Country-based pricing tiers
- Payment integration with Google Play Billing (for mobile users)

---

## 🛠️ Tech Stack
- **Python 3.9+**
- **Flask** (web framework)
- **SQLAlchemy** (ORM)
- **SQLite / PostgreSQL** (database)
- **OpenAI API** (AI-powered analysis)
- **Authlib** (Google OAuth login)
- **Flask-Mail** (email verification)


