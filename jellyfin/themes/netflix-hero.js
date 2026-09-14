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
        const hash = window.location.hash;
        return hash === '' || hash === '#/' || hash === '#/home' || hash === '#/home?tab=0';
    }

    function alignHeroToTop() {
        if (!currentHeroEl) return;
        
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
        currentHeroEl.style.setProperty('margin-top', '0px', 'important');

        // Make header transparent
        updateHeaderStyle();
    }

    function updateHeaderStyle() {
        const headers = document.querySelectorAll('header.MuiAppBar-root, header, .skinHeader');
        if (!headers.length) return;

        if (!isHome()) {
            headers.forEach(h => {
                h.style.removeProperty('background');
                h.style.removeProperty('background-color');
                h.style.removeProperty('backdrop-filter');
                h.style.removeProperty('-webkit-backdrop-filter');
                h.style.removeProperty('box-shadow');
                h.style.removeProperty('border');
            });
            return;
        }

        const isScrolled = window.scrollY > 40;
        headers.forEach(h => {
            if (isScrolled) {
                h.style.setProperty('background', 'rgba(16, 16, 16, 0.92)', 'important');
                h.style.setProperty('backdrop-filter', 'blur(16px)', 'important');
                h.style.setProperty('-webkit-backdrop-filter', 'blur(16px)', 'important');
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
        const headers = document.querySelectorAll('header.MuiAppBar-root, header, .skinHeader');
        headers.forEach(h => {
            h.style.removeProperty('background');
            h.style.removeProperty('background-color');
            h.style.removeProperty('backdrop-filter');
            h.style.removeProperty('-webkit-backdrop-filter');
            h.style.removeProperty('box-shadow');
            h.style.removeProperty('border');
        });
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
            renderHero(cachedEntries, apiClient);
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
                renderHero(cachedEntries, apiClient);
                initNetflixSections();
            }
        } catch (e) {
            console.error('[NetflixHero] Failed to initialize hero', e);
        } finally {
            isFetching = false;
        }
    }

    let isUpdatingSections = false;
    let sectionDebounceTimer = null;

    function scheduleNetflixSections(delay = 150) {
        if (sectionDebounceTimer) clearTimeout(sectionDebounceTimer);
        sectionDebounceTimer = setTimeout(() => {
            initNetflixSections();
        }, delay);
    }

    /**
     * Netflix Content Sections Controller
     * - Personalizes Continue Watching title with user's name
     * - Injects and syncs Netflix pagination indicator dashes on row headers
     * - Controls slider scroll buttons with smooth sliding
     */
    function initNetflixSections() {
        if (!isHome() || isUpdatingSections) return;
        isUpdatingSections = true;

        try {
            // 1. Personalize Continue Watching title (only if not already done)
            const cwSection = document.querySelector('#homeTab .ContinueWatchingNextUp');
            const cwTitle = cwSection ? cwSection.querySelector('h2.sectionTitle') : null;
            if (cwTitle && cwTitle.textContent.includes('Continue Watching') && !cwTitle.textContent.startsWith('Continue Watching for')) {
                const rawName = window.ApiClient?.getCurrentUser()?.Name || 'Roshana';
                const displayName = rawName.replace(/^mk/i, '').replace(/^[a-z]/, c => c.toUpperCase()) || 'Roshana';
                cwTitle.textContent = 'Continue Watching for ' + displayName;
            }

            // Clean episode names in Continue Watching to show clean Show Name like Netflix
            if (cwSection) {
                const cwCards = cwSection.querySelectorAll('.card');
                cwCards.forEach(card => {
                    const a = card.querySelector('.cardText-first a');
                    if (a && a.textContent.includes(' - S')) {
                        if (!a.getAttribute('data-full-title')) {
                            a.setAttribute('data-full-title', a.textContent);
                        }
                        a.textContent = a.textContent.split(/ - S\d+/i)[0].trim();
                    }
                });
            }

            // 2. Set up dynamic pagination indicator dashes & slider buttons for each scroller
            const sections = document.querySelectorAll('#homeTab .verticalSection.emby-scroller-container');
            sections.forEach(sec => {
                const titleContainer = sec.querySelector('.sectionTitleContainer');
                const scroller = sec.querySelector('.emby-scroller');
                if (!titleContainer || !scroller) return;

                let indContainer = titleContainer.querySelector('.netflix-indicators');
                if (!indContainer) {
                    indContainer = document.createElement('div');
                    indContainer.className = 'netflix-indicators';
                    titleContainer.appendChild(indContainer);
                }

                function updateIndicators() {
                    const scrollLeft = scroller.scrollLeft;
                    const maxScroll = scroller.scrollWidth - scroller.clientWidth;
                    if (maxScroll <= 10) {
                        if (indContainer.children.length > 0) indContainer.innerHTML = '';
                        return;
                    }

                    const totalPages = Math.max(2, Math.min(6, Math.ceil(scroller.scrollWidth / scroller.clientWidth) + 1));
                    const currentPage = Math.min(totalPages - 1, Math.round((scrollLeft / maxScroll) * (totalPages - 1)));

                    if (indContainer.children.length !== totalPages) {
                        indContainer.innerHTML = '';
                        for (let i = 0; i < totalPages; i++) {
                            const dash = document.createElement('span');
                            dash.className = 'netflix-indicator-dash' + (i === currentPage ? ' active' : '');
                            dash.title = 'Page ' + (i + 1);
                            dash.onclick = (e) => {
                                e.stopPropagation();
                                scroller.scrollTo({
                                    left: (maxScroll / (totalPages - 1)) * i,
                                    behavior: 'smooth'
                                });
                            };
                            indContainer.appendChild(dash);
                        }
                    } else {
                        Array.from(indContainer.children).forEach((dash, idx) => {
                            dash.classList.toggle('active', idx === currentPage);
                        });
                    }
                }

                if (!scroller._netflixScrollBound) {
                    scroller._netflixScrollBound = true;
                    scroller.addEventListener('scroll', updateIndicators, { passive: true });
                }
                updateIndicators();

                // Wire up left and right scroll buttons to smooth scroll by 85% of visible width
                const leftBtn = sec.querySelector('.emby-scrollbuttons-button[data-direction="left"]');
                const rightBtn = sec.querySelector('.emby-scrollbuttons-button[data-direction="right"]');
                if (leftBtn && !leftBtn._netflixClickBound) {
                    leftBtn._netflixClickBound = true;
                    leftBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const step = scroller.clientWidth * 0.85;
                        scroller.scrollBy({ left: -step, behavior: 'smooth' });
                    });
                }
                if (rightBtn && !rightBtn._netflixClickBound) {
                    rightBtn._netflixClickBound = true;
                    rightBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const step = scroller.clientWidth * 0.85;
                        scroller.scrollBy({ left: step, behavior: 'smooth' });
                    });
                }
            });
        } finally {
            setTimeout(() => {
                isUpdatingSections = false;
            }, 50);
        }
    }

    // MutationObserver to catch dynamically rendered sections without recursive loop
    let sectionObserver = null;
    function observeSections() {
        if (sectionObserver) return;
        const target = document.getElementById('indexPage') || document.body;
        sectionObserver = new MutationObserver((mutations) => {
            if (!isHome() || isUpdatingSections) return;
            const isSelfMutation = mutations.every(m => {
                const t = m.target;
                return t && (t.classList?.contains('netflix-indicators') ||
                             t.classList?.contains('netflix-indicator-dash') ||
                             t.parentElement?.classList?.contains('netflix-indicators'));
            });
            if (!isSelfMutation) {
                scheduleNetflixSections(200);
            }
        });
        sectionObserver.observe(target, { childList: true, subtree: true });
    }

    // Lifecycle events
    window.addEventListener('hashchange', () => {
        setTimeout(initHero, 80);
        setTimeout(initNetflixSections, 150);
        setTimeout(initNetflixSections, 600);
    });

    window.addEventListener('pageshow', () => {
        setTimeout(initHero, 80);
        setTimeout(initNetflixSections, 150);
        setTimeout(initNetflixSections, 600);
    });

    document.addEventListener('viewshow', () => {
        setTimeout(initHero, 80);
        setTimeout(initNetflixSections, 150);
        setTimeout(initNetflixSections, 600);
    });

    window.addEventListener('resize', () => {
        if (isHome()) {
            alignHeroToTop();
            initNetflixSections();
        }
    }, { passive: true });

    window.addEventListener('scroll', updateHeaderStyle, { passive: true });

    // Initial trigger
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(initHero, 150);
            setTimeout(initNetflixSections, 300);
            setTimeout(observeSections, 500);
        });
    } else {
        setTimeout(initHero, 150);
        setTimeout(initNetflixSections, 300);
        setTimeout(observeSections, 500);
    }
})();
