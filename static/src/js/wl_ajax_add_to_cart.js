/** @odoo-module **/

/*
 * Warung Lakku - AJAX Add to Cart (Product Detail + Listing)
 * =================================================================
 *
 * Strategy: at widget start, NEUTRALIZE the buttons so neither Odoo's
 * default handler nor browser's auto-submit can fire. Then bind our
 * own click handler that POSTs to /shop/cart/update_json (JSON-RPC).
 *
 * Neutralization:
 *   1. Remove `a-submit` class from buttons
 *      → Odoo's WebsiteSale widget binds to `.a-submit`, won't match
 *   2. Change `type="submit"` → `type="button"`
 *      → Browser won't auto-submit the form on click
 *   3. Remove `js_check_product` class (also triggers Odoo handlers)
 *
 * Targets:
 *   - #add_to_cart on product detail page (/shop/<slug>)
 *   - .wl_card_add_to_cart_btn on /shop listing page
 *
 * After AJAX success:
 *   1. Update cart counter in navbar (.my_cart_quantity) + pulse
 *   2. Show Bootstrap 5 toast "Berhasil ditambahkan ke keranjang"
 *   3. Customer stays on the same page (no redirect)
 *
 * Route: /shop/cart/update_json (type='json', csrf=False)
 *
 * Author: Kelvin Yuli Andrian
 * Since: v17.0.3.10.48 (detail page only)
 * v17.0.3.10.49: added listing page support
 * v17.0.3.10.50: neutralize buttons instead of relying on stopPropagation
 */

import publicWidget from "@web/legacy/js/public/public_widget";

/*
 * Note: We use Odoo's legacy `ajax.jsonRpc` instead of `@web/core/network/rpc`
 * because the latter is NOT available in the `web.assets_frontend_lazy` bundle
 * (it's only in `web.assets_backend` or `web.assets_frontend_minimal`).
 * Using the wrong import causes the widget to fail loading with error:
 *   "The following modules are needed by other modules but have not been
 *    defined: ["@web/core/network/rpc"]"
 *
 * `ajax.jsonRpc` is available globally in the frontend bundle and works
 * the same way for our use case (JSON-RPC POST to /shop/cart/update_json).
 */
// eslint-disable-next-line no-undef
const jsonRpc = (route, method, params) =>
    // eslint-disable-next-line no-undef
    ajax.jsonRpc(route, method, params);

const WL_AJAX_ADD_TO_CART = publicWidget.Widget.extend({
    selector: "#wrapwrap",
    events: {
        "click #add_to_cart": "_onAddToCartClickDetail",
        "click .wl_card_add_to_cart_btn": "_onAddToCartClickListing",
    },

    start: function () {
        this._super.apply(this, arguments);
        // Neutralize buttons so Odoo's default handlers don't fire
        this._neutralizeButtons();
    },

    /**
     * Remove Odoo's hook classes and change button type to prevent
     * any default form submission behavior.
     */
    _neutralizeButtons: function () {
        // Detail page: #add_to_cart
        const $detailBtn = this.$("#add_to_cart");
        if ($detailBtn.length) {
            $detailBtn
                .removeClass("a-submit js_check_product")
                .attr("type", "button");
        }

        // Listing page: .wl_card_add_to_cart_btn
        const $listingBtns = this.$(".wl_card_add_to_cart_btn");
        $listingBtns.each(function () {
            const $b = $(this);
            $b.removeClass("a-submit js_check_product").attr("type", "button");
        });
    },

    // ============================================================
    // PRODUCT DETAIL PAGE (/shop/<slug>)
    // ============================================================
    _onAddToCartClickDetail: function (ev) {
        const path = window.location.pathname;
        if (!/^\/shop\/[^/]+$/.test(path)) {
            return;
        }

        ev.preventDefault();
        ev.stopPropagation();

        const $btn = $(ev.currentTarget);
        const $form = $btn.closest("form");
        const productId = parseInt($form.find('input[name="product_id"]').val(), 10);
        const addQty = parseInt($form.find('input[name="add_qty"]').val(), 10) || 1;

        this._addToCart($btn, productId, addQty, false);
    },

    // ============================================================
    // PRODUCT LISTING PAGE (/shop)
    // ============================================================
    _onAddToCartClickListing: function (ev) {
        const path = window.location.pathname;
        if (path !== "/shop" && !path.startsWith("/shop?")) {
            return;
        }

        ev.preventDefault();
        ev.stopPropagation();

        const $btn = $(ev.currentTarget);
        const $form = $btn.closest("form");
        const productId = parseInt($form.find('input[name="product_id"]').val(), 10);

        this._addToCart($btn, productId, 1, true);
    },

    // ============================================================
    // COMMON: call /shop/cart/update_json
    // ============================================================
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

    _updateCartCounter: function (data, addedQty) {
        const $counter = $(".my_cart_quantity");
        if (!data || data.cart_quantity === undefined) {
            const current = parseInt($counter.text(), 10) || 0;
            $counter.text(current + addedQty);
        } else {
            $counter.text(data.cart_quantity);
        }
        $counter.removeClass("d-none");

        $counter.stop(true, true).animate(
            { scale: 1.4 },
            150,
            function () {
                $(this).animate({ scale: 1 }, 150);
            }
        );
    },

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
