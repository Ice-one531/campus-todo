// ============================================================
// 日志页
// ============================================================
const LogsView = {
  props: ['snap', 'counts'],
  emits: ['reload', 'toast'],

  template: `
  <div>
    <div class="card" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <el-select v-model="level" style="width:130px" @change="load">
        <el-option label="全部级别" value="ALL" />
        <el-option label="INFO" value="INFO" />
        <el-option label="WARN" value="WARN" />
        <el-option label="ERROR" value="ERROR" />
      </el-select>

      <el-input v-model="keyword" placeholder="搜索关键字" style="max-width:240px" clearable />

      <el-checkbox v-model="autoRefresh" label="自动刷新（3秒）" />

      <el-button @click="load" :loading="loading">刷新</el-button>
      <el-button type="danger" plain @click="clearLogs">清空日志</el-button>

      <span style="margin-left:auto;color:#94a3b8;font-size:12px">
        共 {{ items.length }} 条
      </span>
    </div>

    <div class="card" style="max-height:calc(100vh - 250px);overflow:auto">
      <div v-if="!filtered.length" class="empty">没有日志</div>
      <div v-for="l in filtered" :key="l.id" class="log-line">
        <span class="log-time">{{ (l.created_at||'').slice(5,19) }}</span>
        <span :class="['log-lv', 'lv-' + l.level]">{{ l.level }}</span>
        <span>{{ l.message }}</span>
      </div>
    </div>
  </div>
  `,

  data() {
    return {
      items: [],
      level: 'ALL',
      keyword: '',
      loading: false,
      autoRefresh: false,
      timer: null,
    };
  },

  computed: {
    filtered() {
      const kw = (this.keyword || '').trim();
      if (!kw) return this.items;
      return this.items.filter(l => (l.message || '').includes(kw));
    },
  },

  mounted() { this.load(); },

  watch: {
    autoRefresh(v) {
      if (this.timer) { clearInterval(this.timer); this.timer = null; }
      if (v) this.timer = setInterval(() => this.load(), 3000);
    },
  },

  beforeUnmount() {
    if (this.timer) clearInterval(this.timer);
  },

  methods: {
    async load() {
      this.loading = true;
      try {
        const r = await API.logs(300, this.level === 'ALL' ? null : this.level);
        this.items = r.items || [];
      } catch (e) {
        this.$emit('toast', '加载日志失败：' + e.message, 'error');
      } finally {
        this.loading = false;
      }
    },

    async clearLogs() {
      try {
        await this.$confirm('确定清空所有日志？', '确认', { type: 'warning' });
      } catch (e) { return; }
      try {
        await API.control('clear_logs');
        this.items = [];
        this.$emit('toast', '日志已清空', 'success');
      } catch (e) {
        this.$emit('toast', e.message, 'error');
      }
    },
  },
};