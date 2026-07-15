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
    selector: "body",

    start: function () {
        this._super.apply(this, arguments);
        // Bind to form submit via event delegation.
        // This catches ALL forms posting to /shop/cart/update (both
        // product detail page and listing page product cards).
        // Use namespace to avoid duplicate bindings if widget restarts.
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
     * Show toast notification at top-right.
     * Uses manual show/hide (no Bootstrap JS dependency).
     */
    _showToast: function (message, type) {
        type = type || "success";
        const icon =
            type === "success"
                ? "fa-check-circle"
                : type === "danger"
                ? "fa-exclamation-circle"
                : "fa-info-circle";

        let $container = $("#wl-toast-container");
        if (!$container.length) {
            $container = $(
                '<div id="wl-toast-container" ' +
                    'class="toast-container position-fixed top-0 end-0 p-3" ' +
                    'style="z-index: 1080;"></div>'
            ).appendTo("body");
            // Inject minimal toast CSS once (Bootstrap CSS toast rules may
            // not be in the frontend lazy bundle).
            if (!$("#wl-toast-css").length) {
                $("<style id='wl-toast-css'>").html(
                    ".toast{background:rgba(255,255,255,.95);border-radius:.375rem;" +
                    "box-shadow:0 .5rem 1rem rgba(0,0,0,.15);max-width:350px;" +
                    "opacity:0;transition:opacity .3s ease;overflow:hidden}" +
                    ".toast.show{opacity:1}" +
                    ".text-bg-success{background-color:#198754!important;color:#fff!important}" +
                    ".text-bg-danger{background-color:#dc3545!important;color:#fff!important}" +
                    ".text-bg-info{background-color:#0dcaf0!important;color:#000!important}" +
                    ".toast-body{padding:.75rem 1rem;font-size:.95rem}" +
                    ".btn-close{filter:invert(1) grayscale(100%) brightness(200%);" +
                    "background:transparent;border:0;padding:.5rem;cursor:pointer}"
                ).appendTo("head");
            }
        }

        const $toast = $(
            '<div class="toast align-items-center text-bg-' +
                type +
                ' border-0" role="alert" ' +
                'aria-live="assertive" aria-atomic="true">' +
                '<div class="d-flex">' +
                '<div class="toast-body">' +
                '<i class="fa ' +
                icon +
                ' me-2"></i>' +
                message +
                "</div>" +
                '<button type="button" class="btn-close btn-close-white me-2 m-auto" ' +
                'aria-label="Close"></button>' +
                "</div>" +
                "</div>"
        ).appendTo($container);

        // Manual show + autohide (no Bootstrap JS dependency)
        $toast.addClass("show");
        const hideTimer = setTimeout(() => {
            $toast.removeClass("show");
            setTimeout(() => $toast.remove(), 300);
        }, 3500);

        // Manual close button
        $toast.find(".btn-close").on("click", function () {
            clearTimeout(hideTimer);
            $toast.removeClass("show");
            setTimeout(() => $toast.remove(), 300);
        });
    },
});

publicWidget.registry.WLCartSubmit = WL_CART_SUBMIT;

export default WL_CART_SUBMIT;
