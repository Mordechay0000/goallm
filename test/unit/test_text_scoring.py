"""The hidden score: hard words masked, suspicious words only counted; one density rule decides at every level –
a hot sentence, component or section turns into X's, and the page is blocked only by ratio."""
import pytest

from core.filters.text import lexicon
from core.filters.text.text_filter import _filter_plain_text, filter_text_content
from data.constants import TEXT_HARD_WEIGHT

# Non-graphic texts in the style of mixed sites (gossip / dating / fashion / "study" / romance). Each must be blocked.
IMMODEST = {
    "he_gossip": "הדוגמנית המפורסמת הצטלמה בבגד ים חושני בחופשה במיאמי, ושיתפה תמונות עם בן הזוג החדש שלה. השניים נראו "
                 "מתנשקים על החוף, והעוקבים הגיבו בהתלהבות למחשוף הנועז.",
    "he_dating": "איך להצליח בפגישה הראשונה: טיפים לפלרטוט, מה ללבוש כדי להיראות מושכת, ואיך לבנות אינטימיות ומשיכה מינית "
                 "כבר מהפגישה הראשונה. המומחית ממליצה לתת לתשוקה להתפתח.",
    "he_study": "המחקר בדק את חיי המין של זוגות צעירים: תדירות יחסי מין, ירידה בליבידו אחרי לידה, והשפעת הלחץ על האורגזמה. "
                "הסקסולוגית שהשתתפה במחקר ממליצה לדבר בפתיחות.",
    "he_fashion": "תצוגת האופנה של הקולקציה החדשה כללה הלבשה תחתונה, חזיות תחרה ובגדי ים. על מסלול האופנה צעדו הדוגמניות "
                  "המובילות, והקהל מחא כפיים לעיצובים הפרובוקטיביים.",
    "he_romance": "הרומן האסור בין השניים התחיל בנשיקה סוערת אחרי המסיבה. התשוקה ביניהם גברה מיום ליום, והמאהב החדש שלה לא "
                  "ידע שבעלה כבר חושד. הסיפור הרומנטי הסתבך.",
    "en_gossip": "The supermodel showed off her figure in a tiny swimsuit on the beach with her new boyfriend. The couple "
                 "were spotted kissing, and fans praised her daring look with deep cleavage.",
    "en_dating": "Ten flirting tips for your first date: what to wear to look attractive, how to build intimacy and sexual "
                 "attraction, and when it is time to try a dating app.",
    "en_study": "The study looked at the sex life of young couples: libido after childbirth, orgasm and stress, and what a "
                "sex therapist recommends for intimacy.",
    "en_fashion": "At the lingerie fashion show, runway models in panties and lace bras walked past the crowd, and the "
                  "revealing outfits drew applause.",
}


@pytest.mark.parametrize("name", sorted(IMMODEST))
def test_immodest_texts_are_blocked(name):
    _out, block, reason, _d = _filter_plain_text(IMMODEST[name])
    assert block, reason


def test_suspicious_words_are_hidden_score_not_masked():
    text = "בכתבה הוזכרה ירידה בליבידו כתופעת לוואי"
    out, block, _r, debug = _filter_plain_text(text)
    assert out == text and not block and debug["score"]["page"] > 0


def test_one_word_repeated_is_not_many_words():
    # a news story that keeps saying "הטרדה מינית" – diminishing returns, no block
    text = " ".join(["המשטרה חוקרת תלונה על הטרדה מינית במקום העבודה, והחשוד הורחק."] * 15)
    _out, block, _r, debug = _filter_plain_text(text)
    assert not block, debug["score"]


def test_scattered_words_on_a_long_page_do_not_add_up_but_a_cluster_turns_into_xs():
    filler = " ".join(["חדשות היום מהארץ ומהעולם, מזג האוויר והתחבורה."] * 40)
    scattered = filler + " דוגמנית " + filler + " רומנטי " + filler + " נשיקות " + filler
    out, block, _r, _d = _filter_plain_text(scattered)
    assert out == scattered and not block
    cluster = filler + " דוגמנית בבגד ים חושני עם מחשוף, נשיקות ותשוקה. " + filler
    out, block, _r, debug = _filter_plain_text(cluster)
    assert not block and "מחשוף" not in out and "XXXXXXX XXXX XX XXXXX" in out  # the page is fine, the sentence is not
    assert out.count("מזג האוויר") == 80 and debug["score"]["hidden_blocks"] == 1


def test_hard_words_weigh_at_least_twice_any_suspicious_word():
    for lang in lexicon.LANGS:
        lex = lexicon.load(lang)
        terms = list(lex.single.values()) + list(lex.stems.values()) + [t for ps in lex.phrases.values() for _, t in ps]
        scored = [t.weight for t in terms if t.kind == lexicon.SCORED]
        assert scored and max(scored) * 2 <= TEXT_HARD_WEIGHT, lang


def test_one_hard_word_in_a_sentence_masks_the_word_two_mask_the_sentence():
    one = "המשטרה פרסמה הודעה על פורנוגרפיה ברשת. הממשלה דנה בתקציב."
    out, block, _r, _d = _filter_plain_text(one)
    assert "XXXXXXXXXX" in out and "המשטרה פרסמה הודעה" in out and not block
    two = "באתר הוצגו תמונות פורנו וסרטי סקס חינם. " + " ".join(["הממשלה דנה היום בתקציב המדינה לשנה הבאה."] * 10)
    out, block, _r, _d = _filter_plain_text(two)
    assert "באתר" not in out and "תמונות" not in out and out.count("בתקציב המדינה") == 10 and not block


def test_a_dense_section_across_paragraphs_turns_into_xs_on_a_clean_page():
    clean = "\n\n".join(["הממשלה דנה היום בתקציב המדינה לשנה הבאה, ושרי האוצר הציגו את התוכנית לציבור."] * 30)
    section = ("הדוגמנית הצטלמה בבגד ים.\n\nבן הזוג שלה צפה בה בחוף.\n\nהמחשוף הנועז עורר תגובות.\n\n"
               "הנשיקות על החוף צולמו.\n\nוהתשוקה ביניהם גלויה.")
    out, block, _r, debug = _filter_plain_text(clean + "\n\n" + section + "\n\n" + clean)
    assert not block and debug["score"]["sections"] == 1
    assert all(w not in out for w in ("הדוגמנית", "צפה בה", "המחשוף", "הנשיקות", "גלויה"))
    assert out.count("בתקציב המדינה") == 60
    # the same section alone is the whole text – blocked
    assert _filter_plain_text(section)[1]


def test_torah_context_softens_suspicious_words_but_never_hard_ones():
    torah = ("פרשת השבוע: רש\"י על הפסוק מבאר, והגמרא אומרת שחז\"ל למדו מכאן הלכות צניעות. ויהיו שניהם עירומים, "
             "ואמר רש\"י שלא ידעו דרך צניעות. הקב\"ה ציוה, ובתהלים נאמר, ובשולחן ערוך נפסק. ") * 3
    out, block, _r, debug = _filter_plain_text(torah)
    assert not block and debug["score"]["context_factor"] < 1 and out == torah
    out2, _b, _r, _d = _filter_plain_text(torah + ' הלהט"ב')
    assert "XXX" in out2  # hard words are masked in any context


def test_neutral_phrases_absorb_their_words():
    for text in ("מין העובר נקבע בבדיקה", "carbon dating of the scroll", "a true music lover", "הומו סאפיינס"):
        out, _b, _r, debug = _filter_plain_text(text)
        assert out == text and debug["score"]["page"] == 0, (text, debug["score"])


def test_hebrew_phrase_agreement_with_the_definite_article():
    for text in ("ההלבשה התחתונה", "הרומן האסור", "בבגדי הים"):
        _o, _b, _r, debug = _filter_plain_text(text)
        assert debug["score"]["page"] >= 3, text


# ---------- mixed HTML pages ----------

CLEAN_TEASER = '<div class="card"><h3>{t}</h3><p>הממשלה אישרה את התקציב החדש לשנה הבאה, ושרי האוצר הציגו את התוכנית.</p></div>'
BAD_TEASER = ('<div class="card"><h3>הדוגמנית בחופשה</h3><p>הדוגמנית הצטלמה בבגד ים חושני עם מחשוף נועז, '
              'ונראתה מתנשקת עם בן הזוג.</p></div>')


def _html(body):
    return f'<html><head><meta charset="utf-8"><title>חדשות</title></head><body>{body}</body></html>'.encode()


def _filter(body, url="https://news.example/"):
    out, block, reason, debug = filter_text_content(_html(body), url=url, content_type="text/html; charset=utf-8")
    return out.decode(), block, reason, debug


def test_portal_with_one_bad_teaser_turns_only_that_teaser_into_xs():
    teasers = [CLEAN_TEASER.format(t=f"כותרת {i}") for i in range(12)]
    teasers.insert(5, BAD_TEASER)
    html, block, _r, debug = _filter("".join(teasers))
    assert not block and debug["score"]["hidden_blocks"] >= 1
    assert "מחשוף" not in html and "מתנשקת" not in html and html.count("התקציב החדש") == 12


def test_search_results_page_with_bad_results_is_not_blocked():
    clean = '<div class="g"><h3><a href="/r{i}">תוצאה {i}: מזג האוויר מחר</a></h3><span>תחזית מזג האוויר לסוף השבוע, גשם בצפון.</span></div>'
    bad = ('<div class="g"><h3><a href="/b{i}">סרטי סקס חינם {i}</a></h3>'
           '<span>אתר עם תמונות ארוטיות ונערות חשופות.</span></div>')
    results = [clean.format(i=i) for i in range(8)]
    results[2:2] = [bad.format(i=1)]
    results[6:6] = [bad.format(i=2)]
    html, block, _r, debug = _filter("".join(results), url="https://www.google.com/search")
    assert not block and html.count("מזג האוויר מחר") == 8
    assert "חינם" not in html and "חשופות" not in html and "נערות" not in html


def test_one_problem_word_in_a_short_heading_is_masked_alone_two_turn_the_heading_into_xs():
    body = ('<h2>סרטי סקס חינם</h2><h2>הדוגמנית בבגד ים חושני</h2>'
            '<p>' + " ".join(["העירייה פרסמה הודעה על שינויים בתנועה בשל הכנס."] * 8) + '</p>')
    html, block, _r, _d = _filter(body)
    assert not block and "סרטי XXX חינם" in html  # one word of three: only the word
    assert "הדוגמנית" not in html and "חושני" not in html  # three problem words: the whole heading
    assert html.count("העירייה פרסמה הודעה") == 8


def test_two_lone_words_far_apart_are_not_a_section():
    filler = " ".join(["העירייה פרסמה הודעה על שינויים בתנועה בשל הכנס."] * 30)
    text = f"נמצא חומר פורנוגרפי במחשב. {filler} המשטרה עצרה חשוד בהפצת סרטי סקס. {filler}"
    out, block, _r, debug = _filter_plain_text(text)
    assert debug["score"]["sections"] == 0 and out.count("העירייה פרסמה הודעה") == 60
    assert "נמצא חומר" in out and "המשטרה עצרה חשוד" in out and not block


def test_one_word_never_blocks_a_short_page():
    html, block, _r, _d = _filter('<h1>הכנס בנושא להט"ב בוטל</h1><p>העירייה הודיעה על ביטול הכנס.</p>')
    assert not block and "הכנס בנושא" in html and "בוטל" in html


def test_a_list_of_bad_links_is_hidden_as_one_unit():
    links = "".join(f"<li><a href='/x{i}'>{w}</a></li>" for i, w in enumerate(["פורנוגרפיה", "ארוטיקה", "חשפנות", "סטריפטיז"]))
    article = "<p>" + " ".join(["ההיריון נמשך כארבעים שבועות, והמעקב הרפואי חשוב לבריאות האם והעובר."] * 30) + "</p>"
    html, block, _r, debug = _filter(article + f"<div class='navbox'><ul>{links}</ul></div>", url="https://wiki.example/pregnancy")
    assert not block and debug["score"]["hidden_blocks"] == 1 and "ארבעים שבועות" in html
    assert all(w not in html for w in ("ארוטיקה", "חשפנות", "סטריפטיז"))


def test_when_the_bad_text_is_the_page_itself_the_page_is_blocked():
    body = "<article>" + "".join(f"<p>{t}</p>" for t in IMMODEST.values() if any("א" <= c <= "ת" for c in t)) + "</article>"
    _html_out, block, reason, _debug = _filter(body, url="https://gossip.example/a")
    assert block, reason  # a page that is mostly X's is a blocked page


def test_a_long_clean_page_with_one_dense_part_keeps_the_page_and_xs_the_part():
    clean = "".join(f"<p>{'הממשלה דנה היום בתקציב המדינה לשנה הבאה, ושרי האוצר הציגו את התוכנית.'}</p>" for _ in range(40))
    dense = "<div class='comment'><p>" + IMMODEST["he_gossip"] + "</p><p>" + IMMODEST["he_romance"] + "</p></div>"
    html, block, _r, _d = _filter(clean + dense + clean)
    assert not block and html.count("בתקציב המדינה") == 80 and "הדוגמנית" not in html and "המאהב" not in html


def test_image_alt_text_is_masked_and_scored():
    out, _b, _r, _d = filter_text_content(_html('<p>שלום</p><img src="a.jpg" alt="תמונה מתוך סרט פורנו">'),
                                          url="https://x.example/", content_type="text/html; charset=utf-8")
    assert "פורנו" not in out.decode() and "XXXX" in out.decode()


# ---------- vocabulary found missing on real dating / relationship columns ----------


@pytest.mark.parametrize("text", [
    "רווקת השבוע, בת 34 מתל אביב, מספרת שניסתה את טינדר ואתרי היכרויות ועדיין מחפשת בן זוג שתתאהב בו.",
    "המחקר מצא כי לוחמים רבים סובלים מירידה בחשק המיני ומבעיות זקפה, והמטפלת ממליצה לחזק את המגע המיני ואת היחסים האינטימיים.",
])
def test_dating_and_sexual_function_columns_are_blocked(text):
    _out, block, reason, _d = _filter_plain_text(text)
    assert block, reason


def test_slang_noun_is_masked_but_the_same_letters_as_a_verb_are_not():
    out, _b, _r, _d = _filter_plain_text("קשה לי להיות רק היזיזה שלך")
    assert "יזיזה" not in out
    text = "המשטרה ביקשה שהנהג יזיז את הרכב"
    out, block, _r, _d = _filter_plain_text(text)
    assert out == text and not block


def test_a_page_with_nothing_to_change_keeps_its_original_bytes():
    raw = ("<html><head><meta charset='utf-8'></head><body><p class=a>מזג&nbsp;האוויר</p><br>"
           + "<p>הממשלה אישרה את התקציב.</p>" * 20 + "</body></html>").encode()
    out, block, _r, _d = filter_text_content(raw, url="https://news.example/", content_type="text/html; charset=utf-8")
    assert out is raw and not block


def test_link_text_is_xd_but_judged_on_its_own_page():
    # a homepage whose bad items are links to other articles: the items turn into X's, the homepage stays open
    bad = ('<div class="teaser"><a href="/d{i}"><img src="t.jpg" alt="דוגמנית בבגד ים חושני">'
           '<h3>הדוגמנית בבגד ים חושני עם מחשוף נועז ונשיקות סוערות</h3></a></div>')
    clean = '<div class="teaser"><a href="/n{i}"><h3>הממשלה אישרה את התקציב החדש לשנה הבאה {i}</h3></a></div>'
    items = [clean.format(i=i) for i in range(20)]
    for k in (3, 9, 15):
        items[k] = bad.format(i=k)
    html, block, _r, debug = _filter("".join(items))
    assert not block and html.count("התקציב החדש") == 17 and "מחשוף" not in html and "נשיקות סוערות" not in html
    assert debug["score"]["left"] == 0


def test_an_article_that_is_all_about_it_is_blocked_even_when_no_part_is_dense():
    # suspicious words spread thinly through a whole article: no sentence or section is hot, the article is
    paras = ["הם הכירו באפליקציית היכרויות, והשיחה זרמה מהרגע הראשון.", "היא סיפרה שהיא מחפשת בן זוג רציני.",
             "אחרי כמה שבועות הוא הזמין אותה לסוף שבוע רומנטי בצפון.", "שם, היא אומרת, הבינה שהיא מאוהבת בו לגמרי.",
             "הנשיקה הראשונה הייתה על החוף.", "והתשוקה ביניהם, היא אומרת, לא נגמרת.", "בחתונה היא תלבש שמלה חושנית."]
    filler = "<p>" + " ".join(["העיר הייתה שקטה באותו ערב, והרחובות התרוקנו מוקדם מהרגיל."] * 12) + "</p>"
    body = "<article>" + "".join(f"<p>{t}</p>{filler}" for t in paras) + "</article>"
    _html_out, block, reason, debug = _filter(body, url="https://news.example/a")
    assert block and "density" in reason and debug["score"]["hidden_blocks"] == 0, (reason, debug["score"])
