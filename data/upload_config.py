"""
הגדרות להעלאות קבצים: תמיכה (פניות/תשובות) ותמונת פרופיל.
"""

# --- העלאות תמיכה (פניות/תשובות): רשימה מותרת בלבד ---
SUPPORT_MAX_BYTES = 25 * 1024 * 1024  # 25MB
# בלי .html/.htm/.svg/.xml/.js – קבצים כאלה מוגשים מדומיין ה-CRM ויכלו לרוץ שם כדף ולגנוב טוקן של מנהל.
SUPPORT_ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".pdf", ".txt", ".log", ".csv", ".json", ".har",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".mp4", ".webm", ".mov", ".mp3", ".m4a", ".wav",
}


# --- תמונת פרופיל: רק תמונות נתמכות ---
AVATAR_MAX_BYTES = 5 * 1024 * 1024  # 5MB

AVATAR_ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
}
