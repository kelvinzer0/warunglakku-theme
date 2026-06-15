<div align="center">

<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=FFC107,FF8F00,FF5722&height=220&section=header&text=Warung%20Lakku%20Theme&fontSize=42&fontColor=ffffff&animation=twinkling&fontAlignY=32&desc=Odoo%2017%20Website%20Theme%20-%20Gradient%20Colorful&descSize=18&descAlignY=52&descColor=ffffffcc" />

<a href="https://github.com/kelvinzer0/warunglakku-theme/blob/main/LICENSE">
  <img src="https://img.shields.io/badge/License-LGPL--3-FFC107?style=for-the-badge&logo=opensource&logoColor=white" alt="License" />
</a>
<a href="https://github.com/kelvinzer0/warunglakku-theme/releases">
  <img src="https://img.shields.io/badge/Odoo-17.0-FF8F00?style=for-the-badge&logo=odoo&logoColor=white" alt="Odoo 17" />
</a>
<a href="https://github.com/kelvinzer0/warunglakku-theme">
  <img src="https://img.shields.io/badge/Category-Theme%2FWebsite-E91E63?style=for-the-badge&logo=style&logoColor=white" alt="Theme" />
</a>

<br/><br/>

</div>

## Warung Lakku Theme for Odoo 17

A warm & vibrant **Odoo 17 website theme** inspired by Indonesian warung culture. Features bold gradients (Yellow -> Amber -> Orange), Poppins + Inter typography, rounded pill buttons with glow shadows, and a WhatsApp floating button.

Adapted from the BK Delivery design system, reimagined with Warung Lakku branding.

---

## Features

- **Brand Gradient** — `#FFC107` -> `#FF8F00` -> `#FF5722` hero, buttons, badges
- **Google Fonts** — Poppins (headings) + Inter (body)
- **Rounded Pill Buttons** — With glow shadow on hover
- **Feature Cards** — Hover animations with scale & shadow transitions
- **Gradient Menu Circles** — Colorful icon circles for menu items
- **Product Card Styling** — Rounded corners, hover lift, amber price text
- **WhatsApp Floating Button** — Fixed bottom-right with pulse animation
- **Scroll Reveal Animations** — IntersectionObserver-based fade-in
- **Custom Scrollbar** — Brand-colored scrollbar thumb
- **Gradient Footer Border** — Brand gradient top-border on footer
- **Ready-to-use Snippets** — Hero, Features, CTA, and WA button snippets
- **Default Homepage** — Complete homepage layout out of the box

---

## Color Palette

| Color | Hex | Role |
|---|---|---|
| Warung Yellow | `#FFC107` | Brand primary, CTA backgrounds |
| Amber Deep | `#FF8F00` | Hover states, gradient mid |
| Deep Orange | `#FF5722` | Secondary brand, gradient end |
| Pink Pop | `#E91E63` | Accent highlights, badges |
| Warm White | `#FFFDF7` | Page background |
| Charcoal | `#2D2D2D` | Footer, dark sections, text |

### Gradients

```
Brand:   #FFC107 -> #FF8F00 -> #FF5722
Sunset:  #FF8F00 -> #FF5722 -> #E91E63
Golden:  #FFECB3 -> #FFC107
Hero:    #FFC107 0% -> #FF8F00 40% -> #FF5722 70% -> #E91E63 100%
```

---

## Installation

### 1. Clone into your Odoo addons directory

```bash
cd /opt/odoo17/custom-addons/
git clone https://github.com/kelvinzer0/warunglakku-theme.git theme_warunglakku
```

> **Important:** The folder MUST be named `theme_warunglakku` for Odoo to recognize it as a theme module.

### 2. Add to addons path

Make sure your `odoo.conf` includes the custom addons path:

```ini
addons_path = /opt/odoo17/odoo/addons,/opt/odoo17/custom-addons
```

### 3. Update Apps List

- Go to **Apps** in Odoo
- Click **Update Apps List**
- Search for "Warung Lakku Theme"
- Click **Activate**

### 4. Apply the Theme

- Go to **Website** -> **Configuration** -> **Settings**
- Select "Warung Lakku" as your website theme
- Or go to **Website Editor** and choose from theme options

---

## Project Structure

```
theme_warunglakku/
├── __init__.py                  # Module init
├── __manifest__.py              # Module manifest (Odoo 17)
├── controllers/
│   ├── __init__.py
│   └── main.py                  # Custom controller
├── models/
│   ├── __init__.py
│   └── theme_models.py          # Theme utils abstract model
├── views/
│   ├── assets.xml               # SCSS/JS asset registration (ir.asset)
│   ├── theme_options.xml        # Theme options for Website Editor
│   ├── snippets.xml             # Custom drag-and-drop snippets
│   └── homepage.xml             # Default homepage template
├── static/
│   ├── img/
│   │   ├── icon.svg             # Theme icon
│   │   └── preview.jpg          # Theme preview image
│   └── src/
│       ├── scss/
│       │   ├── primary_variables.scss  # Color palette & font config (pre-Bootstrap)
│       │   ├── fonts.scss              # Google Fonts import
│       │   └── custom.scss             # Custom styles (post-Bootstrap)
│       └── js/
│           └── theme.js               # Frontend JavaScript widget
├── .gitignore
├── LICENSE
└── README.md
```

---

## Snippets

After installation, these snippets appear in the Website Editor:

| Snippet | Description |
|---|---|
| **Gradient Hero** | Full-width hero with brand gradient background |
| **Feature Cards** | 3-column feature cards with gradient icon circles |
| **Gradient CTA** | Call-to-action section with WhatsApp link |
| **WhatsApp Float** | Floating WhatsApp button (bottom-right corner) |

---

## Customization

### Change WhatsApp Number

Edit the WhatsApp number in:
- `views/snippets.xml` — Snippet templates
- `views/homepage.xml` — Homepage template

Replace `6285854749767` with your number.

### Change Colors

Edit `static/src/scss/primary_variables.scss` to modify the color palette. Changes will appear in the Website Editor color picker.

### Change Fonts

Edit the font families and Google Fonts URLs in `static/src/scss/primary_variables.scss` under `$o-theme-fonts`.

---

## Technical Notes

- Uses **`ir.asset`** model (Odoo 17) for asset registration instead of template inheritance
- `primary_variables.scss` is loaded **before** Bootstrap compilation, so all variables are available during Bootstrap build
- `custom.scss` is loaded **after** Bootstrap, allowing override of any Odoo/Bootstrap style
- Theme widget uses `publicWidget.Widget` with `IntersectionObserver` for scroll animations
- Compatible with **Odoo 17 Community** and **Enterprise**

---

## Requirements

- Odoo 17.0+
- `website` module
- `theme_common` module (ships with Odoo)

---

## License

This module is licensed under [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html).

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=FFC107,FF8F00,FF5722&height=120&section=footer" width="100%" />

<br/>

**Made with Indonesian warmth by [Kelvinzer0](https://github.com/kelvinzer0)**

</div>
