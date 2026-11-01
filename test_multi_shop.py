import io
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from pypdf import PdfWriter

BASE_URL = "http://127.0.0.1:8000/api/v1"
RUN_ID = int(time.time())

# Helper to generate genuine blank PDF bytes
def make_valid_pdf_bytes():
    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()

VALID_PDF_BYTES = make_valid_pdf_bytes()

def api_post(endpoint, data, token=None):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            **({'Authorization': f'Token {token}'} if token else {})
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))

def api_get(endpoint, token=None, headers_extra=None):
    url = f"{BASE_URL}{endpoint}"
    h = {
        'Content-Type': 'application/json',
        **({'Authorization': f'Token {token}'} if token else {}),
        **(headers_extra or {})
    }
    req = urllib.request.Request(url, headers=h, method='GET')
    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return resp.status, json.loads(resp.read().decode('utf-8'))
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, {'message': str(e)}

print("=== STARTING COMPREHENSIVE PRINTX AUDIT & SECURITY TEST SUITE ===")

# 1. Shop A admin signup
email_a = f"alice_{RUN_ID}@shopa.com"
shop_name_a = f"Campus Express Prints ({RUN_ID})"
status_a, res_a = api_post('/admin/auth/signup/', {
    'name': 'Alice Shopkeeper',
    'email': email_a,
    'password': 'Password123!',
    'confirm_password': 'Password123!',
    'shop_name': shop_name_a,
    'shop_phone': '+1-555-0101',
    'shop_address': 'Building A, University Center'
})
assert status_a == 201, f"Shop A signup failed: {res_a}"
token_a = res_a['data']['token']
shop_a_id = res_a['data']['shop']['public_id']
print(f"PASS [1]: Shop A Admin registered. Token: {token_a[:10]}..., Shop A Public ID: {shop_a_id}")

# 2. Shop B admin signup
email_b = f"bob_{RUN_ID}@shopb.com"
shop_name_b = f"North Library Xerox ({RUN_ID})"
status_b, res_b = api_post('/admin/auth/signup/', {
    'name': 'Bob Printer',
    'email': email_b,
    'password': 'Password123!',
    'confirm_password': 'Password123!',
    'shop_name': shop_name_b,
    'shop_phone': '+1-555-0102',
    'shop_address': 'Library 1st Floor, Room 102'
})
assert status_b == 201, f"Shop B signup failed: {res_b}"
token_b = res_b['data']['token']
shop_b_id = res_b['data']['shop']['public_id']
print(f"PASS [2]: Shop B Admin registered. Token: {token_b[:10]}..., Shop B Public ID: {shop_b_id}")

# 3. Both admins login successfully
st_login_a, login_res_a = api_post('/admin/auth/login/', {'email': email_a, 'password': 'Password123!'})
st_login_b, login_res_b = api_post('/admin/auth/login/', {'email': email_b, 'password': 'Password123!'})
assert st_login_a == 200 and st_login_b == 200, "Admin login failed"
print(f"PASS [3]: Both Shop A & Shop B admins authenticated successfully via Django REST.")

# 4. Shop A generates QR code
st_qr_a, qr_res_a = api_post('/admin/qr/generate/', {}, token=token_a)
assert st_qr_a == 200, f"Shop A QR generation failed: {qr_res_a}"
qr_url_a = qr_res_a['data']['qr_code_url']
print(f"PASS [4]: Shop A QR Code generated: {qr_url_a}")

# 5. Customer scans Shop A QR -> fetches Shop A public data
st_pub_a, pub_res_a = api_get(f'/shops/public/{shop_a_id}/')
assert st_pub_a == 200, f"Public Shop A lookup failed: {pub_res_a}"
assert pub_res_a['data']['name'] == shop_name_a
print(f"PASS [5]: Customer scan resolved Shop A: {pub_res_a['data']['name']}")

# 6. Customer scans Shop B QR -> fetches Shop B public data
st_pub_b, pub_res_b = api_get(f'/shops/public/{shop_b_id}/')
assert st_pub_b == 200, f"Public Shop B lookup failed: {pub_res_b}"
assert pub_res_b['data']['name'] == shop_name_b
print(f"PASS [6]: Customer scan resolved Shop B: {pub_res_b['data']['name']}")

# 7. Document Security: Malicious / Non-PDF upload rejected!
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
malicious_body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="shop_public_id"\r\n\r\n'
    f'{shop_a_id}\r\n'
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="file"; filename="payload.exe"\r\n'
    f'Content-Type: application/octet-stream\r\n\r\n'
    f'MZ NOT A PDF EXECUTABLE CONTENT\r\n'
    f'--{boundary}--\r\n'
).encode('utf-8')
req_mal = urllib.request.Request(
    f"{BASE_URL}/documents/upload/",
    data=malicious_body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)
try:
    with urllib.request.urlopen(req_mal) as resp:
        st_mal = resp.status
except urllib.error.HTTPError as e:
    st_mal = e.code
assert st_mal == 400, f"Malicious non-PDF was not rejected! Status: {st_mal}"
print("PASS [7.1]: Document Security Verified: Non-PDF malicious upload rejected with HTTP 400.")

# Upload genuine PDF for Shop A
body_a = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="shop_public_id"\r\n\r\n'
    f'{shop_a_id}\r\n'
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="file"; filename="syllabus_a.pdf"\r\n'
    f'Content-Type: application/pdf\r\n\r\n'
).encode('utf-8') + VALID_PDF_BYTES + f'\r\n--{boundary}--\r\n'.encode('utf-8')

req_doc_a = urllib.request.Request(
    f"{BASE_URL}/documents/upload/",
    data=body_a,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)
with urllib.request.urlopen(req_doc_a) as resp:
    doc_res_a = json.loads(resp.read().decode('utf-8'))
doc_a_id = doc_res_a['data']['id']
doc_a_storage_key = doc_res_a['data']['storage_key']
assert doc_res_a['data']['checksum'], "Document checksum missing!"
print(f"PASS [7.2]: Document syllabus_a.pdf uploaded to private storage (Key: {doc_a_storage_key}).")

# 8. Customer creates order for Shop A
st_order_a, order_res_a = api_post('/orders/create/', {
    'shop_public_id': shop_a_id,
    'document_id': doc_a_id,
    'copies': 2,
    'color_mode': 'bw',
    'paper_size': 'A4',
    'duplex': True,
    'binding': 'staple',
    'payment_method': 'cash_on_pickup'
})
assert st_order_a == 201, f"Order A creation failed: {order_res_a}"
order_a_num = order_res_a['data']['order_number']
order_a_pk = order_res_a['data']['id']
order_a_token = order_res_a['data']['access_token']
assert order_a_token, "Order A access_token was not generated!"
print(f"PASS [8]: Order {order_a_num} created for Shop A, Secret Tracking Token: {order_a_token[:10]}...")

# 9. Upload document and create order for Shop B
body_b = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="shop_public_id"\r\n\r\n'
    f'{shop_b_id}\r\n'
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="file"; filename="assignment_b.pdf"\r\n'
    f'Content-Type: application/pdf\r\n\r\n'
).encode('utf-8') + VALID_PDF_BYTES + f'\r\n--{boundary}--\r\n'.encode('utf-8')

req_doc_b = urllib.request.Request(
    f"{BASE_URL}/documents/upload/",
    data=body_b,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)
with urllib.request.urlopen(req_doc_b) as resp:
    doc_res_b = json.loads(resp.read().decode('utf-8'))
doc_b_id = doc_res_b['data']['id']

st_order_b, order_res_b = api_post('/orders/create/', {
    'shop_public_id': shop_b_id,
    'document_id': doc_b_id,
    'copies': 1,
    'color_mode': 'color',
    'paper_size': 'A4',
    'duplex': False,
    'binding': 'none',
    'payment_method': 'cash_on_pickup'
})
assert st_order_b == 201, f"Order B creation failed: {order_res_b}"
order_b_num = order_res_b['data']['order_number']
order_b_pk = order_res_b['data']['id']
order_b_token = order_res_b['data']['access_token']
print(f"PASS [9]: Order {order_b_num} created for Shop B, Total: ${order_res_b['data']['total_price']}")

# 10. Multi-Shop Isolation Verification:
# Shop A admin queries orders: Must only see Order A, never Order B!
st_orders_a, orders_list_a = api_get('/admin/orders/', token=token_a)
shop_a_orders_ids = [o['order_number'] for o in orders_list_a['data']]
assert order_a_num in shop_a_orders_ids, "Order A missing from Shop A"
assert order_b_num not in shop_a_orders_ids, "CRITICAL ISOLATION BREACH: Shop B order visible to Shop A!"

# Shop B admin queries orders: Must only see Order B, never Order A!
st_orders_b, orders_list_b = api_get('/admin/orders/', token=token_b)
shop_b_orders_ids = [o['order_number'] for o in orders_list_b['data']]
assert order_b_num in shop_b_orders_ids, "Order B missing from Shop B"
assert order_a_num not in shop_b_orders_ids, "CRITICAL ISOLATION BREACH: Shop A order visible to Shop B!"

# IDOR Security Check: Shop A admin attempts to approve payment on Shop B's order:
idor_status, idor_res = api_post(f'/admin/orders/{order_b_pk}/pay-ok/', {}, token=token_a)
assert idor_status == 404, f"CRITICAL IDOR BREACH: Shop A accessed Shop B order! Response: {idor_res}"
print("PASS [10]: Multi-Shop Isolation enforced! Shop A cannot view or act upon Shop B orders (HTTP 404 on IDOR).")

# 11. Guest Order Tracking Security Verification
# Querying without access_token is strictly rejected (prevents ID guessing!)
st_guess, guess_res = api_get(f'/orders/track/{order_a_num}/')
assert st_guess == 403, f"Security Breach: Order tracking allowed guessing without access token! Status: {st_guess}"
print("PASS [11.1]: Guest Order Tracking Protected: Unauthenticated request without secret token rejected (HTTP 403).")

# Querying WITH valid access_token succeeds
st_auth_track, auth_track_res = api_get(f'/orders/track/{order_a_num}/?token={order_a_token}')
assert st_auth_track == 200, f"Valid tracking token failed: {auth_track_res}"
print("PASS [11.2]: Guest Order Tracking Verified: Access granted with valid tracking secret token.")

# 12. Document Download Authorization & Anti-Leakage
# Anonymous user attempting to download document directly -> rejected (403)
st_anon_dl, _ = api_get(f'/documents/{doc_a_id}/download/')
assert st_anon_dl == 403, "Security Breach: Unauthenticated user was able to download private document!"

# Shop B admin attempting to download Shop A's document -> rejected (403)
st_cross_dl, _ = api_get(f'/documents/{doc_a_id}/download/', token=token_b)
assert st_cross_dl == 403, "Security Breach: Shop B admin downloaded Shop A's private document!"

# Shop A admin authorized download -> succeeds and streams genuine PDF bytes
st_owner_dl, owner_doc_bytes = api_get(f'/documents/{doc_a_id}/download/', token=token_a)
assert st_owner_dl == 200 and owner_doc_bytes.startswith(b'%PDF-'), "Authorized download failed to stream PDF!"
print("PASS [12]: Document Download Authorization Verified: Cross-shop downloads blocked; owner streams PDF.")

# 13. Pay OK & Block Order Rules
st_pay, pay_res = api_post(f'/admin/orders/{order_a_pk}/pay-ok/', {}, token=token_a)
assert st_pay == 200 and pay_res['data']['payment_status'] == 'paid'

st_block, block_res = api_post(f'/admin/orders/{order_a_pk}/block/', {'reason': 'Tampered document content'}, token=token_a)
assert st_block == 200 and block_res['data']['is_blocked'] is True

st_print_blocked, print_blocked_res = api_post(f'/admin/orders/{order_a_pk}/authorize-print/', {}, token=token_a)
assert st_print_blocked == 400, "CRITICAL SECURITY BREACH: Blocked order was permitted to be printed!"
print("PASS [13]: Security Enforcement Verified: Blocked order cannot be authorized for printing (HTTP 400 rejected).")

# 14. PC Print Agent Spooling & Streaming Retrieval Verification
st_pay_b, pay_res_b = api_post(f'/admin/orders/{order_b_pk}/pay-ok/', {}, token=token_b)
assert st_pay_b == 200

st_print_b, print_res_b = api_post(f'/admin/orders/{order_b_pk}/authorize-print/', {}, token=token_b)
assert st_print_b == 200
print(f"PASS [14.1]: Shop B Admin authorized printing for Order {order_b_num}.")

st_token_b, agent_data_b = api_get('/admin/agent/token/', token=token_b)
agent_token_b = agent_data_b['data']['agent_token']

def agent_poll(agent_token):
    req = urllib.request.Request(
        f"{BASE_URL}/agent/jobs/poll/",
        headers={'X-Agent-Token': agent_token, 'Content-Type': 'application/json'},
        method='GET'
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

st_poll_b, poll_data_b = agent_poll(agent_token_b)
assert st_poll_b == 200 and len(poll_data_b['data']) >= 1
job_b = poll_data_b['data'][0]
assert job_b['order_number'] == order_b_num

# Agent streams authorized document using X-Agent-Token
doc_dl_url = job_b['document_url']
req_agent_dl = urllib.request.Request(
    f"http://127.0.0.1:8000{doc_dl_url}",
    headers={'X-Agent-Token': agent_token_b},
    method='GET'
)
with urllib.request.urlopen(req_agent_dl) as resp:
    agent_dl_bytes = resp.read()
assert agent_dl_bytes.startswith(b'%PDF-'), "Agent document stream was not a valid PDF!"
print(f"PASS [14.2]: Shop B Agent retrieved authorized PDF ({len(agent_dl_bytes)} bytes) from private storage.")

# Agent updates status
def agent_update(job_id, agent_token, status_val):
    req = urllib.request.Request(
        f"{BASE_URL}/agent/jobs/{job_id}/status/",
        data=json.dumps({'status': status_val, 'pages_printed': 1}).encode('utf-8'),
        headers={'X-Agent-Token': agent_token, 'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

st_up_comp, up_comp_res = agent_update(job_b['id'], agent_token_b, 'completed')
assert st_up_comp == 200 and up_comp_res['data']['status'] == 'completed'

# Customer Tracking confirms ready_for_pickup
st_track, track_res = api_get(f'/orders/track/{order_b_num}/?token={order_b_token}')
assert st_track == 200 and track_res['data']['status'] == 'ready_for_pickup'
print(f"PASS [14.3]: Real-time customer tracking confirmed: {track_res['data']['status']}.")

# 15. Unauthorized access protection & Logout
st_anon, _ = api_get('/admin/dashboard/stats/')
assert st_anon == 401

st_logout, _ = api_post('/admin/auth/logout/', {}, token=token_a)
assert st_logout == 200

st_after_logout, _ = api_get('/admin/dashboard/stats/', token=token_a)
assert st_after_logout == 401
print("PASS [15]: Authentication Security Verified: Protected pages block unauthorized users and revoked tokens.")

print("\n>>> ALL 15 COMPREHENSIVE SECURITY, ISOLATION & STORAGE AUDIT TESTS PASSED WITH 100% SUCCESS! <<<")
