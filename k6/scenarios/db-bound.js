import http from 'k6/http';
import { check } from 'k6';

const HOST = __ENV.TARGET_HOST || '192.168.55.114';
const PORT = __ENV.TARGET_PORT || '8001';
const BASE_URL = `http://${HOST}:${PORT}`;

export const options = {
  stages: [
    { duration: '30s', target: 200 },
    { duration: '60s', target: 200 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<10000'],
    http_req_failed: ['rate<0.05'],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/db`);
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
}
