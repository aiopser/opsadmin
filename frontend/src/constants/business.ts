import { transformRecordToOption } from '@/utils/common';

export const enableStatusRecord: Record<Api.Common.EnableStatus, App.I18n.I18nKey> = {
  '1': 'page.manage.common.status.enable',
  '2': 'page.manage.common.status.disable'
};

export const enableStatusOptions = transformRecordToOption(enableStatusRecord);

export const userGenderRecord: Record<Api.SystemManage.UserGender, App.I18n.I18nKey> = {
  '1': 'page.manage.user.gender.male',
  '2': 'page.manage.user.gender.female'
};

export const userGenderOptions = transformRecordToOption(userGenderRecord);

export const menuTypeRecord: Record<Api.SystemManage.MenuType, App.I18n.I18nKey> = {
  '1': 'page.manage.menu.type.directory',
  '2': 'page.manage.menu.type.menu'
};

export const menuTypeOptions = transformRecordToOption(menuTypeRecord);

export const menuIconTypeRecord: Record<Api.SystemManage.IconType, App.I18n.I18nKey> = {
  '1': 'page.manage.menu.iconType.iconify',
  '2': 'page.manage.menu.iconType.local'
};

export const menuIconTypeOptions = transformRecordToOption(menuIconTypeRecord);

export const runStatusRecord: Record<Api.Jobs.RunStatus, App.I18n.I18nKey> = {
  pending: 'page.task.run.status.pending',
  queued: 'page.task.run.status.queued',
  running: 'page.task.run.status.running',
  waiting: 'page.task.run.status.waiting',
  cancel_requested: 'page.task.run.status.cancel_requested',
  success: 'page.task.run.status.success',
  failed: 'page.task.run.status.failed',
  timeout: 'page.task.run.status.timeout',
  canceled: 'page.task.run.status.canceled'
};

export const runStatusTagType: Record<Api.Jobs.RunStatus, UI.ThemeColor> = {
  pending: 'info',
  queued: 'info',
  running: 'primary',
  waiting: 'primary',
  cancel_requested: 'warning',
  success: 'success',
  failed: 'danger',
  timeout: 'danger',
  canceled: 'info'
};

export const executionKindRecord: Record<Api.Jobs.ExecutionKind, App.I18n.I18nKey> = {
  workflow: 'page.task.run.kind.workflow',
  quick_command: 'page.task.run.kind.quick_command',
  playbook: 'page.task.run.kind.playbook',
  module: 'page.task.run.kind.module'
};

export const runDomainRecord: Record<Api.Jobs.RunDomain, App.I18n.I18nKey> = {
  task: 'page.task.run.domain.task',
  ops: 'page.task.run.domain.ops'
};

export const triggerTypeLabels: Record<Api.Jobs.TriggerType, string> = {
  manual: '手动触发',
  scheduled: '定时触发',
  api: 'API 触发'
};

const dashboardRecentTypeLabels: Record<string, string> = {
  quick_command: '脚本',
  playbook: 'Playbook',
  module: 'Ansible 模块',
  manual: '手动发起',
  scheduled: '定时触发',
  scheduled_manual: '手动触发',
  api: 'API 发起'
};

export function dashboardRecentTypeText(type: string): string {
  return dashboardRecentTypeLabels[type] ?? type;
}

export function dashboardSuccessRateText(rate: number | null | undefined): string {
  return rate === null || rate === undefined ? '-' : `${rate}%`;
}

export const nodeStatusRecord: Record<Api.Jobs.NodeStatus, App.I18n.I18nKey> = {
  pending: 'page.task.detail.node.status.pending',
  queued: 'page.task.detail.node.status.queued',
  running: 'page.task.detail.node.status.running',
  success: 'page.task.detail.node.status.success',
  failed: 'page.task.detail.node.status.failed',
  skipped: 'page.task.detail.node.status.skipped',
  ignored: 'page.task.detail.node.status.ignored',
  timeout: 'page.task.detail.node.status.timeout',
  canceled: 'page.task.detail.node.status.canceled'
};
