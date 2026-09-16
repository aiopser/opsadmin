import { type Ref, onScopeDispose, ref, shallowRef, watch } from 'vue';
import { fetchGetRunEvents, fetchRealtimeTicket, runEventWebSocketUrl } from '@/service/api';

/** 事件流内存上限：仅保留最近 N 条，超出的最早事件计入 dropped。 */
export const RUN_EVENT_LIMIT = 1000;

export interface RunEventStream {
  events: Ref<Api.Jobs.RunEvent[]>;
  terminal: Ref<boolean>;
  connected: Ref<boolean>;
  transportError: Ref<string>;
  /** 因超出内存上限被丢弃的最早事件数量 */
  dropped: Ref<number>;
}

export function useRunEventStream(runId: Ref<number | null>, domain: Ref<Api.Jobs.RunDomain>): RunEventStream {
  const events = shallowRef<Api.Jobs.RunEvent[]>([]);
  const terminal = ref(false);
  const connected = ref(false);
  const transportError = ref('');
  const dropped = ref(0);
  let stopSession = () => {};

  function startSession(id: number, runDomain: Api.Jobs.RunDomain): () => void {
    const controller = new AbortController();
    let active = true;
    let cursor = 0;
    let pulling = false;
    let pullAgain = false;
    let connecting = false;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let poll: ReturnType<typeof setTimeout> | undefined;
    let delay = 1000;

    function stop() {
      active = false;
      controller.abort();
      clearTimeout(retry);
      clearTimeout(poll);
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
      socket = null;
      connected.value = false;
    }

    function schedulePoll() {
      clearTimeout(poll);
      if (active)
        poll = setTimeout(
          () => {
            pull();
          },
          connected.value ? 15000 : 5000
        );
    }

    async function pull() {
      if (!active) return;
      if (pulling) {
        pullAgain = true;
        return;
      }
      pulling = true;
      try {
        // Each page depends on the cursor returned by the previous page.
        /* eslint-disable no-await-in-loop */
        do {
          pullAgain = false;
          const result = await fetchGetRunEvents(id, cursor, { domain: runDomain, signal: controller.signal });
          if (!active) return;
          if (result.error || !result.data) {
            transportError.value = '事件同步暂不可用，正在重试';
            return;
          }
          const page = result.data;
          if (page.hasMore && page.nextCursor <= cursor) {
            transportError.value = '事件游标未推进';
            return;
          }
          const previousCursor = cursor;
          const fresh = [
            ...new Map(
              page.events.filter(item => item.sequence > previousCursor).map(item => [item.sequence, item])
            ).values()
          ].sort((a, b) => a.sequence - b.sequence);
          const merged = [...events.value, ...fresh];
          const overflow = merged.length - RUN_EVENT_LIMIT;
          if (overflow > 0) {
            dropped.value += overflow;
            events.value = merged.slice(overflow);
          } else {
            events.value = merged;
          }
          cursor = page.nextCursor;
          transportError.value = '';
          if (page.terminal && !page.hasMore) {
            terminal.value = true;
            stop();
            return;
          }
          pullAgain ||= page.hasMore;
        } while (active && pullAgain);
        /* eslint-enable no-await-in-loop */
      } catch {
        if (active) transportError.value = '事件同步暂不可用，正在重试';
      } finally {
        pulling = false;
        schedulePoll();
      }
    }

    function reconnect() {
      if (!active || retry) return;
      retry = setTimeout(() => {
        retry = undefined;
        connect();
      }, delay);
      delay = Math.min(delay * 2, 30000);
    }

    async function connect() {
      if (!active || socket || connecting) return;
      connecting = true;
      try {
        const result = await fetchRealtimeTicket(id, runDomain, controller.signal);
        if (!active) return;
        if (result.error || !result.data) {
          reconnect();
          return;
        }
        const ticket = result.data.ticket;
        const ws = new WebSocket(runEventWebSocketUrl());
        socket = ws;
        ws.onopen = () => {
          if (active) ws.send(JSON.stringify({ type: 'subscribe', run_id: id, ticket }));
        };
        ws.onmessage = message => {
          if (!active || socket !== ws) return;
          try {
            const data: unknown = JSON.parse(String(message.data));
            if (!data || typeof data !== 'object' || !('type' in data)) return;
            if (data.type === 'subscribed' && 'run_id' in data && data.run_id === id) {
              connected.value = true;
              delay = 1000;
              pull();
            } else if (data.type === 'events_available' && 'run_id' in data && data.run_id === id) {
              pull();
            } else if (data.type === 'error') ws.close();
          } catch {
            /* Malformed notifications never advance the REST cursor. */
          }
        };
        ws.onerror = () => ws.close();
        ws.onclose = () => {
          if (!active || socket !== ws) return;
          socket = null;
          connected.value = false;
          reconnect();
        };
      } catch {
        if (active) reconnect();
      } finally {
        connecting = false;
      }
    }

    pull().then(() => {
      if (active) connect();
    });
    return stop;
  }

  watch(
    [runId, domain],
    ([id, runDomain]) => {
      stopSession();
      events.value = [];
      terminal.value = false;
      connected.value = false;
      transportError.value = '';
      dropped.value = 0;
      stopSession = id !== null && Number.isSafeInteger(id) && id > 0 ? startSession(id, runDomain) : () => {};
    },
    { immediate: true }
  );
  onScopeDispose(() => stopSession());
  return { events, terminal, connected, transportError, dropped };
}
