// ============================================================
// 配置页
// ============================================================
const SettingsView = {
  props: ['snap', 'counts'],
  emits: ['reload', 'toast'],

  template: `
  <div v-loading="loading">
    <!-- 监控群 -->
    <div class="card">
      <h3 class="card-title">监控的 QQ 群</h3>
      <div style="display:flex;gap:8px;margin-bottom:10px">
        <el-input v-model.number="newGroup" placeholder="输入群号，例如 12345678"
                  style="max-width:260px" @keyup.enter="addGroup" />
        <el-button type="primary" @click="addGroup">添加</el-button>
      </div>
      <div v-if="cfgData.monitored_groups && cfgData.monitored_groups.length">
        <el-tag v-for="g in cfgData.monitored_groups" :key="g" closable
                @close="removeGroup(g)" size="large" style="margin:0 8px 8px 0">
          {{ g }}
        </el-tag>
      </div>
      <el-alert v-else type="warning" :closable="false" show-icon
                title="还没有添加任何群" description="列表为空时不会监控任何群（安全默认）" />
    </div>

    <!-- 个人信息 -->
    <div class="card">
      <h3 class="card-title">个人信息（用于判断"这条通知与我有关吗"）</h3>
      <el-form label-width="110px" size="default">
        <el-form-item label="姓名">
          <el-input v-model="nameStr" placeholder="多个用逗号分隔" />
        </el-form-item>
        <el-form-item label="学号">
          <el-input v-model="studentStr" placeholder="多个用逗号分隔" />
        </el-form-item>
        <el-form-item label="班级">
          <el-input v-model="classStr" placeholder="例如 软件技术2班, 软技2班" />
        </el-form-item>
        <el-form-item label="职务">
          <el-input v-model="roleStr" placeholder="例如 社工部干部, 心理委员" />
        </el-form-item>
        <el-form-item label="性别">
          <el-input v-model="cfgData.user_profile.gender" style="max-width:120px" />
        </el-form-item>
        <el-form-item label="关注关键词">
          <el-input v-model="kwStr" type="textarea" :rows="2"
                    placeholder="例如 男生, 搬运, 答辩, 开会" />
        </el-form-item>
      </el-form>
      <div class="form-tip">
        这些词会被拼成一段文字交给大模型，帮它判断"@软件2班"这类通知是否与你相关
      </div>
    </div>

    <!-- 模型 -->
    <div class="card">
      <h3 class="card-title">模型与推理</h3>
      <el-form label-width="110px">
        <el-form-item label="模型名称">
          <el-input v-model="cfgData.model.main" style="max-width:260px" />
          <div class="form-tip">本机 8GB 显存建议 qwen2.5:7b</div>
        </el-form-item>
        <el-form-item label="Ollama 地址">
          <el-input v-model="cfgData.model.ollama_host" style="max-width:260px" />
        </el-form-item>
        <el-form-item label="显存驻留">
          <el-input v-model="cfgData.model.keep_alive" style="max-width:120px" />
          <div class="form-tip">闲置多久后从显存卸载，例如 10m / 30m / 0（立即卸载）</div>
        </el-form-item>
        <el-form-item label="超时（秒）">
          <el-input-number v-model="cfgData.model.timeout" :min="10" :max="600" />
        </el-form-item>
      </el-form>
    </div>

    <!-- 游戏模式 -->
    <div class="card">
      <h3 class="card-title">游戏模式</h3>
      <el-form label-width="110px">
        <el-form-item label="游戏进程名">
          <el-input v-model="procStr" type="textarea" :rows="3"
                    placeholder="每行一个进程名，例如 DeltaForceClient-Win64-Shipping.exe" />
          <div class="form-tip">
            检测到这些进程就判定为"游戏中"，自动卸载模型释放显存。
            注意：不要把启动器（launcher）加进去，否则常驻后台会一直判定为游戏模式。
          </div>
        </el-form-item>
        <el-form-item label="检测间隔（秒）">
          <el-input-number v-model="cfgData.game_mode.poll_seconds" :min="0.5" :max="10" :step="0.5" />
          <div class="form-tip">游戏启动到吃显存只有 1~2 秒，建议 1.5 秒</div>
        </el-form-item>
      </el-form>
    </div>

    <!-- 行为 -->
    <div class="card">
      <h3 class="card-title">识别行为</h3>
      <el-form label-width="110px">
        <el-form-item label="图片识别">
          <el-switch v-model="cfgData.settings.enable_ocr" />
          <div class="form-tip">开启后群里的图片会走 OCR 转文字（1 秒/张，不占显存）</div>
        </el-form-item>
        <el-form-item label="置信度阈值">
          <el-slider v-model="cfgData.settings.confidence_threshold" :min="0" :max="1" :step="0.05"
                     style="max-width:320px" show-input />
          <div class="form-tip">低于这个值的新任务会进"待确认"而不是"进行中"</div>
        </el-form-item>
        <el-form-item label="合并窗口">
          <el-input-number v-model="cfgData.settings.window_minutes" :min="1" :max="30" />
          <span style="margin-left:8px;color:#64748b">分钟</span>
        </el-form-item>
        <el-form-item label="自动清理">
          <el-input-number v-model="cfgData.settings.auto_clean_days" :min="1" :max="365" />
          <span style="margin-left:8px;color:#64748b">天后删除已完成任务</span>
        </el-form-item>
      </el-form>
    </div>

    <!-- 局域网 -->
    <div class="card">
      <h3 class="card-title">手机访问（局域网）</h3>
      <el-form label-width="110px">
        <el-form-item label="允许局域网">
          <el-switch v-model="cfgData.settings.allow_lan_access" />
          <div class="form-tip">
            开启后同一 WiFi 下的手机可以访问。校园网是同网段几千台机器，
            <b style="color:#dc2626">必须设置令牌</b>，否则同网段任何人都能看你的待办。
          </div>
        </el-form-item>
        <el-form-item label="访问令牌" v-if="cfgData.settings.allow_lan_access">
          <el-input v-model="cfgData.settings.lan_token" style="max-width:320px"
                    placeholder="随便设一串，手机访问时要带上">
            <template #append>
              <el-button @click="genToken">随机生成</el-button>
            </template>
          </el-input>
          <div class="form-tip">手机访问地址：http://本机IP:8000/console/?token=你的令牌</div>
        </el-form-item>
      </el-form>
    </div>

    <!-- 保存 -->
    <div style="position:sticky;bottom:0;background:#f5f7fa;padding:12px 0;display:flex;gap:10px">
      <el-button type="primary" size="large" @click="save" :loading="saving">保存配置</el-button>
      <el-button size="large" @click="load">放弃修改</el-button>
      <span style="color:#94a3b8;font-size:12px;align-self:center">
        保存后立即生效，不需要重启服务
      </span>
    </div>
  </div>
  `,

  data() {
    return {
      loading: false,
      saving: false,
      cfgData: {
        monitored_groups: [],
        user_profile: {},
        model: {},
        game_mode: {},
        settings: {},
        urgent: {},
      },
      newGroup: null,
      nameStr: '', studentStr: '', classStr: '', roleStr: '', kwStr: '', procStr: '',
    };
  },

  mounted() { this.load(); },

  methods: {
    async load() {
      this.loading = true;
      try {
        const c = await API.config();
        this.cfgData = c;
        const p = c.user_profile || {};
        this.nameStr = (p.name || []).join(', ');
        this.studentStr = (p.student_id || []).join(', ');
        this.classStr = (p.class_info || []).join(', ');
        this.roleStr = (p.roles || []).join(', ');
        this.kwStr = (p.custom_keywords || []).join(', ');
        this.procStr = (c.game_mode && c.game_mode.game_processes || []).join('\n');
      } catch (e) {
        this.$emit('toast', '加载配置失败：' + e.message, 'error');
      } finally {
        this.loading = false;
      }
    },

    async save() {
      this.saving = true;
      try {
        const c = this.cfgData;
        c.user_profile.name = this.splitList(this.nameStr);
        c.user_profile.student_id = this.splitList(this.studentStr);
        c.user_profile.class_info = this.splitList(this.classStr);
        c.user_profile.roles = this.splitList(this.roleStr);
        c.user_profile.custom_keywords = this.splitList(this.kwStr);
        c.game_mode.game_processes = this.procStr
          .split('\n').map(s => s.trim()).filter(Boolean);

        if (c.settings.allow_lan_access && !c.settings.lan_token) {
          this.$emit('toast', '开启局域网访问必须设置令牌', 'error');
          return;
        }
        await API.saveConfig(c);
        this.$emit('toast', '配置已保存', 'success');
        this.$emit('reload');
      } catch (e) {
        this.$emit('toast', '保存失败：' + e.message, 'error');
      } finally {
        this.saving = false;
      }
    },

    splitList(s) {
      return (s || '').split(/[,，\n]/).map(x => x.trim()).filter(Boolean);
    },

    addGroup() {
      const g = parseInt(this.newGroup);
      if (!g) { this.$emit('toast', '请输入数字群号', 'warning'); return; }
      if (!this.cfgData.monitored_groups.includes(g)) {
        this.cfgData.monitored_groups.push(g);
      }
      this.newGroup = null;
    },

    removeGroup(g) {
      this.cfgData.monitored_groups = this.cfgData.monitored_groups.filter(x => x !== g);
    },

    genToken() {
      const rnd = () => Math.random().toString(36).slice(2, 10);
      this.cfgData.settings.lan_token = rnd() + rnd();
      this.$emit('toast', '已生成令牌，记得保存', 'success');
    },
  },
};