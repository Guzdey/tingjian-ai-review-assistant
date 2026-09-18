(function configureTingjian(global) {
  if (global.TINGJIAN_API_BASE) return;
  const isLocal = ['localhost', '127.0.0.1'].includes(global.location.hostname);
  global.TINGJIAN_API_BASE = isLocal
    ? 'http://127.0.0.1:8000'
    : global.location.origin;
})(window);
