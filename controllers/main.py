# -*- coding: utf-8 -*-
# Part of Warung Lakku Theme. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import content_disposition, request
import base64


class ThemeWarungLakkuController(http.Controller):
    """Controller for theme assets and custom pages"""

    @http.route('/theme_warunglakku/assets', type='http', auth='public', website=True)
    def theme_assets(self, **kwargs):
        """Serve theme-specific assets"""
        return request.render('theme_warunglakku.theme_assets_page', {})
