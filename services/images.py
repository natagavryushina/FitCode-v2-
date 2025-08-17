from __future__ import annotations

import os
from typing import Dict

# Open-license/royalty-free sources (e.g., Pexels). Replace with your CDN in prod.
_DEFAULT_IMAGES: Dict[str, str] = {
	"welcome": "https://images.pexels.com/photos/414029/pexels-photo-414029.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&dpr=1",
	"generic": "https://images.pexels.com/photos/3763873/pexels-photo-3763873.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&dpr=1",
	"workout": "https://images.pexels.com/photos/841130/pexels-photo-841130.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&dpr=1",
	"week": "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&dpr=1",
	"kbzhu": "https://images.pexels.com/photos/1092730/pexels-photo-1092730.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&dpr=1",
	"profile": "https://images.pexels.com/photos/1552249/pexels-photo-1552249.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&dpr=1",
	"support": "https://images.pexels.com/photos/3184360/pexels-photo-3184360.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&dpr=1",
	"loyalty": "https://images.pexels.com/photos/1661004/pexels-photo-1661004.jpeg?auto=compress&cs=tinysrgb&w=1280&h=720&dpr=1",
}


def get_image_url(topic: str) -> str | None:
	# Allow env override: IMAGE_TOPIC (upper)
	override = os.getenv(f"IMAGE_{topic.upper()}")
	if override:
		return override
	return _DEFAULT_IMAGES.get(topic) or _DEFAULT_IMAGES.get("generic")