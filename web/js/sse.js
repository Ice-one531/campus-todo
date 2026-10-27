// ============================================================
// SSE 订阅（后端 → 前端单向推送）
// 为什么不用轮询：每秒一次 HTTP 请求会白占 worker，也没必要
// 为什么不用 WebSocket：状态是单向推送，SSE 更简单，且自带断线重连
// ============================================================
function createStatusStream({ onMessage, onStateChange }) {
  let es = null;
  let retry = 0;

  function connect() {
    try {
      const _u = (typeof withToken === 'function') ? withToken('/api/stream/status') : '/api/stream/status';
        es = new EventSource(_u);

      es.onopen = () => {
        retry = 0;
        if (onStateChange) onStateChange('open');
      };

      es.onmessage = (e) => {
        if (!e.data || e.data.startsWith(':')) return;
        try {
          const payload = JSON.parse(e.data);
          if (onMessage) onMessage(payload);
        } catch (err) {
          console.warn('SSE 解析失败', err, e.data);
        }
      };

      es.onerror = () => {
        if (onStateChange) onStateChange('closed');
        // EventSource 自带重连，但服务重启后可能卡住，手动兜底
        retry += 1;
        if (retry > 3) {
          es.close();
          es = null;
          setTimeout(connect, Math.min(3000 * retry, 15000));
        }
      };
    } catch (err) {
      console.error('SSE 连接失败', err);
    }
  }

  connect();

  return {
    close() { if (es) { es.close(); es = null; } },
  };
}