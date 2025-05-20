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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))