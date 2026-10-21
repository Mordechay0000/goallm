"""The hidden score: hard words masked, suspicious words only counted, local / diverse / context-aware decisions,
and on mixed HTML pages the offending block is hidden instead of the whole page."""
import pytest

from core.filters.text.text_filter import HIDDEN_PLACEHOLDER, _filter_plain_text, filter_text_content

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


def test_scattered_words_on_a_long_page_do_not_add_up_but_a_cluster_does():
    filler = " ".join(["חדשות היום מהארץ ומהעולם, מזג האוויר והתחבורה."] * 40)
    scattered = filler + " דוגמנית " + filler + " רומנטי " + filler + " נשיקות " + filler
    assert not _filter_plain_text(scattered)[1]
    cluster = filler + " דוגמנית בבגד ים חושני עם מחשוף, נשיקות ותשוקה. " + filler
    assert _filter_plain_text(cluster)[1]


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


def test_portal_with_one_bad_teaser_hides_only_that_teaser():
    teasers = [CLEAN_TEASER.format(t=f"כותרת {i}") for i in range(12)]
    teasers.insert(5, BAD_TEASER)
    out, block, _r, debug = filter_text_content(_html("".join(teasers)), url="https://news.example/", content_type="text/html; charset=utf-8")
    html = out.decode()
    assert not block and debug["score"]["hidden_blocks"] == 1
    assert html.count(HIDDEN_PLACEHOLDER) == 1 and "מחשוף" not in html and html.count("התקציב החדש") == 12


def test_a_list_of_bad_links_is_hidden_as_one_unit():
    links = "".join(f"<li><a href='/x{i}'>{w}</a></li>" for i, w in enumerate(["פורנוגרפיה", "ארוטיקה", "חשפנות", "סטריפטיז"]))
    article = "<p>" + " ".join(["ההיריון נמשך כארבעים שבועות, והמעקב הרפואי חשוב לבריאות האם והעובר."] * 30) + "</p>"
    out, block, _r, debug = filter_text_content(_html(article + f"<div class='navbox'><ul>{links}</ul></div>"),
                                                url="https://wiki.example/pregnancy", content_type="text/html; charset=utf-8")
    html = out.decode()
    assert not block and html.count(HIDDEN_PLACEHOLDER) == 1 and "ארבעים שבועות" in html


def test_when_the_bad_text_is_the_page_itself_the_page_is_blocked():
    body = "<article>" + "".join(f"<p>{t}</p>" for t in IMMODEST.values() if any("א" <= c <= "ת" for c in t)) + "</article>"
    _out, block, reason, _debug = filter_text_content(_html(body), url="https://gossip.example/a", content_type="text/html; charset=utf-8")
    assert block, reason  # a page made of hidden paragraphs is a blocked page, not a page full of placeholders


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
