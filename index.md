---
layout: home
title: Home
---

<div class="home">
  <header class="site-intro">
    <h1 class="page-heading">{{ site.title }}</h1>
    <p class="intro-text">Welcome to our weekly fantasy football newsletter archive! Dive into comprehensive analysis, power rankings, and entertaining commentary from each week of the season.</p>
  </header>

  <div class="newsletter-archive">
    <h2>Newsletter Archive</h2>
    
    <div class="season-section">
      <h3>2025 Season</h3>
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
        <p class="no-newsletters">No newsletters yet for the 2025 season. Check back soon!</p>
      {% endif %}
    </div>

  </div>

  <footer class="archive-footer">
    <p><em>Newsletters are automatically updated weekly during the season.</em></p>
  </footer>
</div>