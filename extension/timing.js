export function turnTiming(started, now = () => performance.now()) {
  const phases = {};
  let first, streaming;
  const add = (key, elapsed) => { phases[key] = (phases[key] ?? 0) + elapsed; };
  return {
    async measure(key, work) {
      const from = now();
      try { return await work(); }
      finally { add(key, now() - from); }
    },
    context(work) {
      const from = now();
      try { return work(); }
      finally { add('context', now() - from); }
    },
    async stream(work) {
      const attempt = { from: now() }; streaming = attempt;
      try { return await work(); }
      finally {
        const end = now();
        if (attempt.first !== undefined) {
          add('waiting', attempt.first - attempt.from);
          add('receiving', end - attempt.first);
        } else add('request', end - attempt.from);
        streaming = undefined;
      }
    },
    seeText(text) {
      if (!text || first !== undefined && (!streaming || streaming.first !== undefined)) return;
      // SSE comments, tool calls and whitespace-only deltas are not visible reply text.
      if (!/\S/.test(text)) return;
      const at = now();
      first ??= at - started;
      if (streaming) streaming.first ??= at;
    },
    report() { return { ...(first !== undefined ? { first } : {}), total: now() - started, ...phases }; }
  };
}
