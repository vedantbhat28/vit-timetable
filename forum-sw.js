/* Forum push service worker.
   Registered by forum.html with its own scope (./forum-notify/) so it never
   clashes with any other service worker on the site. */
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });

/* Payload from the forum-push edge function: {title, body, postId, replyId, tag} */
self.addEventListener('push', function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) {}
  var opts = {
    body: d.body || '',
    tag: d.tag || 'forum',
    renotify: true,
    icon: 'icons/icon-32.png',
    data: { postId: d.postId || null }
  };
  e.waitUntil(Promise.all([
    self.registration.showNotification(d.title || 'VIT Pune Forum', opts),
    /* let any open forum tab refresh its bell badge immediately */
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (cs) {
      cs.forEach(function (c) { c.postMessage({ type: 'forum-push' }); });
    })
  ]));
});

self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  var pid = e.notification.data && e.notification.data.postId;
  var url = new URL('forum.html' + (pid ? '#/post/' + pid : ''), self.location.href);
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (cs) {
    for (var i = 0; i < cs.length; i++) {
      var c = cs[i], same = false;
      try { same = new URL(c.url).pathname === url.pathname; } catch (x) {}
      if (same) {
        var msg = function () { c.postMessage({ type: 'forum-open', postId: pid }); };
        return c.focus().then(msg, msg);
      }
    }
    return self.clients.openWindow(url.href);
  }));
});
