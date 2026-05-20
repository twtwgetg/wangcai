import requests

for q in ["青岛天气", "猫", "风景", "苍井空", "test"]:
    r = requests.get(
        "http://localhost:9528/search",
        params={"q": q, "format": "json", "categories": "images"},
        timeout=15,
    )
    data = r.json()
    results = data.get("results", [])
    print(f"{q}: {len(results)} results")
    if results:
        img = results[0].get("img_src", "NONE") or results[0].get("thumbnail_src", "NONE")
        print(f"  first img_src: {img}")
