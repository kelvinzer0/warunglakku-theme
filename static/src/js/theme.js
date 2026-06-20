odoo.define('theme_warunglakku.frontend', ['web.public.widget'], function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.ThemeWarungLakku = publicWidget.Widget.extend({
        // #wrapwrap is Odoo 17's main frontend page wrapper. It is
        // always present on /shop and other website pages. (Older
        // themes used `.website` but that class is not always added
        // in Odoo 17, so the widget would never instantiate.)
        selector: '#wrapwrap',
        disabledInEditableMode: false,

        start: function () {
            this._super.apply(this, arguments);
            this._initScrollEffects();
            this._initWhatsAppButton();
            this._initOperatingHoursLiveStatus();
        },

        _initScrollEffects: function () {
            var header = document.querySelector('.o_main_navbar');

            if (header) {
                window.addEventListener('scroll', function () {
                    if (window.scrollY > 50) {
                        header.classList.add('wl-header-scrolled');
                    } else {
                        header.classList.remove('wl-header-scrolled');
                    }
                }, { passive: true });
            }

            var reveals = document.querySelectorAll('.wl-menu-card, .o_wsale_product_item');
            if (reveals.length && 'IntersectionObserver' in window) {
                var observer = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            entry.target.style.opacity = '1';
                            entry.target.style.transform = 'translateY(0)';
                            observer.unobserve(entry.target);
                        }
                    });
                }, { threshold: 0.1 });

                reveals.forEach(function (el) {
                    el.style.opacity = '0';
                    el.style.transform = 'translateY(20px)';
                    el.style.transition = 'all 0.4s ease';
                    observer.observe(el);
                });
            }
        },

        _initWhatsAppButton: function () {
            var waBtn = document.querySelector('.wa-float-btn');
            if (waBtn) {
                setTimeout(function () {
                    waBtn.classList.add('wl-pulse');
                }, 3000);
            }
        },

        /**
         * Re-evaluate the operating hours widget status every 30 seconds
         * on the client side. This corrects stale server-rendered HTML
         * (Odoo caches /shop) so the widget always reflects the current
         * time, not the time the page was rendered.
         *
         * Also adds an intermediate "Akan Tutup" (Closing Soon) state
         * shown for the last 30 minutes before close_time, giving
         * customers a clear visual warning that the store is about to
         * close.
         *
         * Reads data attributes on .wl_oh_card and .wl_oh_mobile:
         *   data-today-mode  = 'specific_hours' | 'open_24_hours' | 'closed' | 'appointment_only'
         *   data-today-open  = minutes-from-midnight (e.g. '720' for 12:00)
         *   data-today-close = minutes-from-midnight (e.g. '1200' for 20:00)
         *
         * Updates on .wl_oh_status and .wl_oh_mobile_status:
         *   data-state = 'open' | 'closing_soon' | 'closed'
         *   data-open  = 'true' | 'false'
         *   text content of .wl_oh_status_text
         */
        _initOperatingHoursLiveStatus: function () {
            // Jakarta timezone offset in minutes (UTC+7 = 420 min).
            // We hardcode this because the business hours data is
            // always in Jakarta time (cached from Evolution API which
            // returns WhatsApp Business hours in the business's tz).
            var JAKARTA_OFFSET_MIN = 7 * 60;

            function nowMinutesInJakarta() {
                // Get current UTC time in minutes, then shift to Jakarta.
                var now = new Date();
                // now.getUTCHours()/getUTCMinutes() give UTC time.
                var utcMin = now.getUTCHours() * 60 + now.getUTCMinutes();
                var jakartaMin = utcMin + JAKARTA_OFFSET_MIN;
                // Wrap around midnight (0-1439 range).
                jakartaMin = ((jakartaMin % 1440) + 1440) % 1440;
                return jakartaMin;
            }

            function computeState(mode, openStr, closeStr) {
                // Returns one of: 'open', 'closing_soon', 'closed'
                if (mode === 'open_24_hours') {
                    return 'open';
                }
                if (mode === 'specific_hours') {
                    var openMin = parseInt(openStr, 10);
                    var closeMin = parseInt(closeStr, 10);
                    if (isNaN(openMin) || isNaN(closeMin)) {
                        return 'closed';
                    }
                    var now = nowMinutesInJakarta();
                    if (now < openMin || now >= closeMin) {
                        return 'closed';
                    }
                    // Closing soon if within 30 minutes of close.
                    if (closeMin - now <= 30) {
                        return 'closing_soon';
                    }
                    return 'open';
                }
                // closed, appointment_only, or unknown
                return 'closed';
            }

            var STATE_TEXT = {
                'open': 'Buka Sekarang',
                'closing_soon': 'Akan Tutup',
                'closed': 'Tutup',
            };

            function updateWidget(widgetEl) {
                if (!widgetEl) { return; }
                var mode = widgetEl.getAttribute('data-today-mode') || 'closed';
                var openStr = widgetEl.getAttribute('data-today-open') || '';
                var closeStr = widgetEl.getAttribute('data-today-close') || '';
                var state = computeState(mode, openStr, closeStr);

                // Update status elements (sidebar + mobile use the same
                // .wl_oh_status / .wl_oh_mobile_status classes).
                var statusEls = widgetEl.querySelectorAll('.wl_oh_status, .wl_oh_mobile_status');
                statusEls.forEach(function (statusEl) {
                    var prev = statusEl.getAttribute('data-state');
                    if (prev === state) { return; } // no change, skip DOM writes
                    statusEl.setAttribute('data-state', state);
                    statusEl.setAttribute('data-open', state === 'open' ? 'true' : 'false');
                    var textEl = statusEl.querySelector('.wl_oh_status_text');
                    if (textEl) {
                        textEl.textContent = STATE_TEXT[state] || 'Tutup';
                    }
                });

                // Update the parent details[data-open] for mobile accordion
                // (so the summary chevron color also matches).
                if (widgetEl.classList.contains('wl_oh_mobile')) {
                    widgetEl.setAttribute('data-open', state === 'open' ? 'true' : 'false');
                }
            }

            function updateAll() {
                var widgets = document.querySelectorAll('.wl_oh_card, .wl_oh_mobile');
                widgets.forEach(updateWidget);
            }

            // Initial update on load (after small delay to ensure DOM is ready).
            setTimeout(updateAll, 200);

            // Re-evaluate every 30 seconds. This is cheap (no network,
            // just DOM attribute reads/writes when state changes).
            setInterval(updateAll, 30000);

            // Also re-evaluate when tab becomes visible again
            // (user might have been on another tab for an hour).
            document.addEventListener('visibilitychange', function () {
                if (!document.hidden) {
                    updateAll();
                }
            });
        },
    });
});
