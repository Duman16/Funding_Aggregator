/**
 * Funding Aggregator — k6 Load Test
 * Week 13: Performance Testing
 *
 * Usage:
 *   k6 run load_tests/k6_script.js
 *   k6 run --out json=results.json load_tests/k6_script.js
 *
 * Install k6: https://k6.io/docs/getting-started/installation/
 */
import http from "k6/http";
import { check, sleep, group } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

// ─── Custom Metrics ────────────────────────────────────────────────────────
const errorRate = new Rate("errors");
const grantListDuration = new Trend("grant_list_duration", true);
const grantDetailDuration = new Trend("grant_detail_duration", true);
const authDuration = new Trend("auth_duration", true);

// ─── Configuration ─────────────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  scenarios: {
    // Scenario 1: Ramp up to 100 concurrent users
    load_test: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 25 },   // warm up
        { duration: "1m",  target: 100 },  // ramp to 100 users
        { duration: "2m",  target: 100 },  // hold at 100
        { duration: "30s", target: 0 },    // ramp down
      ],
      gracefulRampDown: "10s",
    },

    // Scenario 2: Spike test
    spike_test: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 10 },
        { duration: "10s", target: 200 },  // spike!
        { duration: "20s", target: 200 },
        { duration: "10s", target: 10 },
        { duration: "10s", target: 0 },
      ],
      startTime: "5m",  // start after load_test finishes
      gracefulRampDown: "5s",
    },
  },

  thresholds: {
    // 95% of requests must complete within 500ms
    http_req_duration: ["p(95)<500"],
    // Error rate must be below 5%
    errors: ["rate<0.05"],
    // Grant list 95th percentile under 600ms
    grant_list_duration: ["p(95)<600"],
    // Grant detail 95th percentile under 400ms
    grant_detail_duration: ["p(95)<400"],
  },
};

// ─── Test Data ─────────────────────────────────────────────────────────────
const TEST_USER = {
  email: `loadtest_${__VU}@example.com`,
  password: "LoadTest123!",
};

const SEARCH_TERMS = [
  "research", "health", "science", "education",
  "technology", "environment", "community", "medical",
];

const SOURCES = ["grants_gov", "nih_reporter", "usa_spending"];
const STATUSES = ["open", "forecasted"];

// ─── Helpers ────────────────────────────────────────────────────────────────
function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function getAuthToken() {
  // Register
  http.post(
    `${BASE_URL}/api/v1/auth/register`,
    JSON.stringify(TEST_USER),
    { headers: { "Content-Type": "application/json" } }
  );

  // Login
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify(TEST_USER),
    { headers: { "Content-Type": "application/json" } }
  );

  if (loginRes.status === 200) {
    return loginRes.json("access_token");
  }
  return null;
}

// ─── Main Test Function ─────────────────────────────────────────────────────
export default function () {
  const headers = { "Content-Type": "application/json" };

  // ── Group 1: Public endpoints ─────────────────────────────────────────
  group("Public Endpoints", function () {
    // Health check
    group("Health Check", function () {
      const res = http.get(`${BASE_URL}/api/v1/health`, { headers });
      const ok = check(res, {
        "health status 200": (r) => r.status === 200,
        "health status is ok": (r) => r.json("status") === "ok" || r.json("status") === "degraded",
      });
      errorRate.add(!ok);
    });

    // Stats
    group("Stats", function () {
      const res = http.get(`${BASE_URL}/api/v1/stats`, { headers });
      check(res, {
        "stats status 200": (r) => r.status === 200,
        "stats has total_grants": (r) => r.json("total_grants") !== undefined,
      });
    });

    sleep(0.5);
  });

  // ── Group 2: Grant listing with various filters ───────────────────────
  group("Grant Listing", function () {
    // Basic list
    group("List All Grants", function () {
      const start = Date.now();
      const res = http.get(`${BASE_URL}/api/v1/grants`, { headers });
      grantListDuration.add(Date.now() - start);

      const ok = check(res, {
        "grants list 200": (r) => r.status === 200,
        "has items array": (r) => Array.isArray(r.json("items")),
        "has total": (r) => r.json("total") !== undefined,
        "has pagination": (r) => r.json("page") === 1,
      });
      errorRate.add(!ok);
    });

    sleep(0.3);

    // Filter by source
    group("Filter by Source", function () {
      const source = randomItem(SOURCES);
      const start = Date.now();
      const res = http.get(`${BASE_URL}/api/v1/grants?source=${source}&per_page=10`, { headers });
      grantListDuration.add(Date.now() - start);

      check(res, {
        "source filter 200": (r) => r.status === 200,
      });
    });

    sleep(0.3);

    // Full-text search
    group("Full-Text Search", function () {
      const term = randomItem(SEARCH_TERMS);
      const start = Date.now();
      const res = http.get(
        `${BASE_URL}/api/v1/grants?search=${term}&per_page=20`,
        { headers }
      );
      grantListDuration.add(Date.now() - start);

      check(res, {
        "search 200": (r) => r.status === 200,
        "search returns results": (r) => r.json("total") >= 0,
      });
    });

    sleep(0.3);

    // Filter by status
    group("Filter by Status", function () {
      const s = randomItem(STATUSES);
      const res = http.get(
        `${BASE_URL}/api/v1/grants?status=${s}&page=1&per_page=10`,
        { headers }
      );
      check(res, {
        "status filter 200": (r) => r.status === 200,
      });
    });

    sleep(0.3);

    // Pagination
    group("Pagination", function () {
      const page = Math.floor(Math.random() * 5) + 1;
      const res = http.get(
        `${BASE_URL}/api/v1/grants?page=${page}&per_page=25`,
        { headers }
      );
      check(res, {
        "pagination 200": (r) => r.status === 200,
        "correct page": (r) => r.json("page") === page,
      });
    });

    sleep(0.3);
  });

  // ── Group 3: Grant detail ────────────────────────────────────────────
  group("Grant Detail", function () {
    // First fetch list to get real IDs
    const listRes = http.get(`${BASE_URL}/api/v1/grants?per_page=5`, { headers });

    if (listRes.status === 200) {
      const items = listRes.json("items") || [];
      if (items.length > 0) {
        const grant = randomItem(items);
        const start = Date.now();
        const res = http.get(`${BASE_URL}/api/v1/grants/${grant.id}`, { headers });
        grantDetailDuration.add(Date.now() - start);

        const ok = check(res, {
          "grant detail 200": (r) => r.status === 200,
          "has title": (r) => r.json("title") !== undefined,
          "has source": (r) => r.json("source") !== undefined,
        });
        errorRate.add(!ok);
      }
    }

    // 404 test
    const notFoundRes = http.get(
      `${BASE_URL}/api/v1/grants/00000000-0000-0000-0000-000000000000`,
      { headers }
    );
    check(notFoundRes, {
      "non-existent grant 404": (r) => r.status === 404,
    });

    sleep(0.5);
  });

  // ── Group 4: Auth (10% of VUs) ───────────────────────────────────────
  group("Authentication", function () {
    if (__VU % 10 === 0) {
      // Register + login
      const start = Date.now();
      const token = getAuthToken();
      authDuration.add(Date.now() - start);

      if (token) {
        // /me endpoint
        const meRes = http.get(`${BASE_URL}/api/v1/auth/me`, {
          headers: {
            ...headers,
            Authorization: `Bearer ${token}`,
          },
        });
        check(meRes, {
          "me 200": (r) => r.status === 200,
          "me has email": (r) => r.json("email") !== undefined,
        });
      }
    }
  });

  // ── Group 5: Categories ──────────────────────────────────────────────
  group("Categories", function () {
    const res = http.get(`${BASE_URL}/api/v1/categories`, { headers });
    check(res, {
      "categories 200": (r) => r.status === 200,
    });

    sleep(0.2);
  });

  sleep(1);
}

// ─── Setup: seed test data before test ─────────────────────────────────────
export function setup() {
  console.log(`Starting load test against: ${BASE_URL}`);

  const healthRes = http.get(`${BASE_URL}/api/v1/health`);
  if (healthRes.status !== 200) {
    console.error("Service is not healthy! Aborting.");
    return { healthy: false };
  }

  const statsRes = http.get(`${BASE_URL}/api/v1/stats`);
  const totalGrants = statsRes.json("total_grants") || 0;
  console.log(`Total grants in DB: ${totalGrants}`);

  return { healthy: true, totalGrants };
}

// ─── Teardown ───────────────────────────────────────────────────────────────
export function teardown(data) {
  console.log(`Load test complete. Initial grants: ${data.totalGrants}`);
}
