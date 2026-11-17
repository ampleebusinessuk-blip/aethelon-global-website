(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];

  /* Language: pages under /de/, /fr/, /es/, /ar/, /hi/ carry a translated string table (window.I18N) */
  const LANG = document.documentElement.lang || 'en';
  const BASE = document.documentElement.dataset.base || '';
  const t = s => (window.I18N && window.I18N[s]) || s;

  /* Region picker language links keep you on the same page in the other language */
  const plainPath = (BASE && location.pathname.startsWith(BASE + '/') ? location.pathname.slice(BASE.length) : location.pathname) || '/';
  document.querySelectorAll('a[data-lang]').forEach(a => {
    const l = a.dataset.lang;
    a.href = (l === 'en' ? '' : '/' + l) + plainPath + location.search + location.hash;
    const li = a.closest('.region');
    if (a.hasAttribute('data-primary') && l === LANG) { a.setAttribute('aria-current', 'true'); li && li.classList.add('is-current'); }
    else if (a.getAttribute('aria-current') && !(a.hasAttribute('data-primary') && l === LANG)) { a.removeAttribute('aria-current'); }
  });
  document.querySelectorAll('.region.is-current').forEach(li => { if (!li.querySelector('[aria-current]')) li.classList.remove('is-current'); });
  const cur = document.querySelector('.region-list [aria-current]');
  if (cur) document.querySelectorAll('.m-region summary').forEach(sum => {
    const row = cur.closest('.region'), span = sum.querySelector('span'), flag = sum.querySelector('.flag');
    if (span) span.textContent = row.querySelector('.region-name').textContent + ' · ' + cur.textContent;
    if (flag) flag.replaceWith(row.querySelector('.flag').cloneNode(true));
  });
  const header = $('.site-header');
  const alwaysSolid = document.body.classList.contains('solid-header');

  /* ---------- Header (absolute, not sticky) ---------- */
  const dim = $('#pageDim');
  const megaBg = $('.mega-bg');
  const desktop = () => window.innerWidth >= 1200;
  const setMegaBg = li => {
    if (!megaBg) return;
    if (!li || !desktop()) { megaBg.style.height = '0'; header.classList.remove('mega-open'); dim && dim.classList.remove('is-on'); return; }
    const inner = $('.mega-inner', li);
    megaBg.style.height = ($('.header-inner', header).offsetHeight + inner.scrollHeight) + 'px';
    header.classList.add('mega-open'); dim && dim.classList.add('is-on');
  };
  const closeMegas = () => { $$('.has-mega').forEach(o => { o.classList.remove('is-open'); $('.nav-link', o).setAttribute('aria-expanded', 'false'); }); setMegaBg(null); };
  $$('.has-mega').forEach(li => {
    const btn = $('.nav-link', li);
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const open = !li.classList.contains('is-open');
      $$('.has-mega').forEach(o => { if (o !== li) { o.classList.remove('is-open'); $('.nav-link', o).setAttribute('aria-expanded', 'false'); } });
      li.classList.toggle('is-open', open);
      btn.setAttribute('aria-expanded', String(open));
      setMegaBg(open ? li : null);
    });
  });
  document.addEventListener('click', e => { if (desktop() && !e.target.closest('.has-mega')) closeMegas(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeMegas(); closeSearch(); closeRegion(true); } });
  dim && dim.addEventListener('click', closeMegas);
  window.addEventListener('resize', () => { if (!desktop()) setMegaBg(null); });

  /* Mobile menu: full-screen panel slides in from the right */
  const burger = $('#burger');
  if (burger) {
    burger.addEventListener('click', () => {
      const open = header.classList.toggle('menu-open');
      burger.setAttribute('aria-expanded', String(open));
      burger.setAttribute('aria-label', open ? t('Close menu') : t('Open menu'));
      document.body.style.overflow = open ? 'hidden' : '';
    });
    $$('.main-nav a').forEach(a => a.addEventListener('click', () => {
      header.classList.remove('menu-open'); burger.setAttribute('aria-expanded', 'false'); document.body.style.overflow = '';
    }));
  }

  /* Region & language picker */
  const regionBtn = $('#regionToggle'), regionPanel = $('#regionPanel');
  function closeRegion(focus) {
    if (!regionPanel || regionPanel.hidden) return;
    regionPanel.classList.remove('is-open'); regionBtn.setAttribute('aria-expanded', 'false');
    setTimeout(() => { if (!regionPanel.classList.contains('is-open')) regionPanel.hidden = true; }, 180);
    if (focus) regionBtn.focus();
  }
  if (regionBtn && regionPanel) {
    regionBtn.addEventListener('click', e => {
      e.stopPropagation();
      if (!regionPanel.hidden) return closeRegion();
      closeMegas(); closeSearch();
      regionPanel.hidden = false;
      requestAnimationFrame(() => regionPanel.classList.add('is-open'));
      regionBtn.setAttribute('aria-expanded', 'true');
    });
    document.addEventListener('click', e => { if (!e.target.closest('.region-wrap')) closeRegion(); });
  }

  /* Search panel drops from the top */
  const searchPanel = $('#searchPanel');
  const searchToggle = $('#searchToggle');
  function closeSearch() { if (!searchPanel || searchPanel.hidden) return; searchPanel.classList.remove('is-open'); if (searchToggle) searchToggle.setAttribute('aria-expanded', 'false'); setTimeout(() => { searchPanel.hidden = true; }, 200); }
  if (searchPanel && searchToggle) {
    searchToggle.addEventListener('click', () => {
      closeMegas(); closeRegion();
      searchPanel.hidden = false;
      requestAnimationFrame(() => searchPanel.classList.add('is-open'));
      searchToggle.setAttribute('aria-expanded', 'true');
      setTimeout(() => $('input', searchPanel).focus(), 50);
    });
    const sc = $('#searchClose');
    if (sc) sc.addEventListener('click', closeSearch);
  }

  /* Mark the current section in the nav */
  const path = location.pathname;
  $$('.main-nav a.nav-link').forEach(a => { const h = a.getAttribute('href'); if (h && h !== '/' && path.startsWith(h)) a.classList.add('is-current'); });
  $$('.has-mega').forEach(li => { if ($$('.mega a', li).some(a => path.startsWith(a.getAttribute('href')))) $('.nav-link', li).classList.add('is-current'); });

  /* ---------- Home hero carousel ---------- */
  const hero = $('#hero');
  let setHeroPaused = () => {}, heroPaused = () => true;
  if (hero) {
    const slides = $$('.hero-slide', hero);
    const indWrap = $('.hero-indicators', hero);
    const DELAY = Number(hero.dataset.delay) || 5500;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    hero.style.setProperty('--delay', DELAY + 'ms');
    let idx = 0, timer = null, paused = reduceMotion, started = 0, remaining = DELAY;

    slides.forEach(slide => {
      const v = $('.hero-video', slide);
      if (!v) return;
      v.addEventListener('loadeddata', () => v.classList.add('is-ready'));
      v.addEventListener('error', () => v.remove(), true);
    });
    const loadVideo = slide => {
      const v = slide && $('.hero-video', slide);
      if (!v || v.dataset.loaded) return;
      v.dataset.loaded = '1';
      const src = document.createElement('source');
      src.src = v.dataset.src; src.type = 'video/mp4';
      src.addEventListener('error', () => v.remove());
      v.appendChild(src);
      v.load();
    };
    const inds = slides.map((_, i) => {
      const b = document.createElement('button');
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-label', t('Go to slide {n}').replace('{n}', i + 1));
      b.addEventListener('click', () => go(i));
      indWrap.appendChild(b);
      return b;
    });
    const schedule = ms => { clearTimeout(timer); if (!paused) { started = Date.now(); remaining = ms; timer = setTimeout(() => go(idx + 1), ms); } };
    function go(i) {
      const prev = slides[idx];
      idx = (i + slides.length) % slides.length;
      slides.forEach((s, j) => {
        const on = j === idx;
        s.classList.toggle('is-active', on);
        s.setAttribute('aria-hidden', String(!on));
        $$('a,button', s).forEach(el => el.tabIndex = on ? 0 : -1);
        const v = $('.hero-video', s);
        if (v) { if (on) { loadVideo(s); v.play().catch(() => {}); } else if (s !== prev) v.pause(); }
      });
      if (prev && prev !== slides[idx]) setTimeout(() => { const v = $('.hero-video', prev); if (v && !prev.classList.contains('is-active')) v.pause(); }, 800);
      loadVideo(slides[idx + 1]);
      inds.forEach((b, j) => { b.classList.remove('is-active'); b.classList.toggle('is-done', j < idx); b.setAttribute('aria-selected', String(j === idx)); });
      void inds[idx].offsetWidth;
      inds[idx].classList.add('is-active');
      schedule(DELAY);
    }
    setHeroPaused = p => {
      paused = p;
      hero.classList.toggle('is-paused', p);
      $('#heroToggle').setAttribute('aria-label', p ? t('Play') : t('Pause'));
      const v = $('.hero-video', slides[idx]);
      if (p) { clearTimeout(timer); remaining = Math.max(0, remaining - (Date.now() - started)); v && v.pause(); }
      else { v && v.play().catch(() => {}); schedule(remaining || DELAY); }
    };
    heroPaused = () => paused;
    $('#heroToggle').addEventListener('click', () => setHeroPaused(!paused));
    $('#heroNext').addEventListener('click', () => go(idx + 1));
    $('#heroPrev').addEventListener('click', () => go(idx - 1));
    hero.addEventListener('keydown', e => { if (e.key === 'ArrowRight') go(idx + 1); if (e.key === 'ArrowLeft') go(idx - 1); });
    let tx = null;
    hero.addEventListener('touchstart', e => { tx = e.touches[0].clientX; }, { passive: true });
    hero.addEventListener('touchend', e => { if (tx === null) return; const dx = e.changedTouches[0].clientX - tx; if (Math.abs(dx) > 50) go(idx + (dx < 0 ? 1 : -1)); tx = null; });
    new IntersectionObserver(([e]) => { const v = $('.hero-video', slides[idx]); if (v) e.isIntersecting && !paused ? v.play().catch(() => {}) : v.pause(); }).observe(hero);
    if (reduceMotion) hero.classList.add('is-paused');
    go(0);
  }

  /* ---------- Watch-video modal ---------- */
  const modal = $('#filmModal');
  if (modal) {
    const film = $('.film-video', modal);
    const missing = $('.film-missing', modal);
    let wasPaused = false, opener = null;
    $$('[data-film]').forEach(btn => btn.addEventListener('click', () => {
      opener = btn;
      wasPaused = heroPaused(); setHeroPaused(true);
      missing.hidden = true; film.hidden = false;
      film.src = btn.dataset.film;
      film.onerror = () => { film.hidden = true; missing.hidden = false; missing.textContent = t('This video is not available yet.'); };
      modal.setAttribute('aria-label', btn.dataset.filmTitle || 'Video');
      modal.hidden = false;
      document.body.style.overflow = 'hidden';
      film.play().catch(() => {});
      $('.film-close', modal).focus();
    }));
    const closeFilm = () => {
      film.pause(); film.removeAttribute('src'); film.load();
      modal.hidden = true; document.body.style.overflow = '';
      if (!wasPaused) setHeroPaused(false);
      opener && opener.focus();
    };
    $$('[data-close]', modal).forEach(el => el.addEventListener('click', closeFilm));
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !modal.hidden) closeFilm(); });
  }

  /* ---------- Home "stories & insights" rail (data from the site generator) ---------- */
  const homeRail = $('#homeRail');
  if (homeRail && window.HOME_FEED) {
    const e = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    homeRail.innerHTML = window.HOME_FEED.map(s => `<a class="dcard" href="${s.href}">
      <div class="dcard-media"><img src="${s.image}" alt="" loading="lazy"></div>
      <div class="dcard-body"><span class="eyebrow">${e(s.type)}</span><h3>${e(s.title)}</h3><span class="serif-meta">${e(s.meta)}</span></div></a>`).join('');
  }

  /* ---------- Rails: arrow buttons scroll one card at a time ---------- */
  $$('[data-rail]').forEach(r => {
    const track = $('.rail-track', r), prev = $('[data-rail-prev]', r), next = $('[data-rail-next]', r);
    if (!track) return;
    const step = () => { const c = track.firstElementChild; return c ? c.getBoundingClientRect().width + (parseFloat(getComputedStyle(track).columnGap) || 16) : 300; };
    const update = () => { if (prev) prev.disabled = track.scrollLeft < 4; if (next) next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 4; };
    if (prev) prev.addEventListener('click', () => track.scrollBy({ left: -step(), behavior: 'smooth' }));
    if (next) next.addEventListener('click', () => track.scrollBy({ left: step(), behavior: 'smooth' }));
    track.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    setTimeout(update, 100);
  });

  /* ---------- Share menus ---------- */
  $$('[data-share]').forEach(b => {
    const menu = b.nextElementSibling;
    b.addEventListener('click', ev => { ev.stopPropagation(); const open = menu.hidden; $$('.share-menu').forEach(m => { m.hidden = true; }); menu.hidden = !open; b.setAttribute('aria-expanded', String(open)); });
  });
  document.addEventListener('click', ev => { if (!ev.target.closest('.share-wrap')) $$('.share-menu').forEach(m => { m.hidden = true; }); });

  /* ---------- Generic filter + search + load-more lists (insights, stories, careers) ---------- */
  $$('[data-list]').forEach(wrap => {
    const items = $$('[data-item]', wrap);
    const chips = $$('[data-filter]', wrap);
    const search = $('[data-search]', wrap);
    const more = $('[data-more]', wrap);
    const empty = $('[data-empty]', wrap);
    const count = $('[data-count]', wrap);
    const pageSize = Number(wrap.dataset.pageSize) || 9;
    let filter = 'all', shown = pageSize;
    const params = new URLSearchParams(location.search);
    if (params.get('filter')) filter = params.get('filter');
    const apply = () => {
      const q = (search && search.value.trim().toLowerCase()) || '';
      const matches = items.filter(it => (filter === 'all' || (it.dataset.tags || '').split(' ').includes(filter)) && (!q || it.textContent.toLowerCase().includes(q)));
      items.forEach(it => { it.hidden = true; });
      matches.slice(0, shown).forEach(it => { it.hidden = false; });
      if (more) more.hidden = shown >= matches.length;
      if (empty) empty.hidden = matches.length > 0;
      if (count) count.textContent = t(matches.length === 1 ? '{n} result' : '{n} results').replace('{n}', matches.length);
      chips.forEach(c => c.classList.toggle('is-active', c.dataset.filter === filter));
    };
    chips.forEach(c => c.addEventListener('click', () => { filter = c.dataset.filter; shown = pageSize; apply(); }));
    search && search.addEventListener('input', () => { shown = pageSize; apply(); });
    more && more.addEventListener('click', () => { shown += pageSize; apply(); });
    apply();
  });

  /* ---------- Site search page ---------- */
  const results = $('#searchResults');
  if (results) {
    const input = $('#searchInput');
    const status = $('#searchStatus');
    const q0 = new URLSearchParams(location.search).get('q') || '';
    input.value = q0;
    const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    fetch(BASE + '/search-index.json').then(r => r.json()).then(index => {
      const run = () => {
        const q = input.value.trim().toLowerCase();
        history.replaceState(null, '', q ? `?q=${encodeURIComponent(q)}` : location.pathname);
        if (!q) { results.innerHTML = ''; status.textContent = t('Type to search pages, services, stories and insights.'); return; }
        const words = q.split(/\s+/);
        const scored = index.map(p => {
          const ti = p.title.toLowerCase(), b = (p.summary + ' ' + p.text).toLowerCase();
          let s = 0;
          for (const w of words) { if (ti.includes(w)) s += 5; if (b.includes(w)) s += 1; }
          if (ti.includes(q)) s += 10;
          return [s, p];
        }).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0]).map(([, p]) => p);
        status.textContent = t(scored.length === 1 ? '{n} result for “{q}”' : '{n} results for “{q}”').replace('{n}', scored.length).replace('{q}', q);
        results.innerHTML = scored.slice(0, 30).map(p => `<a class="search-hit" href="${p.url}"><span class="search-type">${esc(p.type)}</span><h3>${esc(p.title)}</h3><p>${esc(p.summary)}</p></a>`).join('');
      };
      input.addEventListener('input', run);
      run();
    }).catch(() => { status.textContent = t('Search is unavailable right now.'); });
  }

  /* ---------- Copy link / share ---------- */
  $$('[data-copy-link]').forEach(btn => btn.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); const old = btn.textContent; btn.textContent = t('Link copied ✓'); setTimeout(() => { btn.textContent = old; }, 2000); } catch { prompt(t('Copy this link:'), location.href); }
  }));

  /* ---------- Testimonials, ticker ---------- */
  const track = $('#quoteTrack');
  if (track) {
    const step = () => ($('.quote', track)?.offsetWidth || 400) + 28;
    $('#qNext')?.addEventListener('click', () => track.scrollBy({ left: step(), behavior: 'smooth' }));
    $('#qPrev')?.addEventListener('click', () => track.scrollBy({ left: -step(), behavior: 'smooth' }));
  }
  const ticker = $('#tickerTrack');
  if (ticker) ticker.innerHTML += ticker.innerHTML;

  /* ---------- Reveal on scroll ---------- */
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } }), { threshold: 0.12 });
    $$('.reveal').forEach(el => io.observe(el));
  } else $$('.reveal').forEach(el => el.classList.add('is-in'));

  /* ---------- Forms: validate, then open the visitor's email app with the message ready to send ----------
     No server needed. To collect submissions on a server instead, set data-endpoint="https://..." on the form. */
  $$('form[data-form]').forEach(form => {
    const msg = $('.form-msg', form);
    form.addEventListener('input', e => { if (e.target.classList.contains('invalid')) { e.target.classList.remove('invalid'); e.target.setAttribute('aria-invalid', 'false'); } });
    form.addEventListener('change', e => { if (e.target.type === 'checkbox' && e.target.checked) e.target.classList.remove('invalid'); });
    form.addEventListener('submit', async e => {
      e.preventDefault();
      let ok = true;
      $$('[required]', form).forEach(f => {
        const bad = f.type === 'checkbox' ? !f.checked : (!f.value.trim() || (f.type === 'email' && !/^\S+@\S+\.\S+$/.test(f.value)));
        f.classList.toggle('invalid', bad); f.setAttribute('aria-invalid', String(bad)); if (bad) ok = false;
      });
      if (!ok) { msg.textContent = t('Please complete the highlighted fields.'); msg.dataset.state = 'error'; $('.invalid', form)?.focus(); return; }
      const data = new FormData(form);
      const endpoint = form.dataset.endpoint;
      if (endpoint) {
        try {
          const r = await fetch(endpoint, { method: 'POST', body: data, headers: { Accept: 'application/json' } });
          if (!r.ok) throw new Error(r.status);
          msg.textContent = form.dataset.success || t('Thank you — we’ll be in touch shortly.'); msg.dataset.state = 'ok'; form.reset(); return;
        } catch { /* fall through to email */ }
      }
      const lines = [];
      for (const [k, v] of data.entries()) if (typeof v === 'string' && v.trim() && k !== 'consent') lines.push(`${k[0].toUpperCase() + k.slice(1)}: ${v}`);
      const subject = form.dataset.subject || t('Website enquiry');
      location.href = `mailto:${form.dataset.mailto}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join('\n\n'))}`;
      msg.innerHTML = t('Your email app should open with your message ready to send. If it doesn’t, email us at {email}.').replace('{email}', `<a href="mailto:${form.dataset.mailto}">${form.dataset.mailto}</a>`);
      msg.dataset.state = 'ok';
    });
  });
})();
