export const statusLabels: Readonly<Record<string, string>> = {
  not_started: '未开始',
  pending: '待处理',
  queued: '排队中',
  running: '进行中',
  ready: '待确认',
  approved: '已通过',
  rejected: '已拒绝',
  not_required: '无需审批',
  success: '成功',
  failed: '失败',
  needs_reconciliation: '结果待核实',
  partial: '部分纳管',
  superseded: '已失效'
};

export function statusLabel(status: string): string {
  return statusLabels[status] ?? status;
}
