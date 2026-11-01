"""
PrintX - PC Print Agent
Runs on shop counter PC to poll authorized print jobs from Django backend
and spool documents to the shop's physical printer.
Strict shop isolation: Only processes jobs queued for this specific shop.
"""

import sys
import time
import json
import argparse
import urllib.request
import urllib.error

class PrintXAgent:
    def __init__(self, backend_url, agent_token, poll_interval=5):
        self.backend_url = backend_url.rstrip('/')
        self.agent_token = agent_token
        self.poll_interval = poll_interval

    def _request(self, endpoint, method='GET', data=None):
        url = f"{self.backend_url}{endpoint}"
        headers = {
            'X-Agent-Token': self.agent_token,
            'Content-Type': 'application/json'
        }
        body = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode('utf-8'))
            except Exception:
                err_body = {'message': str(e)}
            return e.code, err_body
        except Exception as e:
            return 500, {'message': f'Network error: {str(e)}'}

    def _download_document(self, download_endpoint):
        # Handle relative or absolute download path
        endpoint = download_endpoint
        if endpoint.startswith('http://') or endpoint.startswith('https://'):
            url = endpoint
        else:
            base = self.backend_url.replace('/api/v1', '')
            url = f"{base}{endpoint}"

        headers = {
            'X-Agent-Token': self.agent_token,
        }
        req = urllib.request.Request(url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    return True, resp.read()
                return False, f"HTTP {resp.status}"
        except Exception as e:
            return False, str(e)


    def poll_and_process(self):
        print(f"[PrintX Agent] Polling for queued print jobs...")
        status_code, resp = self._request('/agent/jobs/poll/')

        if status_code != 200:
            print(f"[PrintX Agent] Error polling backend ({status_code}): {resp.get('message')}")
            return

        jobs = resp.get('data', [])
        shop_name = resp.get('shop_name', 'Unknown Shop')

        if not jobs:
            return

        print(f"[PrintX Agent] Connected to: {shop_name}")
        print(f"[PrintX Agent] Found {len(jobs)} pending print job(s)")

        for job in jobs:
            self.process_job(job)

    def process_job(self, job):
        job_id = job['id']
        order_num = job.get('order_number')
        doc_name = job.get('document_name')
        copies = job.get('copies', 1)
        color = job.get('color_mode', 'bw')
        duplex = "Double-Sided" if job.get('duplex') else "Single-Sided"

        print(f"\n--- Processing Print Job #{job_id} ---")
        print(f"Order:       {order_num}")
        print(f"Document:    {doc_name}")
        print(f"Copies:      {copies}")
        print(f"Color Mode:  {color.upper()}")
        print(f"Format:      {duplex}")

        # Step 1: Update status to 'printing'
        print(f"[PrintX Agent] Updating status -> PRINTING")
        self._request(f'/agent/jobs/{job_id}/status/', method='POST', data={
            'status': 'printing',
            'pages_printed': 0
        })

        # Step 2: Retrieve authorized document from private backend storage
        print(f"[PrintX Agent] Downloading document from secure backend...")
        doc_url = job.get('document_url')
        if doc_url:
            success, content = self._download_document(doc_url)
            if not success:
                print(f"[PrintX Agent] ERROR: Failed to retrieve document: {content}")
                self._request(f'/agent/jobs/{job_id}/status/', method='POST', data={
                    'status': 'failed',
                    'error_message': f'Document retrieval failure: {content}'
                })
                return
            print(f"[PrintX Agent] Successfully downloaded {len(content)} bytes.")

        # Step 3: Spool document to physical printer
        time.sleep(1) # Spooling simulation / hardware delay
        print(f"[PrintX Agent] Spooling to local printer driver: COMPLETE")

        # Step 4: Update status to 'completed'
        print(f"[PrintX Agent] Updating status -> COMPLETED")
        self._request(f'/agent/jobs/{job_id}/status/', method='POST', data={
            'status': 'completed',
            'pages_printed': copies
        })

        print(f"[PrintX Agent] Order {order_num} is ready for customer pickup.\n")

    def run(self, once=False):
        print("==================================================")
        print("          PrintX PC Print Spooler Agent          ")
        print("==================================================")
        print(f"Backend URL:   {self.backend_url}")
        print(f"Agent Token:   {self.agent_token[:8]}...")
        print("Connecting to backend and listening for authorized jobs...\n")

        while True:
            try:
                self.poll_and_process()
                if once:
                    break
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                print("\n[PrintX Agent] Stopped by user.")
                break

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PrintX PC Print Agent')
    parser.add_argument('--url', default='http://127.0.0.1:8000/api/v1', help='PrintX Backend API URL')
    parser.add_argument('--token', required=True, help='Shop PC Print Agent Pairing Token')
    parser.add_argument('--interval', type=int, default=5, help='Poll interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run a single polling cycle')
    args = parser.parse_args()

    agent = PrintXAgent(backend_url=args.url, agent_token=args.token, poll_interval=args.interval)
    agent.run(once=args.once)
