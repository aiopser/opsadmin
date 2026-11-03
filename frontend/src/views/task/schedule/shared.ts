/** 与后端 TIME_ZONE=Asia/Shanghai 的无偏移日期输入约定一致。 */
export const SYSTEM_TIMEZONE_LABEL = 'Asia/Shanghai';

/** 5 段 Cron 位说明（顺序与表达式一致：分 时 日 月 周） */
export interface CronFieldSpec {
  key: string;
  label: string;
  /** 允许值范围 */
  range: string;
  /** 允许的特殊字符 */
  chars: string;
}

export const cronFieldSpecs: CronFieldSpec[] = [
  { key: 'minute', label: '分钟', range: '0-59', chars: ', - * /' },
  { key: 'hour', label: '小时', range: '0-23', chars: ', - * /' },
  { key: 'day', label: '日', range: '1-31', chars: ', - * ? / L W C' },
  { key: 'month', label: '月', range: '1-12 或 JAN-DEC', chars: ', - * /' },
  { key: 'weekday', label: '星期', range: '1-7 或 SUN-SAT（0 表示周日）', chars: ', - * ? / L C #' }
];

/** 按插入符位置定位当前编辑的 Cron 段（0-4），用于字段说明图高亮定位。 */
export function cronSegmentIndex(expression: string, caret: number): number {
  const safeCaret = Math.min(Math.max(caret, 0), expression.length);
  const segments = expression.slice(0, safeCaret).split(/\s+/);
  return Math.min(Math.max(segments.length - 1, 0), cronFieldSpecs.length - 1);
}

/** Only describe supported calendars; never omit a day/month restriction. */
export function humanizeCron(expression: string): string {
  if (!expression.trim()) return '填写后显示触发说明';
  const parts = expression.trim().split(/\s+/);
  if (parts.length !== 5) return '表达式需为 5 段：分 时 日 月 周';
  const [minute, hour, day, month, weekday] = parts;
  if (/^\d+$/.test(minute) && /^\d+$/.test(hour)) {
    const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
    if (day === '*' && month === '*' && weekday === '1-5') return `工作日 ${time} 触发`;
    if (/^\d+$/.test(day) && month === '*' && weekday === '*') return `每月 ${day} 日 ${time} 触发`;
  }
  if (day !== '*' || month !== '*' || weekday !== '*') return '自定义周期，请确认表达式正确';
  return describeDailyCron(minute, hour);
}

function describeDailyCron(minute: string, hour: string): string {
  if (/^\d+$/.test(minute) && /^\d+$/.test(hour)) {
    return `每天 ${hour.padStart(2, '0')}:${minute.padStart(2, '0')} 触发`;
  }
  if (/^\*\/\d+$/.test(minute) && hour === '*') return `每 ${minute.slice(2)} 分钟触发一次`;
  if (/^\d+(,\d+)*$/.test(minute) && /^\*\/\d+$/.test(hour)) return `每 ${hour.slice(2)} 小时的第 ${minute} 分触发`;
  if (hour === '*' && minute === '*') return '每分钟触发一次';
  if (/^\d+$/.test(minute) && hour === '*') return `每小时的第 ${minute} 分触发`;
  return '自定义周期，请确认表达式正确';
}
