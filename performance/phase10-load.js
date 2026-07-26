import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    api_smoke: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

const baseUrl = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const headers = {};
  if (__ENV.ACCESS_TOKEN) {
    headers.Authorization = `Bearer ${__ENV.ACCESS_TOKEN}`;
  }
  const health = http.get(`${baseUrl}/health/ready`);
  check(health, { "readiness is healthy": (response) => response.status === 200 });

  if (__ENV.ACCESS_TOKEN) {
    const notifications = http.get(`${baseUrl}/api/v1/notifications?limit=20`, {
      headers,
    });
    check(notifications, {
      "notification listing succeeds": (response) => response.status === 200,
    });
    const systemHealth = http.get(`${baseUrl}/api/v1/admin/system-health`, {
      headers,
    });
    check(systemHealth, {
      "system health is bounded": (response) =>
        response.status === 200 || response.status === 403,
    });
  }
  sleep(1);
}
