// ============================================================
// 评测页（答辩要的准确率就出自这里）
// ============================================================
const EvalView = {
  props: ['snap', 'counts'],
  emits: ['reload', 'toast'],

  template: `
  <div>
    <div class="card">
      <h3 class="card-title">怎么用</h3>
      <ol style="margin:0;padding-left:20px;line-height:2;font-size:13.5px;color:#475569">
        <li>打开 <span class="mono">E:\\CampusTodo\\eval\\dataset.csv</span></li>
        <li>往里面填真实群通知和你的正确答案（至少 100 条，答辩才有说服力）</li>
        <li>点下面的「开始评测」，系统会逐条跑模型并与标注对比</li>
        <li>把结果表格截图放进论文，回答"准确率多少"</li>
      </ol>
    </div>

    <div class="card">
      <h3 class="card-title">运行评测</h3>
      <el-button type="primary" size="large" @click="run" :loading="running">
        {{ running ? '评测中…（100 条约需 10 分钟）' : '开始评测' }}
      </el-button>
      <div class="form-tip" style="margin-top:10px">
        评测会真实调用模型，耗时取决于条数。中途不要关闭页面。
      </div>
    </div>

    <div v-if="result" class="card">
      <h3 class="card-title">结果</h3>
      <div class="grid grid-4" style="margin-bottom:18px">
        <div class="metric">
          <div class="metric-num" :style="{color: color(result.accuracy)}">
            {{ (result.accuracy * 100).toFixed(1) }}%
          </div>
          <div class="metric-label">准确率</div>
        </div>
        <div class="metric">
          <div class="metric-num" style="color:#2563eb">
            {{ (result.precision * 100).toFixed(1) }}%
          </div>
          <div class="metric-label">精确率 P</div>
        </div>
        <div class="metric">
          <div class="metric-num" style="color:#22c55e">
            {{ (result.recall * 100).toFixed(1) }}%
          </div>
          <div class="metric-label">召回率 R</div>
        </div>
        <div class="metric">
          <div class="metric-num" style="color:#7c3aed">
            {{ (result.f1 * 100).toFixed(1) }}%
          </div>
          <div class="metric-label">F1</div>
        </div>
      </div>

      <el-descriptions :column="4" border size="small" style="margin-bottom:16px">
        <el-descriptions-item label="样本数">{{ result.total }}</el-descriptions-item>
        <el-descriptions-item label="命中 TP">{{ result.tp }}</el-descriptions-item>
        <el-descriptions-item label="误报 FP">{{ result.fp }}</el-descriptions-item>
        <el-descriptions-item label="漏报 FN">{{ result.fn }}</el-descriptions-item>
      </el-descriptions>

      <div style="font-size:13px;color:#475569;margin-bottom:10px">
        字段级准确率（标题/时间/地点）：<b>{{ (result.field_accuracy*100).toFixed(1) }}%</b>
      </div>

      <el-collapse>
        <el-collapse-item title="查看逐条明细" name="detail">
          <el-table :data="result.details" size="small" max-height="400">
            <el-table-column prop="text" label="通知" width="220" show-overflow-tooltip />
            <el-table-column label="应有" width="70">
              <template #default="{row}">
                <el-tag :type="row.expect ? 'success' : 'info'" size="small">
                  {{ row.expect ? '任务' : '非任务' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="实际" width="70">
              <template #default="{row}">
                <el-tag :type="row.got ? 'success' : 'info'" size="small">
                  {{ row.got ? '任务' : '非任务' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="抽出标题" width="150" />
            <el-table-column prop="deadline" label="抽出时间" width="150" />
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
  `,

  data() {
    return { running: false, result: null };
  },

  methods: {
    async run() {
      this.running = true;
      this.result = null;
      try {
        const r = await API.runEval();
        this.result = r;
        this.$emit('toast', '评测完成', 'success');
      } catch (e) {
        this.$emit('toast', '评测失败：' + e.message, 'error');
      } finally {
        this.running = false;
      }
    },
    color(v) { return v >= 0.8 ? '#22c55e' : v >= 0.6 ? '#f59e0b' : '#dc2626'; },
  },
};