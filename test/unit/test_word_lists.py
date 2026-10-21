"""Word lists: permitted contexts are never masked or blocked; LGBTQ+ terms are masked in every context."""
import pytest

from core.filters.text.text_filter import _filter_plain_text, _tokenize_words

# Permitted: each of these was blocked (or would be) by the old list / matcher.
PERMITTED = [
    "ויהיו שניהם ערומים האדם ואשתו ולא יתבששו",          # בראשית ב
    "לא תרצח לא תנאף לא תגנב",                            # עשרת הדברות
    "אלכה אחרי מאהבי נתני לחמי ומימי",                     # הושע ב
    "כי חולת אהבה אני",                                    # שיר השירים
    "לאהוב שלום ולרדוף שלום",
    "מה דעתך על הכתבה? מעניין 3 אהבו",                    # כפתור "אהבו" באתר חדשות
    "לפני ארבע שנים ישבנו סביב השולחן וחשבנו",
    "המשטרה עצרה חשוד בעבירות מין; הטרדה מינית בעבודה",
    "מין העובר נקבע בשבוע ה-20. מין: זכר / נקבה",
    "פריחה בישבן אצל תינוקות",
    "מזון בריא לכל המשפחה",                                # "מזון" ← "זונה" במאתר הישן
    "גילוי עריות, איסור ייחוד וקול באשה ערוה",
    "אונס רחמנא פטריה",
    "Sex: Male / Female",
    "You shall not commit adultery.",
    "The two of them were naked, the man and his wife",
    "Do not uncover the nakedness of your father's wife",
    "nude heels and nude make-up",
    "a true lover of Torah; the mistress of the house",
    "sexual abuse charges were filed",
    "a gay and festive Purim seudah",
]


@pytest.mark.parametrize("text", PERMITTED)
def test_permitted_contexts_are_never_masked_or_blocked(text):
    # suspicious words may add a hidden score here – but nothing is masked and nothing is blocked
    out, block, _reason, debug = _filter_plain_text(text)
    assert out == text and not block, debug.get("score")


LGBT_ANY_CONTEXT = [
    'ארגוני הלהט"ב הפגינו מול הכנסת',
    "הכנסת דנה בחוק נישואים חד מיניים",
    "מצעד הגאווה בירושלים",
    "Lesbian relations are forbidden (Kitzur Shulchan Aruch)",
    "the court ruled on same-sex marriage",
    "transgender policy",
]


@pytest.mark.parametrize("text", LGBT_ANY_CONTEXT)
def test_lgbt_terms_are_masked_in_every_context(text):
    out, _block, _reason, debug = _filter_plain_text(text)
    assert "XXX" in out, debug


def test_homo_sapiens_is_not_lgbt():
    out, _b, _r, _d = _filter_plain_text("הומו סאפיינס הופיע לפני כ-300 אלף שנה")
    assert "X" not in out


EXPLICIT = ["סקס", "סקסי", "והסקסית", "פורנו", "בפורנוגרפיה", "ארוטית", "אירוטיקה", "ביקיני", "לפלרטט", "דייטים",
            "חשפניות", "גייז", "porn", "pornographic", "erotica", "sexy", "striptease", "gays", "nsfw"]


@pytest.mark.parametrize("word", EXPLICIT)
def test_explicit_words_and_their_forms_are_caught(word):
    _out, _block, _reason, debug = _filter_plain_text(f"x {word} y")
    assert debug["counts"]["matched"] == 1


def test_exact_entries_do_not_inflect():
    # "=gays" is exact and hard; "gay" alone ("cheerful") is only a hidden score – never masked
    assert _filter_plain_text("gay")[0] == "gay"
    assert _filter_plain_text("gays")[0] == "XXXX"


def test_acronyms_and_geresh_stay_one_token_and_maqaf_splits():
    assert [t for t, _, _ in _tokenize_words('ארגוני הלהט"ב')] == ["ארגוני", 'הלהט"ב']
    assert [t for t, _, _ in _tokenize_words("ר' משה")] == ["ר", "משה"]  # a trailing geresh is not inside a word
    assert [t for t, _, _ in _tokenize_words("כִּי־חוֹלַת")] == ["כִּי", "חוֹלַת"]
