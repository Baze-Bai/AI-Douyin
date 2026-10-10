# AI Douyin automation tools

A separate implementation of creator/content collection and contextual messaging, grouped with the TikTok creator tools in the portfolio rather than counted as a separate experience.

## Components

`douyin_gui.py` provides the Tkinter operator interface. `douyin_scraper.py`, `douyin_comment.py` and `douyin_messenger.py` implement collection, comment analysis and messaging workflows. `browser_utils.py` and the Qwen adapters support browser and model integration.

Install `requirements.txt` and Playwright Chromium. Review model configuration and platform selectors, then run `python douyin_gui.py`. Use your own private environment/configuration and manually authenticated browser session.

Technologies: Python, Tkinter, Playwright and Qwen. GUI assets/builds, browser state, account configuration, harvested records and generated messages are not included. This source snapshot was syntax-checked; current Douyin compatibility and authenticated operations were not verified. Operate only within platform rules and with authorization; do not use the messaging workflow for unsolicited bulk outreach.
