"""Locust load test for VCW Flask application.

Usage:
    .venv/Scripts/python.exe -m locust -f locustfile.py --host=http://localhost:5000

Scenarios:
  - Health check (lightweight, high frequency)
  - Generate copy (medium weight)
  - Batch generate (heavy weight)
  - Config page read
"""

from locust import HttpUser, task, between


class VCWUser(HttpUser):
    """Simulates a typical VCW user."""

    wait_time = between(1, 3)

    @task(5)
    def health_check(self):
        """高频健康检查端点。"""
        with self.client.get("/health", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") != "ok":
                    resp.failure(f"Health degraded: {data}")
            elif resp.status_code == 503:
                data = resp.json()
                if data.get("status") != "degraded":
                    resp.failure(f"Unexpected 503 body: {data}")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(3)
    def index_page(self):
        self.client.get("/")

    @task(2)
    def config_page(self):
        self.client.get("/config")

    @task(1)
    def generate_copy(self):
        """文案生成端点（需要 API key 配置）。"""
        payload = {
            "topic": "DSE考砸后的保底路径",
            "audience": "港宝家长",
            "style": "焦虑型",
        }
        with self.client.post("/api/v1/generate", json=payload, catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("success"):
                    # API key missing is expected in load test env
                    if data.get("error", {}).get("code") == "API_KEY_MISSING":
                        resp.success()
                    else:
                        resp.failure(f"Generate failed: {data}")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def batch_generate(self):
        """批量生成端点。"""
        payload = {
            "topic": "压力测试主题",
            "audience": "港宝家长",
            "angles": ["焦虑型", "数据型", "故事型"],
        }
        with self.client.post("/api/v1/generate/batch", json=payload, catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("success"):
                    if data.get("error", {}).get("code") == "API_KEY_MISSING":
                        resp.success()
                    else:
                        resp.failure(f"Batch failed: {data}")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")
