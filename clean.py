import json
import re
import os

filepath = 'full_items_data.json'
if not os.path.exists(filepath):
    print(f"File {filepath} not found.")
    exit(1)

with open(filepath, 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    new_stats = []
    for stat in item.get('stats', []):
        # 1. Hapus teks Harga: 
        stat = stat.replace("Harga: ", "")
        
        # 2. Ubah angka desimal ke persen
        stat = re.sub(r'\*([0-9.]+)', lambda m: f"+{int(float(m.group(1))*100)}%", stat)
        
        new_stats.append(stat)
    item['stats'] = new_stats

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("JSON formatted successfully!")
