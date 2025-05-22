import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os

# --- Streamlit Config (debe ir primero) ---
st.set_page_config(page_title="Blasting WebApp", layout="wide")

# --- Autenticación ---
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SPREADSHEET_NAME = 'Blasting tracker'

if os.path.exists("blasting-credentials.json"):
    creds = ServiceAccountCredentials.from_json_keyfile_name("blasting-credentials.json", SCOPE)
else:
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)

client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)

# --- Selección de hoja ---
hojas_disponibles = [ws.title for ws in spreadsheet.worksheets() if "/" in ws.title or ws.title.lower() == "draft"]
hojas_disponibles.sort(key=lambda x: x if x.lower() == "draft" else pd.to_datetime(x, dayfirst=True), reverse=True)
hoja_seleccionada = st.selectbox("📅 Select date", hojas_disponibles, index=0)
sheet = spreadsheet.worksheet(hoja_seleccionada)
data = sheet.get_all_records()

# --- Preparar DataFrame ---
df = pd.DataFrame(data)
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_").str.replace("-", "_").str.replace("(", "").str.replace(")", "")
df = df[df['tracking_id'] != '']

money_cols = [
    'margin', 'bonus_driver1', 'bonus_driver2', 'est_charge',
    'base_driver_earnings_1', 'base_driver_earnings_2',
    'current_driver_earnings_1', 'current_driver_earnings_2',
    'total_current_earnings'
]
for col in money_cols:
    if col in df.columns:
        df[col] = df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '').replace('', '0').astype(float)

# --- LOGO + TÍTULO ---
st.image("https://i.imgur.com/s2bcjYq.png", width=140)
st.markdown("<h1 style='text-align: center; color: #004aad;'>🚚 Bungii Blasting Tracker</h1>", unsafe_allow_html=True)
st.caption(f"📅 Sheet: `{hoja_seleccionada}`")
st.markdown("---")

# --- Filtros ---
st.markdown("### 🎛️ Filters")
filtros = st.columns([1.5, 1.5, 1.5, 2])

unique_blasters = df['blaster'].dropna().unique().tolist()
selected_blaster = filtros[0].selectbox("👤 Blaster", ["All"] + sorted(unique_blasters))
if selected_blaster != "All":
    df = df[df['blaster'] == selected_blaster]

markets = df['market'].dropna().unique().tolist()
selected_market = filtros[1].selectbox("🌎 Market", ["All"] + sorted(markets))
if selected_market != "All":
    df = df[df['market'] == selected_market]

statuses = df['status'].dropna().str.capitalize().unique().tolist()
selected_status = filtros[2].selectbox("🚦 Status", ["All"] + sorted(statuses))
if selected_status != "All":
    df = df[df['status'].str.capitalize() == selected_status]

filtros[3].markdown("[📄 Ver Active Drivers](https://docs.google.com/spreadsheets/d/1H-iMzmnnWsevIzjbW1QOwIqcy4zTV1eRaJSteRfZiwg/edit?usp=sharing)")

# --- KPIs ---
st.markdown("### 📊 KPIs")
total_trips = len(df)
assigned = df[df['status'].str.lower() == "assigned"]
assigned_pct = round((len(assigned) / total_trips) * 100, 1) if total_trips else 0
avg_margin = round(df['margin'].mean(), 2) if not df['margin'].isnull().all() else 0

k1, k2, k3 = st.columns(3)
k1.metric("🧾 Total trips", total_trips)
k2.metric("✅ Assigned (%)", f"{assigned_pct}%")
k3.metric("💰 Avg. margin", f"${avg_margin}")

# --- VIAJES ---
st.markdown("### 🗂️ Status")

status_colors = {
    'pending': '#FFD43B',
    'blasting': '#FFA500',
    'assigned': '#00C49A',
    'dropped': '#FF6B6B'
}

for status in ['pending', 'blasting', 'assigned', 'dropped']:
    section_df = df[df['status'].str.lower() == status]
    if not section_df.empty:
        color = status_colors.get(status.lower(), '#DDDDDD')
        st.markdown(f"<h3 style='color:{color}'>{status.capitalize()} ({len(section_df)})</h3>", unsafe_allow_html=True)

        for i, row in section_df.iterrows():
            tracking = row.get("tracking_id", f"Row {i}")
            st.markdown("---")
            st.markdown(f"### 🚚 {tracking} | {row.get('market', '')} | {row.get('partner', '')}")

            with st.expander("🔍 View details", expanded=False):
                st.write(f"**Stage:** {row.get('blasting_stage', '')}")
                st.write(f"**Delivery (CST):** {row.get('delivery_datetime_cst', '')}")
                st.write(f"**Type of Delivery:** {row.get('type_of_delivery', '')}")
                st.write(f"**Base Earnings 1:** ${row.get('base_driver_earnings_1', 0):.2f}")
                st.write(f"**Current Earnings 1:** ${row.get('current_driver_earnings_1', 0):.2f}")
                st.write(f"**Margin:** ${row.get('margin', 0):.2f}")
                st.write(f"**Driver Assigned:** {row.get('driver_assigned', '')}")
                st.write(f"**Blaster:** {row.get('blaster', '')}")
                st.write(f"**Comments:** {row.get('comments', '')}")

            with st.expander("✏️ Edit travel", expanded=False):
                with st.form(f"edit_form_{tracking}"):
                    new_status = st.selectbox("Status", ["Pending", "Blasting", "Assigned", "Dropped"], index=["Pending", "Blasting", "Assigned", "Dropped"].index(row.get("status", "Pending").capitalize()))
                    new_stage = st.selectbox("Blasting Stage", ["Initial offer", "Bonus adjustment", "Follow - up", "Assigned"], index=["Initial offer", "Bonus adjustment", "Follow - up", "Assigned"].index(row.get("blasting_stage", "Initial offer")))
                    new_est_charge = st.number_input("Est. Charge", value=row.get("est_charge", 0.0), step=1.0)
                    new_base_1 = st.number_input("Base Driver Earnings 1", value=row.get("base_driver_earnings_1", 0.0), step=1.0)
                    new_base_2 = st.number_input("Base Driver Earnings 2", value=row.get("base_driver_earnings_2", 0.0), step=1.0)
                    new_current_1 = st.number_input("Current Driver Earnings 1", value=row.get("current_driver_earnings_1", 0.0), step=1.0)
                    new_current_2 = st.number_input("Current Driver Earnings 2", value=row.get("current_driver_earnings_2", 0.0), step=1.0)
                    new_driver_assigned = st.text_input("Driver Assigned", value=row.get("driver_assigned", ""))
                    submitted = st.form_submit_button("💾 Save changes")

                if submitted:
                    if any(val <= 0 for val in [new_est_charge, new_base_1, new_current_1]):
                        st.warning("⚠️ No se pueden guardar valores vacíos o en cero en campos clave.")
                    else:
                        try:
                            cell = sheet.find(tracking)
                            row_number = cell.row
                            updates = {
                                'status': new_status,
                                'blasting_stage': new_stage,
                                'est_charge': new_est_charge,
                                'base_driver_earnings_1': new_base_1,
                                'base_driver_earnings_2': new_base_2,
                                'current_driver_earnings_1': new_current_1,
                                'current_driver_earnings_2': new_current_2,
                                'driver_assigned': new_driver_assigned,
                            }
                            headers = df.columns.tolist()
                            for key, val in updates.items():
                                if key in headers:
                                    col_index = headers.index(key) + 1
                                    sheet.update_cell(row_number, col_index, val)

                            st.success(f"✅ Cambios guardados para {tracking}")
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error al guardar cambios: {e}")