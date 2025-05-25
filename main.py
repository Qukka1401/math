from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
import json
import io
import unicodedata

app = FastAPI()

# Загрузка параметров перехода
try:
    with open("parameters.json", "r", encoding="utf-8") as f:
        parameters = json.load(f)
except FileNotFoundError:
    raise HTTPException(status_code=500, detail="Файл parameters.json не найден")
except json.JSONDecodeError:
    raise HTTPException(status_code=500, detail="Ошибка в формате файла parameters.json")

# Нормализация строк для устранения проблем с кодировкой
def normalize_string(s: str) -> str:
    """Normalize string to remove potential encoding or whitespace issues."""
    return unicodedata.normalize("NFC", s.strip())

@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    from_system: str = "СК-42",
    to_system: str = "ГСК-2011"
):
    # Нормализация входных параметров
    from_system = normalize_string(from_system)
    to_system = normalize_string(to_system)

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

        # Проверка наличия системы в parameters.json
        normalized_parameters = {normalize_string(key): value for key, value in parameters.items()}
        if from_system not in normalized_parameters:
            raise HTTPException(status_code=400, detail=f"Система {from_system} не найдена в параметрах")
        if to_system not in normalized_parameters:
            raise HTTPException(status_code=400, detail=f"Система {to_system} не найдена в параметрах")

        converted = []

        for _, row in df.iterrows():
            X, Y, Z = row['X'], row['Y'], row['Z']

            if to_system == normalize_string("ГСК-2011"):
                p = normalized_parameters[from_system]
                res = convert_coordinates(X, Y, Z,
                                        p["dX"], p["dY"], p["dZ"],
                                        np.radians(p["wx"] / 3600),
                                        np.radians(p["wy"] / 3600),
                                        np.radians(p["wz"] / 3600),
                                        p["m"],
                                        to_gsk=True)
            elif from_system == normalize_string("ГСК-2011"):
                p = normalized_parameters[to_system]
                res = convert_coordinates(X, Y, Z,
                                        p["dX"], p["dY"], p["dZ"],
                                        np.radians(p["wx"] / 3600),
                                        np.radians(p["wy"] / 3600),
                                        np.radians(p["wz"] / 3600),
                                        p["m"],
                                        to_gsk=False)
            else:
                # Переход через ГСК-2011
                p_from = normalized_parameters[from_system]
                X1, Y1, Z1 = convert_coordinates(X, Y, Z,
                                                p_from["dX"], p_from["dY"], p_from["dZ"],
                                                np.radians(p_from["wx"] / 3600),
                                                np.radians(p_from["wy"] / 3600),
                                                np.radians(p_from["wz"] / 3600),
                                                p_from["m"],
                                                to_gsk=True)

                p_to = normalized_parameters[to_system]
                res = convert_coordinates(X1, Y1, Z1,
                                        p_to["dX"], p_to["dY"], p_to["dZ"],
                                        np.radians(p_to["wx"] / 3600),
                                        np.radians(p_to["wy"] / 3600),
                                        np.radians(p["wz"] / 3600),
                                        p_to["m"],
                                        to_gsk=False)

            converted.append(res)

        # Формулы преобразования в LaTeX
        to_GSK_LaTeX = r"""
        \begin{equation}
        \begin{bmatrix}
        X_{ГСК} \\
        Y_{ГСК} \\
        Z_{ГСК}
        \end{bmatrix}
        = (1 + m)
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
        \end{equation}
        """

        from_GSK_LaTeX = r"""
        \begin{equation}
        \begin{bmatrix}
        X \\
        Y \\
        Z
        \end{bmatrix}
        = (1 - m)
        \begin{bmatrix}
        1 & -\omega_z & \omega_y \\
        \omega_z & 1 & -\omega_x \\
        -\omega_y & \omega_x & 1
        \end{bmatrix}
        \begin{bmatrix}
        X_{ГСК} \\
        Y_{ГСК} \\
        Z_{ГСК}
        \end{bmatrix}
        -
        \begin{bmatrix}
        \Delta X \\
        \Delta Y \\
        \Delta Z
        \end{bmatrix}
        \end{equation}
        """

        # Подстановка параметров
        p_from = normalized_parameters[from_system]
        to_GSK_LaTeX_subs = r"""
        \begin{equation}
        \begin{bmatrix}
        X_{ГСК} \\
        Y_{ГСК} \\
        Z_{ГСК}
        \end{bmatrix}
        = (1 + %s)
        \begin{bmatrix}
        1 & %s & -%s \\
        -%s & 1 & %s \\
        %s & -%s & 1
        \end{bmatrix}
        \begin{bmatrix}
        X \\
        Y \\
        Z
        \end{bmatrix}
        +
        \begin{bmatrix}
        %s \\
        %s \\
        %s
        \end{bmatrix}
        \end{equation}
        """ % (
            p_from["m"],
            np.radians(p_from["wz"] / 3600),
            np.radians(p_from["wy"] / 3600),
            np.radians(p_from["wz"] / 3600),
            np.radians(p_from["wx"] / 3600),
            np.radians(p_from["wy"] / 3600),
            np.radians(p_from["wx"] / 3600),
            p_from["dX"],
            p_from["dY"],
            p_from["dZ"]
        )

        p_to = normalized_parameters[to_system]
        from_GSK_LaTeX_subs = r"""
        \begin{equation}
        \begin{bmatrix}
        X \\
        Y \\
        Z
        \end{bmatrix}
        = (1 - %s)
        \begin{bmatrix}
        1 & -%s & %s \\
        %s & 1 & -%s \\
        -%s & %s & 1
        \end{bmatrix}
        \begin{bmatrix}
        X_{ГСК} \\
        Y_{ГСК} \\
        Z_{ГСК}
        \end{bmatrix}
        -
        \begin{bmatrix}
        %s \\
        %s \\
        %s
        \end{bmatrix}
        \end{equation}
        """ % (
            p_to["m"],
            np.radians(p_to["wz"] / 3600),
            np.radians(p_to["wy"] / 3600),
            np.radians(p_to["wz"] / 3600),
            np.radians(p_to["wx"] / 3600),
            np.radians(p_to["wy"] / 3600),
            np.radians(p_to["wx"] / 3600),
            p_to["dX"],
            p_to["dY"],
            p_to["dZ"]
        )

        # Формирование отчета в Markdown
        report_content = f"# Отчет по преобразованию координат\n\n"
        report_content += f"## Общая формула преобразования\n\n"
        if from_system != normalize_string("ГСК-2011"):
            report_content += f"### Формула для перевода в систему ГСК-2011\n\n{to_GSK_LaTeX}\n\n"
        if to_system != normalize_string("ГСК-2011"):
            report_content += f"### Формула для перевода из системы ГСК-2011\n\n{from_GSK_LaTeX}\n\n"

        report_content += f"## Формула с подставленными параметрами\n\n"
        if from_system != normalize_string("ГСК-2011"):
            report_content += f"### Перевод из {from_system} в ГСК-2011\n\n{to_GSK_LaTeX_subs}\n\n"
        if to_system != normalize_string("ГСК-2011"):
            report_content += f"### Перевод из ГСК-2011 в {to_system}\n\n{from_GSK_LaTeX_subs}\n\n"

        # Таблица исходных координат
        report_content += f"## Таблица координат в системе {from_system}\n\n"
        report_content += "| Начальный X | Начальный Y | Начальный Z |\n"
        report_content += "|-------------|-------------|-------------|\n"
        for _, row in df.iterrows():
            report_content += f"| {row['X']:.3f} | {row['Y']:.3f} | {row['Z']:.3f} |\n"

        # Таблица преобразованных координат
        result_df = pd.DataFrame(converted, columns=["X", "Y", "Z"])
        report_content += f"## Таблица координат в системе {to_system}\n\n"
        report_content += "| Конечный X | Конечный Y | Конечный Z |\n"
        report_content += "|------------|------------|------------|\n"
        for _, row in result_df.iterrows():
            report_content += f"| {row['X']:.3f} | {row['Y']:.3f} | {row['Z']:.3f} |\n"

        report_content += f"## Вывод\n\n"
        report_content += "Процесс преобразования координат выполнен успешно. Результаты представлены в таблицах выше."

        # Запись отчета в файл
        with open('report.md', 'w', encoding='utf-8') as f:
            f.write(report_content)

        # CSV в строку
        stream = io.StringIO()
        result_df.to_csv(stream, index=False)

        # Markdown-отчет для ответа (без заголовка "Результат преобразования")
        report_md = f"""
### Исходная система: `{from_system}`
### Целевая система: `{to_system}`

#### Первые 5 строк результата:
{result_df.head().to_markdown(index=False)}
"""

        # Отладочная информация
        print(f"Request received: from_system={from_system}, to_system={to_system}")
        print(f"Available systems: {list(normalized_parameters.keys())}")
        print("Response prepared with markdown_report")

        return JSONResponse(content={
            "csv": stream.getvalue(),
            "report": report_md,
            "markdown_report": report_content  # Полный отчет для скачивания
        })

    except Exception as e:
        print(f"Error occurred: {str(e)}")  # Логирование ошибки
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")

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