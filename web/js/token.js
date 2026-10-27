// ============================================================
// 访问令牌管理
// 局域网共享时，同学通过 http://IP:8000/console/?token=xxx 访问，
// 这里把 token 存下来，后续所有请求自动带上。
// ============================================================
const TOKEN = (() => {
  const KEY = 'campus_token';
  // 1. URL 里带了就以它为准（并写入本地）
  const url = new URLSearchParams(location.search);
  const fromUrl = url.get('token');
  if (fromUrl) {
    try { localStorage.setItem(KEY, fromUrl); } catch (e) {}
    // 清理地址栏，不让 token 一直挂在 URL 上
    try {
      url.delete('token');
      const qs = url.toString();
      history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
    } catch (e) {}
    return fromUrl;
  }
  // 2. 否则用本地存的
  try { return localStorage.getItem(KEY) || ''; } catch (e) { return ''; }
})();

/** 给 URL 追加 token 参数（供 EventSource 用，它不支持自定义头） */
function withToken(url) {
  if (!TOKEN) return url;
  return url + (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(TOKEN);
}