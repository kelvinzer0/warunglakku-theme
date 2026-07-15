/** @odoo-module **/

/*
 * Warung Lakku - Add to Cart via Form Submit Interception
 * =================================================================
 *
 * STRATEGY: Bind to the form's `submit` event (NOT button click).
 * When the form is about to submit (via button click, Enter key, etc.),
 * intercept the event, prevent the default synchronous form POST, and
 * instead send an AJAX request to /shop/cart/update_json.
 *
 * Why form submit (not click)?
 *   - More reliable: works for keyboard submit, programmatic submit, etc.
 *   - Don't need to fight Odoo's click handlers (we intercept LATER in
 *     the event chain, at form level).
 *   - Don't need to neutralize buttons (no class removal, no type change).
 *   - Survives DOM re-renders (event delegation on document).
 *
 * Implementation:
 *   - Use jQuery event delegation: $(document).on('submit', 'form[action*="/shop/cart/update"]', handler)
 *   - This catches ALL add-to-cart forms (detail page + listing cards)
 *   - Use native fetch() for JSON-RPC (no Odoo dependency)
 *   - Manual toast (no Bootstrap JS dependency)
 *
 * Author: Kelvin Yuli Andrian
 * Since: v17.0.3.10.56 (replaces v3.10.48-v3.10.55 AJAX widget approach)
 */

import publicWidget from "@web/legacy/js/public/public_widget";

const WL_CART_SUBMIT = publicWidget.Widget.extend({
    selector: "#wrapwrap",

    start: function () {
        this._super.apply(this, arguments);
        // Bind to form submit via event delegation on document.
        // Using document (not this.$el) so we catch ALL forms including
        // ones added dynamically after widget start.
        // Namespace .wl_cart for clean unbind on destroy.
        $(document).on(
            "submit.wl_cart",
            'form[action*="/shop/cart/update"]',
            this._onFormSubmit.bind(this)
        );
    },

    destroy: function () {
        // Clean up binding when widget destroyed
        $(document).off(".wl_cart");
        this._super.apply(this, arguments);
    },

    /**
     * Intercept form submit. Send AJAX instead of synchronous POST.
     */
    _onFormSubmit: function (ev) {
        // Only intercept on /shop and /shop/<slug> pages
        const path = window.location.pathname;
        const isShopListing = path === "/shop" || path.startsWith("/shop?");
        const isProductDetail = /^\/shop\/[^/]+$/.test(path);
        if (!isShopListing && !isProductDetail) {
            return; // Let Odoo's default behavior (e.g. on /shop/cart)
        }

        ev.preventDefault();
        ev.stopImmediatePropagation();

        const $form = $(ev.target);
        const productId = parseInt($form.find('input[name="product_id"]').val(), 10);
        const addQty =
            parseInt($form.find('input[name="add_qty"]').val(), 10) || 1;

        // Find the submit button (the one that was clicked, or first submit)
        const $btn = $form.find('button[type="submit"], input[type="submit"]').first();
        const isListing = $btn.hasClass("wl_card_add_to_cart_btn");

        this._addToCart($btn, productId, addQty, isListing);
    },

    /**
     * POST to /shop/cart/update_json via native fetch().
     * Uses JSON-RPC 2.0 envelope (Odoo's json route format).
     */
    _addToCart: function ($btn, productId, addQty, isListing) {
        if (!productId || productId < 1) {
            this._showToast("Produk tidak valid", "danger");
            return;
        }

        const originalHtml = $btn.html();

        // Loading state
        if (isListing) {
            $btn.html('<i class="fa fa-spinner fa-spin"></i>')
                .addClass("disabled")
                .css("pointer-events", "none");
        } else {
            $btn.html('<i class="fa fa-spinner fa-spin me-2"></i>Menambahkan...')
                .addClass("disabled")
                .css("pointer-events", "none");
        }

        // Build JSON-RPC envelope
        const body = JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: {
                product_id: productId,
                add_qty: addQty,
                display: false,
            },
            id: Date.now(),
        });

        fetch("/shop/cart/update_json", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            body: body,
            credentials: "same-origin",
        })
            .then((resp) => {
                if (!resp.ok) {
                    throw new Error(`HTTP ${resp.status} ${resp.statusText}`);
                }
                return resp.json();
            })
            .then((data) => {
                if (data.error) {
                    throw new Error(
                        data.error.message || JSON.stringify(data.error)
                    );
                }
                const result = data.result || {};

                // Update cart counter in navbar
                this._updateCartCounter(result, addQty);

                // Show success toast
                this._showToast(
                    `Berhasil ditambahkan ke keranjang (${addQty}x)`,
                    "success"
                );

                // Brief success state on button
                if (isListing) {
                    $btn.html('<i class="fa fa-check"></i>');
                } else {
                    $btn.html('<i class="fa fa-check me-2"></i>Ditambahkan!');
                }
                setTimeout(() => {
                    $btn.html(originalHtml)
                        .removeClass("disabled")
                        .css("pointer-events", "");
                }, 1200);
            })
            .catch((err) => {
                console.error("[WL Cart] Failed:", err);
                const msg =
                    err && err.message
                        ? err.message
                        : "Gagal menambahkan ke keranjang. Silakan coba lagi.";
                this._showToast(msg, "danger");
                $btn.html(originalHtml)
                    .removeClass("disabled")
                    .css("pointer-events", "");
            });
    },

    /**
     * Update navbar cart counter with pulse animation.
     */
    _updateCartCounter: function (data, addedQty) {
        const $counter = $(".my_cart_quantity");
        if (!data || data.cart_quantity === undefined) {
            // Cart was empty before — fallback to incrementing current value
            const current = parseInt($counter.text(), 10) || 0;
            $counter.text(current + addedQty);
        } else {
            $counter.text(data.cart_quantity);
        }
        $counter.removeClass("d-none");

        // Brief pulse animation to draw attention
        $counter.stop(true, true).animate(
            { scale: 1.4 },
            150,
            function () {
                $(this).animate({ scale: 1 }, 150);
            }
        );
    },

    /**
     * Show toast notification matching Odoo's native design system.
     * Mirrors o_notification_fade structure + CSS from website_sale
     * add_to_cart_notification.js so our toast looks consistent with
     * the native one shown on product detail page.
     *
     * Spec (from Odoo 17 native toast via agent-browser audit):
     *   - Container: .o_notification_manager (position-fixed, top-right)
     *   - Toast: white bg, border 1px solid rgba(0,0,0,.1), radius 6.4px,
     *            shadow 0 4px 16px rgba(0,0,0,.12), width 350px
     *   - Header: bg rgba(255,255,255,.85), border-bottom, padding 8px 12px
     *   - Body: bg rgba(255,255,255,.93), padding 12px
     *   - Font: Inter, -apple-system, sans-serif
     *   - CTA button: btn btn-primary w-100
     */
    _showToast: function (message, type) {
        type = type || "success";

        // Use Odoo's native notification container if it exists,
        // otherwise create our own with same class name.
        let $container = $(".o_notification_manager").first();
        if (!$container.length) {
            $container = $(
                '<div class="o_notification_manager position-fixed top-0 end-0 p-3" ' +
                    'style="z-index: 1080; width: 350px;"></div>'
            ).appendTo("body");
        }

        // Color scheme by type (matching Odoo's o_cc1/o_cc2 etc.)
        const colorMap = {
            success: { bg: "#ffffff", border: "rgba(0,0,0,.1)", icon: "fa-check-circle", iconColor: "#198754" },
            danger: { bg: "#ffffff", border: "rgba(220,53,69,.3)", icon: "fa-exclamation-circle", iconColor: "#dc3545" },
            info: { bg: "#ffffff", border: "rgba(13,202,240,.3)", icon: "fa-info-circle", iconColor: "#0dcaf0" },
        };
        const c = colorMap[type] || colorMap.success;

        // Build toast HTML matching Odoo native structure
        const $toast = $(
            '<div role="alert" aria-live="assertive" aria-atomic="true" ' +
                'class="toast o_cc1 position-relative start-0 mt-2 o_notification_fade" ' +
                'style="background-color: ' + c.bg + "; " +
                "border: 1px solid " + c.border + "; " +
                "border-radius: 6.4px; " +
                "box-shadow: 0 4px 16px rgba(0,0,0,.12); " +
                "max-width: 350px; width: 100%; " +
                'font-family: Inter, -apple-system, sans-serif;">' +
                '<div class="toast-header justify-content-between" ' +
                'style="background-color: rgba(255,255,255,.85); ' +
                "border-bottom: 1px solid rgba(0,0,0,.05); " +
                'padding: 8px 12px;">' +
                "<strong style=\"font-size: .9rem; color: #212529;\">" +
                '<i class="fa ' + c.icon + ' me-2" style="color: ' + c.iconColor + ';"></i>' +
                "Warung Lakku</strong>" +
                '<button type="button" class="btn-close" aria-label="Tutup" ' +
                'style="filter: none; opacity: .5;"></button>' +
                "</div>" +
                '<div class="toast-body" style="padding: 12px; color: #212529;">' +
                "<div>" + message + "</div>" +
                '<a role="button" class="w-100 btn btn-primary mt-2" href="/shop/cart" ' +
                'style="border-radius: 4px;"> Lihat keranjang </a>' +
                "</div>" +
                "</div>"
        ).appendTo($container);

        // Manual show + autohide (no Bootstrap JS dependency)
        // Match Odoo's fade-in animation
        $toast.addClass("show o_notification_fade-enter-active");
        const hideTimer = setTimeout(() => {
            $toast.removeClass("show");
            $toast.addClass("o_notification_fade-leave-active");
            setTimeout(() => $toast.remove(), 300);
        }, 4000);

        // Manual close button
        $toast.find(".btn-close").on("click", function () {
            clearTimeout(hideTimer);
            $toast.removeClass("show");
            $toast.addClass("o_notification_fade-leave-active");
            setTimeout(() => $toast.remove(), 300);
        });
    },
});

publicWidget.registry.WLCartSubmit = WL_CART_SUBMIT;

export default WL_CART_SUBMIT;
