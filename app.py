import streamlit as st
import requests
import pandas as pd
import io

# Настройка страницы
st.set_page_config(page_title="Преобразование координатных данных", layout="centered")

# Кастомные стили
st.markdown("""
    <style>
    h1 {
        color: #2c3e50;
        text-align: center;
    }
    .stButton>button {
        background-color: #3498db;
        color: white;
        border-radius: 5px;
    }
    .stButton>button:hover {
        background-color: #2980b9;
    }
    .stFileUploader {
        background-color: #f0faff;
        border: 1px solid #3498db;
        border-radius: 5px;
        padding: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# URL бэкенда
BACKEND_URL = "https://math-zz0z.onrender.com/convert"

# Заголовок
st.title("Преобразование координатных данных")

# Загрузка файла
uploaded_file = st.file_uploader("Загрузите Excel-файл", type=["xlsx", "xls"])

# Выбор систем
systems = ["СК-42", "СК-95", "ПЗ-90", "ПЗ-90.02", "ПЗ-90.11", "WGS-84", "ITRF-2008"]
from_system = st.selectbox("Исходная система:", systems)
to_system = st.selectbox("Целевая система:", ["ГСК-2011"])

# Кнопка преобразования
if uploaded_file and st.button("Преобразовать"):
    with st.spinner("Обработка данных..."):
        try:
            # Подготовка данных
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            data = {"from_system": from_system, "to_system": to_system}

            # Запрос на бэкенд
            response = requests.post(BACKEND_URL, data=data, files=files)

            if response.status_code == 200:
                result = response.json()
                # Отладочный вывод
                st.write("API Response:", result)

                # Проверка наличия необходимых полей
                if "report" not in result:
                    st.error("Ошибка: Поле 'report' отсутствует в ответе API. Пожалуйста, обновите серверную часть приложения.")
                    st.stop()
                if "csv" not in result:
                    st.error("Ошибка: Поле 'csv' отсутствует в ответе API. Пожалуйста, обновите серверную часть приложения.")
                    st.stop()

                # Отображение краткого отчета
                st.markdown(result["report"])

                # Первые 5 строк (таблица уже в result["report"])
                df = pd.read_csv(io.StringIO(result["csv"]))
                st.dataframe(df.head())

                # Кнопка скачивания CSV
                st.download_button(
                    label="Скачать CSV",
                    data=result["csv"],
                    file_name="converted_coordinates.csv",
                    mime="text/csv"
                )

                # Кнопка скачивания Markdown-отчета
                if "markdown_report" in result:
                    st.download_button(
                        label="Скачать отчет в Markdown",
                        data=result["markdown_report"],
                        file_name="report.md",
                        mime="text/markdown"
                    )
                else:
                    st.warning("Markdown-отчет недоступен. Пожалуйста, обновите серверную часть приложения.")
            else:
                st.error(f"Ошибка API: {response.json().get('detail', 'Неизвестная ошибка')}")
        except Exception as e:
            st.error(f"Ошибка: {str(e)}")