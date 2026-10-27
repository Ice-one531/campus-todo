// ============================================================
// 主应用：待办优先 + 双栏 + QQ 绑定
// ============================================================
const { createApp } = Vue;

const App = {
  components: { SettingsView, LogsView, EvalView },

  data() {
    return {
      route: 'home',
      snap: {
        service_running: false, model_status: '未知', model_name: '',
        game_mode: 'auto', is_gaming: false, queue_size: 0,
        ocr_status: '未知', todos: {},
      },
      counts: { pending_confirm: 0, active: 0, completed: 0, ignored: 0 },

      // 待办
      tab: 'active',
      todosByTab: { active: [], pending_confirm: [], completed: [], ignored: [] },
      loadingTodos: false,
      _firstLoad: true,
      tabs: [
        { key: 'active',           label: '待处理', icon: '★',  count: 0 },
        { key: 'pending_confirm',  label: '待确认', icon: '⚠️', count: 0 },
        { key: 'completed',        label: '已完成', icon: '✅', count: 0 },
      ],

      // QQ
      qq: { running: false, logged_in: false, phase: 'unknown', hint: '', uin: null, nickname: null },
      health: { state: 'unknown', text: '检测中…', checked_at: 0, watchdog: {} },
      watchdogOn: false,
      healthTimer: null,
      qqDialog: false,
      qrData: null,
      starting: false,
      qqTimer: null,

      // 群
      allGroups: [],
      monitoredList: [],
      groupDialog: false,
      groupLoading: false,

      // 弹窗
      rawDialog: false, rawContent: '',
      diffDialog: false, diffOld: '', diffNew: '', diffId: 0,

      // 快速添加
      quickText: '',

      stream: null,
      sseOk: false,
      clock: '',
      timerId: null,
    };
  },

  computed: {
    todayText() {
      const d = new Date();
      const w = ['周日','周一','周二','周三','周四','周五','周六'][d.getDay()];
      return `${d.getMonth()+1}月${d.getDate()}日 ${w}`;
    },
    greeting() {
      const h = new Date().getHours();
      if (h < 6) return '夜深了，早点休息';
      if (h < 12) return '早上好';
      if (h < 14) return '中午好';
      if (h < 18) return '下午好';
      return '晚上好';
    },
    qqPill() {
      if (this.qq.logged_in) return { cls: 'ok', text: `QQ ${this.qq.nickname || ''}`, tip: `${this.qq.uin}` };
      if (this.qq.running) return { cls: 'warn', text: 'QQ 待登录', tip: '点击扫码登录' };
      return { cls: 'off', text: 'QQ 未连接', tip: '点击绑定 QQ' };
    },
    modelPill() {
      const s = this.snap.model_status || '';
      if (s.includes('已加载')) return { cls: 'ok', text: '模型就绪', tip: this.snap.model_name };
      if (s.includes('加载中')) return { cls: 'busy', text: '模型加载中', tip: '' };
      if (s.includes('游戏中')) return { cls: 'off', text: '模型休眠', tip: '游戏模式，让出显存' };
      return { cls: 'off', text: '模型未加载', tip: s };
    },
    gamePill() {
      if (this.snap.is_gaming) return { cls: 'warn', text: '游戏模式', tip: '消息入队，退出游戏后自动处理' };
      if (this.snap.game_mode === 'force_game') return { cls: 'warn', text: '强制游戏', tip: '手动关闭推理' };
      return { cls: 'ok', text: '日常模式', tip: '消息实时解析' };
    },
    currentTodos() {
      return this.todosByTab[this.tab] || [];
    },
    healthAge() {
      if (!this.health.checked_at) return '';
      const s = Math.floor(Date.now() / 1000 - this.health.checked_at);
      if (s < 5) return '刚刚';
      if (s < 60) return s + '秒';
      return Math.floor(s / 60) + '分';
    },
    emptyText() {
      return {
        active: '没有待处理的任务，清闲～',
        pending_confirm: '没有需要确认的任务',
        completed: '还没有完成的任务',
        ignored: '没有忽略的任务',
      }[this.tab] || '暂无内容';
    },
    viewComp() {
      return { settings: 'SettingsView', logs: 'LogsView', eval: 'EvalView' }[this.route] || null;
    },
  },

  mounted() {
    this.refreshAll();
    this.loadQQ();

    this.stream = createStatusStream({
      onMessage: (p) => {
        this.snap = Object.assign({}, this.snap, p);
        if (p.todos) this.syncCounts(p.todos);
        this.sseOk = true;
      },
      onStateChange: (s) => { this.sseOk = (s === 'open'); },
    });

    // 兜底轮询
    this.timerId = setInterval(() => {
      if (!this.sseOk) this.refreshAll();
    }, 20000);

    // NapCat 健康检查（10 秒一次）
    this.refreshHealth();
    this.healthTimer = setInterval(() => this.refreshHealth(), 10000);
  },

  beforeUnmount() {
    if (this.stream) this.stream.close();
    if (this.timerId) clearInterval(this.timerId);
    if (this.qqTimer) clearInterval(this.qqTimer);
    if (this.healthTimer) clearInterval(this.healthTimer);
  },

  watch: {
    tab() { this.loadTodos(); },
    'snap.last_event'() {
      this.loadTodos();
      if (['qq_starting', 'group_changed'].includes(this.snap.last_event)) this.loadQQ();
    },
  },

  methods: {
    // ---------- 基础 ----------
    async refreshAll() {
      try {
        const s = await API.status();
        this.snap = Object.assign({}, this.snap, s);
        if (s.todos) this.syncCounts(s.todos);

        // 首次加载：智能选 tab（避免打开看到空白页）
        if (this._firstLoad) {
          this._firstLoad = false;
          const t = s.todos || {};
          if ((t.active || 0) === 0 && (t.pending_confirm || 0) > 0) {
            this.tab = 'pending_confirm';
          }
        }
        await this.loadTodos();
      } catch (e) { console.warn('刷新失败', e); }
    },

    syncCounts(t) {
      this.counts = t;
      this.tabs[0].count = t.active || 0;
      this.tabs[1].count = t.pending_confirm || 0;
      this.tabs[2].count = t.completed || 0;
    },

    async loadTodos() {
      this.loadingTodos = true;
      try {
        const r = await API.todos(this.tab);
        // 后端会告诉我们当前是否已登录；未登录时不显示任何待办
        if (r && r.logged_in === false) {
          this.todosByTab[this.tab] = [];
          this.todosByTab.active = [];
          this.todosByTab.pending_confirm = [];
          this.todosByTab.completed = [];
        } else {
          this.todosByTab[this.tab] = (r && r.items) || [];
        }
      } catch (e) { console.warn(e); }
      finally { this.loadingTodos = false; }
    },

    toast(msg, type = 'info') {
      ElementPlus.ElMessage({ message: msg, type, duration: type === 'error' ? 4000 : 2200, showClose: true });
    },

    onMenu(cmd) {
      if (cmd === 'restart') { this.restartQQ(); return; }
      this.route = cmd;
      if (cmd !== 'home') this.$nextTick(() => this.loadTodos());
    },

    // ---------- 待办操作 ----------
    async toggleDone(t) {
      const target = t.status === 'completed' ? 'active' : 'completed';
      await this.setStatus(t, target);
    },

    async setStatus(t, status) {
      try {
        await API.patchTodo(t.id, { status });
        this.toast(status === 'completed' ? '已标记完成' : '已更新', 'success');
        await this.loadTodos();
        this.refreshAll();
      } catch (e) { this.toast('操作失败：' + e.message, 'error'); }
    },

    async removeTodo(t) {
      try {
        await this.$confirm(`删除「${t.title}」？`, '确认', { type: 'warning' });
      } catch (e) { return; }
      try {
        await API.deleteTodo(t.id);
        this.toast('已删除', 'success');
        this.loadTodos();
        this.refreshAll();
      } catch (e) { this.toast(e.message, 'error'); }
    },

    async quickAdd() {
      const text = (this.quickText || '').trim();
      if (!text) return;
      try {
        // 走 webhook 的自定义通道：直接入库
        const h = { 'Content-Type': 'application/json' };
        if (typeof TOKEN !== 'undefined' && TOKEN) h['X-Token'] = TOKEN;
        await fetch('/api/todos/manual', {
          method: 'POST', headers: h, body: JSON.stringify({ text }),
        });
        this.quickText = '';
        this.toast('已添加', 'success');
        this.loadTodos();
        this.refreshAll();
      } catch (e) { this.toast('添加失败', 'error'); }
    },

    showRaw(t) {
      this.rawContent = t.raw_attachment || '（没有原始记录）';
      this.rawDialog = true;
    },

    showDiff(t) {
      this.diffOld = t.old_details || '（无历史）';
      this.diffNew = `标题: ${t.title}\n时间: ${t.deadline}\n地点: ${t.location}\n详情: ${t.details}`;
      this.diffId = t.id;
      this.diffDialog = true;
    },

    async clearFlag() {
      try {
        await API.patchTodo(this.diffId, { clear_modified: true });
        this.diffDialog = false;
        this.loadTodos();
        this.toast('已核对', 'success');
      } catch (e) { this.toast(e.message, 'error'); }
    },

    confCls(c) {
      if (c >= 0.8) return 'high';
      if (c >= 0.5) return 'mid';
      return 'low';
    },

    groupName(sg) {
      const m = (sg || '').match(/(\d+)/);
      if (!m) return sg;
      const hit = this.monitoredList.find(g => String(g.group_id) === m[1]);
      return hit ? hit.group_name : m[1];
    },

    // ---------- 服务开关 ----------
    async toggleService() {
      if (this.snap.service_running) {
        this.toast('服务是常驻的，要停止请关闭对应进程', 'info');
      } else {
        this.toast('服务未运行，请运行 tools\\1_start_all.bat', 'warning');
      }
    },

    // ---------- 健康 / 看门狗 ----------
    async refreshHealth() {
      try {
        const h = await API.qqHealth();
        this.health = h;
        if (h.watchdog) this.watchdogOn = !!h.watchdog.enabled;
        // 同步到 qq 对象（胶囊用）
        if (h.state === 'ready') {
          this.qq.running = true;
          this.qq.logged_in = true;
        } else if (h.state === 'stopped') {
          this.qq.running = false;
          this.qq.logged_in = false;
        }
      } catch (e) { /* 静默 */ }
    },

    async toggleWatchdog(val) {
      try {
        const r = await API.qqWatchdog({ enabled: val, interval: 30 });
        this.watchdogOn = r.enabled;
        this.toast(val ? '已开启自动恢复' : '已关闭自动恢复', 'success');
        this.refreshHealth();
      } catch (e) {
        this.toast('设置失败：' + e.message, 'error');
        this.watchdogOn = !val;
      }
    },

    // ---------- QQ ----------
    async loadQQ() {
      try {
        const r = await API.qqStatus();
        this.qq = Object.assign(this.qq, r);
        if (r.logged_in) this.loadMonitored();
      } catch (e) { console.warn('QQ 状态查询失败', e); }
    },

    openQQ() {
      this.qqDialog = true;
      this.loadQQ();
      this.startQQPoll();
      this.loadQR();
    },

    startQQPoll() {
      if (this.qqTimer) clearInterval(this.qqTimer);
    if (this.healthTimer) clearInterval(this.healthTimer);
      this.qqTimer = setInterval(async () => {
        if (!this.qqDialog) { clearInterval(this.qqTimer); this.qqTimer = null; return; }
        await this.loadQQ();
        if (this.qq.logged_in) {
          clearInterval(this.qqTimer);
          this.qqTimer = null;
          this.qrData = null;
          this.toast(`已登录：${this.qq.nickname}`, 'success');
          this.loadMonitored();
        } else if (this.qq.phase === 'waiting_scan' || this.qq.phase === 'qr_expired') {
          this.loadQR();
        }
      }, 2000);
    },

    async loadQR() {
      try {
        const r = await API.qqQR();
        if (r.logged_in) { this.qrData = null; return; }
        if (r.qr) this.qrData = r.qr;
      } catch (e) { this.qrData = null; }
    },

    async startNapcat() {
      this.starting = true;
      try {
        const r = await API.qqStart();
        this.toast(r.msg || '已启动', r.ok ? 'success' : 'warning');
        await this.loadQQ();
        setTimeout(() => this.loadQR(), 3000);
      } catch (e) {
        this.toast('启动失败：' + e.message, 'error');
      } finally { this.starting = false; }
    },

    async restartQQ() {
      try {
        this.toast('正在重启 NapCat…', 'info');
        await API.qqRestart();
        await this.loadQQ();
        this.toast('已重启', 'success');
      } catch (e) { this.toast('重启失败：' + e.message, 'error'); }
    },

    async logoutQQ() {
      try {
        await API.qqLogout();
        await this.loadQQ();
        // 退出后必须刷新待办和计数，否则 Tab 上的数字会残留
        this.todosByTab = { active: [], pending_confirm: [], completed: [], ignored: [] };
        this.counts = { pending_confirm: 0, active: 0, completed: 0, ignored: 0 };
        this.tabs.forEach(t => { t.count = 0; });
        await this.refreshAll();
        this.toast('已退出登录', 'success');
      } catch (e) { this.toast(e.message, 'error'); }
    },

    // ---------- 群管理 ----------
    async loadMonitored() {
      try {
        const r = await API.qqGroups();
        this.allGroups = r.groups || [];
        this.monitoredList = this.allGroups.filter(g => g.monitored);
      } catch (e) {
        // NapCat 未登录时会失败，静默处理
        const c = await API.config();
        this.monitoredList = (c.monitored_groups || []).map(id => ({ group_id: id, group_name: String(id) }));
      }
    },

    async openGroupPicker() {
      this.groupDialog = true;
      this.groupLoading = true;
      try {
        const r = await API.qqGroups();
        this.allGroups = r.groups || [];
      } catch (e) {
        this.toast('拉取群列表失败：' + e.message, 'error');
        this.allGroups = [];
      } finally { this.groupLoading = false; }
    },

    async toggleGroup(gid) {
      try {
        const r = await API.qqToggleGroup(gid);
        this.toast(r.monitored ? '已开始监控' : '已取消监控', 'success');
        await this.loadMonitored();
        if (this.route === 'home') this.loadTodos();
      } catch (e) { this.toast(e.message, 'error'); }
    },
  },
};

const vueApp = createApp(App);
vueApp.use(ElementPlus, { locale: ElementPlusLocaleZhCn });
if (window.ElementPlusIconsVue) {
  for (const [name, comp] of Object.entries(ElementPlusIconsVue)) {
    vueApp.component(name, comp);
  }
}
vueApp.mount('#app');