// OLD-SITE service worker (github.io). Its only jobs now:
//  1) make sure installed apps fetch the redirect page instead of an old cached copy,
//  2) keep old push subscriptions working until people re-enable reminders on the new domain.
var CACHE = 'vit-tt-old-redirect-v1';
var SHELL = ['./', './index.html', './redirect.js', './manifest.json',
  './icons/icon-192.png', './icons/icon-512.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).catch(function () {}));
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
      .then(function () { return self.clients.matchAll({ type: 'window' }); })
      .then(function (wins) {
        // reload any open old app window once, so it picks up the redirect right now
        wins.forEach(function (w) { try { w.navigate(w.url); } catch (err) {} });
      })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  if (new URL(req.url).origin !== self.location.origin) return;
  var nav = req.mode === 'navigate';
  e.respondWith(
    fetch(req, { cache: 'no-cache' })                         // always revalidate: GitHub Pages sends a 10 minute cache header
      .then(function (res) {
        if (res && res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); }).catch(function () {});
        }
        return res;
      })
      .catch(function () {
        return caches.match(req).then(function (hit) {
          return hit || (nav ? caches.match('./index.html') : undefined);
        });
      })
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
