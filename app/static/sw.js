const CACHE_NAME = 'pregnancy-health-v1';
const REMINDER_HOUR = 19;
const STATIC_ASSETS = [
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => response)
      .catch(() => caches.match(event.request))
  );
  event.waitUntil(maybeShowMovementReminder());
});

async function maybeShowMovementReminder() {
  if (!self.registration) {
    return;
  }
  const today = localDateString();
  const cache = await caches.open(CACHE_NAME);
  const reminded = await cache.match('reminder-' + today);
  if (reminded) {
    return;
  }

  const hour = new Date().getHours();
  if (hour < REMINDER_HOUR) {
    return;
  }

  try {
    const [statusResp, settingsResp] = await Promise.all([
      fetch('/movement/api/status'),
      fetch('/movement/api/settings'),
    ]);
    if (!statusResp.ok || !settingsResp.ok) {
      return;
    }
    const status = await statusResp.json();
    const settings = await settingsResp.json();
    if (!settings.reminder_enabled || status.qualified_today) {
      return;
    }
    await self.registration.showNotification('动作记录提醒', {
      body: '今天还没完成胎动计数，记得数满 10 次哦',
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/icon-192.png',
      tag: 'movement-reminder-' + today,
      data: { url: '/movement/' },
    });
    await cache.put('reminder-' + today, new Response('1'));
  } catch (e) {
    // 离线或权限未开启时忽略
  }
}

function localDateString() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return y + '-' + m + '-' + day;
}

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/movement/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })
  );
});
