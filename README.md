# עוזר AI לשירות לקוחות באתר מסחר

אבטיפוס שמקבל פנייה חופשית של לקוח מחובר, מבין אותה באמצעות מודל שפה, ומקבל **החלטה דטרמיניסטית בקוד** על סמך מדיניות השירות ונתוני ההזמנה. העיקרון המרכזי: **המודל מבין ומנסח; הקוד מחליט ומבצע**.

הוגש כמענה למטלת "עוזר AI לשירות באתר מסחר" של מטריקס דיגיטל.

## מבנה המאגר

```
Docs/AI_Service_Assistant_Design.md   מסמך התכנון המלא — ארכיטקטורה, טבלת החלטות, פרומפטים, תוכנית בדיקות
matrix-ai-service/                    הקוד, הבדיקות, התיעוד וההדגמה — כאן נמצא כל הפתרון בפועל
```

מסמך המטלה המקורית (`AIEngineerTest.md`) אינו כלול במאגר — זהו תוכן המטלה עצמו, לא תוצר של הפתרון.

## התחלה מהירה

- **הוראות הפעלה מלאות** (התקנה, סביבה וירטואלית, הרצה, בדיקות): [`matrix-ai-service/README.md`](matrix-ai-service/README.md)
- **הדגמה ויזואלית** בלי צורך להריץ כלום — פותחים ישירות בדפדפן: [`matrix-ai-service/progress/Demo/request-pipeline.html`](matrix-ai-service/progress/Demo/request-pipeline.html)
- **תוצאות בדיקות מלאות** (10 מקרים, הורצו בפועל מול Gemini): [`matrix-ai-service/progress/10-בדיקות-ותוצאות.md`](matrix-ai-service/progress/10-בדיקות-ותוצאות.md)
- **תיעוד שלב-אחר-שלב** של כל החלטה, מצוטט מהמקור: [`matrix-ai-service/progress/`](matrix-ai-service/progress/) (עברית) · [`matrix-ai-service/progress/en/`](matrix-ai-service/progress/en/) (אנגלית)
