/** @odoo-module **/

/*
 * Warung Lakku - AJAX Add to Cart (Product Detail + Listing)
 * =================================================================
 *
 * Intercepts Add-to-Cart click on both:
 *   1. Product detail page (/shop/<slug>) — selector: #add_to_cart
 *   2. Product listing page (/shop) — selector: .wl_card_add_to_cart_btn
 *
 * Both POST to /shop/cart/update_json (JSON-RPC) instead of submitting
 * the form synchronously. After AJAX success:
 *   1. Update cart counter in navbar (.my_cart_quantity) with pulse
 *   2. Show Bootstrap 5 toast "Berhasil ditambahkan ke keranjang"
 *   3. Customer stays on the same page (no redirect to /shop/cart)
 *
 * Route: /shop/cart/update_json
 *   - Type: json (JSON-RPC, csrf=False)
 *   - Args: product_id (int), add_qty (int), display (bool)
 *   - Returns: { line_id, cart_quantity, minor_amount, notification_info }
 *
 * Author: Kelvin Yuli Andrian
 * Since: v17.0.3.10.48 (detail page only)
 * Updated: v17.0.3.10.49 (added listing page support)
 */

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonRpc } from "@web/core/network/rpc";

const WL_AJAX_ADD_TO_CART = publicWidget.Widget.extend({
    selector: "body",
    events: {
        "click #add_to_cart": "_onAddToCartClickDetail",
        "click .wl_card_add_to_cart_btn": "_onAddToCartClickListing",
    },

    // ============================================================
    // PRODUCT DETAIL PAGE (/shop/<slug>)
    // ============================================================
    _onAddToCartClickDetail: function (ev) {
        const path = window.location.pathname;
        // Only intercept on product detail page (NOT /shop, /shop/cart, etc.)
        if (!/^\/shop\/[^/]+$/.test(path)) {
            return;
        }

        ev.preventDefault();
        ev.stopImmediatePropagation();

        const $btn = $(ev.currentTarget);
        const $form = $btn.closest("form");
        const productId = parseInt($form.find('input[name="product_id"]').val(), 10);
        const addQty = parseInt($form.find('input[name="add_qty"]').val(), 10) || 1;

        this._addToCart($btn, productId, addQty);
    },

    // ============================================================
    // PRODUCT LISTING PAGE (/shop)
    // ============================================================
    _onAddToCartClickListing: function (ev) {
        // Only intercept on /shop listing page (NOT on detail, cart, etc.)
        const path = window.location.pathname;
        if (path !== "/shop" && !path.startsWith("/shop?")) {
            return;
        }

        ev.preventDefault();
        ev.stopImmediatePropagation();

        const $btn = $(ev.currentTarget);
        const $form = $btn.closest("form");
        // On listing, product_id is injected by theme's shop_add_to_cart.xml
        // via <input type="hidden" name="product_id" t-att-value="product.product_variant_id.id"/>
        const productId = parseInt($form.find('input[name="product_id"]').val(), 10);

        // Listing always adds 1 (no qty input on cards)
        this._addToCart($btn, productId, 1);
    },

    // ============================================================
    // COMMON: call /shop/cart/update_json
    // ============================================================
    _addToCart: function ($btn, productId, addQty) {
        if (!productId || productId < 1) {
            this._showToast("Produk tidak valid", "danger");
            return;
        }

        const originalHtml = $btn.html();
        const isListing = $btn.hasClass("wl_card_add_to_cart_btn");

        // Loading state (different style for listing button)
        if (isListing) {
            $btn.html('<i class="fa fa-spinner fa-spin"></i>')
                .addClass("disabled")
                .css("pointer-events", "none");
        } else {
            $btn.html('<i class="fa fa-spinner fa-spin me-2"></i>Menambahkan...')
                .addClass("disabled")
                .css("pointer-events", "none");
        }

        jsonRpc("/shop/cart/update_json", "call", {
            product_id: productId,
            add_qty: addQty,
            display: false,
        }).then((data) => {
            this._updateCartCounter(data, addQty);

            this._showToast(
                `Berhasil ditambahkan ke keranjang (${addQty}x)`,
                "success"
            );

            // Brief success state
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
        }).catch((err) => {
            console.error("[WL AjaxAddToCart] Failed:", err);
            const msg =
                err && err.data && err.data.message
                    ? err.data.message
                    : "Gagal menambahkan ke keranjang. Silakan coba lagi.";
            this._showToast(msg, "danger");
            $btn.html(originalHtml)
                .removeClass("disabled")
                .css("pointer-events", "");
        });
    },

    /**
     * Update the cart quantity counter in the navbar.
     * On the very first add (cart was empty), endpoint returns {} —
     * fallback to incrementing the current counter.
     */
    _updateCartCounter: function (data, addedQty) {
        const $counter = $(".my_cart_quantity");
        if (!data || data.cart_quantity === undefined) {
            const current = parseInt($counter.text(), 10) || 0;
            $counter.text(current + addedQty);
        } else {
            $counter.text(data.cart_quantity);
        }
        $counter.removeClass("d-none");

        // Brief pulse animation
        $counter.stop(true, true).animate(
            { scale: 1.4 },
            150,
            function () {
                $(this).animate({ scale: 1 }, 150);
            }
        );
    },

    /**
     * Show a Bootstrap 5 toast notification at top-right of viewport.
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
                'data-bs-dismiss="toast" aria-label="Close"></button>' +
                "</div>" +
                "</div>"
        ).appendTo($container);

        // eslint-disable-next-line no-undef
        const bsToast = new bootstrap.Toast($toast[0], {
            delay: 3500,
            autohide: true,
        });
        bsToast.show();

        $toast.on("hidden.bs.toast", function () {
            $(this).remove();
        });
    },
});

publicWidget.registry.WLAjaxAddToCart = WL_AJAX_ADD_TO_CART;

export default WL_AJAX_ADD_TO_CART;
