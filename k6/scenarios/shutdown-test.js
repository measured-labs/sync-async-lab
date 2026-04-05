import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const HOST = __ENV.TARGET_HOST || '192.168.55.114';
const PORT = __ENV.TARGET_PORT || '8001';
const BASE_URL = `http://${HOST}:${PORT}`;

const errorRate = new Rate('request_errors');

export const options = {
  stages: [
    { duration: '10s', target: 100 },
    { duration: '50s', target: 100 },
  ],
  thresholds: {
    request_errors: ['rate<1.0'],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/io`, { timeout: '5s' });
  const success = res.status === 200;
  check(res, { 'status is 200': () => success });
  errorRate.add(!success);
}
