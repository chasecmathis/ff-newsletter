---
layout: default
title: Home
---

# {{ site.title }}

Welcome to our weekly fantasy football newsletter archive!

## Newsletter Archive

### 2025 Season
{% assign newsletters_2025 = site.pages | where_exp: "page", "page.path contains 'newsletters/2025'" | sort: "path" %}
{% for newsletter in newsletters_2025 %}
- [{{ newsletter.title | default: newsletter.name }}]({{ newsletter.url | relative_url }})
{% endfor %}

### 2024 Season
{% assign newsletters_2024 = site.pages | where_exp: "page", "page.path contains 'newsletters/2024'" | sort: "path" %}
{% for newsletter in newsletters_2024 %}
- [{{ newsletter.title | default: newsletter.name }}]({{ newsletter.url | relative_url }})
{% endfor %}

---

*Newsletters are automatically updated weekly during the season.*