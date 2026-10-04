/**
 * СТАТИК ДЕМО горим — сервергүйгээр интерфэйсийг харуулах зорилготой.
 * Бүх API дуудалтыг бэлэн өгөгдлөөр (FX) хариулна.
 * Бодит системд энэ файл ачаалагдахгүй — /api/* нь жинхэнэ сервер рүү хандана.
 *
 * Үүсгэгч: make_preview_demo.py (preview_demo.html)
 */
(function () {
  const FX = __FX_PLACEHOLDER__;
  const state = { clockedIn: false };
  // Статик демо-д харуулах сар (fixture-д байгаа хамгийн сүүлийн сар)
  FX.demo_month = Object.keys(FX.payroll_months || {}).sort().pop() ||
                  (FX.meta && FX.meta.server_time || '').slice(0, 7);

  const json = (data, status) => ({
    ok: (status || 200) < 400,
    status: status || 200,
    headers: { get: () => 'application/json' },
    json: async () => data,
  });
  const clone = o => JSON.parse(JSON.stringify(o));
  // Демо зураг (120x160 саарал дүрс) — data URI
  const DEMO_PHOTO = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAAKAAgBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==';
  const DEMO_OPEN = { id: 900, employee_id: 12, work_date: (FX.meta && FX.meta.server_time || '2026-10-04').slice(0, 10),
    kind: 'extra', start_ts: (FX.meta && FX.meta.server_time || '2026-10-04 17:30:00'),
    end_ts: null, start_photo: 'photos/2026-10/012_demo_extra_in.jpg', end_photo: null,
    minutes: 0, status: 'open', note: 'Демо нэмэлт ажил' };

  // Хоосон самбар (демо бичлэгийг устгасны дараах байдал)
  const EMPTY_BOARD = clone(FX.board);
  EMPTY_BOARD.employees.forEach(e => Object.assign(e, {
    status_code: 'pending', status_label: 'Хүлээгдэж байна', color: 'gray',
    clock_in: null, clock_out: null, clock_in_hm: '—', clock_out_hm: '—',
    worked_hm: '—', payable_hm: '—', late_minutes: 0, early_minutes: 0,
    deduct_minutes: 0, on_site: false, is_late: false, is_early_leave: false,
  }));
  EMPTY_BOARD.summary = { total: EMPTY_BOARD.employees.length, working: 0, late: 0,
                          absent: 0, done: 0, early: 0, on_time: 0 };
  EMPTY_BOARD.demo_data = false;

  window.fetch = async function (url, opts) {
    const u = String(url);
    const path = u.split('?')[0];
    const method = ((opts && opts.method) || 'GET').toUpperCase();
    await new Promise(r => setTimeout(r, 80));      // сүлжээний саатал дуурайх

    // ---------- Бүртгэл ----------
    if (path === '/api/employee/clock-in' || path === '/api/employee/clock-out') {
      const isIn = path.endsWith('clock-in');
      state.clockedIn = isIn;
      const hm = FX.meta.server_time.slice(11, 16);
      const rec = Object.assign({}, FX.emp_working.record,
        { clock_in: FX.meta.server_time, clock_in_hm: hm, clock_out: null, clock_out_hm: '—' });
      if (isIn) {
        rec.worked_hm = '0ц 00м'; rec.payable_hm = '0ц 00м';
      } else {
        rec.clock_out = FX.meta.server_time; rec.clock_out_hm = hm;
        rec.worked_hm = '8ц 05м'; rec.payable_hm = '8ц 05м';
      }
      const today = clone(FX.emp_working);
      today.record = rec;
      today.status_code = isIn ? 'working' : 'done';
      today.status_label = isIn ? 'Ажиллаж байна' : 'Ажил дууссан';
      return json({
        ok: true, record: rec,
        geofence: { ok: true, enabled: true, distance_m: 12.5, radius_m: 300, message: '' },
        message: (isIn ? 'Ажилд орох' : 'Ажлаас буух') + ' бүртгэл амжилттай. ' + hm,
        employee: FX.emp_login.employee, today: today,
        vision: FX.vision.text.split('\n').slice(0, 4).join('\n'),
      });
    }
    if (path === '/api/employee/today') return json(state.clockedIn ? FX.emp_working : FX.emp_today);
    if (path === '/api/employee/history') return json(FX.emp_history);
    if (path === '/api/geo/check') {
      return json({ ok: true, enabled: true, distance_m: 12.5, radius_m: 300, message: '' });
    }

    // ---------- Нэвтрэлт ----------
    if (path === '/api/auth/employee-login') {
      return json({ ok: true, role: 'employee', token: 'demo-token',
                    employee: FX.emp_login.employee, today: FX.emp_today });
    }
    if (path === '/api/auth/admin-login') {
      return json({ ok: true, role: 'admin', token: 'demo-token', name: 'admin',
                    company_name: FX.meta.company_name });
    }
    if (path === '/api/auth/logout') return json({ ok: true, message: 'Системээс гарлаа.' });
    if (path === '/api/auth/me') return json({ role: 'admin', kind: 'session', label: 'admin' });
    if (path === '/api/meta') return json(FX.meta);

    // ---------- Удирдлага ----------
    if (path === '/api/admin/board') {
      const want = (u.match(/date=([\d-]+)/) || [])[1];
      if (want && want !== FX.board.date) {                 // өөр өдөр: бичлэг байхгүй
        const b = clone(EMPTY_BOARD);
        b.date = want;
        b.is_today = false;
        b.is_workday = false;
        b.employees.forEach(e => { e.status_label = 'Амралтын өдөр'; });
        return json(b);
      }
      return json(FX.board);
    }
    if (path === '/api/admin/monthly') return json(FX.monthly);
    if (path === '/api/admin/matrix') return json(FX.matrix);
    if (path === '/api/admin/daily') return json(FX.daily);
    if (path === '/api/admin/employees') {
      if (method === 'POST') {
        return json({ ok: true, employee: FX.employees.employees[0],
                      message: 'Ажилтан амжилттай бүртгэгдлээ. (демо)' });
      }
      return json(FX.employees);
    }

    // ---------- v3: фото, нэмэлт ажил, мэдэгдэл, бодит цалин (демо) ----------
    if (path === '/api/employee/live') {
      const base = clone(FX.emp_live);
      base.as_of = (FX.meta && FX.meta.server_time) || base.as_of;
      return json(base);
    }
    if (path === '/api/employee/extra') {
      if (method === 'POST') {
        const cur = FX.emp_extra;
        if (path.endsWith('/start') || u.includes('/extra/start')) { cur.open = DEMO_OPEN; return json({ ok: true, segment: DEMO_OPEN, message: 'Нэмэлт ажил эхэллээ (зураг хадгалагдсан). (демо)' }); }
        cur.open = null;
        const seg = clone((cur.segments || [])[0] || {});
        seg.status = 'approved'; seg.minutes = 45; seg.end_ts = seg.start_ts;
        cur.segments = [seg, ...(cur.segments || [])];
        return json({ ok: true, segment: seg, message: 'Нэмэлт ажил дууслаа: 45 минут. (демо)' });
      }
      return json(FX.emp_extra);
    }
    if (path === '/api/employee/notifications') {
      if (method === 'POST') { FX.emp_notifications.unread = 0;
        (FX.emp_notifications.notifications || []).forEach(n => n.read_at = n.read_at || '2026-10-04 20:00:00');
        return json({ ok: true, marked: 99, unread: 0 }); }
      return json(FX.emp_notifications);
    }
    if (path === '/api/admin/notifications') return json(FX.admin_notifications);
    if (path === '/api/admin/notifications/tick') {
      return json({ ok: true, started: 4, ending: 2, missed: 1, absent: 1, night: 2,
                    at: (FX.meta && FX.meta.server_time || '').slice(0, 16),
                    message: 'Сануулга илгээгдлээ (демо).' });
    }
    if (path === '/api/admin/segments') return json(FX.admin_segments);
    if (path.startsWith('/api/admin/segments/')) {
      return json({ ok: true, message: 'Сегмент батлагдлаа (демо).' });
    }
    if (path === '/api/admin/photos') return json(FX.admin_photos);
    if (path === '/api/photos') {
      // Статик демо: жижиг дүрсэн дэх зураг (data URI)
      const b64 = DEMO_PHOTO;
      const raw = Uint8Array.from(atob(b64.split(',')[1]), c => c.charCodeAt(0));
      return { ok: true, status: 200, headers: { get: () => 'image/jpeg' },
               blob: async () => new Blob([raw], { type: 'image/jpeg' }) };
    }
    if (path === '/api/employee/clock-in' || path === '/api/employee/clock-out') {
      const inOut = path.endsWith('clock-in');
      if (!state.clockedIn && !inOut) return json({ ok: false, error: 'Эхлээд ажилд орох бүртгэлээ хийнэ үү.' }, 422);
      state.clockedIn = inOut;
      const rec = clone(FX.emp_today.record || {});
      const now = (FX.meta && FX.meta.server_time || '2026-10-04 09:00:00').slice(11, 16);
      if (inOut) Object.assign(rec, { clock_in: (FX.meta.server_time || '').slice(0, 10) + ' ' + now + ':00',
        clock_in_hm: now, in_photo: DEMO_PHOTO, status: 'working' });
      else Object.assign(rec, { clock_out: (FX.meta.server_time || '').slice(0, 10) + ' ' + now + ':00',
        clock_out_hm: now, out_photo: DEMO_PHOTO, status: 'completed' });
      FX.emp_today.record = rec;
      FX.emp_today.status_code = inOut ? 'working' : 'done';
      FX.emp_today.status_label = inOut ? 'Ажиллаж байна' : 'Ажил дууссан';
      return json({ ok: true, record: rec, photo: DEMO_PHOTO,
        geofence: { ok: true, enabled: true, distance_m: 42.5, radius_m: 250, message: '' },
        message: (inOut ? 'Ажилд орох бүртгэл амжилттай. ' : 'Ажлаас буух бүртгэл амжилттай. ') + now,
        today: FX.emp_today });
    }
    // ---------- Цалин (демо) ----------
    const wantMonth = (u.match(/month=([\d-]+)/) || [])[1];
    if (path === '/api/admin/payroll') {
      const pr = clone((FX.payroll_months && FX.payroll_months[wantMonth]) || FX.payroll_months[FX.demo_month]);
      if (wantMonth && !(FX.payroll_months && FX.payroll_months[wantMonth])) {
        pr.month = wantMonth;
        pr.month_label = wantMonth;
      }
      return json(pr);
    }
    if (path === '/api/admin/payroll-rules') {
      if (method === 'PUT') {
        try { Object.assign(FX.payroll_rules.rules, JSON.parse(opts.body || '{}')); } catch (e) {}
        return json({ ok: true, rules: FX.payroll_rules.rules, recalculated: 566,
                      message: 'Цалингийн дүрэм хадгалагдаж, 566 бүртгэл дахин тооцоологдлоо. (демо)' });
      }
      return json(FX.payroll_rules);
    }
    // ---------- Ажлын байр (демо) ----------
    if (path === '/api/admin/sites') {
      if (method === 'POST') {
        return json({ ok: true,
                      site: { id: 90, name: 'Шинэ талбай (демо)', address: 'Улаанбаатар', lat: 47.9,
                              lng: 106.9, radius_m: 300, active: 1, employee_count: 0 },
                      message: '«Шинэ талбай (демо)» ажлын байр нэмэгдлээ.' });
      }
      return json(FX.sites);
    }
    if (path.startsWith('/api/admin/sites/')) {
      if (method === 'DELETE') return json({ ok: true, message: 'Ажлын байр идэвхгүй боллоо. (демо)' });
      return json({ ok: true, site: FX.sites.sites[0], message: 'Ажлын байр шинэчлэгдлээ. (демо)' });
    }
    // ---------- Чөлөө (демо) ----------
    if (path === '/api/admin/leaves') {
      if (method === 'POST') {
        const base = (FX.leaves_months[FX.demo_month] || {}).leaves || [];
        const lv = clone(base[base.length - 1] || {});
        Object.assign(lv, { id: 900, ...(JSON.parse(opts.body || '{}')), hours: 4 });
        return json({ ok: true, leave: lv,
                      message: `${lv.kind || 'Чөлөө'} амжилттай олгогдлоо. (демо)` });
      }
      return json((FX.leaves_months && FX.leaves_months[wantMonth]) || FX.leaves_months[FX.demo_month]);
    }
    if (/^\/api\/admin\/leaves\/\d+$/.test(path) && method === 'DELETE') {
      return json({ ok: true, message: 'Чөлөө устгагдлаа. (демо)' });
    }
    if (/^\/api\/admin\/leaves\/\d+\/summary$/.test(path)) {
      const eid = path.split('/')[4];
      const m = wantMonth || FX.demo_month;
      const emp = FX.employees.employees.find(e => String(e.id) === String(eid)) || {};
      return json({ employee: emp, month: m,
                    summary: (FX.leave_summaries && FX.leave_summaries[eid + '|' + m]) ||
                             { 'чөлөө': { days: 0, hours: 0, paid: false },
                               'амралт': { days: 0, hours: 0, paid: true },
                               'өвчтэй': { days: 0, hours: 0, paid: true } } });
    }
    // ---------- Ажилтны цалин (демо) ----------
    if (/^\/api\/admin\/employees\/\d+\/pay$/.test(path)) {
      const eid = Number(path.split('/')[4]);
      const m = wantMonth || FX.demo_month;
      if (eid === FX.emp_pay_sample_id && FX.emp_pay_months[m]) return json(FX.emp_pay_months[m]);
      const pr = clone(FX.payroll_months[FX.demo_month]);
      const row = pr.rows.find(r => r.employee_id === eid) || pr.rows[0];
      const emp = FX.employees.employees.find(e => e.id === eid) || {};
      return json({ employee: emp, month: m, row,
                    pay: { employee_id: eid, code: row.code, full_name: row.full_name,
                           daily_rate: row.daily_rate, night_role: row.night_role,
                           site: null, night_half: Math.round(row.daily_rate * 0.5),
                           night_full: Math.round(row.daily_rate) },
                    rules: pr.rules, currency: pr.currency, site: null });
    }
    if (/^\/api\/admin\/employees\/\d+\/days$/.test(path)) {
      const eid = Number(path.split('/')[4]);
      const m = wantMonth || FX.demo_month;
      if (eid === FX.emp_pay_sample_id && FX.emp_days_months[m]) return json(FX.emp_days_months[m]);
      return json({ employee: {}, month: m, days: [], total_pay: 0, total_extra: 0 });
    }
    if (path === '/api/employee/my-pay') {
      return json((FX.my_pay_months && FX.my_pay_months[wantMonth]) || FX.my_pay_months[FX.demo_month]);
    }
    // ---------- v4.5: хоёр төлбөр (25-ны аванс + 10-ны үндсэн цалин) ----------
    if (path === '/api/admin/periods') return json(FX.periods);
    if (path === '/api/admin/pay-cycle') {
      const w = (u.match(/period=([\d-]+)/) || [])[1];
      const key = (w && FX.pay_cycle_months[w]) ? w : FX.demo_period;
      return json(clone(FX.pay_cycle_months[key]));
    }
    if (path === '/api/admin/period-payroll') {
      const w = (u.match(/period=([\d-]+)/) || [])[1];
      const key = (w && FX.pay_cycle_months[w]) ? w : FX.demo_period;
      const cy = clone(FX.pay_cycle_months[key]);
      return json({ period: cy.period, label: cy.label, start: cy.start, end: cy.end,
                    payout_date: cy.payout_date, rows: cy.rows, totals: cy.totals,
                    currency: cy.currency, currency_label: cy.currency_label,
                    company_name: cy.company_name, generated_at: cy.generated_at });
    }
    if (path === '/api/admin/advances') {
      const w = (u.match(/period=([\d-]+)/) || [])[1];
      const key = (w && FX.advances_months[w]) ? w : FX.demo_period;
      return json(clone(FX.advances_months[key]));
    }
    if (path.startsWith('/api/admin/advances/')) {
      const eid = Number(path.split('/').pop());
      const row = (FX.advances_months[FX.demo_period].rows || []).find(r => r.employee_id === eid);
      return json({ ok: true, period: FX.demo_period, employee_id: eid, advance: row || null,
                    window_earnings: row ? row.window_earnings : 0,
                    bounds: (FX.pay_cycle_months[FX.demo_period] || {}).bounds || {} });
    }
    if (path === '/api/admin/advances/pay' || path === '/api/admin/advances/cancel') {
      const post = path.endsWith('/pay') ? 'paid' : 'cancelled';
      let body = {}; try { body = JSON.parse(opts.body || '{}'); } catch (e) {}
      const cy = FX.pay_cycle_months[FX.demo_period];
      const row = (cy.rows || []).find(r => String(r.employee_id) === String(body.employee_id)
                                          || r.code === body.code);
      if (row) {
        const amt = post === 'paid' ? (row.advance_amount || 1000000) : 0;
        row.advance_status = post;
        row.advance_status_label = post === 'paid' ? 'Олгосон' : 'Цуцлагдсан';
        row.advance_amount = amt;
        row.advance_deduct = post === 'paid' ? amt : 0;
        row.total = Math.max(0, row.gross - row.penalty - row.advance_deduct);
        row.paid_on = post === 'paid' ? (cy.advance_pay_date || '') : null;
        const adv = FX.advances_months[FX.demo_period];
        const arow = (adv.rows || []).find(r => r.employee_id === row.employee_id);
        if (arow) { arow.status = post === 'cancelled' ? 'cancelled' : 'paid';
                    arow.status_label = row.advance_status_label; arow.amount = amt; }
      }
      return json({ ok: true, advance: row || null,
                    message: row ? (post === 'paid'
                      ? row.full_name + ': ' + (row.advance_amount || 0).toLocaleString('en-US')
                        .replace(/,/g, ' ') + '₮ аванс олгогдсон гэж бүртгэгдлээ — 10-ны цалингаас хасагдана. (демо)'
                      : row.full_name + ': авансын бичлэг «Цуцлагдсан» боллоо. (демо)')
                      : 'Аванс бүртгэгдлээ. (демо)' });
    }
    if (path === '/api/employee/my-pay-cycle') {
      const c = clone(FX.my_pay_cycle);
      // Ажилтны карт нь зөвхөн өөрийн мэдээлэл — сервертэй адил
      return json(c);
    }
    if (path === '/api/employee/my-leaves') {
      return json((FX.my_leaves_months && FX.my_leaves_months[wantMonth]) || FX.my_leaves_months[FX.demo_month]);
    }
    if (path.startsWith('/api/admin/employees/')) {
      return json({ ok: true, employee: FX.employees.employees[0],
                    message: 'Ажилтны мэдээлэл шинэчлэгдлээ. (демо)' });
    }
    if (path === '/api/admin/settings') {
      if (method === 'PUT') {
        try { Object.assign(FX.settings.settings, JSON.parse(opts.body || '{}')); } catch (e) {}
        return json({ ok: true, settings: FX.settings.settings,
                      message: 'Тохиргоо хадгалагдлаа. (демо)', recalculated: 470 });
      }
      return json(FX.settings);
    }
    if (path === '/api/admin/api-keys') {
      if (method === 'POST') {
        return json({ ok: true, key: { key: 'att_demo_new_key_2026', name: 'Демо агент', role: 'agent' },
                      message: 'API түлхүүр үүсгэгдлээ. (демо)' });
      }
      return json(FX.keys);
    }
    if (path.startsWith('/api/admin/api-keys/')) {
      return json({ ok: true, message: 'API түлхүүр идэвхгүй боллоо. (демо)' });
    }
    if (path === '/api/admin/demo/seed') {
      return json({ ok: true, created: 11, board: FX.board,
                    message: '11 ажилтны туршилтын бүртгэл үүсгэгдлээ. (Демо өгөгдөл)' });
    }
    if (path === '/api/admin/demo/today') {
      return json({ ok: true, deleted: 11, board: EMPTY_BOARD,
                    message: '11 туршилтын бичлэг устгагдлаа.' });
    }
    if (path === '/api/admin/records') return json({ ok: true, record: {}, message: 'Бүртгэл хадгалагдлаа. (демо)' });
    if (path === '/api/admin/recalc') {
      return json({ ok: true, recalculated: 470,
                    message: '470 бүртгэл одоогийн ажлын хуваарийн дагуу дахин тооцоологдлоо. (демо)' });
    }
    if (path === '/api/admin/audit') return json(FX.audit);
    if (path === '/api/admin/geofence-log') return json(FX.geolog);
    if (path === '/api/admin/geofence-check') {
      return json({ ok: true, enabled: true, distance_m: 8.0, radius_m: 300, message: '' });
    }

    // ---------- AI агент ----------
    if (path === '/api/agent/vision') return json(FX.vision);
    if (path === '/api/agent/status') return json(FX.board);
    if (path.startsWith('/api/agent/')) return json(FX.vision);

    return json({ ok: true, message: 'Демо горим — өгөгдөл нь жишээ.' });
  };
})();
