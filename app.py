import streamlit as st
import requests
import pandas as pd
import io

# Укажите URL вашего FastAPI-бэкенда
BACKEND_URL = "http://localhost:8000/convert"

# st.set_page_config(page_title="Конвертер координат", layout="centered")

# Заголовок и описание
st.title("Конвертер координат между системами")
st.markdown("Загрузите Excel-файл с координатами и выберите системы для преобразования.")

# Загрузка файла
uploaded_file = st.file_uploader("Выберите Excel-файл (.xlsx)", type=["xlsx", "xls"])

# Выбор систем
systems = ["СК-42", "СК-95", "ПЗ-90", "ПЗ-90.02", "ПЗ-90.11", "WGS-84", "ITRF-2008"]
from_system = st.selectbox("Исходная система:", systems)
to_system = st.selectbox("Целевая система:", ["ГСК-2011"])

# Кнопка запуска преобразования
if uploaded_file and st.button("Выполнить преобразование"):
    with st.spinner("Преобразование данных..."):
        try:
            # Подготовка данных
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            data = {"from_system": from_system, "to_system": to_system}

            # Отправка запроса на бэкенд
            response = requests.post(BACKEND_URL, data=data, files=files)

            if response.status_code == 200:
                result = response.json()

                # Отображение отчета
                st.markdown("### Отчет о преобразовании:")
                st.markdown(result["report"])

                # Отображение первых строк
                df = pd.read_csv(io.StringIO(result["csv"]))
                st.markdown("### Первые 5 строк результата:")
                st.dataframe(df.head())

                # Кнопка загрузки
                st.download_button(
                    label="Скачать результат в CSV",
                    data=result["csv"],
                    file_name="converted_coordinates.csv",
                    mime="text/csv"
                )
            else:
                error = response.json().get("detail", "Неизвестная ошибка")
                st.error(f" Ошибка при обработке данных: {error}")

        except Exception as e:
            st.error(f" Произошла ошибка: {str(e)}")