from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
import json
import io

app = FastAPI()

# Загрузка параметров перехода
try:
    with open("parameters.json", "r") as f:
        parameters = json.load(f)
except FileNotFoundError:
    raise HTTPException(status_code=500, detail="Файл parameters.json не найден")

def convert_coordinates(X, Y, Z, dX, dY, dZ, wx, wy, wz, m, to_gsk):
    """Преобразует координаты между системами"""
    if not to_gsk:
        m = -m
        wx, wy, wz = -wx, -wy, -wz
        dX, dY, dZ = -dX, -dY, -dZ

    R = np.array([
        [1, wz, -wy],
        [-wz, 1, wx],
        [wy, -wx, 1]
    ])

    input_coords = np.array([X, Y, Z])
    transformed = (1 + m) * R @ input_coords + np.array([dX, dY, dZ])
    return transformed[0], transformed[1], transformed[2]

@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    from_system: str = "СК-42",
    to_system: str = "ГСК-2011"
):
    # Проверка формата файла
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Требуется файл Excel (.xlsx или .xls)")

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))

        # Проверка наличия нужных колонок
        required_columns = ['X', 'Y', 'Z']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(status_code=400, detail=f"Файл должен содержать колонки: {required_columns}")

        converted = []

        for _, row in df.iterrows():
            X, Y, Z = row['X'], row['Y'], row['Z']

            if to_system == "ГСК-2011":
                p = parameters[from_system]
                res = convert_coordinates(X, Y, Z,
                                         p["dX"], p["dY"], p["dZ"],
                                         np.radians(p["wx"] / 3600),
                                         np.radians(p["wy"] / 3600),
                                         np.radians(p["wz"] / 3600),
                                         p["m"],
                                         to_gsk=True)
            elif from_system == "ГСК-2011":
                p = parameters[to_system]
                res = convert_coordinates(X, Y, Z,
                                         p["dX"], p["dY"], p["dZ"],
                                         np.radians(p["wx"] / 3600),
                                         np.radians(p["wy"] / 3600),
                                         np.radians(p["wz"] / 3600),
                                         p["m"],
                                         to_gsk=False)
            else:
                # Переход через ГСК-2011
                p_from = parameters[from_system]
                X1, Y1, Z1 = convert_coordinates(X, Y, Z,
                                                p_from["dX"], p_from["dY"], p_from["dZ"],
                                                np.radians(p_from["wx"] / 3600),
                                                np.radians(p_from["wy"] / 3600),
                                                np.radians(p_from["wz"] / 3600),
                                                p_from["m"],
                                                to_gsk=True)

                p_to = parameters[to_system]
                res = convert_coordinates(X1, Y1, Z1,
                                         p_to["dX"], p_to["dY"], p_to["dZ"],
                                         np.radians(p_to["wx"] / 3600),
                                         np.radians(p_to["wy"] / 3600),
                                         np.radians(p_to["wz"] / 3600),
                                         p_to["m"],
                                         to_gsk=False)

            converted.append(res)

        result_df = pd.DataFrame(converted, columns=["X", "Y", "Z"])

        # Формирование отчета на языке Markdown
        report_content = f"# Отчет по преобразованию координат\n\n"
        report_content += f"## Параметры преобразования\n\n"
        report_content += f"- **Исходная система**: {from_system}\n"
        report_content += f"- **Целевая система**: {to_system}\n\n"

        # Общая формула
        report_content += f"## Общая формула преобразования\n\n"
        report_content += r"""
Формула преобразования координат:
\[
\begin{bmatrix}
X' \\
Y' \\
Z'
\end{bmatrix}
=
(1 + m)
\begin{bmatrix}
1 & \omega_z & -\omega_y \\
-\omega_z & 1 & \omega_x \\
\omega_y & -\omega_x & 1
\end{bmatrix}
\begin{bmatrix}
X \\
Y \\
Z
\end{bmatrix}
+
\begin{bmatrix}
\Delta X \\
\Delta Y \\
\Delta Z
\end{bmatrix}
\]
где:
- \(X, Y, Z\) — исходные координаты,
- \(X', Y', Z'\) — преобразованные координаты,
- \(\Delta X, \Delta Y, \Delta Z\) — параметры смещения,
- \(\omega_x, \omega_y, \omega_z\) — углы поворота (в радианах),
- \(m\) — масштабный коэффициент.
"""

        # Параметры преобразования
        if from_system != "ГСК-2011":
            p_from = parameters[from_system]
            report_content += f"\n### Параметры для перехода {from_system} → ГСК-2011\n\n"
            report_content += f"- ΔX: {p_from['dX']} м\n"
            report_content += f"- ΔY: {p_from['dY']} м\n"
            report_content += f"- ΔZ: {p_from['dZ']} м\n"
            report_content += f"- ωx: {p_from['wx']} угл. сек\n"
            report_content += f"- ωy: {p_from['wy']} угл. сек\n"
            report_content += f"- ωz: {p_from['wz']} угл. сек\n"
            report_content += f"- m: {p_from['m']}\n"

        if to_system != "ГСК-2011":
            p_to = parameters[to_system]
            report_content += f"\n### Параметры для перехода ГСК-2011 → {to_system}\n\n"
            report_content += f"- ΔX: {p_to['dX']} м\n"
            report_content += f"- ΔY: {p_to['dY']} м\n"
            report_content += f"- ΔZ: {p_to['dZ']} м\n"
            report_content += f"- ωx: {p_to['wx']} угл. сек\n"
            report_content += f"- ωy: {p_to['wy']} угл. сек\n"
            report_content += f"- ωz: {p_to['wz']} угл. сек\n"
            report_content += f"- m: {p_to['m']}\n"

        # Таблица исходных координат
        report_content += f"\n## Таблица координат {from_system}\n\n"
        report_content += "| Начальный X | Начальный Y | Начальный Z |\n"
        report_content += "|-------------|-------------|-------------|\n"
        for _, row in df.iterrows():
            report_content += f"| {row['X']:.3f} | {row['Y']:.3f} | {row['Z']:.3f} |\n"

        # Таблица преобразованных координат
        report_content += f"\n## Таблица координат {to_system}\n\n"
        report_content += "| Конечный X | Конечный Y | Конечный Z |\n"
        report_content += "|------------|------------|------------|\n"
        for _, row in result_df.iterrows():
            report_content += f"| {row['X']:.3f} | {row['Y']:.3f} | {row['Z']:.3f} |\n"

        # Вывод
        report_content += f"\n## Вывод\n\n"
        report_content += "Процесс преобразования координат был успешно выполнен, с результатами, представленными выше."

        # Сохранение отчета в файл
        with open('report.md', 'w', encoding='utf-8') as f:
            f.write(report_content)

        # CSV в строку
        stream = io.StringIO()
        result_df.to_csv(stream, index=False)

        # Markdown-отчет для ответа
        report_md = f"""
## Результат преобразования

### Исходная система: `{from_system}`
### Целевая система: `{to_system}`

#### Первые 5 строк результата:
{result_df.head().to_markdown(index=False)}
"""

        return JSONResponse(content={
            "csv": stream.getvalue(),
            "report": report_content
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))