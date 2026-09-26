# עוזר AI לשירות לקוחות באתר מסחר

אבטיפוס שמקבל פנייה חופשית של לקוח מחובר, מבין אותה באמצעות מודל שפה, ומקבל **החלטה דטרמיניסטית בקוד** על סמך מדיניות השירות ונתוני ההזמנה. העיקרון המרכזי: **המודל מבין ומנסח; הקוד מחליט ומבצע**.

מסמך התכנון המלא: [`Docs/AI_Service_Assistant_Design.md`](../Docs/AI_Service_Assistant_Design.md) — ארכיטקטורה, טבלת החלטות, פרומפטים, תוכנית בדיקות. מסמך המטלה המקורית (`Docs/AIEngineerTest.md`) אינו כלול במאגר הציבורי (ראו `.gitignore` בשורש) — זהו תוכן המטלה עצמו, לא תוצר של הפתרון.

## הדגמה ויזואלית (Demo)

[`progress/Demo/request-pipeline.html`](progress/Demo/request-pipeline.html) — עמוד HTML עצמאי (בלי צורך בשרת, מפתח API או התקנה) שמראה ויזואלית איך פנייה עוברת דרך כל קובץ במערכת: LLM #1 (חילוץ) → שליפת הזמנה → מנוע המדיניות → פתיחת בקשת שירות → LLM #2 (ניסוח) → Reply Guard → תשובה. כולל 4 תרחישים אמיתיים (מתוך `progress/10`) שאפשר לעבור ביניהם צעד-צעד, עם קוד ה-JSON האמיתי בכל שלב. פותחים ישירות בדפדפן (double-click על הקובץ, או `start progress/Demo/request-pipeline.html` ב-Windows).

## דרישות סביבה

- Python 3.11+ (פותח ונבדק על 3.14)
- מפתח API אחד לפחות: Gemini (`GEMINI_API_KEY`) או Groq (`GROQ_API_KEY`) — שימו לב: הקוד הנוכחי (`src/llm.py`) מכיר בפועל ספק בשם `grok` שמצביע ל-xAI (`XAI_API_KEY`, `api.x.ai`), לא ל-Groq. אם תשתמשו ב-`GROQ_API_KEY`, תדרש הוספת קונפיגורציית ספק Groq בפועל ל-`llm.py` לפני שזה יעבוד.

## התקנה

```bash
cd matrix-ai-service
python -m venv .venv        # יוצר סביבה וירטואלית מבודדת בתיקיית .venv/
```

הפעלת הסביבה הווירטואלית (תלוי בשל שבו מריצים):
```bash
# Windows – PowerShell
.venv\Scripts\Activate.ps1

# Windows – Git Bash
source .venv/Scripts/activate

# macOS / Linux
source .venv/bin/activate
```
לאחר ההפעלה שורת הפרומפט תתחיל ב-`(.venv)`. `.venv/` לא נכלל בבקרת גרסאות (`.gitignore`).

```bash
pip install -r requirements.txt
cp .env.example .env
# ערכו את .env והכניסו GEMINI_API_KEY=... (או GROQ_API_KEY=...)
```

`.env` **לא** נכלל בבקרת גרסאות (`.gitignore`) — אין בו סיסמאות/מפתחות בהגשה.

## הפעלה

לדוגמאות מלאות עם פלט אמיתי מכל 10 מקרי הבדיקה (כולל שאלת הבהרה + הרצה חוזרת עם `--context`, תקלה מדומה, ובדיקת מסד הנתונים) — ראו [`progress/10-בדיקות-ותוצאות.md`](progress/10-בדיקות-ותוצאות.md) (עברית) / [`progress/en/10-tests-and-results.md`](progress/en/10-tests-and-results.md) (אנגלית). לתצוגה ויזואלית של אותה זרימה בלי להריץ כלום — [`progress/Demo/request-pipeline.html`](progress/Demo/request-pipeline.html). למטה רק תמצית פקודות:

```bash
# בקשה בסיסית
python run.py C-101 "אני רוצה לבטל את הזמנה ORD-1001."

# תשובת המשך להבהרה, עם הקשר מהשיחה הקודמת
python run.py C-101 "לא נפתח" --context "return:ORD-1003"

# דימוי כשל שירות הזמנות
python run.py C-101 "..." --simulate-outage

# עם לוגים (ספק, latency, guard) ל-stderr
python run.py C-101 "..." -v

# תאריך קובע אחר (ברירת מחדל: 2026-09-22, תאריך הבדיקה מהמטלה)
python run.py C-101 "..." --today 2026-09-22
```

הפלט הוא JSON יחיד ל-stdout: `intent`, `action`, `reply`, `order_id`, `source_ids`, `service_request`, `reason`.

בדיקות יחידה (קוד בלבד, בלי מודל — 14 בדיקות על טבלת ההחלטות ב-`tests/test_policy_engine.py`, פירוט ב-[`progress/12-בדיקות-יחידה.md`](progress/12-בדיקות-יחידה.md)) — מריצים מתיקיית `matrix-ai-service/` (לא מתוך `tests/`), ודרך `python -m` כדי להימנע מבעיות launcher כשיש כמה התקנות Python במחשב:
```bash
python -m pytest
```

## מבנה הפרויקט

```
data/orders.json, policies.json     נתוני הבדיקה — מהמטלה, ללא שינוי מלבד פורמט תאריך
data/service_requests.db            נוצר אוטומטית בהרצה ראשונה (SQLite)
src/models.py                       חוזי נתונים (Pydantic)
src/policy_engine.py                טבלת ההחלטות (קוד דטרמיניסטי)
src/order_service.py                שליפת הזמנה מדומה + בדיקת בעלות
src/service_requests.py             פתיחת בקשת שירות מדומה → SQLite, אידמפוטנטי
src/llm.py                          לקוח OpenAI-compatible + שרשרת ספקים
src/prompts.py                      פרומפט חילוץ (עם few-shot) + פרומפט ניסוח
src/reply_guard.py                  בדיקה דטרמיניסטית של התשובה + תבנית fallback
src/agent.py                        התזמור — מחבר הכול לזרימה אחת
run.py                              CLI
tests/test_policy_engine.py         14 בדיקות יחידה על טבלת ההחלטות, בלי מודל
progress/                           תיעוד שלב-אחר-שלב בעברית, כל החלטה מצוטטת מהמקור
progress/en/                        אותו תיעוד באנגלית
progress/Demo/request-pipeline.html דף HTML עצמאי — תצוגה ויזואלית של הזרימה, בלי הרצה
```

## תוצאות בדיקות

כל 8 מקרי המטלה + 2 מקרים נוספים הורצו בפועל מול **Gemini 3.1 Flash-Lite** (לא סימולציה) — כולם עברו. טבלה מלאה, כולל דוגמת הרצה עם רשומת בקשת שירות שנוצרה, ב-[`progress/10-בדיקות-ותוצאות.md`](progress/10-בדיקות-ותוצאות.md) (עברית) / [`progress/en/10-tests-and-results.md`](progress/en/10-tests-and-results.md) (אנגלית).

**שיפור אחד בעקבות בדיקה (נדרש במטלה):** מקרה 5 (החזרה, מצב מוצר לא ידוע) נפל בהתחלה ל-fallback גנרי במקום לשאול שאלה ממוקדת, כי ה-Guard פסל תאריך תקין שנכתב בפורמט שונה מ"חבילת העובדות" (`12.09.2026` מול `2026-09-12`) — false positive. אובחן, תוקן (נרמול תאריכים ב-`reply_guard.py`), ואומת מחדש. פירוט מלא, כולל שיפור שני שנמצא באותה סבב, באותו קובץ תוצאות.

## כלי AI שנעזרתי בהם ואיך אימתתי

| כלי | שימוש בפועל | איך אימתתי |
| --- | --- | --- |
| Claude (Sonnet 5, Claude Code) | ניתוח המטלה, כתיבת מסמך התכנון, כתיבת כל הקוד, אבחון ותיקון באגים, כתיבת התיעוד | כל קובץ קוד עבר `py_compile` מיד עם הכתיבה. כל החלטה תוכננה מול שני קבצי המקור ותועדה עם ציטוט שורה; היכן שלא היה מקור מפורש — סומן ככה במפורש. |
| Gemini 3.1 Flash-Lite | מודל הריצה בפועל בפתרון (חילוץ + ניסוח), בכל 10 מקרי הבדיקה | הרצה אמיתית מול ה-API על כל המקרים; פלט מובנה עבר ולידציית Pydantic, תשובה חופשית עברה Reply Guard דטרמיניסטי. |
| בדיקת תיעוד חי של Google | בחירת גרסת מודל (3.1 Flash-Lite ולא 3.5) | לא הוסתמך על ידע מאומן מראש — נבדק מול `aistudio.google.com`/`ai.google.dev` בזמן ההרצה, כי שמות/מחירי דגמים משתנים. |

פירוט מלא: `Docs/AI_Service_Assistant_Design.md`, סעיף 23; ובחירת המודל הספציפית — [`progress/09-בחירת-מודל-ואבטחה.md`](progress/09-בחירת-מודל-ואבטחה.md).

## מגבלות ידועות

- מדיניות "לא נפתח" מבוססת הצהרת לקוח, לא מאומתת (בייצור: אימות בקליטת ההחזרה).
- ייצור מזהה בקשת שירות לא בטוח תחת כתיבה מקבילה (מגבלת אבטיפוס חד-משתמש; פירוט ותוכנית תיקון: `Docs/AI_Service_Assistant_Design.md` סעיף 24 ו-[`progress/11-שדרוג-לרב-משתמשים.md`](progress/11-שדרוג-לרב-משתמשים.md)).
- מעבדת הערכה מקומית (ריבוי-ניסוחים, השוואת ספקים) לא בוצעה — הרחבה אופציונלית, לא ליבת המטלה.

תיעוד מלא, שלב-אחר-שלב, של כל החלטה ולמה נבחרה: תיקיית [`progress/`](progress/) (עברית) ו-[`progress/en/`](progress/en/) (אנגלית).
