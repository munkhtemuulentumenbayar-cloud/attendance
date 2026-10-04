/* ==========================================================================
   Цаг бүртгэл ба ирцийн систем — Service Worker (PWA)
   • Offline үед: нэвтрэх хуудас + аппын бүрхүүл (HTML/icon) кэшнээс ажиллана
   • API (/api/*) — ХЭЗЭЭ Ч кэшлэхгүй: ирц, цалингийн өгөгдөл зөвхөн сүлжээнээс
   • Онлайн байх үед кэш нь шинэ хувилбараар автоматаар шинэчлэгдэнэ
   v4.6: гар утсанд home screen-д суулгах боломж (Android) + iOS-д offline дэмжлэг
   ========================================================================== */
const CACHE = 'att-v4.6.0';
const CORE = [
  '/',
  '/static/index.html',
  '/static/app.webmanifest',
  '/static/icons/favicon-32.png',
  '/static/icons/apple-touch-icon-180.png',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      // нэг ч файл татагдахгүй байсан ч суулгалт зогсохгүй
      .then((c) => Promise.allSettled(CORE.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);

  if (req.method !== 'GET') return;                     // POST/PUT/DELETE → сүлжээ
  if (url.origin !== self.location.origin) return;      // гадаад (Google Maps) → сүлжээ
  if (url.pathname.startsWith('/api/')) return;         // өгөгдөл → зөвхөн сүлжээ

  // HTML (navigation) — offline үед кэшээс аппын бүрхүүл
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((res) => {
          const cp = res.clone();
          caches.open(CACHE).then((c) => c.put('/', cp)).catch(() => {});
          return res;
        })
        .catch(() => caches.match('/'))
    );
    return;
  }

  // Статик файл — кэшээс шалгаад, сүлжээнээс шинэчилнэ (offline-д кэшээс)
  e.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req)
        .then((res) => {
          if (res && res.status === 200 && res.type === 'basic') {
            const cp = res.clone();
            caches.open(CACHE).then((c) => c.put(req, cp)).catch(() => {});
          }
          return res;
        })
        .catch(() => hit);
      return hit || net;
    })
  );
});
