# ניסויי Basic Theta*

זהו מאגר נפרד לקוד ולתוצאות של מטלה 10. המימוש עצמו נמצא ב־
`UziaPeer/Python`: ענף `codex/theta-star-implementation` למימוש הרגיל,
וענף `codex/theta-star-performance` ל־cache. אין בפרויקט מימוש AP.

להתקנה מקומית ב־Windows, מתוך תיקיית המאגר:

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

להרצת השוואה קטנה משלכם:

```powershell
./.venv/Scripts/python.exe run.py --sizes 10 20 40 --densities 0 20 --seeds 3 --algorithms astar astar-ps basic --output new_results --direct
./.venv/Scripts/python.exe profile_run.py
```

להשוואה עם ענף השיפור יש לשכפל אותו ליד הסקריפט:

```powershell
git clone --branch codex/theta-star-performance https://github.com/UziaPeer/Python.git theta-star-performance
./.venv/Scripts/python.exe run.py --sizes 80 150 300 600 1000 --densities 20 --seeds 2 --algorithms basic basic-cached --optimized-file theta-star-performance/graphs/theta_star_cached.py --output new_cache_results --direct
```

`experiments-csv` שומר את ההרצות ב־CSV, לכן לתוצאה חדשה משתמשים
בתיקיית `--output` חדשה. כל seed נותן את אותה מפה לכל השיטות.
לא מובטח שיש מסלול; `no_path` ו־`timeout` נשמרים ב־CSV.
`seconds` מודד חיפוש, ו־`total_seconds` כולל גם בניית גרף מפורש
עבור A* של NetworkX. זו אינה שחזור מדויק של זמני המאמר.

ברירת המחדל מגבילה כל הרצה ל־60 שניות בתהליך נפרד. `--direct`
מיועד רק לניסויים קטנים ומהירים. התוצאות שפורסמו נמצאות בתיקיות
`thealgorithms_results/`, `thealgorithms_cache_v3/`,
`thealgorithms_limit_large/`, `thealgorithms_limit_cached/` ו־
`thealgorithms_profile/`. הסיכום נמצא ב־`report_he.md`.
