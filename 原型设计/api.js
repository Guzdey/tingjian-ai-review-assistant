(function exposeTingjianApi(global) {
  'use strict';
  const configuredBase = global.TINGJIAN_API_BASE
    || global.localStorage.getItem('tingjian_api_base')
    || 'http://127.0.0.1:8000';
  const baseUrl = configuredBase.replace(/\/$/, '');

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = global.setTimeout(() => controller.abort(), options.timeoutMs || 20000);
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        method: options.method || 'GET',
        headers: {'Content-Type': 'application/json', ...(options.headers || {})},
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: controller.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof payload.detail === 'string' ? payload.detail : `HTTP ${response.status}`;
        throw new Error(detail);
      }
      return payload;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('请求超时，请稍后重试');
      throw error;
    } finally {
      global.clearTimeout(timeout);
    }
  }

  global.tingjianApi = {
    baseUrl,
    health: () => request('/api/health', {timeoutMs: 4000}),
    parseNeed: body => request('/api/needs/parse', {method: 'POST', body}),
    createReport: body => request('/api/reports', {method: 'POST', body, timeoutMs: 30000}),
    getEvidence: (productId, {aspect, stance, limit = 30} = {}) => {
      const query = new URLSearchParams({limit: String(limit)});
      if (aspect) query.set('aspect', aspect);
      if (stance) query.set('stance', stance);
      return request(`/api/products/${encodeURIComponent(productId)}/evidence?${query}`);
    },
    compare: body => request('/api/compare', {method: 'POST', body, timeoutMs: 30000}),
  };
})(window);
