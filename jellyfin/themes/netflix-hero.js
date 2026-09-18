/**
 * Netflix Hero Banner for Jellyfin 12
 * Standalone, lightweight script with zero third-party plugin dependencies.
 */
(function () {
    'use strict';

    let currentHeroEl = null;
    let heroTimer = null;
    let cachedEntries = [];
    let currentIndex = 0;
    let isFetching = false;

    function isHome() {
        const hash = window.location.hash || '';
        const cleanHash = hash.split('?')[0];
        if (cleanHash !== '' && cleanHash !== '#/' && cleanHash !== '#/home' && cleanHash !== '#/home.html') {
            return false;
        }
        if (hash.includes('tab=')) {
            const params = new URLSearchParams(hash.split('?')[1] || '');
            return params.get('tab') === '0';
        }
        return true;
    }

    function hasMediaBar() {
        return Boolean(window.slideshowPure || document.getElementById('slides-container'));
    }

    function setupMediaBarBridge() {
        const sc = document.getElementById('slides-container');
        if (!sc) return;

        // If Media Bar is hidden or we are not on the main home view, reset layout
        if (sc.style.display === 'none' || !isHome()) {
            removeHeroLayoutStyles();
            return;
        }

        // Remove standalone hero if it was previously rendered
        removeHero();

        // Ensure full-bleed classes and header transparency
        alignHeroToTop();

        // Observe style changes on slides-container so tab switches update immediately
        if (!sc.hasAttribute('data-display-observed')) {
            sc.setAttribute('data-display-observed', 'true');
            const displayObs = new MutationObserver(() => {
                if (sc.style.display === 'none' || !isHome()) {
                    removeHeroLayoutStyles();
                } else {
                    alignHeroToTop();
                }
            });
            displayObs.observe(sc, { attributes: true, attributeFilter: ['style'] });
        }

        // Catch logo image 404s/errors and swap with bold Netflix typography
        if (!sc.hasAttribute('data-logo-fallback-bound')) {
            sc.setAttribute('data-logo-fallback-bound', 'true');
            sc.addEventListener('error', (e) => {
                if (e.target && e.target.tagName === 'IMG' && e.target.classList.contains('logo')) {
                    const img = e.target;
                    const title = img.alt || '';
                    if (!title) return;
                    const fallback = document.createElement('h1');
                    fallback.className = 'logo logo-text-fallback';
                    fallback.textContent = title;
                    img.replaceWith(fallback);
                }
            }, true);
        }

        // Enable trailers and slide animations in config
        if (window.slideshowPure && window.slideshowPure.CONFIG) {
            window.slideshowPure.CONFIG.enableTrailers = true;
            window.slideshowPure.CONFIG.slideAnimationEnabled = true;
        }

        // Clean up inline 'top' style on dots container and guard against script recalculations
        const dots = sc.querySelector('.dots-container');
        if (dots && !dots.hasAttribute('data-bridged')) {
            dots.setAttribute('data-bridged', 'true');
            if (dots.style.top) {
                dots.style.top = '';
            }
            const dotObserver = new MutationObserver(() => {
                if (dots.style.top) {
                    dots.style.top = '';
                }
            });
            dotObserver.observe(dots, { attributes: true, attributeFilter: ['style'] });
        }

        // Bridge volume toggle mute/unmute state class
        const volumeBtn = sc.querySelector('.volume-toggle');
        if (volumeBtn && !volumeBtn.hasAttribute('data-bridged')) {
            volumeBtn.setAttribute('data-bridged', 'true');
            const updateMuteClass = () => {
                const isMuted = window.slideshowPure?.STATE?.slideshow?.isMuted ?? true;
                volumeBtn.classList.toggle('is-unmuted', !isMuted);
                volumeBtn.classList.toggle('is-muted', isMuted);
            };
            updateMuteClass();
            volumeBtn.addEventListener('click', () => {
                setTimeout(updateMuteClass, 50);
                setTimeout(updateMuteClass, 200);
            });
            const innerI = volumeBtn.querySelector('i');
            if (innerI) {
                const iconObserver = new MutationObserver(() => {
                    const text = innerI.textContent.trim();
                    const isUnmuted = text === 'volume_up';
                    volumeBtn.classList.toggle('is-unmuted', isUnmuted);
                    volumeBtn.classList.toggle('is-muted', !isUnmuted);
                });
                iconObserver.observe(innerI, { childList: true, characterData: true, subtree: true });
            }
        }
    }

    function alignHeroToTop() {
        const sc = document.getElementById('slides-container');
        if (!currentHeroEl && !sc) return;
        
        // If Media Bar is hidden or we are not on main home view, reset layout
        if (sc && (sc.style.display === 'none' || !isHome())) {
            removeHeroLayoutStyles();
            return;
        }

        // Ensure body flag is active
        document.body.classList.add('has-netflix-hero');
        const indexPage = document.getElementById('indexPage');
        if (indexPage) {
            indexPage.classList.add('has-netflix-hero');
            indexPage.style.setProperty('padding-top', '0px', 'important');
            indexPage.style.setProperty('margin-top', '0px', 'important');
        }
        const homeTab = document.getElementById('homeTab');
        if (homeTab) {
            homeTab.classList.add('has-netflix-hero');
            homeTab.style.setProperty('padding-top', '0px', 'important');
            homeTab.style.setProperty('margin-top', '0px', 'important');
        }

        // Hero starts at y=0 with spacer collapsed via CSS
        if (currentHeroEl) {
            currentHeroEl.style.setProperty('margin-top', '0px', 'important');
        }

        // Make header transparent
        updateHeaderStyle();
    }

    function updateHeaderStyle() {
        const headers = document.querySelectorAll('header.MuiAppBar-root, header, .skinHeader');
        if (!headers.length) return;

        const isScrolled = window.scrollY > 30;
        headers.forEach(h => {
            if (isScrolled) {
                h.style.setProperty('background', 'rgba(16, 16, 16, 0.95)', 'important');
                h.style.setProperty('backdrop-filter', 'blur(16px)', 'important');
                h.style.setProperty('-webkit-backdrop-filter', 'blur(16px)', 'important');
                h.style.setProperty('box-shadow', '0 4px 20px rgba(0, 0, 0, 0.6)', 'important');
                h.style.setProperty('border', 'none', 'important');
            } else {
                h.style.setProperty('background', 'linear-gradient(180deg, rgba(0, 0, 0, 0.85) 0%, rgba(0, 0, 0, 0.4) 40%, transparent 100%)', 'important');
                h.style.setProperty('background-color', 'transparent', 'important');
                h.style.setProperty('backdrop-filter', 'none', 'important');
                h.style.setProperty('-webkit-backdrop-filter', 'none', 'important');
                h.style.setProperty('box-shadow', 'none', 'important');
                h.style.setProperty('border', 'none', 'important');
            }
        });
    }

    function removeHeroLayoutStyles() {
        document.body.classList.remove('has-netflix-hero');
        const indexPage = document.getElementById('indexPage');
        if (indexPage) {
            indexPage.classList.remove('has-netflix-hero');
            indexPage.style.removeProperty('padding-top');
            indexPage.style.removeProperty('margin-top');
        }
        const homeTab = document.getElementById('homeTab');
        if (homeTab) {
            homeTab.classList.remove('has-netflix-hero');
            homeTab.style.removeProperty('padding-top');
            homeTab.style.removeProperty('margin-top');
        }
        updateHeaderStyle();
    }

    function removeHero() {
        if (heroTimer) {
            clearInterval(heroTimer);
            heroTimer = null;
        }
        if (currentHeroEl) {
            currentHeroEl.remove();
            currentHeroEl = null;
        }
        removeHeroLayoutStyles();
    }

    async function fetchHeroEntries(apiClient) {
        const userId = apiClient.getCurrentUserId();
        if (!userId) return [];

        const seen = new Set();
        const rawEntries = [];

        // 1. Fetch resumable (continue watching)
        try {
            const resumable = await apiClient.getItems(userId, {
                Filters: 'IsResumable',
                IncludeItemTypes: 'Movie,Episode',
                SortBy: 'DatePlayed',
                SortOrder: 'Descending',
                Limit: 5,
                Fields: 'Overview,Genres,CommunityRating,PremiereDate,RunTimeTicks,OfficialRating'
            });
            for (const it of (resumable.Items || [])) {
                const targetId = it.Type === 'Episode' && it.SeriesId ? it.SeriesId : it.Id;
                if (!seen.has(targetId)) {
                    seen.add(targetId);
                    rawEntries.push({ item: it, targetId });
                }
            }
        } catch (e) {
            console.warn('[NetflixHero] Resumable fetch failed', e);
        }

        // 2. Supplement with latest movies & series
        if (rawEntries.length < 5) {
            try {
                const latest = await apiClient.getItems(userId, {
                    IncludeItemTypes: 'Movie,Series',
                    SortBy: 'DateCreated',
                    SortOrder: 'Descending',
                    Limit: 6,
                    Fields: 'Overview,Genres,CommunityRating,PremiereDate,OfficialRating'
                });
                for (const it of (latest.Items || [])) {
                    if (!seen.has(it.Id)) {
                        seen.add(it.Id);
                        rawEntries.push({ item: it, targetId: it.Id });
                    }
                }
            } catch (e) {
                console.warn('[NetflixHero] Latest fetch failed', e);
            }
        }

        // 3. Enrich parent series info for episode backdrops/logos
        const enriched = [];
        for (const entry of rawEntries.slice(0, 5)) {
            let displayItem = entry.item;
            if (entry.item.Type === 'Episode' && entry.item.SeriesId) {
                try {
                    displayItem = await apiClient.getItem(userId, entry.item.SeriesId);
                } catch (err) {
                    displayItem = entry.item;
                }
            }
            enriched.push({ display: displayItem, play: entry.item });
        }

        return enriched;
    }

    function createSlideElement(entry, apiClient) {
        const { display, play } = entry;
        const slide = document.createElement('div');
        slide.className = 'netflix-hero-slide';

        // High quality backdrop URL
        let backdropUrl = '';
        const targetWidth = Math.min(window.innerWidth ? Math.round(window.innerWidth * (window.devicePixelRatio || 1)) : 1920, 2560);
        if (display.BackdropImageTags && display.BackdropImageTags.length > 0) {
            backdropUrl = apiClient.getUrl(`Items/${display.Id}/Images/Backdrop/0`, {
                maxWidth: targetWidth,
                quality: 90,
                tag: display.BackdropImageTags[0]
            });
        } else if (display.ImageTags && display.ImageTags.Primary) {
            backdropUrl = apiClient.getUrl(`Items/${display.Id}/Images/Primary`, {
                maxWidth: targetWidth,
                quality: 90,
                tag: display.ImageTags.Primary
            });
        }

        // Title Logo URL
        let logoUrl = '';
        if (display.ImageTags && display.ImageTags.Logo) {
            logoUrl = apiClient.getUrl(`Items/${display.Id}/Images/Logo`, {
                maxWidth: 600,
                tag: display.ImageTags.Logo
            });
        }

        const rating = display.CommunityRating ? Number(display.CommunityRating).toFixed(1) : null;
        const year = display.ProductionYear || (display.PremiereDate ? new Date(display.PremiereDate).getFullYear() : '');
        const officialRating = display.OfficialRating || null;
        const genres = (display.Genres || []).slice(0, 3).join(' • ');
        const overview = display.Overview || play.Overview || '';

        slide.innerHTML = `
            <div class="netflix-hero-backdrop-container">
                ${backdropUrl ? `<img class="netflix-hero-backdrop" src="${backdropUrl}" alt="${display.Name || ''}" fetchpriority="high" />` : ''}
                <div class="netflix-hero-vignette"></div>
                <div class="netflix-hero-seam"></div>
            </div>
            <div class="netflix-hero-content">
                <div class="netflix-hero-brand">
                    ${logoUrl
                        ? `<img class="netflix-hero-logo" src="${logoUrl}" alt="${display.Name || ''}" draggable="false" />`
                        : `<h1 class="netflix-hero-title">${display.Name || ''}</h1>`
                    }
                </div>
                <div class="netflix-hero-meta">
                    ${rating ? `<span class="netflix-hero-score"><span class="netflix-hero-star">★</span> ${rating}</span>` : ''}
                    ${year ? `<span class="netflix-hero-year">${year}</span>` : ''}
                    ${officialRating ? `<span class="netflix-hero-rating">${officialRating}</span>` : ''}
                    ${genres ? `<span class="netflix-hero-genres">${genres}</span>` : ''}
                </div>
                ${overview ? `<p class="netflix-hero-overview">${overview}</p>` : ''}
                <div class="netflix-hero-actions">
                    <button type="button" class="netflix-hero-btn netflix-hero-btn-play">
                        <svg viewBox="0 0 24 24" class="netflix-hero-btn-icon"><polygon points="5 3 19 12 5 21 5 3" fill="currentColor"></polygon></svg>
                        <span>${play.Type === 'Episode' || (play.UserData && play.UserData.PlaybackPositionTicks > 0) ? 'Resume' : 'Play'}</span>
                    </button>
                    <button type="button" class="netflix-hero-btn netflix-hero-btn-info">
                        <svg viewBox="0 0 24 24" class="netflix-hero-btn-icon"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle><line x1="12" y1="16" x2="12" y2="12" stroke="currentColor" stroke-width="2"></line><line x1="12" y1="8" x2="12.01" y2="8" stroke="currentColor" stroke-width="2"></line></svg>
                        <span>More info</span>
                    </button>
                </div>
            </div>
        `;

        // Handle Play Click
        const playBtn = slide.querySelector('.netflix-hero-btn-play');
        if (playBtn) {
            playBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (window.PlaybackManager) {
                    window.PlaybackManager.play({ ids: [play.Id] });
                } else {
                    window.location.hash = `#/details?id=${play.Id}&serverId=${play.ServerId || ''}`;
                }
            });
        }

        // Handle More Info Click
        const infoBtn = slide.querySelector('.netflix-hero-btn-info');
        if (infoBtn) {
            infoBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                window.location.hash = `#/details?id=${display.Id}&serverId=${display.ServerId || ''}`;
            });
        }

        return slide;
    }

    function renderHero(entries, apiClient) {
        if (!entries || !entries.length) return;
        const host = document.querySelector('#indexPage #homeTab.is-active .sections')
            || (document.querySelector('#homeTab.is-active') ? document.querySelector('#indexPage #homeTab .sections') : null);

        if (!host) return;

        // If hero already mounted on current host, don't re-create
        if (currentHeroEl && currentHeroEl.parentNode === host.parentNode && currentHeroEl.nextSibling === host) {
            alignHeroToTop();
            return;
        }

        if (currentHeroEl) {
            currentHeroEl.remove();
            currentHeroEl = null;
        }
        if (heroTimer) {
            clearInterval(heroTimer);
            heroTimer = null;
        }

        const hero = document.createElement('div');
        hero.className = 'netflix-hero';

        // Render current active slide
        currentIndex = 0;
        const slide = createSlideElement(entries[currentIndex], apiClient);
        hero.appendChild(slide);

        // Auto-rotation timer if multiple items exist (every 10 seconds, paused on hover)
        if (entries.length > 1) {
            let isHovered = false;
            hero.addEventListener('mouseenter', () => { isHovered = true; });
            hero.addEventListener('mouseleave', () => { isHovered = false; });

            heroTimer = setInterval(() => {
                if (isHovered || !isHome()) return;
                currentIndex = (currentIndex + 1) % entries.length;
                const newSlide = createSlideElement(entries[currentIndex], apiClient);
                hero.innerHTML = '';
                hero.appendChild(newSlide);
            }, 10000);
        }

        host.parentNode.insertBefore(hero, host);
        currentHeroEl = hero;

        // Immediately align hero to top of viewport
        requestAnimationFrame(alignHeroToTop);
        setTimeout(alignHeroToTop, 100);
        setTimeout(alignHeroToTop, 300);
    }

    async function initHero() {
        if (!isHome()) {
            removeHero();
            return;
        }

        if (hasMediaBar()) {
            setupMediaBarBridge();
            initNetflixSections();
            return;
        }

        const apiClient = window.ApiClient;
        if (!apiClient || !apiClient.getCurrentUserId()) {
            setTimeout(initHero, 200);
            return;
        }

        const host = document.querySelector('#indexPage #homeTab.is-active .sections')
            || (document.querySelector('#homeTab.is-active') ? document.querySelector('#indexPage #homeTab .sections') : null);

        if (!host) {
            setTimeout(initHero, 200);
            return;
        }

        if (cachedEntries.length > 0) {
            if (hasMediaBar()) {
                setupMediaBarBridge();
            } else {
                renderHero(cachedEntries, apiClient);
            }
            initNetflixSections();
            return;
        }

        if (isFetching) {
            initNetflixSections();
            return;
        }
        isFetching = true;

        try {
            cachedEntries = await fetchHeroEntries(apiClient);
            if (isHome()) {
                if (hasMediaBar()) {
                    setupMediaBarBridge();
                } else {
                    renderHero(cachedEntries, apiClient);
                }
                initNetflixSections();
            }
        } catch (e) {
            console.error('[NetflixHero] Failed to initialize hero', e);
        } finally {
            isFetching = false;
        }
    }

    // Lifecycle events
    window.addEventListener('hashchange', () => {
        setTimeout(initHero, 80);
        setTimeout(updateHeaderStyle, 100);
    });

    window.addEventListener('pageshow', () => {
        setTimeout(initHero, 80);
        setTimeout(updateHeaderStyle, 100);
    });

    document.addEventListener('viewshow', () => {
        setTimeout(initHero, 80);
        setTimeout(updateHeaderStyle, 100);
    });

    window.addEventListener('resize', () => {
        if (isHome()) {
            alignHeroToTop();
        }
        updateHeaderStyle();
    }, { passive: true });

    window.addEventListener('scroll', updateHeaderStyle, { passive: true });

    // Initial trigger
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(initHero, 150);
            setTimeout(updateHeaderStyle, 200);
        });
    } else {
        setTimeout(initHero, 150);
        setTimeout(updateHeaderStyle, 200);
    }
})();
