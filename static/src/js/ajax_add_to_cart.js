/** @odoo-module **/

/*
 * Warung Lakku - AJAX Add to Cart on Product Detail Page
 * ========================================================
 *
 * When customer clicks "Tambahkan ke keranjang" on a product detail page
 * (URL pattern: /shop/<slug>), intercept the click and POST to
 * /shop/cart/update_json via JSON-RPC instead of submitting the form
 * synchronously (which would redirect to /shop/cart).
 *
 * After AJAX success:
 *   1. Update cart counter in navbar (.my_cart_quantity)
 *   2. Show toast notification "Berhasil ditambahkan ke keranjang"
 *   3. Customer stays on the product page (no redirect)
 *
 * On product card grid (/shop listing), the existing Odoo behavior is
 * preserved (form submits → redirect to /shop/cart). This is intentional
 * because the product card "Add to Cart" buttons already use a different
 * code path (a-submit on #products_grid).
 *
 * Route: /shop/cart/update_json
 *   - Type: json (JSON-RPC, no CSRF required since type='json')
 *   - Args: product_id (int), add_qty (int), display (bool)
 *   - Returns: { line_id, cart_quantity, minor_amount, notification_info }
 *
 * Author: Kelvin Yuli Andrian
 * Since: v17.0.3.10.48
 */

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonRpc } from "@web/core/network/rpc";

const WL_AJAX_ADD_TO_CART = publicWidget.Widget.extend({
    selector: "#add_to_cart_wrap",
    events: {
        "click #add_to_cart": "_onAddToCartClick",
    },

    /**
     * Intercept #add_to_cart click on product detail page only.
     * On /shop (listing) or other contexts, let default Odoo behavior run.
     */
    _onAddToCartClick: function (ev) {
        // Only intercept on product detail page
        // Pattern: /shop/<slug> (e.g. /shop/wa-12345-kerupuk-1)
        // NOT /shop (listing), /shop/cart, /shop/checkout, /shop/payment
        const path = window.location.pathname;
        if (!/^\/shop\/[^/]+$/.test(path)) {
            return; // Let Odoo's default handler proceed
        }

        ev.preventDefault();
        ev.stopImmediatePropagation();

        const $btn = this.$("#add_to_cart");
        const $form = $btn.closest("form");
        const productId = parseInt($form.find('input[name="product_id"]').val(), 10);
        const addQty = parseInt($form.find('input[name="add_qty"]').val(), 10) || 1;

        if (!productId || productId < 1) {
            this._showToast("Produk tidak valid", "danger");
            return;
        }

        // Show loading state
        const originalHtml = $btn.html();
        $btn.html('<i class="fa fa-spinner fa-spin me-2"></i>Menambahkan...')
            .addClass("disabled")
            .css("pointer-events", "none");

        jsonRpc("/shop/cart/update_json", "call", {
            product_id: productId,
            add_qty: addQty,
            display: false,
        }).then((data) => {
            // Update cart counter in navbar
            this._updateCartCounter(data, addQty);

            // Show success toast
            this._showToast(
                `Berhasil ditambahkan ke keranjang (${addQty}x)`,
                "success"
            );

            // Optional: brief check icon before restoring
            $btn.html('<i class="fa fa-check me-2"></i>Ditambahkan!');
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
     * Odoo's update_json returns cart_quantity when cart is non-empty.
     * On the very first add (cart was empty), it returns {} — fallback to
     * incrementing the current counter.
     */
    _updateCartCounter: function (data, addedQty) {
        const $counter = $(".my_cart_quantity");
        if (!data || data.cart_quantity === undefined) {
            // Cart was empty before, this is the first add
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
     * Creates the toast container if it doesn't exist yet.
     */
    _showToast: function (message, type) {
        type = type || "success";
        const icon =
            type === "success"
                ? "fa-check-circle"
                : type === "danger"
                ? "fa-exclamation-circle"
                : "fa-info-circle";

        // Ensure container exists
        let $container = $("#wl-toast-container");
        if (!$container.length) {
            $container = $(
                '<div id="wl-toast-container" ' +
                    'class="toast-container position-fixed top-0 end-0 p-3" ' +
                    'style="z-index: 1080;"></div>'
            ).appendTo("body");
        }

        // Create toast element (Bootstrap 5)
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

        // Initialize and show via Bootstrap 5 Toast API
        // eslint-disable-next-line no-undef
        const bsToast = new bootstrap.Toast($toast[0], {
            delay: 3500,
            autohide: true,
        });
        bsToast.show();

        // Remove from DOM after hidden
        $toast.on("hidden.bs.toast", function () {
            $(this).remove();
        });
    },
});

publicWidget.registry.WLAjaxAddToCart = WL_AJAX_ADD_TO_CART;

export default WL_AJAX_ADD_TO_CART;
