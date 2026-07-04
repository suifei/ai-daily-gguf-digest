/**
 * AI日报 GGUF量化模型快报 — 交互脚本
 * 提供目录切换、平滑滚动、键盘导航等功能
 */

(function() {
    'use strict';

    // --- TOC Sidebar Toggle ---
    const tocSidebar = document.getElementById('tocSidebar');
    const tocOverlay = document.getElementById('tocOverlay');

    window.toggleTOC = function() {
        const isOpen = tocSidebar.classList.contains('open');
        if (isOpen) {
            closeTOC();
        } else {
            openTOC();
        }
    };

    function openTOC() {
        tocSidebar.classList.add('open');
        if (tocOverlay) tocOverlay.classList.add('visible');
        document.body.style.overflow = 'hidden';
    }

    function closeTOC() {
        tocSidebar.classList.remove('open');
        if (tocOverlay) tocOverlay.classList.remove('visible');
        document.body.style.overflow = '';
    }

    // Close TOC on Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeTOC();
    });

    // --- Page Scroll Navigation ---
    window.scrollPage = function(direction) {
        const content = document.querySelector('.magazine-content');
        if (!content) return;
        
        const models = content.querySelectorAll('.model-page');
        if (models.length === 0) return;

        // Find current visible model
        const scrollTop = window.scrollY;
        const windowHeight = window.innerHeight;
        let currentIndex = 0;

        for (let i = 0; i < models.length; i++) {
            const rect = models[i].getBoundingClientRect();
            if (rect.top <= windowHeight / 2) {
                currentIndex = i;
            }
        }

        // Navigate to next/previous
        let targetIndex = currentIndex + direction;
        targetIndex = Math.max(0, Math.min(models.length - 1, targetIndex));

        models[targetIndex].scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    };

    // --- Keyboard Navigation ---
    document.addEventListener('keydown', function(e) {
        // Left arrow / Space: previous
        if (e.key === 'ArrowLeft' || e.key === ' ') {
            e.preventDefault();
            scrollPage(-1);
        }
        // Right arrow: next
        if (e.key === 'ArrowRight') {
            e.preventDefault();
            scrollPage(1);
        }
        // H: toggle TOC
        if (e.key === 'h' || e.key === 'H') {
            toggleTOC();
        }
    });

    // --- Smooth scroll for TOC links ---
    document.querySelectorAll('.toc-link').forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const target = document.getElementById(targetId);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                closeTOC();
            }
        });
    });

    // --- Intersection Observer for active TOC highlight ---
    if ('IntersectionObserver' in window) {
        const models = document.querySelectorAll('.model-page');
        const tocLinks = document.querySelectorAll('.toc-link');

        const observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    tocLinks.forEach(function(link) {
                        link.style.color = '';
                        link.style.background = '';
                        if (link.getAttribute('href') === '#' + id) {
                            link.style.color = '#6c63ff';
                            link.style.background = 'rgba(108,99,255,0.1)';
                        }
                    });
                }
            });
        }, {
            rootMargin: '-20% 0px -60% 0px',
            threshold: 0
        });

        models.forEach(function(model) {
            observer.observe(model);
        });
    }

    // --- Reading Progress Bar ---
    const progressBar = document.createElement('div');
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        height: 3px;
        background: linear-gradient(90deg, #6c63ff, #ff6584);
        z-index: 9999;
        transition: width 0.1s ease;
        width: 0%;
    `;
    document.body.appendChild(progressBar);

    window.addEventListener('scroll', function() {
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
        progressBar.style.width = progress + '%';
    });

    // --- Animate model cards on scroll ---
    if ('IntersectionObserver' in window) {
        const cards = document.querySelectorAll('.model-page');
        cards.forEach(function(card, index) {
            card.style.opacity = '0';
            card.style.transform = 'translateY(30px)';
            card.style.transition = `opacity 0.6s ease ${index * 0.05}s, transform 0.6s ease ${index * 0.05}s`;
        });

        const cardObserver = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                    cardObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        cards.forEach(function(card) {
            cardObserver.observe(card);
        });
    }

    // --- Console welcome message ---
    console.log('%c📰 AI日报 GGUF量化模型快报', 'font-size: 20px; font-weight: bold; color: #6c63ff;');
    console.log('%cKeyboard shortcuts: ←/→ navigate, H toggle TOC, Esc close', 'color: #9898b0;');

})();
