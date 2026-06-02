"""Locust load test for VCW Flask application.

Usage:
    .venv/Scripts/python.exe -m locust -f locustfile.py --host=http://localhost:5000

Scenarios:
  - Health check (lightweight, high frequency)
  - Cached API reads (trends, scheduler, model status)
  - Compression & cache header verification
  - Prometheus metrics scrape
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

    @task(2)
    def trends_page(self):
        """热点列表页面（触发 DB 查询与模板渲染）。"""
        self.client.get("/trends")

    # ------------------------------------------------------------------
    # Cached API endpoints (PO-03 Step 2)
    # ------------------------------------------------------------------

    @task(5)
    def cached_api_trends_fresh(self):
        """访问缓存的热点 API，验证响应头。"""
        with self.client.get("/api/v1/trends/fresh", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status: {resp.status_code}")
                return
            cc = resp.headers.get("Cache-Control", "")
            if "max-age=300" not in cc:
                resp.failure(f"Missing Cache-Control: {cc}")

    @task(2)
    def cached_api_scheduler_status(self):
        """访问缓存的调度器状态 API。"""
        with self.client.get("/api/v1/trends/scheduler/status", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status: {resp.status_code}")
                return
            cc = resp.headers.get("Cache-Control", "")
            if "max-age" not in cc:
                resp.failure(f"Missing Cache-Control: {cc}")

    @task(2)
    def cached_api_model_status(self):
        """访问缓存的模型状态 API。"""
        with self.client.get("/api/v1/model/status", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status: {resp.status_code}")
                return
            cc = resp.headers.get("Cache-Control", "")
            if "max-age" not in cc:
                resp.failure(f"Missing Cache-Control: {cc}")

    # ------------------------------------------------------------------
    # Compression verification (PO-03 Step 1)
    # ------------------------------------------------------------------

    @task(1)
    def compression_check(self):
        """验证大 JSON 响应是否启用 gzip 压缩。"""
        with self.client.get(
            "/api/v1/trends/fresh",
            headers={"Accept-Encoding": "gzip"},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status: {resp.status_code}")
                return
            encoding = resp.headers.get("Content-Encoding", "")
            if "gzip" not in encoding:
                resp.failure(f"Missing gzip encoding: {encoding}")
            # 额外验证 Content-Length 存在（压缩后应有长度）
            if not resp.headers.get("Content-Length"):
                resp.failure("Missing Content-Length")

    # ------------------------------------------------------------------
    # Prometheus metrics scrape
    # ------------------------------------------------------------------

    @task(1)
    def prometheus_metrics(self):
        """抓取 Prometheus /metrics 端点，验证关键指标存在。"""
        with self.client.get("/metrics", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status: {resp.status_code}")
                return
            text = resp.text
            required = [
                "vcw_http_requests_total",
                "vcw_errors_total",
                "db_pool_size",
            ]
            missing = [m for m in required if m not in text]
            if missing:
                resp.failure(f"Missing metrics: {missing}")

    # ------------------------------------------------------------------
    # Write endpoints
    # ------------------------------------------------------------------

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
