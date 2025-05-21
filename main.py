from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
import json
import io

app = FastAPI()

# Загрузка параметров перехода
with open("parameters.json", "r") as f:
    parameters = json.load(f)

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

        # CSV в строку
        stream = io.StringIO()
        result_df.to_csv(stream, index=False)

        # Markdown-отчет
        report_md = f"""
        ## Результат преобразования

        ### Исходная система: `{from_system}`
        ### Целевая система: `{to_system}`

        #### Первые 5 строк результата:
        {result_df.head().to_markdown(index=False)}
        """

        return JSONResponse(content={
            "csv": stream.getvalue(),
            "report": report_md
        })
        
        # Последовательно сформируем отчет на языке Markdown
        report_content = f"# Отчет по преобразованию координат\n\n"
        report_content += f"## Общая формула по которой производились вычисления\n\n"
        if start_system != "ГСК-2011":
            report_content += f"### формула для перевода в систему ГСК\n"
        report_content += f"{to_GSK_LaTeX}\n\n"
        if end_system != "ГСК-2011":
            report_content += f"### формула для перевода из системы ГСК\n"
        report_content += f"{from_GSK_LaTeX}\n\n"
        report_content += f"## Общая формула с подставленными в нее параметрами перехода между выбранными системами.\n\n"
        if start_system != "ГСК-2011":
            report_content += f"### формула для перевода {start_system} в ГСК\n\n"
        report_content += f"{to_GSK_LaTeX_subs}\n\n"
        if end_system != "ГСК-2011":
            report_content += f"### формула для перевода ГСК в {end_system}\n\n"
        report_content += f"{from_GSK_LaTeX_subs}\n\n"
        report_content += f"# Итог\n\n"

        report_content += f"## Таблица координат {start_system}\n\n"
        report_content += "| Начальный X | Начальный Y | Начальный Z |\n"
        report_content += "| --- | --- | --- |\n"
        for index, row in start_df.iterrows():
            report_content += f"| {row[1]} | {row[2]} | {row[3]} |\n"

        report_content += f"## Таблица координат {end_system}\n\n"
        report_content += "| Конечный X | Конечный Y | Конечный Z |\n"
        report_content += "| --- | --- | --- |\n"
        print(transformed_df)
        for index, row in transformed_df.iterrows():
            report_content += f"| {row[0]} | {row[1]} | {row[2]} |\n"

        report_content += f"## Вывод\n\n"
        report_content += "Процесс преобразования координат был успешно выполнен, с результатами, представленными выше."

        with open('report.md', 'w') as f:
            # Записываем отчет
            f.write(report_content)
        print(radians(parameters[start_system]['wz']/3600))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))