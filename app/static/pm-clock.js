/* Server-synchronised display only. Does not change scheduler/server time. */
(function (root) {
  'use strict';
  function formatClock(epoch) {
    return new Intl.DateTimeFormat('id-ID', {timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(epoch)).replaceAll('.', ':');
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {formatClock};
  if (typeof document === 'undefined') return;
  const box = document.querySelector('[data-pm-clock]');
  if (!box) return;
  const timeNode = box.querySelector('[data-clock-time]');
  const dateNode = box.querySelector('[data-clock-date]');
  const status = box.querySelector('[data-clock-status]');
  let epoch = Number(box.dataset.epochMs), anchor = performance.now(), lastGood = 0;
  if (!Number.isFinite(epoch) || epoch <= 0) {
    timeNode.textContent = '--:--:--'; status.textContent = 'Waktu server belum tersedia'; return;
  }
  const dateFormat = new Intl.DateTimeFormat('id-ID',{timeZone:'Asia/Jakarta',weekday:'long',day:'numeric',month:'long',year:'numeric'});
  function draw() {
    const now = epoch + performance.now() - anchor;
    timeNode.textContent = formatClock(now);
    timeNode.dateTime = new Date(now).toISOString();
    dateNode.textContent = dateFormat.format(new Date(now));
    if (lastGood && performance.now() - lastGood > 360000) status.textContent = 'Perkiraan dari sinkronisasi terakhir';
  }
  async function sync() {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 7000);
    const start = performance.now();
    try {
      const response = await fetch(box.dataset.timeUrl,{cache:'no-store',credentials:'same-origin',headers:{'Accept':'application/json'},signal:controller.signal});
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('unavailable');
      const data = await response.json();
      if (!Number.isFinite(data.epoch_ms) || data.timezone !== 'Asia/Jakarta') throw new Error('invalid');
      anchor = performance.now(); epoch = data.epoch_ms + (anchor-start)/2; lastGood = anchor;
      status.textContent = 'Tersinkron dengan server'; draw();
    } catch (_) { status.textContent = 'Perkiraan waktu; sinkronisasi belum tersedia'; }
    finally { clearTimeout(timer); }
  }
  draw(); sync(); setInterval(draw,1000); setInterval(sync,300000);
  document.addEventListener('visibilitychange',() => {if (!document.hidden) sync();});
})(typeof globalThis !== 'undefined' ? globalThis : this);
