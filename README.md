# PrintX — Multi-Shop Cloud Printing Platform

PrintX is an enterprise-grade, multi-shop online printing platform that connects physical print shops with customers through instant QR counter routing, automated page-count detection, authoritative live pricing, private file storage, and PC Print Agent integration.

---

## Architecture Overview

The system is organized into three distinct, decoupled modules:

```text
iamprintX/
├── user_frontend/       # Customer-facing Kiosk & QR mobile experience
├── admin/               # Shop owner & operator dashboard
├── backend/             # Django REST Framework backend & PostgreSQL database
├── print_agent.py       # Automated local printer desktop bridge
├── serve.js             # Static web server for frontends
└── private_printx_storage/ # Secure isolated storage for uploaded files
```

---

### 1. `user_frontend/` — Customer Experience (Zero-Login Kiosk)
- **Instant QR Routing**: Scanning a shop's unique counter QR code (`?shop=SHOP_PUBLIC_ID`) dynamically connects the customer to that specific shop without requiring customer registration or account creation.
- **Genuine PDF Validation**: Validates document integrity and PDF magic bytes (`%PDF-`) directly in the browser and backend.
- **Customizable Print Settings**: Configure color mode (B&W / Color), paper size (A4 / A3 / Letter), duplex (single / double-sided), copies (1–500), custom page ranges, and binding options.
- **Live Authoritative Quotation**: Real-time pricing calculations provided directly by the backend calculation engine.
- **Counter Slip & Token Slip**: Generates an immediate counter slip with a unique Order ID (`PX-XXXXX`), payment due, document details, and selected shop name.
- **Guest Order Tracking**: Secure tracking via single-order access tokens preventing enumeration attacks.

---

### 2. `admin/` — Shop Owner & Admin Dashboard
- **Admin Authentication**: Secure token-based session management for shop owners.
- **Shop Profile & Settings**: Configure shop details, contact information, operating hours, and location.
- **Unique Shop QR Generator**: Generate, download, and print official counter QR codes tied directly to the shop's public identifier.
- **Live Counter Queue**: Real-time order monitoring with tabbed filters (All, Pending, Confirmed, Printing, Completed, Blocked).
- **Payment Approval**: "Pay OK" verification for cash payments made at the shop counter.
- **Order Moderation**: Block or cancel inappropriate or malicious orders with detailed audit logs.
- **PC Print Agent Provisioning**: Generate secure pairing tokens (`agt_...`) for the local automated printing desktop client.

---

### 3. `backend/` — Django REST APIs & PostgreSQL Core
- **Framework**: Django 6.1 + Django REST Framework.
- **Database**: PostgreSQL with strict multi-shop isolation.
- **Security Hardened File Storage**: Documents are stored in `private_printx_storage/` outside of web-accessible roots using random UUID storage keys (`doc_...`), SHA-256 checksums, and strict download authorization.
- **Modules**:
  - `apps.accounts`: Shop administrator user accounts and authentication.
  - `apps.shops`: Multi-tenant shop entities, public identifiers, and QR records.
  - `apps.documents`: Secure private file upload, PDF page detection, and streaming endpoints.
  - `apps.orders`: Order state machine, payments, print jobs, and audit logs.

---

### 4. `print_agent.py` — PC Print Agent
- Connects shop hardware directly to the PrintX cloud backend using polling over HTTPS with an agent authentication token.
- Automatically claims confirmed print jobs, downloads decrypted PDF binaries from the private backend streaming endpoint, and passes them to local OS printer queues (`win32print` / Foxit / SumatraPDF).

---

## Getting Started

### Prerequisites
- Python 3.12+
- PostgreSQL 14+
- Node.js (for local static frontend server)

### 1. Database setup
Ensure PostgreSQL is running and create the database:
```sql
CREATE DATABASE "PrinX";
```

### 2. Backend setup
From the project root, create a virtual environment and install dependencies:
```bash
cd backend
python -m venv .venv
```

Activate it (Windows PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux:
```bash
source .venv/bin/activate
```

Then install dependencies and create your local environment file:
```bash
pip install -r requirements.txt
```

Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

macOS/Linux:
```bash
cp .env.example .env
```

Edit `backend/.env` with your PostgreSQL username/password and set `DJANGO_SECRET_KEY` to a new random value before running the app. Do not commit `.env`; it is ignored by Git. The committed `backend/.env.example` contains placeholders only.

Run migrations and start the backend:
```bash
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### 3. Frontend setup
From the project root, start the static web server:
```bash
node serve.js
```
The frontend server will be available at:
- **Customer Frontend**: `http://localhost:3000/pages/upload.html`
- **Shop Admin Portal**: `http://localhost:3000/admin/index.html`

The Django REST backend is available at `http://127.0.0.1:8000/api/v1/`.

### 4. Optional PC Print Agent
Run the agent with the backend URL and a shop pairing token:
```bash
python print_agent.py --url http://127.0.0.1:8000/api/v1 --token YOUR_AGENT_TOKEN
```

The agent token is sensitive. Do not commit or share it.

> **Deployment note:** The included defaults are for local development. Configure a unique `DJANGO_SECRET_KEY`, `DEBUG=False`, and restricted `ALLOWED_HOSTS` before deploying. Review CORS and database settings for your environment.

---

## License
Proprietary & Confidential. All rights reserved.
