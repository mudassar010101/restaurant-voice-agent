import requests
import re
import json

URL = "https://nexcognit.store/"

response = requests.get(URL)
html = response.text

# The menu is embedded directly in the page as a JavaScript object:
#   const menuData = { italian: { appetizers: [ {...}, {...} ], ... }, chinese: {...} };
# We extract that block and convert it into valid JSON.

match = re.search(r"const\s+menuData\s*=\s*(\{.*?\});", html, re.DOTALL)

if not match:
    raise ValueError("Could not find menuData in the page source. The site structure may have changed.")

raw_js_object = match.group(1)

# Convert JS object syntax -> valid JSON:
# 1. Add quotes around unquoted keys (e.g. italian: -> "italian":)
json_text = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', raw_js_object)

# 2. Remove trailing commas before } or ]
json_text = re.sub(r",(\s*[}\]])", r"\1", json_text)

menu = json.loads(json_text)

# Print nicely
print(json.dumps(menu, indent=2, ensure_ascii=False))

# Save to file
with open("menu.json", "w", encoding="utf-8") as f:
    json.dump(menu, f, indent=2, ensure_ascii=False)

print("\nSaved to menu.json")