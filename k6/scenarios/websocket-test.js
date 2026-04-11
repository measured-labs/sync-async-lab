import ws from 'k6/ws';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const HOST = __ENV.TARGET_HOST || '192.168.55.114';
const PORT = __ENV.TARGET_PORT || '8002';
const WS_URL = `ws://${HOST}:${PORT}/ws`;
const VUS = parseInt(__ENV.WS_VUS || '100');

const msgRtt = new Trend('ws_msg_rtt', true);
const msgCount = new Counter('ws_msg_count');

export const options = {
  scenarios: {
    websocket: {
      executor: 'constant-vus',
      vus: VUS,
      duration: '60s',
    },
  },
};

export default function () {
  const res = ws.connect(WS_URL, {}, function (socket) {
    socket.on('open', function () {
      // Send first message immediately
      const sendTime = Date.now();
      socket.send(JSON.stringify({ ts: sendTime, seq: 0 }));

      // Send 9 more messages with 1s interval
      for (let i = 1; i <= 9; i++) {
        socket.setTimeout(function () {
          const t = Date.now();
          socket.send(JSON.stringify({ ts: t, seq: i }));
        }, i * 1000);
      }

      // Close after all messages sent
      socket.setTimeout(function () {
        socket.close();
      }, 11000);
    });

    socket.on('message', function (data) {
      const msg = JSON.parse(data);
      const rtt = Date.now() - msg.ts;
      msgRtt.add(rtt);
      msgCount.add(1);
    });

    socket.on('error', function (e) {
      // connection error
    });
  });

  check(res, {
    'ws status is 101': (r) => r && r.status === 101,
  });
}
