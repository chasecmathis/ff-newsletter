---
title: Fantasy Football Weekly Report
feature_text: |
  ## Fantasy Football Weekly Report 🏈
  Your comprehensive source for weekly fantasy football analysis, power rankings, and entertaining commentary from each week of the season.
feature_image: "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?ixlib=rb-4.0.3&auto=format&fit=crop&w=1300&h=400&q=80"
excerpt: "Weekly fantasy football analysis and updates"
---

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

### 2024 Season  
{% assign newsletters_2024 = site.pages | where_exp: "page", "page.path contains 'newsletters/2024'" | sort: "path" %}
{% if newsletters_2024.size > 0 %}
<ul class="newsletter-list">
  {% for newsletter in newsletters_2024 %}
  <li>
    <a href="{{ newsletter.url | relative_url }}">
      {{ newsletter.title | default: newsletter.name }}
    </a>
  </li>
  {% endfor %}
</ul>
{% else %}
*No newsletters available for the 2024 season.*
{% endif %}

---

*Newsletters are automatically updated weekly during the season.*