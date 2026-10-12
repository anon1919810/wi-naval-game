import { useCallback, useState } from 'react';
import { useWorkspaceCopy } from './workspace';

type Copy = ReturnType<typeof useWorkspaceCopy>;
type Message = string | ((copy: Copy) => string);

/** Keep raw server text or a render-time message without freezing its language. */
export function useCopyMessage(initial: Message = '') {
  const copy = useWorkspaceCopy();
  const [stored, setStored] = useState<{ value: Message }>(() => ({ value: initial }));
  const setMessage = useCallback((value: Message) => setStored({ value }), []);
  return [typeof stored.value === 'function' ? stored.value(copy) : stored.value, setMessage] as const;
}
