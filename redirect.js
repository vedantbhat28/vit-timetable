/* Old github.io site -> new domain. Used by index.html (and any other old page you want to redirect). */
(function () {
  var NEW_ORIGIN = 'https://vit-tt.pages.dev';   // <- put your new domain here, no trailing slash
  var OLD_BASE   = '/vit-timetable/';          // <- the old repo path on github.io

  var standalone = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;

  // carry the user's settings across (tt-* keys only; custom sounds and install flags stay behind)
  var data = {};
  try {
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (!k || k.indexOf('tt-') !== 0) continue;
      if (k === 'tt-installed' || k === 'tt-install-dismissed' || k.indexOf('tt-rr-snd') === 0) continue;
      var v = localStorage.getItem(k);
      if (v !== null && v.length <= 2000) data[k] = v;
    }
  } catch (e) {}

  function encode(d) {
    var json = JSON.stringify({ p: standalone ? 1 : 0, d: d });
    return btoa(unescape(encodeURIComponent(json))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  var enc = '';
  try {
    enc = encode(data);
    while (enc.length > 40000) {                      // keep the URL a sane size: drop the biggest value until it fits
      var big = null, bl = -1;
      for (var key in data) if (data[key].length > bl) { bl = data[key].length; big = key; }
      if (!big) break;
      delete data[big]; enc = encode(data);
    }
  } catch (e) { enc = ''; }

  var path = '/';
  if (location.pathname.indexOf(OLD_BASE) === 0) path = '/' + location.pathname.slice(OLD_BASE.length);

  var target = NEW_ORIGIN + path + location.search + (enc ? '#m=' + enc : '');
  var link = document.getElementById('go');
  if (link) link.href = target;
  location.replace(target);
})();
