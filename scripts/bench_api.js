// PD Server — API Load Test (k6)
//
// Simulates realistic user flow: register → login → create group → create test
// (tremor, drawing, voice) → upload data → complete → check results
//
// Usage:
//   k6 run scripts/bench_api.js
//
// Options:
//   k6 run -e BASE_URL=http://localhost:5000 -e VUS=20 scripts/bench_api.js
//
// Install k6: https://k6.io/docs/getting-started/installation/

import { check, sleep, group } from 'k6';
import http from 'k6/http';
import { SharedArray } from 'k6/data';
import { randomString } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const DEFAULT_VUS = parseInt(__ENV.VUS || '20');

export const options = {
  stages: [
    { duration: '30s', target: Math.min(DEFAULT_VUS, 10) },    // Ramp to low load
    { duration: '30s', target: DEFAULT_VUS },                   // Ramp to target
    { duration: '60s', target: DEFAULT_VUS },                   // Hold
    { duration: '30s', target: 0 },                             // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],  // 95% under 2s, 99% under 5s
    http_req_failed: ['rate<0.05'],                    // <5% error rate
  },
};

export default function () {
  const email = `bench_${randomString(8)}@test.com`;
  const password = 'BenchPass123!';
  let accessToken = '';
  let testIds = [];
  let groupId = '';

  // ── 1. Register ──────────────────────────────────────────────
  group('Auth Flow', function () {
    const regPayload = JSON.stringify({
      email: email,
      password: password,
    });
    let res = http.post(`${BASE_URL}/api/auth/register`, regPayload, {
      headers: { 'Content-Type': 'application/json' },
      tags: { endpoint: 'register' },
    });
    check(res, { 'register success': (r) => r.status === 201 });
    if (res.status !== 201) {
      sleep(1);
      return;
    }

    // Login
    const loginPayload = JSON.stringify({ email: email, password: password });
    res = http.post(`${BASE_URL}/api/auth/login`, loginPayload, {
      headers: { 'Content-Type': 'application/json' },
      tags: { endpoint: 'login' },
    });
    check(res, { 'login success': (r) => r.status === 200 });
    if (res.status !== 200) {
      sleep(1);
      return;
    }
    accessToken = res.json('access_token');
  });

  if (!accessToken) {
    sleep(1);
    return;
  }

  const authHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${accessToken}`,
  };

  // ── 2. Create Group ──────────────────────────────────────────
  group('Test Group', function () {
    const res = http.post(`${BASE_URL}/api/groups`, '{}', {
      headers: authHeaders,
      tags: { endpoint: 'create_group' },
    });
    check(res, { 'group created': (r) => r.status === 201 });
    if (res.status === 201) {
      groupId = res.json('id');
    }
  });

  if (!groupId) {
    sleep(1);
    return;
  }

  // ── 3. Create Tests + Upload + Complete ──────────────────────
  const testTypes = ['tremor', 'drawing', 'voice'];

  group('Test Lifecycle', function () {
    for (const testType of testTypes) {
      // Create test session
      const createPayload = JSON.stringify({
        group_id: groupId,
        test_type: testType,
        config: { 0: true, 1: true },
      });
      let res = http.post(`${BASE_URL}/api/tests`, createPayload, {
        headers: authHeaders,
        tags: { endpoint: 'create_test' },
      });
      check(res, { [`${testType} test created`]: (r) => r.status === 201 });
      if (res.status !== 201) continue;

      const testId = res.json('id');
      testIds.push(testId);

      // Upload data (different payload per type)
      let uploadUrl = `${BASE_URL}/api/tests/${testId}/${testType}`;
      let uploadRes;

      if (testType === 'tremor') {
        // Generate mock IMU data
        const imuData = {
          ax: Array.from({ length: 100 }, () => Math.random() * 2 - 1),
          ay: Array.from({ length: 100 }, () => Math.random() * 2 - 1),
          az: Array.from({ length: 100 }, () => Math.random() * 2 + 9),
          gx: Array.from({ length: 100 }, () => Math.random() * 0.1 - 0.05),
          gy: Array.from({ length: 100 }, () => Math.random() * 0.1 - 0.05),
          gz: Array.from({ length: 100 }, () => Math.random() * 0.1 - 0.05),
        };
        uploadRes = http.post(uploadUrl, JSON.stringify(imuData), {
          headers: authHeaders,
          tags: { endpoint: 'upload_tremor' },
        });
      } else if (testType === 'drawing') {
        const boundary = '----FormBoundary' + randomString(16);
        let body = `--${boundary}\r\n`;
        body += 'Content-Disposition: form-data; name="left_image"; filename="left.png"\r\n';
        body += 'Content-Type: image/png\r\n\r\n';
        body += 'FAKE_IMAGE_DATA_LEFT\r\n';
        body += `--${boundary}\r\n`;
        body += 'Content-Disposition: form-data; name="right_image"; filename="right.png"\r\n';
        body += 'Content-Type: image/png\r\n\r\n';
        body += 'FAKE_IMAGE_DATA_RIGHT\r\n';
        body += `--${boundary}--\r\n`;

        uploadRes = http.post(uploadUrl, body, {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': `multipart/form-data; boundary=${boundary}`,
          },
          tags: { endpoint: 'upload_drawing' },
        });
      } else if (testType === 'voice') {
        const boundary = '----FormBoundary' + randomString(16);
        let body = `--${boundary}\r\n`;
        body += 'Content-Disposition: form-data; name="file"; filename="voice.wav"\r\n';
        body += 'Content-Type: audio/wav\r\n\r\n';
        body += 'FAKE_AUDIO_DATA\r\n';
        body += `--${boundary}--\r\n`;

        uploadRes = http.post(uploadUrl, body, {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': `multipart/form-data; boundary=${boundary}`,
          },
          tags: { endpoint: 'upload_voice' },
        });
      }

      check(uploadRes, { [`${testType} upload ok`]: (r) => r.status === 200 || r.status === 201 });
      sleep(0.5);
    }
  });

  // ── 4. Complete tests ────────────────────────────────────────
  group('Test Completion', function () {
    for (const testId of testIds) {
      const res = http.post(`${BASE_URL}/api/tests/${testId}/complete`, '{}', {
        headers: authHeaders,
        tags: { endpoint: 'complete_test' },
      });
      check(res, { [`test ${testId} completed`]: (r) => r.status === 200 });
      sleep(0.5);
    }
  });

  // ── 5. Check results ─────────────────────────────────────────
  group('Results', function () {
    for (const testId of testIds) {
      const res = http.get(`${BASE_URL}/api/tests/${testId}`, {
        headers: authHeaders,
        tags: { endpoint: 'get_result' },
      });
      check(res, { [`result for ${testId}`]: (r) => r.status === 200 });
    }
  });

  sleep(1);
}
