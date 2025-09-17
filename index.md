---
layout: page
title: Privacy Projecy Fantasy Football
excerpt: "Weekly fantasy football analysis and power rankings"
---

<div class="hero-section">
  <h1 class="hero-title">⚡ Fantasy Football Weekly Newsletter</h1>
  <p class="hero-subtitle">Your weekly dose of championship-level insights, power rankings, and the hottest takes in the league!</p>
  <div class="hero-badge">🏆 Season Analysis & Rankings</div>
</div>

{:#newsletter-archive}
## Newsletter Archive

### 2025 Season
{% assign newsletters_2025 = site.pages | where_exp: "page", "page.path contains 'newsletters/2025'" | sort: "path" %}
{% if newsletters_2025.size > 0 %}
<ul class="newsletter-list">
  {% for newsletter in newsletters_2025 %}
  <li>
    <a href="{{ newsletter.url | relative_url }}">
      {{ newsletter.title | default: newsletter.name }}
    </a>
  </li>
  {% endfor %}
</ul>
{% else %}
*No newsletters yet for the 2025 season. Check back soon!*
{% endif %}

---

*Newsletters are automatically updated weekly during the season.*