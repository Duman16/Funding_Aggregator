"""
Funding Aggregator — Locust Load Test
Alternative to k6 (pure Python).

Usage:
    pip install locust
    locust -f load_tests/locustfile.py --host=http://localhost:8000
    # Then open http://localhost:8089 and set users=100, spawn rate=10

Headless (CI):
    locust -f load_tests/locustfile.py --host=http://localhost:8000 \
        --headless -u 100 -r 10 --run-time 3m \
        --html=load_tests/report.html
"""
import random
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser


SEARCH_TERMS = ["research", "health", "science", "education", "technology"]
SOURCES = ["grants_gov", "nih_reporter", "usa_spending"]


class GrantsAPIUser(HttpUser):
    """Simulates a typical API consumer browsing grants."""

    wait_time = between(0.5, 2)  # realistic think time
    token: str = None
    grant_ids: list = []

    def on_start(self):
        """Register and login on start."""
        self.email = f"locust_{random.randint(1, 999999)}@test.com"
        self.password = "LocustTest123!"

        self.client.post(
            "/api/v1/auth/register",
            json={"email": self.email, "password": self.password},
            name="/api/v1/auth/register",
        )
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": self.email, "password": self.password},
            name="/api/v1/auth/login",
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token")

    def get_auth_headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(5)
    def list_grants(self):
        """Most common: just browse the list."""
        page = random.randint(1, 3)
        with self.client.get(
            f"/api/v1/grants?page={page}&per_page=20",
            name="/api/v1/grants (list)",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                # Cache grant IDs for detail requests
                ids = [g["id"] for g in data.get("items", [])]
                self.grant_ids.extend(ids)
                self.grant_ids = self.grant_ids[-50:]  # keep last 50
                resp.success()
            else:
                resp.failure(f"List failed: {resp.status_code}")

    @task(3)
    def search_grants(self):
        """Full-text search."""
        term = random.choice(SEARCH_TERMS)
        with self.client.get(
            f"/api/v1/grants?search={term}",
            name="/api/v1/grants (search)",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Search failed: {resp.status_code}")

    @task(3)
    def filter_by_source(self):
        """Filter by data source."""
        source = random.choice(SOURCES)
        with self.client.get(
            f"/api/v1/grants?source={source}&per_page=10",
            name="/api/v1/grants (filter source)",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200,):
                resp.success()
            else:
                resp.failure(f"Source filter failed: {resp.status_code}")

    @task(2)
    def get_grant_detail(self):
        """Get a specific grant by ID."""
        if not self.grant_ids:
            self.list_grants()
            return

        grant_id = random.choice(self.grant_ids)
        with self.client.get(
            f"/api/v1/grants/{grant_id}",
            name="/api/v1/grants/{id}",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Detail failed: {resp.status_code}")

    @task(1)
    def health_check(self):
        self.client.get("/api/v1/health", name="/api/v1/health")

    @task(1)
    def get_stats(self):
        self.client.get("/api/v1/stats", name="/api/v1/stats")

    @task(1)
    def get_categories(self):
        self.client.get("/api/v1/categories", name="/api/v1/categories")

    @task(1)
    def get_me(self):
        """Authenticated endpoint."""
        self.client.get(
            "/api/v1/auth/me",
            headers=self.get_auth_headers(),
            name="/api/v1/auth/me",
        )


class AdminUser(HttpUser):
    """Simulates admin users (low frequency)."""

    wait_time = between(5, 15)
    weight = 1  # 1 admin per 10 regular users

    def on_start(self):
        resp = self.client.post(
            "/api/v1/auth/register",
            json={"email": f"admin_{random.randint(1,999)}@test.com", "password": "Admin123!"},
        )
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": resp.json().get("email", ""), "password": "Admin123!"},
        ) if resp.status_code in (201, 409) else None
        self.token = login.json().get("access_token") if login and login.status_code == 200 else None

    @task
    def check_stats(self):
        self.client.get("/api/v1/stats", name="/api/v1/stats (admin)")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("=== Funding Aggregator Load Test Started ===")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("=== Load Test Complete ===")
    stats = environment.stats
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    print(f"Avg response time: {stats.total.avg_response_time:.1f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.1f}ms")
    print(f"RPS: {stats.total.current_rps:.1f}")
