# -*- coding: utf-8 -*-
"""Extend website model with operating-hours context method.

The data is fetched and cached by the `website_sale_pickup_at_store`
module (which talks to Evolution API). This theme module just reads
the cached JSON from ir.config_parameter and formats it for the
/shop sidebar widget.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from odoo import models

_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    def get_warunglakku_operating_hours(self):
        """Return operating hours context for /shop sidebar.

        Pulls cached business hours from ir.config_parameter
        (populated by `website_sale_pickup_at_store` via Evolution
        API, cache TTL 24h). Returns a dict:

          {
            'available': bool,
            'is_open_now': bool,
            'today_dow': 'mon' | 'tue' | ... | 'sun',
            'today_name': 'Senin' | 'Selasa' | ... | 'Minggu',
            'timezone': 'Asia/Jakarta',
            'days': [
              {
                'day': 'mon',
                'name': 'Senin',
                'mode': 'specific_hours' | 'open_24_hours' | 'closed' | 'appointment_only',
                'open_time': '720' (minutes from midnight),
                'close_time': '1200',
                'is_today': bool,
                'is_open': bool,        # only meaningful for today
                'hours_display': '12:00 - 20:00' | '24 Jam' | 'Tutup' | 'Janji temu'
              },
              ...
            ],
            'fetched_at': '18/06/2026 12:41'  # formatted in Asia/Jakarta
          }

        If no cached data: returns {'available': False}.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        bh_raw = ICP.get_param(
            'website_sale_pickup_at_store.business_hours_json', '')
        fetched_at_raw = ICP.get_param(
            'website_sale_pickup_at_store.business_hours_fetched_at', '')

        if not bh_raw:
            return {'available': False}

        try:
            bh = json.loads(bh_raw)
        except (ValueError, TypeError):
            _logger.warning('[WL_OH] business_hours_json not valid JSON')
            return {'available': False}

        # Jakarta timezone (UTC+7)
        jakarta_tz = timezone(timedelta(hours=7))
        now_jakarta = datetime.now(jakarta_tz)
        # weekday(): 0=Monday, 6=Sunday
        today_idx = now_jakarta.weekday()
        DOW_CODES = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        DOW_NAMES = ['Senin', 'Selasa', 'Rabu', 'Kamis',
                     'Jumat', 'Sabtu', 'Minggu']
        today_dow = DOW_CODES[today_idx]
        today_name = DOW_NAMES[today_idx]

        # Build dict day_of_week -> config
        config_map = {}
        for cfg in bh.get('business_config', []):
            config_map[cfg.get('day_of_week', '')] = cfg

        # Determine "open now" status
        now_min = now_jakarta.hour * 60 + now_jakarta.minute
        today_cfg = config_map.get(today_dow, {})
        today_mode = today_cfg.get('mode', 'closed')
        is_open_now = False
        if today_mode == 'open_24_hours':
            is_open_now = True
        elif today_mode == 'specific_hours':
            try:
                open_min = int(today_cfg.get('open_time', 0))
                close_min = int(today_cfg.get('close_time', 0))
                is_open_now = open_min <= now_min < close_min
            except (ValueError, TypeError):
                is_open_now = False

        # Build days list (Monday → Sunday ordering, Indonesian week)
        days = []
        for dow in DOW_CODES:
            cfg = config_map.get(dow, {})
            mode = cfg.get('mode', 'closed')
            day_info = {
                'day': dow,
                'name': DOW_NAMES[DOW_CODES.index(dow)],
                'mode': mode,
                'open_time': cfg.get('open_time'),
                'close_time': cfg.get('close_time'),
                'is_today': dow == today_dow,
                'is_open': False,
                'hours_display': 'Tutup',
            }
            if mode == 'specific_hours':
                try:
                    o = int(cfg.get('open_time', 0))
                    c = int(cfg.get('close_time', 0))
                    day_info['hours_display'] = (
                        f"{o // 60:02d}:{o % 60:02d} - "
                        f"{c // 60:02d}:{c % 60:02d}"
                    )
                    if dow == today_dow:
                        day_info['is_open'] = is_open_now
                except (ValueError, TypeError):
                    day_info['hours_display'] = '?'
            elif mode == 'open_24_hours':
                day_info['hours_display'] = '24 Jam'
                if dow == today_dow:
                    day_info['is_open'] = True
            elif mode == 'appointment_only':
                day_info['hours_display'] = 'Janji temu'
            else:  # closed or missing
                day_info['hours_display'] = 'Tutup'
            days.append(day_info)

        # Format fetched_at in Jakarta time
        fetched_at_display = ''
        if fetched_at_raw:
            try:
                # The cached timestamp is naive (server UTC). Parse as
                # UTC then convert to Jakarta for display.
                fetched_naive = datetime.fromisoformat(fetched_at_raw)
                fetched_utc = fetched_naive.replace(tzinfo=timezone.utc)
                fetched_jakarta = fetched_utc.astimezone(jakarta_tz)
                fetched_at_display = fetched_jakarta.strftime(
                    '%d/%m/%Y %H:%M')
            except (ValueError, TypeError):
                fetched_at_display = ''

        # Find today's day_info for convenience (used by mobile accordion
        # to show today's hours inline in the collapsed summary).
        today_info = next(
            (d for d in days if d.get('is_today')), None)

        return {
            'available': True,
            'is_open_now': is_open_now,
            'today_dow': today_dow,
            'today_name': today_name,
            'today': today_info,
            'timezone': bh.get('timezone', 'Asia/Jakarta'),
            'days': days,
            'fetched_at': fetched_at_display,
        }

    def get_warunglakku_shop_chips(self):
        """Return recordset of product.public.category records that are
        linked to at least one published product, sorted by name
        (case-insensitive).

        Used by the Filter Chips / Pill Tabs widget on /shop. The chips
        render as a horizontal-scrollable list of pill-shaped links.

        Background:
        - The n8n workflow syncs WA collections → product.category
          (internal category, parent_id=7 "Warung Lakku").
        - /shop filters by product.public.category via ?category=<id> or
          /shop/category/<slug>-<id>.
        - The one-time sync script sync_public_categories.py creates
          matching product.public.category records and links them to
          published products via public_categ_ids.
        - This method returns the "visible" public cats that should
          appear as chips (those with at least 1 published product).

        Returns:
            recordset of product.public.category (empty if none).
        """
        PT = self.env['product.template'].sudo()
        pub_recs = PT.search([('is_published', '=', True)]).mapped('public_categ_ids')
        if not pub_recs:
            return self.env['product.public.category'].sudo()
        # Sort by name case-insensitively for stable ordering
        return pub_recs.sorted(lambda c: (c.name or '').lower())
