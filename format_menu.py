import json

with open("menu.json", "r", encoding="utf-8") as f:
    menu = json.load(f)

lines = []
lines.append("RESTAURANT MENU:")

def add_items(category_name, items):
    lines.append(f"\n{category_name.title()}:")
    for item in items:
        lines.append(f"- {item['name']}: ${item['price']} - {item['desc']}")

for cuisine, categories in menu.items():
    if cuisine == "beverages":
        add_items("Beverages & Desserts", categories)
    else:
        lines.append(f"\n=== {cuisine.title()} ===")
        for cat_name, items in categories.items():
            add_items(cat_name, items)

menu_text = "\n".join(lines)
print(menu_text)

with open("menu_text.txt", "w", encoding="utf-8") as f:
    f.write(menu_text)

print("\n\nSaved to menu_text.txt")