/**
 * Warung Lakku Theme - JavaScript
 * Handles theme interactions and custom behavior
 */
odoo.define('theme_warunglakku.frontend', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    /**
     * Warung Lakku Theme Widget
     * Initializes theme-specific frontend behavior
     */
    publicWidget.registry.ThemeWarungLakku = publicWidget.Widget.extend({
        selector: '.website',
        disabledInEditableMode: false,

        /**
         * @override
         */
        start: function () {
            this._super.apply(this, arguments);
            this._initScrollEffects();
            this._initWhatsAppButton();
        },

        /**
         * Initialize scroll-based effects
         * - Add shadow to header on scroll
         * - Reveal animations for sections
         */
        _initScrollEffects: function () {
            var self = this;
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

            // Reveal animations
            var reveals = document.querySelectorAll('.s_features .col-lg-4, .s_product_list .col-lg-2');
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
                    el.style.transition = 'all 0.5s ease';
                    observer.observe(el);
                });
            }
        },

        /**
         * Initialize WhatsApp floating button behavior
         */
        _initWhatsAppButton: function () {
            var waBtn = document.querySelector('.wa-float-btn');
            if (waBtn) {
                // Add pulse animation after 3 seconds
                setTimeout(function () {
                    waBtn.classList.add('wl-pulse');
                }, 3000);
            }
        },
    });
});
