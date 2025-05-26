from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
import json
import io
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Загрузка параметров перехода
try:
    with open("parameters.json", "r", encoding='utf-8') as f:
        parameters = json.load(f)
    logger.info("parameters.json loaded successfully: %s", list(parameters.keys()))
except FileNotFoundError:
    logger.error("parameters.json not found")
    raise HTTPException(status_code=500, detail="Файл parameters.json не найден")
except json.JSONDecodeError:
    logger.error("Invalid format in parameters.json")
    raise HTTPException(status_code=500, detail="Ошибка в формате файла parameters.json")

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
    # Normalize input strings
    from_system = from_system.strip()
    to_system = to_system.strip()
    logger.info("Received request: from_system=%s, to_system=%s", from_system, to_system)

    # Проверка формата файла
    if not file.filename.endswith((".xlsx", ".xls")):
        logger.error("Invalid file format: %s", file.filename)
        raise HTTPException(status_code=400, detail="Требуется файл Excel (.xlsx или .xls)")

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))

        # Проверка наличия нужных колонок
        required_columns = ['X', 'Y', 'Z']
        if not all(col in df.columns for col in required_columns):
            logger.error("Missing required columns: %s", required_columns)
            raise HTTPException(status_code=400, detail=f"Файл должен содержать колонки: {required_columns}")

        # Проверка наличия системы в parameters.json
        parameters_keys = {k.strip().lower(): k for k in parameters.keys()}
        from_system_key = next((k for k in parameters_keys if k.lower() == from_system.lower()), None)
        to_system_key = next((k for k in parameters_keys if k.lower() == to_system.lower()), None)

        if from_system_key is None:
            logger.error("System not found: %s", from_system)
            raise HTTPException(status_code=400, detail=f"Система {from_system} не найдена в параметрах")
        if to_system_key is None:
            logger.error("System not found: %s", to_system)
            raise HTTPException(status_code=400, detail=f"Система {to_system} не найдена в параметрах")

        converted = []

        for _, row in df.iterrows():
            X, Y, Z = row['X'], row['Y'], row['Z']

            if to_system_key == "ГСК-2011":
                p = parameters[from_system_key]
                res = convert_coordinates(X, Y, Z,
                                        p["dX"], p["dY"], p["dZ"],
                                        np.radians(p["wx"] / 3600),
                                        np.radians(p["wy"] / 3600),
                                        np.radians(p["wz"] / 3600),
                                        p["m"],
                                        to_gsk=True)
            elif from_system_key == "ГСК-2011":
                p = parameters[to_system_key]
                res = convert_coordinates(X, Y, Z,
                                        p["dX"], p["dY"], p["dZ"],
                                        np.radians(p["wx"] / 3600),
                                        np.radians(p["wy"] / 3600),
                                        np.radians(p["wz"] / 3600),
                                        p["m"],
                                        to_gsk=False)
            else:
                p_from = parameters[from_system_key]
                X1, Y1, Z1 = convert_coordinates(X, Y, Z,
                                                p_from["dX"], p_from["dY"], p_from["dZ"],
                                                np.radians(p_from["wx"] / 3600),
                                                np.radians(p_from["wy"] / 3600),
                                                np.radians(p_from["wz"] / 3600),
                                                p_from["m"],
                                                to_gsk=True)

                p_to = parameters[to_system_key]
                res = convert_coordinates(X1, Y1, Z1,
                                        p_to["dX"], p_to["dY"], p_to["dZ"],
                                        np.radians(p_to["wx"] / 3600),
                                        np.radians(p_to["wy"] / 3600),
                                        np.radians(p_to["wz"] / 3600),
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
        p_from = parameters[from_system_key]
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

        p_to = parameters[to_system_key]
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
        if from_system_key != "ГСК-2011":
            report_content += f"### Формула для перевода в систему ГСК-2011\n\n{to_GSK_LaTeX}\n\n"
        if to_system_key != "ГСК-2011":
            report_content += f"### Формула для перевода из системы ГСК-2011\n\n{from_GSK_LaTeX}\n\n"

        report_content += f"## Формула с подставленными параметрами\n\n"
        if from_system_key != "ГСК-2011":
            report_content += f"### Перевод из {from_system} в ГСК-2011\n\n{to_GSK_LaTeX_subs}\n\n"
        if to_system_key != "ГСК-2011":
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

        # Краткий отчет для отображения (без исходной и целевой системы)
        report_md = f"""
#### Первые 5 строк результата:
{result_df.head().to_markdown(index=False)}
"""

        logger.info("Request processed successfully, returning response")
        return JSONResponse(content={
            "csv": stream.getvalue(),
            "report": report_md,
            "markdown_report": report_content
        })

    except Exception as e:
        logger.error("Error processing request: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")