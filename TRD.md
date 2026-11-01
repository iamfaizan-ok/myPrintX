# PrintX — Technical Requirements Document (TRD)

**Version:** 2.0  
**Status:** Approved & Implemented  
**Date:** November 2026  
**Architecture:** Decoupled Architecture (Django REST Framework + PostgreSQL + Vanilla JS Frontend + Windows PC Agent)

---

## 1. System Architecture

```text
┌────────────────────────────────────────────────────────┐
│                   Customer Frontend                    │
│     (Mobile Web / Desktop Browser - Port 3000)         │
│  - QR-routed upload (pages/upload.html)                │
│  - Live PKR quotation (pages/print-settings.html)      │
│  - Receipt Token & Tracking (order-tracking.html)      │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTPS / REST JSON
                           ▼
┌────────────────────────────────────────────────────────┐
│                   Shop Admin Portal                    │
│               (Dashboard - Port 3000)                  │
│  - Live Order Queue (admin/pages/orders.html)          │
│  - Pay OK (Print) verification                         │
│  - QR Code Generation & Download                       │
│  - Shop & Admin Account Settings                       │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTPS / REST Token Auth
                           ▼
┌────────────────────────────────────────────────────────┐
│                   Django REST Core                     │
│                (Backend - Port 8000)                   │
│  - apps.accounts: Auth, User Model, Throttling         │
│  - apps.shops: Multi-tenant Shops & QR Generator       │
│  - apps.documents: Private Storage & Page Extraction   │
│  - apps.orders: State Machine, Pay OK, Webhook Spooler │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
               ▼                          ▼
┌───────────────────────────┐  ┌─────────────────────────┐
│    PostgreSQL Database    │  │  Private Storage Volume │
│  - Orders & Payments      │  │  (outside web-root)     │
│  - Multi-tenant Isolation │  │  - doc_{uuid}.{ext}     │
│  - Atomic row-level locks │  │  - SHA-256 Checksums    │
└───────────────────────────┘  └───────────▲─────────────┘
                                           │ Authorized binary stream
                                           │ (X-Agent-Token)
┌──────────────────────────────────────────┴─────────────┐
│              Windows PC Print Agent                    │
│                (print_agent.py)                        │
│  - Polls /api/v1/agent/jobs/poll/                      │
│  - Downloads document from private backend streaming   │
│  - Dispatches to Win32_Printer / Windows Spooler       │
│  - Reports status ('printing' -> 'completed')          │
└────────────────────────────────────────────────────────┘
```

---

## 2. Database Schema & Data Relationships

### 2.1 Entity Relationship Model

```mermaid
erDiagram
    USER ||--o| SHOP : owns
    SHOP ||--o{ DOCUMENT : stores
    SHOP ||--o{ ORDER : receives
    SHOP ||--o{ PRINT_AGENT : registers
    SHOP ||--o{ PRINT_JOB : executes
    SHOP ||--o{ AUDIT_LOG : tracks
    DOCUMENT ||--o{ ORDER : specifies
    ORDER ||--o| PAYMENT : records
    ORDER ||--o{ PRINT_JOB : spawns
    ORDER ||--o{ AUDIT_LOG : audits
    PRINT_AGENT ||--o{ PRINT_JOB : spools

    USER {
        int id PK
        string email UK
        string name
        string role
        string phone
        datetime created_at
    }

    SHOP {
        int id PK
        string public_id UK
        int owner_id FK
        string name
        string contact_phone
        text address
        string opening_hours
        string qr_code_image
        boolean is_active
    }

    DOCUMENT {
        int id PK
        int shop_id FK
        string storage_key UK
        string original_name
        string file
        string mime_type
        bigint size_bytes
        int total_pages
        string checksum
        string status
        datetime uploaded_at
    }

    ORDER {
        int id PK
        string order_number UK
        string access_token
        int shop_id FK
        int document_id FK
        string customer_name
        string customer_phone
        int copies
        int selected_pages_count
        string page_range
        string color_mode
        string paper_size
        boolean duplex
        string binding
        decimal total_price
        string currency
        string payment_method
        string payment_status
        string status
        boolean is_blocked
        text blocked_reason
        text special_instructions
        datetime created_at
    }

    PAYMENT {
        int id PK
        int order_id FK
        int shop_id FK
        decimal amount
        string currency
        string method
        string status
        string reference_id
        int verified_by_id FK
        datetime verified_at
    }

    PRINT_AGENT {
        int id PK
        int shop_id FK
        string agent_name
        string agent_token UK
        string printer_name
        boolean is_online
        datetime last_heartbeat
    }

    PRINT_JOB {
        int id PK
        int order_id FK
        int shop_id FK
        int agent_id FK
        string status
        int pages_printed
        text error_message
        datetime started_at
        datetime completed_at
    }

    AUDIT_LOG {
        int id PK
        int shop_id FK
        int user_id FK
        int order_id FK
        string action
        text notes
        datetime timestamp
    }
```

---

## 3. Backend API Specifications

### 3.1 Authentication & Profile (`apps.accounts`)
* `POST /api/v1/admin/auth/signup/`: Register shop owner account and instantiate owned Shop entity.
* `POST /api/v1/admin/auth/login/`: Authenticate admin with email/password; returns Django Token. Rate limited (15 req/min).
* `GET /api/v1/admin/auth/me/`: Retrieve authenticated user identity and shop metadata.
* `PATCH /api/v1/admin/auth/me/`: Update administrator name, phone, or password (requires current password verification).
* `POST /api/v1/admin/auth/logout/`: Invalidate and delete current authentication token.

### 3.2 Shop Management & QR Generation (`apps.shops`)
* `GET /api/v1/shops/`: Public list of active shops for homepage discovery.
* `GET /api/v1/shops/public/<public_id>/`: Public shop profile queryable by customer QR scan.
* `GET /api/v1/admin/shop/profile/`: Shop admin retrieves full shop profile.
* `PATCH /api/v1/admin/shop/profile/`: Shop admin updates address, contact phone, or opening hours.
* `POST /api/v1/admin/qr/generate/`: Regenerates high-res PNG QR code linking to `pages/upload.html?shop={public_id}`.
* `GET /api/v1/admin/qr/details/`: Retrieves QR image URL and target customer link.

### 3.3 Private Document Storage (`apps.documents`)
* `POST /api/v1/documents/upload/`: Multipart upload of document. Validates allowed formats (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.doc`, `.docx`, `.txt`) and 50MB ceiling. Parses genuine PDF page count using `pypdf`. Rate limited (60 req/min).
* `GET /api/v1/documents/<pk>/`: Retrieve document metadata (name, pages, size).
* `GET /api/v1/documents/<pk>/download/`: Authenticated private streaming endpoint. Strict download authorization:
  1. Authenticated shop admin of document's shop.
  2. Registered PC Print Agent (`X-Agent-Token`) for an active non-blocked order.
  3. Customer guest tracking token (`access_token`) for a non-blocked order.

### 3.4 Order State Machine & Dual Printing (`apps.orders`)
* `POST /api/v1/orders/create/`: Customer submits print configuration. Authoritatively computes pricing in PKR and returns Order ID (`PX-XXXXX`). Rate limited (60 req/min).
* `GET /api/v1/orders/track/<order_identifier>/`: Real-time order progress tracker. Authenticated by exact Order Number or access token.
* `POST /api/v1/pricing/calculate/`: Real-time price quotation calculating page count, color/BW, duplex, and binding.
* `GET /api/v1/admin/dashboard/stats/`: Live shop dashboard metrics (`total_orders`, `pending`, `payment_pending`, `completed`, `blocked`).
* `GET /api/v1/admin/orders/`: Shop-isolated orders list. Supports `status` filter, `search` query, and server pagination (`page`, `page_size`).
* `GET /api/v1/admin/orders/<pk>/`: Detailed order inspection including linked print jobs and audit trail.
* `POST /api/v1/admin/orders/<pk>/pay-ok/`: Method 2 cash verification. Approves payment and automatically creates PrintJob. Idempotent.
* `POST /api/v1/admin/orders/<pk>/authorize-print/`: Manual re-spooling for paper jams or printer failures.
* `POST /api/v1/admin/orders/<pk>/block/`: Permanent order block preventing printing.
* `POST /api/v1/payments/online/initiate/`: Method 1 initiation. Returns `status: "pending_integration"` when live keys are unconfigured.
* `POST /api/v1/payments/online/webhook/`: Method 1 gateway callback. Verifies `X-Gateway-Signature` and automatically spools PrintJob.
* `GET /api/v1/admin/agent/token/`: Retrieve or generate shop's PC Print Agent pairing token.
* `POST /api/v1/admin/agent/token/`: Regenerate shop's PC Print Agent pairing token.
* `GET /api/v1/agent/jobs/poll/`: PC Print Agent polls queued jobs for its registered shop.
* `POST /api/v1/agent/jobs/<job_id>/status/`: PC Print Agent reports spool status (`printing`, `completed`, `failed`).

---

## 4. Security Architecture & Threat Mitigations

| Threat | Attack Vector | Technical Mitigation Implemented |
| :--- | :--- | :--- |
| **SQL Injection** | Parameter tampering in search or filters | All database interactions use Django ORM parameterized queries (`Q()`, `filter()`). No raw SQL used. |
| **Cross-Site Scripting (XSS)** | Malicious file or customer names (`<script>`) | Global `escapeHTML()` sanitizes all user/document values before DOM insertion in both customer and admin frontends. |
| **Cross-Site Request Forgery (CSRF)** | Unauthorized state-changing browser requests | Backend requires Bearer / Token authorization on sensitive admin endpoints. Decoupled API uses stateless auth tokens. |
| **Insecure Direct Object Reference (IDOR)** | Guessing order or shop IDs to read data | All admin endpoints scope queries to `request.user.owned_shop`. Guest tracking prevents sequential ID access without token. |
| **Path Traversal** | Document upload filenames containing `../` | Files are stored under random UUID storage keys (`doc_{uuid}.{ext}`). Safe download filenames are stripped of `\r`, `\n`, `"`, `/`, and `\`. |
| **HTTP Response Splitting** | Header injection via file names | `Content-Disposition` header filenames are sanitized with regex `[^\w.-]`, eliminating CRLF characters. |
| **Brute Force & Flooding** | Repeated password guesses or upload DoS | Scoped rate limits enforced: `login` (15/min), `order_create` (60/min), general API (300/min). |
| **Race Conditions & Duplicate Prints** | Concurrent Pay OK clicks or duplicate webhooks | `dispatch_print_job` runs inside `transaction.atomic()` with row-level locking (`select_for_update()`) and idempotency checks. |
| **Cross-Shop Data Leaks** | Shop A agent accessing Shop B files | Document streaming verifies `doc.shop == agent.shop` and returns `403 Forbidden` on mismatch. |
| **Malicious Unpaid Prints** | Tampering frontend payment status | Backend NEVER trusts frontend payment messages. Automatic printing is strictly triggered by server-side verification. |

---

## 5. Deployment, Scaling & Environment Requirements

### 5.1 Environment Configuration (`backend/.env`)
```bash
DJANGO_SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=printx.yourdomain.com,api.yourdomain.com
DATABASE_URL=postgresql://user:password@host:5432/printx_db
PRINTX_PRIVATE_STORAGE_ROOT=/var/secure_storage/printx/documents/
PAYMENT_WEBHOOK_SECRET=your-cryptographic-webhook-secret
CORS_ALLOWED_ORIGINS=https://printx.yourdomain.com
RATE_LIMIT_LOGIN=15/minute
RATE_LIMIT_ORDER=60/minute
```

### 5.2 Scalability Roadmap
1. **Asynchronous Spooling**: For high-volume print shops, transition agent polling from HTTP polling to WebSocket connections via Django Channels or Redis pub/sub.
2. **File Retention Lifecycle**: Implement a scheduled cleanup job (`manage.py purge_expired_documents`) to delete private document files 24 hours after completion.
3. **Multi-Counter Support**: Expand `ShopQR` model to assign specific physical printers to individual counters within large printing facilities.
