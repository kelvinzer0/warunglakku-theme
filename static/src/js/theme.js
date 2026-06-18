odoo.define('theme_warunglakku.frontend', ['web.public.widget'], function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.ThemeWarungLakku = publicWidget.Widget.extend({
        selector: '.website',
        disabledInEditableMode: false,

        start: function () {
            this._super.apply(this, arguments);
            this._initScrollEffects();
            this._initWhatsAppButton();
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
    });
});
