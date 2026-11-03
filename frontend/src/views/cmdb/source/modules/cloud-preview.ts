export type CloudPreviewRow = Api.Cmdb.AssetSyncPreview['rows'][number];

export function countIncompleteSpecs(rows: CloudPreviewRow[]): number {
  return rows.filter(row => {
    if (row.action === 'invalid') return false;
    const specs = row.specs;
    return (
      !specs?.cpu_cores ||
      !specs.memory_mb ||
      specs.system_disk_gb === undefined ||
      specs.data_disk_gb === undefined ||
      !specs.region
    );
  }).length;
}

export function canSyncRow(row: CloudPreviewRow): boolean {
  return row.action === 'create' || row.action === 'update';
}

export function actionLabel(action: CloudPreviewRow['action']): string {
  return {
    create: '新增',
    update: '更新',
    unchanged: '未变化',
    invalid: '无效'
  }[action];
}

export function formatMemory(mb?: number): string {
  if (mb === undefined) return '—';
  return mb < 1024 ? `${mb} MiB` : `${Number((mb / 1024).toFixed(3))} GiB`;
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}
