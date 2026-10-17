from core.filters.text.text_filter import filter_text_content


def test_windows_1255_page_keeps_its_charset():
    html = '<html><head><meta charset="windows-1255"></head><body><div>שלום וברכה לכולם</div></body></html>'.encode("cp1255")
    out, _block, _reason, _debug = filter_text_content(html, url="https://x", content_type="text/html")
    assert "שלום וברכה" in out.decode("cp1255")
    assert b'charset="windows-1255"' in out


def test_unchanged_json_is_returned_byte_for_byte():
    payload = b'{"price": 1.10, "name": "\\u05e9"}'
    out, block, _r, _d = filter_text_content(payload, url="https://x", content_type="application/json")
    assert out == payload and block is False


def test_json_keys_are_never_masked():
    payload = '{"sex": "male", "note": "סקס"}'.encode()
    out, _b, _r, _d = filter_text_content(payload, url="https://x", content_type="application/json")
    assert b'"sex"' in out and "סקס" not in out.decode()
