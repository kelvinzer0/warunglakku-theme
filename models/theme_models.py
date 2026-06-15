# -*- coding: utf-8 -*-
# Part of Warung Lakku Theme. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ThemeWarungLakku(models.AbstractModel):
    _name = 'theme.warunglakku'
    _description = 'Warung Lakku Theme Config'
    _inherit = ['theme.utils']
