# -*- coding: utf-8 -*-
{
    'name': 'Warung Lakku Theme',
    'description': """
        Warung Lakku Theme - Gradient Colorful Design System

        A warm & vibrant Odoo 17 website theme inspired by Indonesian warung culture.
        Adapted from BK Delivery design system, reimagined with Warung Lakku branding.

        Features:
        - Brand gradient: Yellow (#FFC107) -> Amber (#FF8F00) -> Orange (#FF5722)
        - Google Fonts: Poppins (headings) + Inter (body)
        - Rounded pill buttons with glow shadows
        - Gradient menu circles
        - Feature cards with hover animations
        - Warm color palette with light backgrounds
        - WhatsApp floating button
        - Scroll reveal animations
        - Custom scrollbar styling
    """,
    'category': 'Theme/Website',
    'version': '17.0.1.0.0',
    'author': 'Kelvinzer0',
    'website': 'https://github.com/kelvinzer0/warunglakku-theme',
    'license': 'LGPL-3',
    'depends': [
        'website',
        'theme_common',
    ],
    'excludes': [],
    'data': [
        'views/assets.xml',
        'views/theme_options.xml',
        'views/snippets.xml',
        'views/homepage.xml',
    ],
    'demo': [],
    'application': True,
    'auto_install': False,
    'installable': True,
    'images': ['static/img/preview.jpg'],
    'sequence': 1001,
}
