import requests

# Direct SearXNG call matching what search_images does
r = requests.get(
    "http://localhost:9528/search",
    params={"q": "风景照片", "format": "json", "categories": "images", "language": "zh-CN"},
    timeout=15,
)
data = r.json()
results = data.get("results", [])
print(f"Total results: {len(results)}")
for i, res in enumerate(results[:3], 1):
    img = res.get("img_src", "") or res.get("thumbnail_src", "")
    title = res.get("title", "")
    print(f"  {i}. title={title[:50]}")
    print(f"     img_src={img[:80] if img else 'NONE'}")
