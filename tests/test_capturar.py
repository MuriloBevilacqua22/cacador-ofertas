from pathlib import Path

from coletor.capturar import capture, search_urls


def test_search_urls_have_term_and_two_pages():
    for store in ("kabum", "pichau", "terabyte"):
        urls = search_urls(store, "rtx 4070")
        assert len(urls) == 2 and all("4070" in u and u.startswith("https://") for u in urls)
        assert urls[0] != urls[1]


class FakeClient:
    def __init__(self):
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return f"<html>{url}</html>"


def test_capture_writes_one_file_per_page(tmp_path: Path):
    c = FakeClient()
    files = capture("kabum", "rtx 4070", tmp_path, c)
    assert len(files) == 2 and all(f.exists() for f in files)
    assert files[0].name == "kabum_rtx-4070_p1.html"
    assert c.urls[0] in files[0].read_text(encoding="utf-8")
