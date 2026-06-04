"""
页面路由测试

覆盖主要页面 Blueprint 的 GET 请求，确保模板渲染正常、状态码正确。
"""


class TestIndexPage:
    """首页路由测试"""

    def test_index_status_200(self, client):
        """首页返回 200"""
        response = client.get("/")
        assert response.status_code == 200

    def test_index_contains_title(self, client):
        """首页包含产品名称"""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "港籍升学文案生成器" in html or "文案生成" in html

    def test_index_prefill_params(self, client):
        """首页支持从热点页面带过来的预填充参数"""
        response = client.get("/?topic=DSE&core_data=5万人")
        assert response.status_code == 200


class TestTrendsPage:
    """热点发现页面测试"""

    def test_trends_status_200(self, client):
        """热点页面返回 200"""
        response = client.get("/trends")
        if response.status_code == 500:
            print("===== RESPONSE BODY =====")
            print(response.get_data(as_text=True))
        assert response.status_code == 200

    def test_trends_pagination(self, client):
        """热点页面支持分页参数"""
        response = client.get("/trends?page=2&per_page=10")
        assert response.status_code == 200


class TestConfigPage:
    """配置页面测试"""

    def test_config_status_200(self, client):
        """配置页面返回 200"""
        response = client.get("/config")
        assert response.status_code == 200


class TestBatchPage:
    """批量生成页面测试"""

    def test_batch_status_200(self, client):
        """批量页面返回 200"""
        response = client.get("/batch")
        assert response.status_code == 200


class TestHistoryPage:
    """历史记录页面测试"""

    def test_history_status_200(self, client):
        """历史页面返回 200"""
        response = client.get("/history")
        assert response.status_code == 200
