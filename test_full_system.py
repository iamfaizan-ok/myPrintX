import os
import sys
import json
import uuid
import time
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
        # Multipart form data
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        headers['Content-Type'] = f"multipart/form-data; boundary={boundary}"
        body = bytearray()
        
        # Add normal form fields
        if data:
            for k, v in data.items():
                body.extend(f"--{boundary}\r\n".encode('utf-8'))
                body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode('utf-8'))
                body.extend(f"{v}\r\n".encode('utf-8'))
                
        # Add file fields
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

def run_all_tests():
    print_header("PRINTX COMPLETE APPLICATION END-TO-END VERIFICATION")

    # -------------------------------------------------------------
    # 1. Admin Authentication, Profile & Account Settings
    # -------------------------------------------------------------
    print_header("1. Admin Authentication & Account Settings")
    test_email = f"owner_{uuid.uuid4().hex[:6]}@centralhub.com"
    test_password = "SecurePassword123"
    
    # 1.1 Signup
    signup_data = {
        "name": "Master Printer Admin",
        "email": test_email,
        "password": test_password,
        "confirm_password": test_password,
        "shop_name": "Apex Fast Prints Hub",
        "shop_phone": "+92-300-9876543",
        "shop_address": "Counter 14, Commercial Plaza"
    }
    status, res, _ = http_request(f"{BASE_URL}/admin/auth/signup/", method='POST', data=signup_data)
    assert_true(status == 201, f"Admin signup returned 201: {status}")
    token = res['data']['token']
    shop_public_id = res['data']['shop']['public_id']
    shop_id = res['data']['shop']['id']
    headers = {"Authorization": f"Token {token}"}
    assert_true(token and shop_public_id, "Token and Shop Public ID generated successfully")

    # 1.2 Admin Me
    status, res, _ = http_request(f"{BASE_URL}/admin/auth/me/", headers=headers)
    assert_true(status == 200 and res['data']['user']['email'] == test_email, "Admin Me profile fetched correctly")

    # 1.3 Account settings update (PATCH)
    status, res, _ = http_request(f"{BASE_URL}/admin/auth/me/", method='PATCH', data={"name": "Master Printer Manager", "phone": "+92-333-1112233"}, headers=headers)
    assert_true(status == 200 and res['data']['user']['name'] == "Master Printer Manager", "Admin account name & phone updated successfully")

    # 1.4 Shop Profile update (PATCH)
    status, res, _ = http_request(f"{BASE_URL}/admin/shop/profile/", method='PATCH', data={"opening_hours": "07:30 - 23:00"}, headers=headers)
    assert_true(status == 200 and res['data']['opening_hours'] == "07:30 - 23:00", "Shop profile opening hours updated successfully")

    # 1.5 Admin Login
    status, res, _ = http_request(f"{BASE_URL}/admin/auth/login/", method='POST', data={"email": test_email, "password": test_password})
    assert_true(status == 200 and res['data']['token'] == token, "Admin Login verified")

    # -------------------------------------------------------------
    # 2. Shop Counter QR Code & Public Discovery
    # -------------------------------------------------------------
    print_header("2. Shop QR Code & Public Counter Discovery")
    # 2.1 Generate QR
    status, res, _ = http_request(f"{BASE_URL}/admin/qr/generate/", method='POST', data={}, headers=headers)
    assert_true(status == 200, "Shop QR code generated by backend")
    qr_data = res['data']
    assert_true(qr_data['public_id'] == shop_public_id, "QR code tied to authenticated shop public_id")
    assert_true("upload.html?shop=" in qr_data['scan_target_url'], f"QR scan target URL points to upload page: {qr_data['scan_target_url']}")

    # 2.2 QR Details
    status, res, _ = http_request(f"{BASE_URL}/admin/qr/details/", headers=headers)
    assert_true(status == 200 and res['data']['qr_code_url'], "QR code details and image URL verified")

    # 2.3 Public Shop Detail
    status, res, _ = http_request(f"{BASE_URL}/shops/public/{shop_public_id}/")
    assert_true(status == 200 and res['data']['name'] == "Apex Fast Prints Hub", "Public shop detail retrieved for customer scanning QR")

    # 2.4 Public Shop List
    status, res, _ = http_request(f"{BASE_URL}/shops/")
    assert_true(status == 200 and len(res['data']) > 0, "Public shops list retrieved for homepage counter discovery")

    # -------------------------------------------------------------
    # 3. Multi-Format Document Upload & Private Storage
    # -------------------------------------------------------------
    print_header("3. Multi-Format Document Upload & Private Storage")
    
    # 3.1 PDF Upload
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    files = {'file': ('research_paper.pdf', pdf_content, 'application/pdf')}
    data = {'shop_public_id': shop_public_id}
    status, res, _ = http_request(f"{BASE_URL}/documents/upload/", method='POST', data=data, files=files)
    assert_true(status == 201, f"PDF upload successful: {status}")
    doc = res['data']
    doc_id = doc['id']
    assert_true(doc['total_pages'] == 1, "Page count extracted accurately from genuine PDF")
    assert_true(doc['checksum'], f"SHA-256 checksum calculated: {doc['checksum'][:16]}...")

    # 3.2 Image Upload
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    files_img = {'file': ('diagram.png', png_content, 'image/png')}
    status, res, _ = http_request(f"{BASE_URL}/documents/upload/", method='POST', data=data, files=files_img)
    assert_true(status == 201, "Image (PNG) multi-format upload supported")

    # 3.3 Security: Unauthorized document download rejected
    status, res, _ = http_request(f"{BASE_URL}/documents/{doc_id}/download/")
    assert_true(status == 403, "Security Rule Verified: Public unauthorized download rejected with 403")

    # 3.4 Authorized download by shop admin
    status, res, content = http_request(f"{BASE_URL}/documents/{doc_id}/download/", headers=headers)
    assert_true(status == 200 and content.startswith(b"%PDF-"), "Authorized admin can securely stream private document")

    # -------------------------------------------------------------
    # 4. Authoritative Pricing Calculation (PKR)
    # -------------------------------------------------------------
    print_header("4. Authoritative Pricing Calculation in PKR")
    
    # 4.1 B&W: 2 copies of 1 page = Rs. 20
    calc_payload = {
        "document_id": doc_id,
        "copies": 2,
        "color_mode": "bw",
        "paper_size": "A4",
        "duplex": False,
        "binding": "none"
    }
    status, res, _ = http_request(f"{BASE_URL}/pricing/calculate/", method='POST', data=calc_payload)
    assert_true(status == 200, "Price calculation endpoint responded")
    p_data = res['data']
    assert_true(p_data['totalPrice'] == 20.0, f"B&W 2 copies = Rs. {p_data['totalPrice']} (Expected Rs. 20.00)")
    assert_true(p_data['currency'] == "PKR", "Currency is PKR")

    # 4.2 Color + Staple: 1 copy of Color (Rs. 20) + Staple (Rs. 10) = Rs. 30
    calc_color = {
        "document_id": doc_id,
        "copies": 1,
        "color_mode": "color",
        "paper_size": "A4",
        "duplex": False,
        "binding": "staple"
    }
    status, res, _ = http_request(f"{BASE_URL}/pricing/calculate/", method='POST', data=calc_color)
    p_color = res['data']
    assert_true(p_color['totalPrice'] == 30.0, f"Color + Staple = Rs. {p_color['totalPrice']} (Expected Rs. 30.00)")

    # -------------------------------------------------------------
    # 5. Customer Order Creation & Confirmation Receipt
    # -------------------------------------------------------------
    print_header("5. Customer Order Creation & Database Record")
    order_payload = {
        "shop_public_id": shop_public_id,
        "document_id": doc_id,
        "copies": 2,
        "page_range": "all",
        "color_mode": "bw",
        "paper_size": "A4",
        "duplex": False,
        "binding": "none",
        "payment_method": "cash_on_pickup",
        "special_instructions": "Urgent print for class"
    }
    status, res, _ = http_request(f"{BASE_URL}/orders/create/", method='POST', data=order_payload)
    assert_true(status == 201, f"Customer order created with 201: {status}")
    order_data = res['data']
    order_num = order_data['order_number']
    order_id = order_data['id']
    access_token = order_data['access_token']
    assert_true(order_num.startswith("PX-"), f"Authoritative order number generated: {order_num}")
    assert_true(order_data['payment_status'] == "unpaid", "Initial payment status is unpaid")
    assert_true(order_data['status'] == "pending", "Initial order status is pending")
    assert_true(access_token, "Secret access token generated for guest tracking")

    # -------------------------------------------------------------
    # 6. Customer Order Tracking (Secure & Multi-Device)
    # -------------------------------------------------------------
    print_header("6. Customer Order Tracking")
    # 6.1 Track with order number
    status, res, _ = http_request(f"{BASE_URL}/orders/track/{order_num}/")
    assert_true(status == 200 and res['data']['order_number'] == order_num, "Customer can track by Order Number")

    # 6.2 Track with access token
    status, res, _ = http_request(f"{BASE_URL}/orders/track/{order_num}/?token={access_token}")
    assert_true(status == 200, "Customer can track with access token")

    # 6.3 Guessing sequential ID without token rejected
    status, res, _ = http_request(f"{BASE_URL}/orders/track/{order_id}/")
    assert_true(status == 403, "Security Protection: Guessing sequential integer ID rejected with 403")

    # -------------------------------------------------------------
    # 7. Admin Dashboard Metrics (Real PostgreSQL Data)
    # -------------------------------------------------------------
    print_header("7. Admin Dashboard Live Metrics")
    status, res, _ = http_request(f"{BASE_URL}/admin/dashboard/stats/", headers=headers)
    assert_true(status == 200, "Dashboard stats fetched")
    stats = res['data']
    assert_true(stats['total_orders'] >= 1, f"Live Total Orders count: {stats['total_orders']}")
    assert_true(stats['payment_pending_orders'] >= 1, f"Live Payment Pending count: {stats['payment_pending_orders']}")
    assert_true(stats['shop_name'] == "Apex Fast Prints Hub", "Metrics isolated to authenticated shop")

    # -------------------------------------------------------------
    # 8. Admin Orders Page: Search, Filters, Pagination, & Details
    # -------------------------------------------------------------
    print_header("8. Admin Orders: Search, Filter, Pagination, Details")
    
    # 8.1 Filter by status
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/?status=pending", headers=headers)
    assert_true(status == 200 and len(res['data']) >= 1, "Filter by status='pending' works")

    # 8.2 Search by order number
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/?search={order_num}", headers=headers)
    assert_true(status == 200 and len(res['data']) == 1, f"Search by order_number '{order_num}' found exact match")

    # 8.3 Search by document name
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/?search=research_paper", headers=headers)
    assert_true(status == 200 and len(res['data']) >= 1, "Search by document name works")

    # 8.4 Pagination
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/?page=1&page_size=1", headers=headers)
    assert_true(status == 200 and 'total_pages' in res, "Pagination metadata returned")

    # 8.5 Admin Order Detailed Inspection
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{order_id}/", headers=headers)
    assert_true(status == 200, "Admin order detail view retrieved")
    detail = res
    assert_true('print_jobs' in detail and 'audit_logs' in detail, "Order detail contains print jobs and audit trail")

    # -------------------------------------------------------------
    # 9. Method 2: Admin Pay OK -> Automatic Printing
    # -------------------------------------------------------------
    print_header("9. Method 2: Admin Pay OK -> Automatic Printing")
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{order_id}/pay-ok/", method='POST', data={}, headers=headers)
    assert_true(status == 200, f"Admin Pay OK succeeded: {res['message']}")
    print_job_id = res.get('print_job_id')
    assert_true(print_job_id is not None, f"Print job #{print_job_id} automatically created via Pay OK")
    assert_true(res['data']['payment_status'] == 'paid', "Order payment status transitioned to paid")

    # 9.1 Idempotency check: Repeated Pay OK does not duplicate print jobs
    status, res2, _ = http_request(f"{BASE_URL}/admin/orders/{order_id}/pay-ok/", method='POST', data={}, headers=headers)
    assert_true(status == 200, "Repeated Pay OK accepted gracefully")
    assert_true(res2.get('print_job_id') == print_job_id, "Idempotency Verified: No duplicate print job created")

    # -------------------------------------------------------------
    # 10. Method 1: Online Payment Initiation & Gateway Webhook
    # -------------------------------------------------------------
    print_header("10. Method 1: Online Payment Verification")
    
    # 10.1 Create an online payment order
    status, res, _ = http_request(f"{BASE_URL}/orders/create/", method='POST', data={
        "shop_public_id": shop_public_id,
        "document_id": doc_id,
        "copies": 1,
        "color_mode": "color",
        "paper_size": "A4",
        "payment_method": "online"
    })
    online_order = res['data']
    online_order_num = online_order['order_number']
    
    # 10.2 Initiate online payment without gateway credentials -> returns pending_integration
    status, res, _ = http_request(f"{BASE_URL}/payments/online/initiate/", method='POST', data={"order_number": online_order_num})
    assert_true(status == 501 and res['status'] == 'pending_integration', "Zero fake payments: Missing gateway credentials correctly returned 'pending_integration'")

    # 10.3 Webhook with invalid signature rejected
    status, res, _ = http_request(f"{BASE_URL}/payments/online/webhook/", method='POST', data={"order_number": online_order_num, "event_type": "payment.succeeded"})
    assert_true(status == 401, "Unsigned gateway webhook strictly rejected with 401")

    # 10.4 Webhook with valid signature -> automatically creates print job
    webhook_headers = {"X-Gateway-Signature": "printx_secure_gateway_webhook_secret_2026"}
    webhook_payload = {
        "order_number": online_order_num,
        "event_type": "payment.succeeded",
        "transaction_id": "txn_verified_12345",
        "gateway": "test_gateway"
    }
    status, res, _ = http_request(f"{BASE_URL}/payments/online/webhook/", method='POST', data=webhook_payload, headers=webhook_headers)
    assert_true(status == 200, f"Webhook verified payment: {res['message']}")
    online_job_id = res.get('print_job_id')
    assert_true(online_job_id is not None, f"Online payment automatically spooled PrintJob #{online_job_id}")

    # -------------------------------------------------------------
    # 11. Security: Blocked Orders Must NEVER Print
    # -------------------------------------------------------------
    print_header("11. Security: Blocked Orders Must NEVER Print")
    # Block the online order
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{online_order['id']}/block/", method='POST', data={"reason": "Test block security"}, headers=headers)
    assert_true(status == 200 and res['data']['is_blocked'] is True, "Order blocked successfully")

    # Try manual authorize print on blocked order -> must fail
    status, res, _ = http_request(f"{BASE_URL}/admin/orders/{online_order['id']}/authorize-print/", method='POST', data={}, headers=headers)
    assert_true(status == 400, "Security Rule Verified: Blocked order cannot be authorized for printing")

    # -------------------------------------------------------------
    # 12. PC Print Agent Spooling & Telemetry
    # -------------------------------------------------------------
    print_header("12. PC Print Agent Spooling & Telemetry")
    # 12.1 Get agent token
    status, res, _ = http_request(f"{BASE_URL}/admin/agent/token/", headers=headers)
    assert_true(status == 200, "Agent pairing token retrieved")
    agent_token = res['data']['agent_token']

    # 12.2 Agent poll jobs
    agent_headers = {"X-Agent-Token": agent_token}
    status, res, _ = http_request(f"{BASE_URL}/agent/jobs/poll/", headers=agent_headers)
    assert_true(status == 200, "Agent polled queued jobs successfully")
    jobs = res['data']
    assert_true(len(jobs) >= 1, f"Agent received {len(jobs)} queued job(s)")
    job_to_print = jobs[0]

    # 12.3 Agent acknowledges job -> status 'printing'
    status, res, _ = http_request(f"{BASE_URL}/agent/jobs/{job_to_print['id']}/status/", method='POST', data={"status": "printing", "pages_printed": 0}, headers=agent_headers)
    assert_true(status == 200 and res['data']['status'] == 'printing', "Agent reported status 'printing'")

    # 12.4 Agent downloads private document
    doc_url = job_to_print['document_url']
    status, res, content = http_request(f"http://127.0.0.1:8000{doc_url}", headers=agent_headers)
    assert_true(status == 200 and len(content) > 0, "Agent successfully downloaded authorized document from private storage")

    # 12.5 Agent reports completion -> order advances to 'ready_for_pickup'
    status, res, _ = http_request(f"{BASE_URL}/agent/jobs/{job_to_print['id']}/status/", method='POST', data={"status": "completed", "pages_printed": 2}, headers=agent_headers)
    assert_true(status == 200, "Agent reported job 'completed'")
    
    # Check parent order status
    status, res, _ = http_request(f"{BASE_URL}/orders/track/{order_num}/")
    assert_true(res['data']['status'] == 'ready_for_pickup', "Order status successfully transitioned to 'ready_for_pickup'")

    print_header("ALL 12 VERIFICATIONS COMPLETED SUCCESSFULLY WITH 100% COMPLIANCE!")

if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print(f"\n[FAIL] TEST RUN ABORTED: {e}")
        sys.exit(1)
