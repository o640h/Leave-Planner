"""Small self-contained startup surface shown before the application window."""

from __future__ import annotations

import base64
from pathlib import Path


def splash_html(*, light: bool, icon_path: Path) -> str:
    """Return the offline splash document in the selected application theme."""

    encoded_icon = base64.b64encode(icon_path.read_bytes()).decode("ascii")
    palette = (
        {
            "surface": "#fbfcfc",
            "raised": "#ffffff",
            "line": "rgba(30, 55, 76, 0.12)",
            "text": "#1b263d",
            "muted": "#748595",
            "accent": "#587f95",
            "shadow": "rgba(34, 56, 73, 0.22)",
        }
        if light
        else {
            "surface": "#181818",
            "raised": "#202020",
            "line": "rgba(255, 255, 255, 0.11)",
            "text": "#e3e8ea",
            "muted": "#69767c",
            "accent": "#91b8c9",
            "shadow": "rgba(0, 0, 0, 0.48)",
        }
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: transparent;
    }}
    body {{
      color: {palette["text"]};
      font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    }}
    .splash {{
      display: grid;
      width: 100%;
      height: 100%;
      place-items: center;
      overflow: hidden;
      border: 0;
      background: {palette["surface"]};
    }}
    .content {{ display: grid; justify-items: center; transform: translateY(-2px); }}
    .mark {{
      display: grid;
      width: 50px;
      height: 50px;
      place-items: center;
      border: 1px solid {palette["line"]};
      border-radius: 11px;
      color: {palette["accent"]};
      background: {palette["raised"]};
      box-shadow: 0 8px 24px {palette["shadow"]};
      animation: mark-breathe 1.4s ease-in-out infinite alternate;
    }}
    .mark img {{ display: block; width: 31px; height: 31px; }}
    strong {{ margin-top: 20px; font-size: 15px; font-weight: 450; letter-spacing: 0.01em; }}
    .status {{
      display: grid;
      grid-template-areas: "status";
      margin-top: 8px;
      color: {palette["muted"]};
      font-size: 10px;
    }}
    .status span {{ grid-area: status; animation: status-first 3.8s ease both; }}
    .status span:last-child {{ animation-name: status-second; }}
    .progress {{
      position: relative;
      width: 150px;
      height: 1px;
      margin-top: 19px;
      overflow: hidden;
      background: {palette["line"]};
    }}
    .progress::after {{
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 42%;
      background: {palette["accent"]};
      animation: progress 1.5s cubic-bezier(0.22, 0.82, 0.28, 1) infinite;
    }}
    @keyframes mark-breathe {{
      from {{ transform: translateY(0); }}
      to {{ transform: translateY(-3px); }}
    }}
    @keyframes status-first {{ 0%, 42% {{ opacity: 1; }} 52%, 100% {{ opacity: 0; }} }}
    @keyframes status-second {{ 0%, 42% {{ opacity: 0; }} 52%, 100% {{ opacity: 1; }} }}
    @keyframes progress {{
      from {{ transform: translateX(-110%); }}
      to {{ transform: translateX(240%); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .mark, .status span, .progress::after {{ animation: none; }}
      .status span:first-child {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main class="splash" role="status" aria-label="Leave Planner is starting">
    <div class="content">
      <div class="mark" aria-hidden="true">
        <img src="data:image/x-icon;base64,{encoded_icon}" alt="">
      </div>
      <strong>Leave Planner</strong>
      <div class="status"><span>Preparing workspace</span><span>Loading local records</span></div>
      <div class="progress" aria-hidden="true"></div>
    </div>
  </main>
</body>
</html>"""
