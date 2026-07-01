import { useState, useEffect, useCallback } from 'react';

interface AsyncState<T> {
  data?: T;
  loading: boolean;
  error?: string;
}

/**
 * 极简数据获取 hook：自动加载、reload、卸载竞态保护。
 * 不引入 react-query 等额外依赖。
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<AsyncState<T>>({ loading: true });
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let active = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    fn()
      .then((data) => {
        if (active) setState({ data, loading: false });
      })
      .catch((e) => {
        if (active) {
          setState({ data: undefined, loading: false, error: e instanceof Error ? e.message : String(e) });
        }
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadKey]);

  return { ...state, reload };
}
