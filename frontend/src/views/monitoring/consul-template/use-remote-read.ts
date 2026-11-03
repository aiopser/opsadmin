import { onScopeDispose, ref } from 'vue';
import { getConsulRemoteRead, requestConsulRemoteRead } from '@/service/api/monitoring';
import type { ConsulRemoteRead, ConsulRemoteReadInput } from '@/service/api/monitoring';

export function useRemoteRead() {
  const reading = ref(false);
  let sequence = 0;

  function cancelRead() {
    sequence += 1;
    reading.value = false;
  }

  async function poll(result: ConsulRemoteRead, current: number, attempt: number): Promise<ConsulRemoteRead | null> {
    if (current !== sequence) return null;
    if (result.status === 'succeeded') return result;
    if (result.status === 'failed' || result.status === 'expired') {
      window.$message?.error(result.error || '远端文件读取失败');
      return null;
    }
    if (attempt >= 90) {
      window.$message?.warning('读取仍未完成，请检查 Worker 后重试');
      return null;
    }
    await new Promise(resolve => {
      setTimeout(resolve, 1000);
    });
    if (current !== sequence) return null;
    const response = await getConsulRemoteRead(result.id);
    if (response.error || !response.data) return null;
    return poll(response.data, current, attempt + 1);
  }

  async function readRemote(input: ConsulRemoteReadInput): Promise<ConsulRemoteRead | null> {
    sequence += 1;
    const current = sequence;
    reading.value = true;
    try {
      const start = await requestConsulRemoteRead(input);
      if (current !== sequence || start.error || !start.data) return null;
      return await poll(start.data, current, 0);
    } finally {
      if (current === sequence) reading.value = false;
    }
  }

  onScopeDispose(cancelRead);
  return { reading, readRemote, cancelRead };
}
