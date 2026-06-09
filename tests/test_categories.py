from bupt_library_crawler.categories import extract_categories, select_categories, top_code_for


def test_extract_categories_marks_leaf_nodes():
    html = """
    <span onclick="init('A',1);">马克思主义</span>
    <span onclick="init('A1',1);">马克思 恩格斯著作</span>
    <span onclick="init('A11',1);">选集 文集</span>
    <span onclick="init('B821',1);">人生观 人生哲学</span>
    """
    categories = {item.code: item for item in extract_categories(html)}

    assert categories["A"].is_leaf is False
    assert categories["A1"].parent_code == "A"
    assert categories["A11"].is_leaf is True
    assert categories["B821"].top_code == "B"


def test_select_categories_can_limit_codes():
    html = "<span onclick=\"init('A11',1);\">选集</span><span onclick=\"init('B821',1);\">人生哲学</span>"
    categories = extract_categories(html)

    selected = select_categories(categories, ["B821"], leaf_only=True)

    assert [item.code for item in selected] == ["B821"]
    assert top_code_for("TP311") == "TP"

