type ConfigRecord = Api.SystemManage.SystemConfig;

export function mergeConfigSnapshot(
  records: readonly Pick<ConfigRecord, 'configKey' | 'configValue'>[],
  drafts: Readonly<Record<string, string>>,
  saved: Readonly<Record<string, string>>
) {
  const nextSaved = Object.fromEntries(records.map(row => [row.configKey, row.configValue ?? '']));
  const nextDrafts = Object.fromEntries(
    records.map(row => [
      row.configKey,
      (drafts[row.configKey] ?? '') !== (saved[row.configKey] ?? '') ? drafts[row.configKey] : (row.configValue ?? '')
    ])
  );
  return { saved: nextSaved, drafts: nextDrafts };
}

export async function persistConfigChanges<T extends { configKey: string }>(
  targets: readonly T[],
  drafts: Readonly<Record<string, string>>,
  save: (row: T, value: string) => Promise<{ error?: unknown }>
) {
  const submissions = targets.map(row => ({ row, value: drafts[row.configKey] ?? '' }));
  const results = await Promise.allSettled(
    submissions.map(({ row, value }) => Promise.resolve().then(() => save(row, value)))
  );
  return {
    saved: Object.fromEntries(
      submissions.flatMap(({ row, value }, index) => {
        const result = results[index];
        return result.status === 'fulfilled' && !result.value.error ? [[row.configKey, value]] : [];
      })
    ),
    failedKeys: submissions.flatMap(({ row }, index) => {
      const result = results[index];
      return result.status === 'rejected' || result.value.error ? [row.configKey] : [];
    })
  };
}

export async function loadConfigPages(
  fetchPage: (
    current: number,
    size: number
  ) => Promise<Pick<Api.SystemManage.SystemConfigList, 'records' | 'total'> | null>
): Promise<ConfigRecord[]> {
  const records: ConfigRecord[] = [];
  const keys = new Set<string>();
  let current = 1;
  while (true) {
    // Each page depends on the previous response total and deduplication result.
    // eslint-disable-next-line no-await-in-loop
    const page = await fetchPage(current, 200);
    if (!page) throw new Error('配置加载失败，请重试');
    const fresh = page.records.filter(row => !keys.has(row.configKey));
    if (!fresh.length && records.length < page.total) throw new Error('配置分页数据不完整，请重试');
    fresh.forEach(row => keys.add(row.configKey));
    records.push(...fresh);
    if (records.length >= page.total) return records;
    current += 1;
  }
}
