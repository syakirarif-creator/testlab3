import streamlit as st
import os
import json
import io
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import ezdxf
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
from folium.plugins import Fullscreen


# =========================================================================
# TETAPAN HALAMAN STREAMLIT
# =========================================================================

st.set_page_config(
    page_title="Sistem Maklumat Geografi",
    page_icon="🗺️",
    layout="wide"
)


# =========================================================================
# SESSION STATE
# =========================================================================

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'proses_aktif' not in st.session_state:
    st.session_state['proses_aktif'] = False


# =========================================================================
# FUNGSI BANTUAN PENGIRAAN GEODESI
# =========================================================================

def kira_bearing_jarak(x, y):

    n = len(x)

    jarak_list = []
    bearing_list = []

    for i in range(n):

        x1, y1 = x[i], y[i]
        x2, y2 = x[(i + 1) % n], y[(i + 1) % n]

        dx = x2 - x1
        dy = y2 - y1

        # Jarak
        jarak = np.sqrt(dx**2 + dy**2)
        jarak_list.append(jarak)

        # Bearing
        sudut_rad = np.arctan2(dx, dy)
        sudut_deg = np.degrees(sudut_rad)

        if sudut_deg < 0:
            sudut_deg += 360

        d = int(sudut_deg)

        minit_total = (sudut_deg - d) * 60
        m = int(minit_total)

        s = round((minit_total - m) * 60, 2)

        bearing_dms = f'{d}° {m:02d}" {s}"'

        bearing_list.append(bearing_dms)

    return jarak_list, bearing_list


# =========================================================================
# FUNGSI GENERATE GEOJSON
# =========================================================================

def generate_geojson(
    x,
    y,
    stesen_nama,
    no_lot,
    nama_pemilik,
    luas
):

    coordinates = [
        [
            [float(x[i]), float(y[i])]
            for i in range(len(x))
        ]
    ]

    # Tutup polygon
    coordinates[0].append(
        [float(x[0]), float(y[0])]
    )

    stesen_clean = [
        int(s) if isinstance(s, (np.integer, int))
        else str(s)
        for s in stesen_nama
    ]

    geojson_data = {

        "type": "FeatureCollection",

        "features": [

            {

                "type": "Feature",

                "geometry": {

                    "type": "Polygon",

                    "coordinates": coordinates

                },

                "properties": {

                    "No_Lot": no_lot,

                    "Pemilik": nama_pemilik,

                    "Luas_m2": float(luas),

                    "Stesen": stesen_clean

                }

            }

        ]

    }

    return json.dumps(
        geojson_data,
        indent=4
    )


# =========================================================================
# FUNGSI GENERATE DXF
# =========================================================================

def generate_dxf(
    x,
    y,
    stesen_nama
):

    doc = ezdxf.new(
        dxfversion='R2010'
    )

    msp = doc.modelspace()

    points = [
        (
            float(x[i]),
            float(y[i]),
            0
        )
        for i in range(len(x))
    ]

    # Tutup polygon
    points.append(points[0])

    msp.add_lwpolyline(points)

    # Label stesen
    for i in range(len(x)):

        msp.add_text(
            f"STN {stesen_nama[i]}",
            dxfattribs={
                'height': 0.5
            }
        ).set_placement(
            (
                float(x[i]) + 0.5,
                float(y[i]) + 0.5,
                0
            )
        )

    stream = io.StringIO()

    doc.write(stream)

    return stream.getvalue()


# =========================================================================
# DASHBOARD UTAMA
# =========================================================================

def main_dashboard():

    st.title(
        "🗺️ Sistem Maklumat Geografi (GIS)"
    )

    st.subheader(
        "Modul Analisis Ukuran & Sempadan Tanah"
    )

    st.write(
        "Sila muat naik fail koordinat CSV anda untuk memulakan tetapan peta."
    )

    uploaded_file = st.file_uploader(
        "Pilih fail CSV",
        type=["csv"]
    )

    # =====================================================================
    # SIDEBAR LOGO
    # =====================================================================

    with st.sidebar:

        logo_path = "Poli_Logo (1).png"

        if os.path.exists(logo_path):

            st.image(
                logo_path,
                width=180
            )

        st.markdown("---")

        st.write(
            f"Pengguna Aktif: "
            f"**{st.session_state.get('username', 'Admin')}**"
        )

        if st.button(
            "Log Keluar (Logout)",
            type="primary",
            use_container_width=True
        ):

            st.session_state['logged_in'] = False
            st.session_state['proses_aktif'] = False

            st.rerun()

    # =====================================================================
    # JIKA FAIL CSV ADA
    # =====================================================================

    if uploaded_file is not None:

        try:

            df = pd.read_csv(
                uploaded_file
            )

            kolum_pilihan = df.columns.tolist()

            # =============================================================
            # TETAPAN KOORDINAT
            # =============================================================

            st.markdown(
                "## Tetapan Koordinat & Layer Peta"
            )

            col_set1, col_set2, col_set3 = st.columns(3)

            with col_set1:

                x_col = st.selectbox(
                    "Koordinat X / Easting",
                    kolum_pilihan,
                    index=(
                        1
                        if len(kolum_pilihan) > 1
                        else 0
                    )
                )

            with col_set2:

                y_col = st.selectbox(
                    "Koordinat Y / Northing",
                    kolum_pilihan,
                    index=(
                        2
                        if len(kolum_pilihan) > 2
                        else 0
                    )
                )

            with col_set3:

                stn_col = st.selectbox(
                    "ID Stesen",
                    kolum_pilihan,
                    index=0
                )

            # =============================================================
            # TETAPAN LOT / CRS / BASEMAP
            # =============================================================

            col_set4, col_set5, col_set6 = st.columns(3)

            with col_set4:

                no_lot_input = st.text_input(
                    "No. Lot / Nama Polygon",
                    value="308"
                )

            with col_set5:

                crs_input = st.selectbox(
                    "Sistem Koordinat / CRS Input",
                    [
                        "Custom EPSG",
                        "WGS 84 (GPS)",
                        "RSO Malaya (MRSO)"
                    ]
                )

            with col_set6:

                basemap_choice = st.selectbox(
                    "Pilih Latar Belakang Peta",
                    [
                        "🗺️ OpenStreetMap",
                        "🛰️ Satelit (Esri)",
                        "🌍 CartoDB Dark",
                        "🛣️ Google Maps (Road)",
                        "🌐 Google Maps (Satellite)",
                        "🛰️ Google Maps (Hybrid)"
                    ]
                )

            # =============================================================
            # EPSG
            # =============================================================

            epsg_code = st.number_input(
                "Masukkan EPSG Code",
                value=4390,
                step=1
            )

            st.caption(
                "Nota: EPSG yang tepat diperlukan supaya poligon "
                "dipaparkan di lokasi sebenar. "
                "Untuk Google Maps, koordinat akan ditukar kepada "
                "WGS 84 / EPSG:4326."
            )

            # =============================================================
            # BUTANG PROSES
            # =============================================================

            if st.button(
                "Lukis Poligon & Jana Peta",
                type="primary",
                use_container_width=True
            ):

                st.session_state['proses_aktif'] = True

            st.markdown("---")

            # =================================================================
            # PROSES DATA
            # =================================================================

            if st.session_state['proses_aktif']:

                # -------------------------------------------------------------
                # Ambil koordinat
                # -------------------------------------------------------------

                x = pd.to_numeric(
                    df[x_col],
                    errors='coerce'
                ).values

                y = pd.to_numeric(
                    df[y_col],
                    errors='coerce'
                ).values

                # Buang data kosong
                valid = (
                    ~np.isnan(x)
                    &
                    ~np.isnan(y)
                )

                x = x[valid]
                y = y[valid]

                if len(x) < 3:

                    st.error(
                        "Sekurang-kurangnya 3 titik koordinat "
                        "diperlukan untuk membentuk polygon."
                    )

                    return

                # -------------------------------------------------------------
                # Polygon
                # -------------------------------------------------------------

                x_plot = np.append(
                    x,
                    x[0]
                )

                y_plot = np.append(
                    y,
                    y[0]
                )

                # -------------------------------------------------------------
                # Luas
                # -------------------------------------------------------------

                luas = (
                    0.5
                    *
                    np.abs(
                        np.dot(
                            x,
                            np.roll(y, 1)
                        )
                        -
                        np.dot(
                            y,
                            np.roll(x, 1)
                        )
                    )
                )

                # -------------------------------------------------------------
                # Centroid
                # -------------------------------------------------------------

                centroid_x = np.mean(x)
                centroid_y = np.mean(y)

                # -------------------------------------------------------------
                # Bearing & Jarak
                # -------------------------------------------------------------

                jarak_arr, bearing_arr = kira_bearing_jarak(
                    x,
                    y
                )

                if stn_col in df.columns:

                    stesen_nama = df.loc[
                        valid,
                        stn_col
                    ].values

                else:

                    stesen_nama = [
                        f"P{i+1}"
                        for i in range(len(x))
                    ]

                # =================================================================
                # TRANSFORMASI KE WGS84
                # =================================================================

                x_map = x.copy()
                y_map = y.copy()

                centroid_x_map = centroid_x
                centroid_y_map = centroid_y

                if int(epsg_code) != 4326:

                    try:

                        transformer = Transformer.from_crs(
                            f"EPSG:{int(epsg_code)}",
                            "EPSG:4326",
                            always_xy=True
                        )

                        x_map, y_map = transformer.transform(
                            x,
                            y
                        )

                        centroid_x_map, centroid_y_map = transformer.transform(
                            centroid_x,
                            centroid_y
                        )

                    except Exception as e:

                        st.warning(
                            f"Transformasi CRS gagal: {e}"
                        )

                # =================================================================
                # SIDEBAR SETTINGS
                # =================================================================

                with st.sidebar:

                    st.markdown(
                        "### ⚙️ Tetapan Paparan"
                    )

                    nama_pemilik = st.text_input(
                        "Nama Pemilik",
                        value="Ali Bin Abu"
                    )

                    alpha_poligon = st.slider(
                        "Garis / Ketelusan Poligon",
                        min_value=0.1,
                        max_value=1.0,
                        value=0.4
                    )

                    # ---------------------------------------------------------
                    # ZOOM
                    # ---------------------------------------------------------

                    st.markdown("---")

                    st.markdown(
                        "### 🔍 Tetapan Zoom Peta"
                    )

                    zoom_level = st.slider(
                        "Tahap Zum Peta",
                        min_value=10,
                        max_value=30,
                        value=24,
                        step=1
                    )

                    st.caption(
                        "Zoom 24–30 = paparan sangat dekat. "
                        "Jika tile tidak tersedia, peta mungkin tidak bertambah detail."
                    )

                    # ---------------------------------------------------------
                    # Paparan
                    # ---------------------------------------------------------

                    st.markdown(
                        "### Kawalan Paparan:"
                    )

                    tunjuk_bearing = st.checkbox(
                        "Bearing & Jarak",
                        value=True
                    )

                    tunjuk_luas = st.checkbox(
                        "No. Lot & Luas",
                        value=True
                    )

                    tunjuk_sempadan = st.checkbox(
                        "Sempadan (Poligon)",
                        value=True
                    )

                    tunjuk_data = st.checkbox(
                        "Data Sempadan",
                        value=True
                    )

                    # =============================================================
                    # DOWNLOAD
                    # =============================================================

                    st.markdown("---")

                    st.markdown(
                        "### 📥 Muat Turun Fail"
                    )

                    geojson_str = generate_geojson(
                        x,
                        y,
                        list(stesen_nama),
                        no_lot_input,
                        nama_pemilik,
                        luas
                    )

                    st.download_button(
                        label="📁 Muat Turun GeoJSON",
                        data=geojson_str,
                        file_name=(
                            f"{no_lot_input.replace(' ', '_')}.geojson"
                        ),
                        mime="application/geo+json",
                        use_container_width=True
                    )

                    dxf_str = generate_dxf(
                        x,
                        y,
                        list(stesen_nama)
                    )

                    st.download_button(
                        label="📐 Muat Turun DXF (AutoCAD)",
                        data=dxf_str,
                        file_name=(
                            f"{no_lot_input.replace(' ', '_')}.dxf"
                        ),
                        mime="application/dxf",
                        use_container_width=True
                    )

                    # =============================================================
                    # CSV BARU
                    # =============================================================

                    st.markdown("---")

                    if st.button(
                        "📤 Muat Naik CSV Baru",
                        use_container_width=True
                    ):

                        st.session_state['proses_aktif'] = False

                        st.rerun()

                # =================================================================
                # DATA CSV
                # =================================================================

                if tunjuk_data:

                    st.markdown(
                        "### Pratonton Data CSV"
                    )

                    st.dataframe(
                        df,
                        use_container_width=True
                    )

                # =================================================================
                # STATUS
                # =================================================================

                st.success(
                    f"Berjaya menjana peta menggunakan "
                    f"EPSG: {epsg_code} "
                    f"({basemap_choice})"
                )

                st.metric(
                    label="Jumlah Luas Kawasan Poligon",
                    value=f"{luas:,.4f} m²"
                )

                # =================================================================
                # JADUAL BEARING & JARAK
                # =================================================================

                st.markdown(
                    "### Jadual Ukuran Garisan Sempadan "
                    "(Bearing & Jarak)"
                )

                data_garisan = []

                for i in range(len(x)):

                    next_idx = (
                        i + 1
                    ) % len(x)

                    data_garisan.append(
                        {
                            "Dari Stesen":
                                stesen_nama[i],

                            "Ke Stesen":
                                stesen_nama[next_idx],

                            "Jarak (m)":
                                round(
                                    jarak_arr[i],
                                    3
                                ),

                            "Bearing":
                                bearing_arr[i]
                        }
                    )

                df_garisan = pd.DataFrame(
                    data_garisan
                )

                st.dataframe(
                    df_garisan,
                    use_container_width=True
                )

                # =================================================================
                # VISUALISASI
                # =================================================================

                st.markdown("---")

                st.markdown(
                    "## 📊 Visualisasi Perbandingan Poligon"
                )

                col_biasa, col_satelit = st.columns(2)

                # =================================================================
                # 1. POLYGON MATPLOTLIB
                # =================================================================

                with col_biasa:

                    st.markdown(
                        "### 1. Poligon Biasa "
                        "(Graf Grid Matplotlib)"
                    )

                    fig, ax = plt.subplots(
                        figsize=(6, 5)
                    )

                    if tunjuk_sempadan:

                        ax.plot(
                            x_plot,
                            y_plot,
                            marker='o',
                            color='#1f77b4',
                            linestyle='-',
                            linewidth=2,
                            label='Sempadan'
                        )

                        ax.fill(
                            x_plot,
                            y_plot,
                            color='skyblue',
                            alpha=alpha_poligon
                        )

                    # -------------------------------------------------------------
                    # Luas
                    # -------------------------------------------------------------

                    if tunjuk_luas:

                        ax.text(
                            centroid_x,
                            centroid_y,
                            f"Lot {no_lot_input}\n"
                            f"Luas: {luas:.2f} m²",
                            ha='center',
                            va='center',
                            fontsize=9,
                            weight='bold',
                            color='darkblue',
                            bbox=dict(
                                facecolor='white',
                                alpha=0.8,
                                edgecolor='none',
                                boxstyle='round,pad=0.3'
                            )
                        )

                    # -------------------------------------------------------------
                    # Bearing
                    # -------------------------------------------------------------

                    if tunjuk_bearing:

                        for i in range(len(x)):

                            x_start = x[i]
                            y_start = y[i]

                            x_end = x[
                                (i + 1) % len(x)
                            ]

                            y_end = y[
                                (i + 1) % len(y)
                            ]

                            mid_x = (
                                x_start + x_end
                            ) / 2

                            mid_y = (
                                y_start + y_end
                            ) / 2

                            teks_garisan = (
                                f"{jarak_arr[i]:.2f}m\n"
                                f"{bearing_arr[i]}"
                            )

                            ax.text(
                                mid_x,
                                mid_y,
                                teks_garisan,
                                fontsize=6,
                                color='darkred',
                                ha='center',
                                va='center',
                                bbox=dict(
                                    facecolor='yellow',
                                    alpha=0.5,
                                    edgecolor='none',
                                    boxstyle='round,pad=0.2'
                                )
                            )

                    # -------------------------------------------------------------
                    # Station
                    # -------------------------------------------------------------

                    for i, txt in enumerate(
                        stesen_nama
                    ):

                        ax.annotate(
                            f"STN {txt}",
                            (
                                x[i],
                                y[i]
                            ),
                            textcoords="offset points",
                            xytext=(0, 8),
                            ha='center',
                            fontsize=7,
                            weight='bold'
                        )

                    ax.set_title(
                        f"Lot {no_lot_input} "
                        f"(EPSG: {epsg_code})"
                    )

                    ax.set_xlabel(
                        "Easting (m)"
                    )

                    ax.set_ylabel(
                        "Northing (m)"
                    )

                    ax.grid(
                        True,
                        linestyle='--',
                        alpha=0.6
                    )

                    ax.legend()

                    st.pyplot(fig)

                # =================================================================
                # 2. PETA INTERAKTIF
                # =================================================================

                with col_satelit:

                    st.markdown(
                        "### 2. Peta Interaktif "
                        "(Google Maps)"
                    )

                    # =============================================================
                    # BASEMAP
                    # =============================================================

                    tiles_map = "OpenStreetMap"
                    attr_map = None

                    # -------------------------------------------------------------
                    # OpenStreetMap
                    # -------------------------------------------------------------

                    if "OpenStreetMap" in basemap_choice:

                        tiles_map = "OpenStreetMap"

                        attr_map = None

                    # -------------------------------------------------------------
                    # Esri Satellite
                    # -------------------------------------------------------------

                    elif "Satelit (Esri)" in basemap_choice:

                        tiles_map = (
                            "https://server.arcgisonline.com/"
                            "ArcGIS/rest/services/"
                            "World_Imagery/MapServer/tile/"
                            "{z}/{y}/{x}"
                        )

                        attr_map = (
                            "Tiles © Esri — Source: Esri, "
                            "i-cubed, USDA, USGS, AEX, "
                            "GeoEye, Getmapping, Aerogrid, "
                            "IGN, IGP, UPR-GIS, and the "
                            "GIS User Community"
                        )

                    # -------------------------------------------------------------
                    # Carto Dark
                    # -------------------------------------------------------------

                    elif "CartoDB Dark" in basemap_choice:

                        tiles_map = "CartoDB dark_matter"

                        attr_map = (
                            "CartoDB"
                        )

                    # -------------------------------------------------------------
                    # Google Road
                    # -------------------------------------------------------------

                    elif "Google Maps (Road)" in basemap_choice:

                        tiles_map = (
                            "https://mt1.google.com/vt/"
                            "lyrs=m&x={x}&y={y}&z={z}"
                        )

                        attr_map = "Google Maps"

                    # -------------------------------------------------------------
                    # Google Satellite
                    # -------------------------------------------------------------

                    elif "Google Maps (Satellite)" in basemap_choice:

                        tiles_map = (
                            "https://mt1.google.com/vt/"
                            "lyrs=s&x={x}&y={y}&z={z}"
                        )

                        attr_map = "Google Maps"

                    # -------------------------------------------------------------
                    # Google Hybrid
                    # -------------------------------------------------------------

                    elif "Google Maps (Hybrid)" in basemap_choice:

                        tiles_map = (
                            "https://mt1.google.com/vt/"
                            "lyrs=y&x={x}&y={y}&z={z}"
                        )

                        attr_map = "Google Maps"

                    # =============================================================
                    # CREATE MAP
                    # =============================================================

                    m = folium.Map(

                        location=[
                            centroid_y_map,
                            centroid_x_map
                        ],

                        zoom_start=zoom_level,

                        zoom_control=True,

                        scrollWheelZoom=True,

                        doubleClickZoom=True,

                        touchZoom=True,

                        max_zoom=30,

                        min_zoom=2,

                        tiles=tiles_map,

                        attr=attr_map,

                        control_scale=True
                    )

                    # Kawalan zoom lebih halus
                    m.options["zoomSnap"] = 0.5
                    m.options["zoomDelta"] = 0.5

                    # =============================================================
                    # FULL SCREEN
                    # =============================================================

                    Fullscreen(

                        position="topleft",

                        title="Papar Skrin Penuh",

                        title_cancel="Keluar Skrin Penuh",

                        force_separate_button=True

                    ).add_to(m)

                    # =============================================================
                    # KOORDINAT POLYGON
                    # =============================================================

                    lokasi_poligon = [

                        [
                            y_map[i],
                            x_map[i]
                        ]

                        for i in range(len(x))

                    ]

                    # =============================================================
                    # POLYGON
                    # =============================================================

                    if tunjuk_sempadan:

                        folium.Polygon(

                            locations=lokasi_poligon,

                            color='#1f77b4',

                            weight=3,

                            fill=True,

                            fill_color='skyblue',

                            fill_opacity=alpha_poligon,

                            popup=(
                                f"<b>Lot "
                                f"{no_lot_input}</b><br>"
                                f"Luas: "
                                f"{luas:.2f} m²"
                            )

                        ).add_to(m)

                        # ---------------------------------------------------------
                        # STATION MARKER
                        # ---------------------------------------------------------

                        for i in range(len(x)):

                            popup_teks = (

                                f"<b>"
                                f"STN {stesen_nama[i]}"
                                f"</b><br>"

                                f"Jarak: "
                                f"{jarak_arr[i]:.2f} m"

                                f"<br>"

                                f"Bearing: "
                                f"{bearing_arr[i]}"

                            )

                            folium.CircleMarker(

                                location=[
                                    y_map[i],
                                    x_map[i]
                                ],

                                radius=5,

                                color='red',

                                fill=True,

                                fill_color='red',

                                fill_opacity=1,

                                popup=popup_teks

                            ).add_to(m)

                    # =============================================================
                    # PAPAR PETA
                    # =============================================================

                    st_folium(

                        m,

                        width=None,

                        height=600,

                        use_container_width=True,

                        returned_objects=[]

                    )

                # =================================================================
                # MAKLUMAT CENTROID
                # =================================================================

                st.markdown("---")

                st.info(

                    f"Centroid poligon di:\n\n"

                    f"E: {centroid_x:.2f} | "

                    f"N: {centroid_y:.2f} | "

                    f"Jumlah Stesen: **{len(x)}**"

                )

            else:

                st.info(
                    "Sila tentukan parameter di atas dan "
                    "klik butang **'Lukis Poligon & Jana Peta'**."
                )

        except Exception as e:

            st.error(
                f"Ralat semasa memproses data: {e}"
            )

    else:

        st.info(
            "Sila muat naik fail CSV untuk memulakan "
            "tetapan koordinat."
        )


# =========================================================================
# LOGIN SCREEN
# =========================================================================

def login_screen():

    col1, col2, col3 = st.columns(
        [1, 2, 1]
    )

    with col2:

        logo_path = "Poli_Logo (1).png"

        if os.path.exists(logo_path):

            st.image(
                logo_path,
                width=250
            )

        else:

            st.info(
                "Sila pastikan fail logo berada "
                "dalam folder yang sama."
            )

        st.title(
            "Sistem Maklumat Geografi"
        )

        st.subheader(
            "Log Masuk Pengguna"
        )

        # =============================================================
        # LOGIN FORM
        # =============================================================

        with st.form("login_form"):

            username = st.text_input(
                "Masukkan Nama Pengguna (Username)"
            )

            kata_laluan = st.text_input(
                "Masukkan Kata Laluan (Password)",
                type="password"
            )

            submit_button = st.form_submit_button(
                "Log Masuk"
            )

            if submit_button:

                if not username or not kata_laluan:

                    st.warning(
                        "Sila isi kedua-dua nama pengguna "
                        "dan kata laluan."
                    )

                elif (
                    username == "admin"
                    and kata_laluan == "12345"
                ):

                    st.success(
                        "Log masuk berjaya! "
                        "Memuatkan antara muka..."
                    )

                    st.session_state[
                        'logged_in'
                    ] = True

                    st.session_state[
                        'username'
                    ] = username

                    st.rerun()

                else:

                    st.error(
                        "Nama pengguna atau kata laluan salah. "
                        "Sila cuba lagi."
                    )


# =========================================================================
# MAIN PROGRAM
# =========================================================================

if st.session_state['logged_in']:

    main_dashboard()

else:

    login_screen()