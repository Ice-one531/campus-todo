// ============================================================
// API 封装
// ============================================================
const API = {
  base: '/api',

  async req(method, path, body) {
    const opt = { method, headers: { 'Content-Type': 'application/json' } };
    // 局域网共享时带令牌
    if (typeof TOKEN !== 'undefined' && TOKEN) {
      opt.headers['X-Token'] = TOKEN;
    }
    if (body !== undefined) opt.body = JSON.stringify(body);
    const res = await fetch(this.base + path, opt);
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = { raw: text }; }
    if (!res.ok) throw new Error((data && (data.detail || data.message)) || res.statusText);
    return data;
  },

  get(p)      { return this.req('GET', p); },
  post(p, b)  { return this.req('POST', p, b === undefined ? {} : b); },
  put(p, b)   { return this.req('PUT', p, b); },
  patch(p, b) { return this.req('PATCH', p, b); },
  del(p)      { return this.req('DELETE', p); },

  // 状态
  status()                  { return this.get('/status'); },
  // 配置
  config()                  { return this.get('/config'); },
  saveConfig(c)             { return this.put('/config', c); },
  // 待办
  todos(status)             { return this.get('/todos' + (status ? `?status=${status}` : '')); },
  patchTodo(id, payload)    { return this.patch(`/todos/${id}`, payload); },
  deleteTodo(id)            { return this.del(`/todos/${id}`); },
  // 控制
  control(action)           { return this.post(`/control/${action}`); },
  setGameMode(mode)         { return this.post('/game_mode', { mode }); },
  // 日志/评测
  logs(tail = 200, level)   { return this.get(`/logs?tail=${tail}` + (level ? `&level=${level}` : '')); },
  runEval()                 { return this.post('/eval/run', {}); },
  // ★ QQ 接入
  qqStatus()                { return this.get('/qq/status'); },
  qqQR()                    { return this.get('/qq/qr'); },
  qqGroups()                { return this.get('/qq/groups'); },
  qqStart()                 { return this.post('/qq/start'); },
  qqStop()                  { return this.post('/qq/stop'); },
  qqRestart()               { return this.post('/qq/restart'); },
  qqLogout()                { return this.post('/qq/logout'); },
  qqToggleGroup(id)         { return this.post(`/qq/groups/${id}/toggle`); },
    qqHealth()                { return this.get('/qq/health'); },
    qqWatchdog(payload)       { return this.post('/qq/watchdog', payload); },
    qqRestartNow()            { return this.post('/qq/restart_now'); },
};
