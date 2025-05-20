import streamlit as st
import requests
import pandas as pd
import io

# Настройка страницы
st.set_page_config(page_title="Конвертер координат", page_icon="🌍", layout="centered")

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
    </style>
""", unsafe_allow_html=True)

# URL бэкенда
BACKEND_URL = "https://math-zz0z.onrender.com/convert"

# Заголовок
st.title("Конвертер координат")

# Загрузка файла
uploaded_file = st.file_uploader("Выберите Excel-файл (.xlsx)", type=["xlsx", "xls"])

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

                # Отчет
                st.markdown("### Результат преобразования:")
                st.markdown(result["report"])

                # Первые 5 строк
                df = pd.read_csv(io.StringIO(result["csv"]))
                st.markdown("### Первые 5 строк:")
                st.dataframe(df.head())

                # Кнопка скачивания
                st.download_button(
                    label="Скачать CSV",
                    data=result["csv"],
                    file_name="converted_coordinates.csv",
                    mime="text/csv"
                )
            else:
                st.error(f"Ошибка: {response.json().get('detail', 'Неизвестная ошибка')}")
        except Exception as e:
            st.error(f"Ошибка: {str(e)}")