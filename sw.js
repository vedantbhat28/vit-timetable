// Service worker: keeps the site installable, a light network-first cache so the
// app shell still opens offline (live class data still needs a connection), and
// Web Push for Reminder Ranger (server: Supabase edge function tt-push-send).
var CACHE = 'vit-tt-v2';
var SHELL = ['./', './index.html', './manifest.json',
  './icons/icon-192.png', './icons/icon-512.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }));
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request)
      .then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(e.request, copy); }).catch(function () {});
        return res;
      })
      .catch(function () { return caches.match(e.request); })
  );
});

// ---- Web Push (Reminder Ranger) ----
self.addEventListener('push', function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { title: 'Lecture reminder', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (wins) {
      // App on screen: let the page show its own banner and sound instead of a system notification.
      var seen = wins.filter(function (w) { return w.visibilityState === 'visible'; });
      if (seen.length) {
        seen.forEach(function (w) { w.postMessage({ type: 'rr-push', d: d }); });
        return;
      }
      var stark = d.l === 3, loud = !!d.snd;
      var o = {
        body: d.body || '',
        tag: d.tag || 'rr',
        icon: 'icons/icon-192.png',
        badge: 'icons/icon-32.png',
        silent: !loud,
        requireInteraction: stark,
        data: { k: d.k || '' }
      };
      if (stark && loud) o.vibrate = [220, 110, 220, 110, 420];   // vibrate cannot be combined with silent
      return self.registration.showNotification(d.title || 'Lecture reminder', o);
    })
  );
});

self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (wins) {
      for (var i = 0; i < wins.length; i++) {
        if ('focus' in wins[i]) return wins[i].focus();
      }
      return self.clients.openWindow(self.registration.scope);
    })
  );
});
