/**
 * AI日报 GGUF量化模型快报 — 期刊策展交互
 * 粘性目录高亮 · 阅读进度条 · 复制反馈 · 极简悬停
 */
(function() {
    'use strict';

    // --- Reading Progress Bar ---
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar';
    document.body.insertBefore(progressBar, document.body.firstChild);

    function updateProgress() {
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (docHeight <= 0) {
            progressBar.style.width = '0%';
            return;
        }
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const progress = (scrollTop / docHeight) * 100;
        progressBar.style.width = Math.min(progress, 100) + '%';
    }

    window.addEventListener('scroll', updateProgress, { passive: true });
    updateProgress();

    // --- Sticky TOC Highlight ---
    const tocLinks = document.querySelectorAll('.toc-list a');
    const modelEntries = document.querySelectorAll('.model-entry');

    if (tocLinks.length > 0 && modelEntries.length > 0) {
        const tocObserver = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    tocLinks.forEach(function(l) { l.classList.remove('active'); });
                    const id = entry.target.getAttribute('id');
                    const link = document.querySelector('.toc-list a[href="#' + id + '"]');
                    if (link) link.classList.add('active');
                }
            });
        }, {
            rootMargin: '-30% 0px -50% 0px',
            threshold: 0
        });

        modelEntries.forEach(function(entry) {
            tocObserver.observe(entry);
        });
    }

    // --- Smooth Scroll for TOC Links ---
    document.querySelectorAll('.toc-list a, .toc-nav a').forEach(function(link) {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href && href.startsWith('#')) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    // Close mobile TOC panel if open
                    const panel = document.querySelector('.toc-panel');
                    if (panel) panel.classList.remove('open');
                }
            }
        });
    });

    // --- Copy Link Feedback ---
    document.querySelectorAll('.spec-link[data-copy]').forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.getAttribute('href');
            const originalText = this.textContent;

            if (navigator.clipboard && url) {
                navigator.clipboard.writeText(url).then(function() {
                    showCopyFeedback(link, '已复制');
                }).catch(function() {
                    fallbackCopy(url, link, '已复制');
                });
            } else {
                window.open(url, '_blank');
            }
        });
    });

    function showCopyFeedback(el, text) {
        el.setAttribute('data-original', el.textContent);
        el.textContent = text;
        el.style.color = '#2D6A4F';
        setTimeout(function() {
            el.textContent = el.getAttribute('data-original');
            el.style.color = '';
        }, 2000);
    }

    function fallbackCopy(text, el, feedback) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            showCopyFeedback(el, feedback);
        } catch(e) {
            window.open(text, '_blank');
        }
        document.body.removeChild(ta);
    }

    // --- Mobile TOC Panel ---
    const tocToggleBtn = document.querySelector('.toc-toggle-btn');
    const tocPanel = document.querySelector('.toc-panel');
    const tocPanelClose = document.querySelector('.toc-panel-close');

    if (tocToggleBtn && tocPanel) {
        tocToggleBtn.addEventListener('click', function() {
            tocPanel.classList.toggle('open');
        });
    }

    if (tocPanelClose && tocPanel) {
        tocPanelClose.addEventListener('click', function() {
            tocPanel.classList.remove('open');
        });
    }

    // --- Console Welcome ---
    console.log('%c📰 AI日报 GGUF量化模型快报', 'font-size: 14px; font-weight: bold; color: #1A1A1A;');
    console.log('%c期刊策展风格 · 人文与极客交织', 'font-size: 11px; color: #8A8A8A;');

})();
