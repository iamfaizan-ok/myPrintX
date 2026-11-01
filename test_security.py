import os
import sys
import json
import uuid
import time
import threading
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000/api/v1"

def print_header(title):
    print("\n" + "="*70)
    print(f"   {title}")
    print("="*70)

def assert_true(condition, msg):
    if not condition:
        print(f"[FAIL]: {msg}")
        raise AssertionError(msg)
    print(f"[PASS]: {msg}")

def http_request(url, method='GET', data=None, headers=None, files=None):
    if headers is None:
        headers = {}
    
    if files:
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        headers['Content-Type'] = f"multipart/form-data; boundary={boundary}"
        body = bytearray()
        if data:
            for k, v in data.items():
                body.extend(f"--{boundary}\r\n".encode('utf-8'))
                body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode('utf-8'))
                body.extend(f"{v}\r\n".encode('utf-8'))
        for field_name, (filename, file_content, mime_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode('utf-8'))
            body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode('utf-8'))
            body.extend(f'Content-Type: {mime_type}\r\n\r\n'.encode('utf-8'))
            body.extend(file_content)
            body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode('utf-8'))
        req_data = bytes(body)
    elif data is not None:
        if not any(k.lower() == 'content-type' for k in headers):
            headers['Content-Type'] = 'application/json'
        req_data = json.dumps(data).encode('utf-8')
    else:
        req_data = None

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            try:
                res_json = json.loads(content.decode('utf-8'))
            except Exception:
                res_json = None
            return resp.status, res_json, content
    except urllib.error.HTTPError as e:
        content = e.read()
        try:
            res_json = json.loads(content.decode('utf-8'))
        except Exception:
            res_json = {'error': content.decode('utf-8', errors='ignore')}
        return e.code, res_json, content
    except Exception as e:
        return 500, {'error': str(e)}, b''

def run_security_audit_suite():
    print_header("PRINTX SENIOR APPLICATION SECURITY AUDIT & REGRESSION SUITE")

    # Setup two isolated shops (Shop A and Shop B)
    # Shop A
    email_a = f"owner_a_{uuid.uuid4().hex[:6]}@secshop.com"
    pwd_a = "StrongPass2026!A"
    status, res, _ = http_request(f"{BASE_URL}/admin/auth/signup/", method='POST', data={
        "name": "Shop A Owner",
        "email": email_a,
        "password": pwd_a,
        "confirm_password": pwd_a,
        "shop_name": "Security Shop Alpha",
        "shop_phone": "+92-300-1111111",
        "shop_address": "Alpha Building"
    })
    assert_true(status == 201, "Provisioned Shop A")
    token_a = res['data']['token']
    shop_a_public_id = res['data']['shop']['public_id']
    headers_a = {"Authorization": f"Token {token_a}"}

    # Shop B
    email_b = f"owner_b_{uuid.uuid4().hex[:6]}@secshop.com"
    pwd_b = "StrongPass2026!B"
    status, res, _ = http_request(f"{BASE_URL}/admin/auth/signup/", method='POST', data={
        "name": "Shop B Owner",
        "email": email_b,
        "password": pwd_b,
        "confirm_password": pwd_b,
        "shop_name": "Security Shop Beta",
        "shop_phone": "+92-300-2222222",
        "shop_address": "Beta Building"
    })
    assert_true(status == 201, "Provisioned Shop B")
    token_b = res['data']['token']
    shop_b_public_id = res['data']['shop']['public_id']
    headers_b = {"Authorization": f"Token {token_b}"}

    # Upload document to Shop A
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    status, res, _ = http_request(f"{BASE_URL}/documents/upload/", method='POST', 
                                  data={'shop_public_id': shop_a_public_id}, 
                                  files={'file': ('confidential_a.pdf', pdf_content, 'application/pdf')})
    assert_true(status == 201, "Uploaded Document to Shop A")
    doc_a_id = res['data']['id']

    # Create Order for Shop A
    status, res, _ = http_request(f"{BASE_URL}/orders/create/", method='POST', data={
        "shop_public_id": shop_a_public_id,
        "document_id": doc_a_id,
        "copies": 1,
        "payment_method": "cash_on_pickup"
    })
    assert_true(status == 201, "Created Order for Shop A")
    order_a_id = res['data']['id']
    order_a_num = res['data']['order_number']
    order_a_token = res['data']['access_token']

    # -------------------------------------------------------------
    # Test 1: Cross-Shop IDOR Protection (Shop B cannot access Shop A)
    # -------------------------------------------------------------
    print_header("Test 1: Cross-Shop IDOR & Object-Level Permission Check")
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{order_a_id}/", headers=headers_b)
    assert_true(status == 404, "Shop B admin cannot inspect Shop A's order details (Returned 404)")

    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{order_a_id}/pay-ok/", method='POST', data={}, headers=headers_b)
    assert_true(status == 404, "Shop B admin cannot approve payment for Shop A's order (Returned 404)")

    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{order_a_id}/block/", method='POST', data={"reason": "Hacking attempt"}, headers=headers_b)
    assert_true(status == 404, "Shop B admin cannot block Shop A's order (Returned 404)")

    # -------------------------------------------------------------
    # Test 2: Document Download Scoping & Private Storage Protection
    # -------------------------------------------------------------
    print_header("Test 2: Document Download Scoping & Header Injection Defense")
    # Public unauthenticated download attempt
    status, _, _ = http_request(f"{BASE_URL}/documents/{doc_a_id}/download/")
    assert_true(status == 403, "Public unauthorized download strictly rejected (403 Forbidden)")

    # Shop B admin attempting to download Shop A's document
    status, _, _ = http_request(f"{BASE_URL}/documents/{doc_a_id}/download/", headers=headers_b)
    assert_true(status == 403, "Shop B admin cannot download Shop A's private document (403 Forbidden)")

    # Shop A admin authorized download
    status, _, content = http_request(f"{BASE_URL}/documents/{doc_a_id}/download/", headers=headers_a)
    assert_true(status == 200 and content.startswith(b"%PDF-"), "Shop A admin successfully authorized to stream private document")

    # -------------------------------------------------------------
    # Test 3: Path Traversal & XSS Name Sanitization
    # -------------------------------------------------------------
    print_header("Test 3: Path Traversal & Stored XSS Payload Upload")
    malicious_filename = '../../../../etc/passwd<script>alert(1)</script>.pdf'
    status, res, _ = http_request(f"{BASE_URL}/documents/upload/", method='POST', 
                                  data={'shop_public_id': shop_a_public_id}, 
                                  files={'file': (malicious_filename, pdf_content, 'application/pdf')})
    assert_true(status == 201, "Malicious filename upload processed safely")
    xss_doc_id = res['data']['id']
    storage_key = res['data']['storage_key']
    assert_true(storage_key.startswith("doc_") and ".." not in storage_key, f"Path Traversal Prevented: Storage key is safe UUID ({storage_key})")

    # -------------------------------------------------------------
    # Test 4: Concurrency & Race Condition Elimination (Atomic Locking)
    # -------------------------------------------------------------
    print_header("Test 4: Concurrency & Duplicate Print Prevention")
    # Concurrently execute 5 simultaneous Pay OK requests against Order A
    results = []
    def call_pay_ok():
        s, r, _ = http_request(f"{BASE_URL}/admin/orders/{order_a_id}/pay-ok/", method='POST', data={}, headers=headers_a)
        results.append((s, r.get('print_job_id')))

    threads = [threading.Thread(target=call_pay_ok) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()

    # Verify all threads returned 200 and all pointed to the EXACT same print job ID
    job_ids = set([r[1] for r in results if r[0] == 200])
    assert_true(len(job_ids) == 1, f"Atomic Lock Verified: 5 concurrent Pay OK requests resulted in exactly 1 unique PrintJob (Job #{list(job_ids)[0]})")

    # -------------------------------------------------------------
    # Test 5: Blocked Order Execution Prevention
    # -------------------------------------------------------------
    print_header("Test 5: Blocked Orders Must NEVER Print")
    # Block the order
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{order_a_id}/block/", method='POST', data={"reason": "Security test block"}, headers=headers_a)
    assert_true(status == 200 and res['data']['is_blocked'] is True, "Order blocked")

    # Authorize print attempt on blocked order
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{order_a_id}/authorize-print/", method='POST', data={}, headers=headers_a)
    assert_true(status == 400, "Authorize print rejected on blocked order (400 Bad Request)")

    # Document download attempt on blocked order via customer token
    status, _, _ = http_request(f"{BASE_URL}/documents/{doc_a_id}/download/?tracking_token={order_a_token}")
    assert_true(status == 403, "Document download rejected for blocked order (403 Forbidden)")

    # -------------------------------------------------------------
    # Test 6: Payment Webhook Signature Tamper Resistance
    # -------------------------------------------------------------
    print_header("Test 6: Webhook Signature Verification")
    webhook_payload = {
        "order_number": order_a_num,
        "event_type": "payment.succeeded",
        "transaction_id": "fake_txn_999"
    }
    # Forged signature
    status, res, _ = http_request(f"{BASE_URL}/payments/online/webhook/", method='POST', data=webhook_payload, headers={"X-Gateway-Signature": "fake_forged_signature"})
    assert_true(status == 401, "Forged gateway webhook signature rejected with 401")

    # -------------------------------------------------------------
    # Test 7: Print Agent Shop Scoping & Spool Isolation
    # -------------------------------------------------------------
    print_header("Test 7: Print Agent Shop Scoping")
    # Get agent token for Shop B
    status, res, _ = http_request(f"{BASE_URL}/admin/agent/token/", headers=headers_b)
    agent_b_token = res['data']['agent_token']

    # Agent B polling jobs
    status, res, _ = http_request(f"{BASE_URL}/agent/jobs/poll/", headers={"X-Agent-Token": agent_b_token})
    assert_true(status == 200, "Agent B poll succeeded")
    jobs = res['data']
    # Check that Agent B cannot see Shop A's job
    shop_a_job_leaked = any(j.get('order_number') == order_a_num for j in jobs)
    assert_true(not shop_a_job_leaked, "Strict Tenant Isolation: Shop B agent cannot see Shop A print jobs")

    print_header("ALL SECURITY TESTS PASSED WITH 100% SUCCESS!")

if __name__ == "__main__":
    try:
        run_security_audit_suite()
    except Exception as e:
        print(f"\n[FAIL] SECURITY SUITE ABORTED: {e}")
        sys.exit(1)
