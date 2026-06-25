import flet as ft
import sqlite3
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from openpyxl import Workbook
import hashlib
import re

conn = sqlite3.connect('buku_kas.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE, password TEXT, security_q TEXT, security_a TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS transaksi
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tanggal TEXT, keterangan TEXT, jenis TEXT, nominal INTEGER, saldo INTEGER,
              FOREIGN KEY(user_id) REFERENCES users(id))''')
conn.commit()

user_login = None

def hash_pass(p): return hashlib.sha256(p.encode()).hexdigest()

def get_emoji(ket):
    ket = ket.lower()
    if re.search(r'gaji|bonus|thr', ket): return "💰"
    elif re.search(r'makan|warung|restoran|kopi|jajan', ket): return "🍔"
    elif re.search(r'transport|bensin|parkir|ojol|grab|gojek', ket): return "🚗"
    elif re.search(r'pulsa|paket data|wifi|internet', ket): return "📱"
    elif re.search(r'gopay|dana|ovo|shopeepay|transfer', ket): return "💳"
    elif re.search(r'belanja|shopee|tokped|lazada|baju', ket): return "🛒"
    elif re.search(r'obat|dokter|rumah sakit|apotek', ket): return "💊"
    else: return "📝"

def main(page: ft.Page):
    page.title = "Buku Kas Sakha"
    page.padding = 20
    page.theme_mode = ft.ThemeMode.LIGHT
    page.transition = ft.PageTransitionTheme.CUPERTINO # Animasi ganti halaman

    filter_aktif = "Semua"
    search_text = ""

    def show_login():
        page.clean()
        username = ft.TextField(label="Username", autofocus=True)
        password = ft.TextField(label="Password", password=True, can_reveal_password=True)
        error_text = ft.Text(color=ft.colors.RED)

        def login(e):
            global user_login
            c.execute("SELECT id FROM users WHERE username=? AND password=?", (username.value, hash_pass(password.value)))
            user = c.fetchone()
            if user:
                user_login = user[0]
                show_main_app()
            else:
                error_text.value = "Username atau password salah!"
                page.update()

        page.add(ft.AnimatedSwitcher(
            content=ft.Column([
                ft.Text("Login Buku Kas", size=30, weight=ft.FontWeight.BOLD),
                username, password, error_text,
                ft.ElevatedButton("Login", on_click=login, expand=True),
                ft.TextButton("Belum punya akun? Daftar", on_click=lambda e: show_register()),
                ft.TextButton("Lupa Password?", on_click=lambda e: show_lupa_pass())
            ], opacity=0, animate_opacity=300),
            transition=ft.AnimatedSwitcherTransition.FADE
        ))
        page.update()

    def show_register():
        page.clean()
        username = ft.TextField(label="Username Baru")
        password = ft.TextField(label="Password", password=True, can_reveal_password=True)
        sec_q = ft.Dropdown(label="Pertanyaan Keamanan", options=[ft.dropdown.Option("Nama hewan peliharaan pertama?"), ft.dropdown.Option("Nama kota kelahiran ibu?"), ft.dropdown.Option("Makanan favorit waktu kecil?")])
        sec_a = ft.TextField(label="Jawaban")
        error_text = ft.Text(color=ft.colors.RED)

        def daftar(e):
            if not sec_q.value or not sec_a.value: error_text.value = "Isi pertanyaan keamanan!"; page.update(); return
            try:
                c.execute("INSERT INTO users (username, password, security_q, security_a) VALUES (?,?,?,?)", (username.value, hash_pass(password.value), sec_q.value, hash_pass(sec_a.value.lower())))
                conn.commit()
                page.snack_bar = ft.SnackBar(ft.Text("Daftar berhasil!"))
                page.snack_bar.open = True
                show_login()
            except:
                error_text.value = "Username udah dipake!"; page.update()

        page.add(ft.Column([ft.Text("Daftar Akun Baru", size=30, weight=ft.FontWeight.BOLD), username, password, sec_q, sec_a, error_text, ft.ElevatedButton("Daftar", on_click=daftar, expand=True), ft.TextButton("Udah punya akun? Login", on_click=lambda e: show_login())]))

    def show_lupa_pass():
        page.clean()
        username = ft.TextField(label="Username")
        error_text = ft.Text(color=ft.colors.RED)
        q_text = ft.Text()
        a_input = ft.TextField(label="Jawaban", visible=False)
        new_pass = ft.TextField(label="Password Baru", password=True, can_reveal_password=True, visible=False)

        def cek_user(e):
            c.execute("SELECT security_q FROM users WHERE username=?", (username.value,))
            res = c.fetchone()
            if res:
                q_text.value = res[0]
                a_input.visible = True
                page.update()
            else:
                error_text.value = "Username gak ketemu!"; page.update()

        def reset_pass(e):
            c.execute("SELECT security_a FROM users WHERE username=?", (username.value,))
            res = c.fetchone()
            if res and res[0] == hash_pass(a_input.value.lower()):
                c.execute("UPDATE users SET password=? WHERE username=?", (hash_pass(new_pass.value), username.value))
                conn.commit()
                page.snack_bar = ft.SnackBar(ft.Text("Password berhasil direset!"))
                page.snack_bar.open = True
                show_login()
            else:
                error_text.value = "Jawaban salah!"; page.update()

        def lanjut_reset(e):
            new_pass.visible = True
            page.update()

        page.add(ft.Column([ft.Text("Reset Password", size=30, weight=ft.FontWeight.BOLD), username, ft.ElevatedButton("Cek Username", on_click=cek_user), q_text, a_input, ft.ElevatedButton("Verifikasi", on_click=lanjut_reset, visible=a_input.visible), new_pass, error_text, ft.ElevatedButton("Reset", on_click=reset_pass, visible=new_pass.visible), ft.TextButton("Kembali", on_click=lambda e: show_login())]))

    def show_main_app():
        page.clean()
        nonlocal filter_aktif, search_text

        def hitung_saldo():
            c.execute("SELECT saldo FROM transaksi WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_login,))
            saldo_akhir = c.fetchone()
            return saldo_akhir[0] if saldo_akhir else 0

        def get_query_filter():
            hari_ini = datetime.now()
            base = f"WHERE user_id={user_login}"
            if filter_aktif == "Harian": tgl = hari_ini.strftime("%Y-%m-%d"); return f"{base} AND tanggal LIKE '{tgl}%'"
            elif filter_aktif == "Mingguan": tgl_mulai = (hari_ini - timedelta(days=7)).strftime("%Y-%m-%d"); return f"{base} AND tanggal >= '{tgl_mulai}'"
            elif filter_aktif == "Bulanan": bulan = hari_ini.strftime("%Y-%m"); return f"{base} AND tanggal LIKE '{bulan}%'"
            elif filter_aktif == "Tahunan": tahun = hari_ini.strftime("%Y"); return f"{base} AND tanggal LIKE '{tahun}%'"
            return base

        def update_list(animasi_baru=None):
            where = get_query_filter()
            query = f"SELECT * FROM transaksi {where} ORDER BY id DESC LIMIT 50"
            c.execute(query)
            rows = c.fetchall()
            if search_text: rows = [r for r in rows if search_text.lower() in r[3].lower()]

            list_view.controls.clear()
            for i, row in enumerate(rows):
                warna = ft.colors.RED_400 if row[4] == "keluar" else ft.colors.GREEN_400
                simbol = "-" if row[4] == "keluar" else "+"
                emoji = get_emoji(row[3])

                item = ft.Container(
                    content=ft.Row([
                        ft.Text(emoji, size=28), # EMOJI OTOMATIS
                        ft.Column([ft.Text(row[3], weight=ft.FontWeight.BOLD), ft.Text(row[2].split()[0], size=12, color=ft.colors.GREY_400)], expand=True),
                        ft.Text(f"{simbol}Rp{row[5]:,}", color=warna, weight=ft.FontWeight.BOLD, size=16)
                    ]),
                    padding=12, border=ft.border.all(1, ft.colors.OUTLINE), border_radius=12, margin=5,
                    opacity=0, offset=ft.Offset(0, 0.5), animate_opacity=300, animate_offset=300
                )
                list_view.controls.append(ft.GestureDetector(on_long_press=lambda e, id=row[0]: show_aksi(id), content=item))
                # Kasih delay animasi biar muncul satu-satu
                item.opacity = 1
                item.offset = ft.Offset(0, 0)

            saldo_baru = hitung_saldo()
            saldo_text.value = f"Rp{saldo_baru:,}"
            saldo_text.color = ft.colors.RED_400 if saldo_baru < 0 else ft.colors.GREEN_400
            saldo_text.animate_scale = ft.Animation(500, ft.AnimationCurve.EASE_OUT) # Animasi saldo
            update_grafik()
            page.update()

        def toggle_theme(e):
            page.theme_mode = ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
            theme_btn.icon = ft.icons.LIGHT_MODE if page.theme_mode == ft.ThemeMode.DARK else ft.icons.DARK_MODE
            page.update()

        def logout(e):
            global user_login
            user_login = None
            show_login()

        def export_file(e, tipe):
            c.execute("SELECT tanggal, keterangan, jenis, nominal, saldo FROM transaksi WHERE user_id=? ORDER BY id", (user_login,))
            rows = c.fetchall()
            if tipe == "Excel":
                wb = Workbook()
                ws = wb.active
                ws.append(['Tanggal', 'Keterangan', 'Jenis', 'Nominal', 'Saldo'])
                for r in rows: ws.append(r[2:])
                path = f'/sdcard/laporan_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
                wb.save(path)
            else:
                path = f'/sdcard/laporan_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
                c_pdf = canvas.Canvas(path)
                c_pdf.setFont("Helvetica-Bold", 16)
                c_pdf.drawString(50, 800, "Laporan Buku Kas Sakha")
                y = 770
                c_pdf.setFont("Helvetica", 10)
                for r in rows:
                    c_pdf.drawString(50, y, f"{get_emoji(r[3])} {r[2]} | {r[3]} | {r[4]} | Rp{r[5]:,} | Saldo: Rp{r[6]:,}")
                    y -= 15
                    if y < 50: c_pdf.showPage(); y = 800
                c_pdf.save()
            page.snack_bar = ft.SnackBar(ft.Text(f"Export {tipe} berhasil! Cek /sdcard/"))
            page.snack_bar.open = True
            page.update()

        def show_aksi(id):
            def hapus(e):
                c.execute("DELETE FROM transaksi WHERE id=? AND user_id=?", (id, user_login))
                conn.commit()
                c.execute("SELECT id, jenis, nominal FROM transaksi WHERE user_id=? ORDER BY id", (user_login,))
                saldo = 0
                for r in c.fetchall():
                    saldo = saldo + r[2] if r[1]=="masuk" else saldo - r[2]
                    c.execute("UPDATE transaksi SET saldo=? WHERE id=?", (saldo, r[0]))
                conn.commit()
                page.close(page.overlay[-1])
                update_list()
            page.open(ft.BottomSheet(content=ft.Column([ft.ListTile(title=ft.Text("Hapus", color=ft.colors.RED), on_click=hapus)], tight=True)))

        def update_grafik():
            points = []
            for i in range(7):
                tgl = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                c.execute(f"SELECT saldo FROM transaksi WHERE user_id=? AND tanggal LIKE '{tgl}%' ORDER BY id DESC LIMIT 1", (user_login,))
                s = c.fetchone()
                points.append(ft.LineChartDataPoint(x=6-i, y=s[0] if s else 0))
            chart.data_series[0].data_points = points
            chart.update()

        def tambah_transaksi(e, jenis):
            def simpan(e):
                if not ket_input.value or not nominal_input.value: return
                nominal = int(nominal_input.value)
                saldo_baru = hitung_saldo() + nominal if jenis == "masuk" else hitung_saldo() - nominal
                c.execute("INSERT INTO transaksi (user_id, tanggal, keterangan, jenis, nominal, saldo) VALUES (?,?,?,?,?,?)",
                          (user_login, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ket_input.value, jenis, nominal, saldo_baru))
                conn.commit()
                page.close(dlg)
                update_list(animasi_baru=True) # Trigger animasi

            ket_input = ft.TextField(label="Keterangan", hint_text="Contoh: Beli kopi, Gaji bulanan", autofocus=True)
            nominal_input = ft.TextField(label="Nominal", keyboard_type=ft.KeyboardType.NUMBER)
            dlg = ft.AlertDialog(title=ft.Text("Kamu Menerima" if jenis=="masuk" else "Kamu Membayar"),
                content=ft.Column([ket_input, nominal_input], tight=True),
                actions=[ft.TextButton("Simpan", on_click=simpan), ft.TextButton("Batal", on_click=lambda e: page.close(dlg))])
            page.open(dlg)

        def ganti_filter(teks):
            nonlocal filter_aktif
            filter_aktif = teks
            update_list()

        def search(e):
            nonlocal search_text
            search_text = e.control.value
            update_list()

        theme_btn = ft.IconButton(ft.icons.DARK_MODE, on_click=toggle_theme)
        logout_btn = ft.IconButton(ft.icons.LOGOUT, on_click=logout)
        saldo_text = ft.Text(f"Rp{hitung_saldo():,}", size=40, weight=ft.FontWeight.BOLD, scale=1, animate_scale=ft.Animation(300))
        chart = ft.LineChart(min_y=-1000000, max_y=1000000, data_series=[ft.LineChartData(data_points=[], color=ft.colors.BLUE, stroke_width=3, curved=True)], height=150)

        btn_bayar = ft.ElevatedButton("Kamu Membayar", icon=ft.icons.ARROW_UPWARD, bgcolor=ft.colors.RED_100, color=ft.colors.RED, on_click=lambda e: tambah_transaksi(e, "keluar"), expand=True)
        btn_terima = ft.ElevatedButton("Kamu Menerima", icon=ft.icons.ARROW_DOWNWARD, bgcolor=ft.colors.GREEN_100, color=ft.colors.GREEN, on_click=lambda e: tambah_transaksi(e, "masuk"), expand=True)

        search_bar = ft.TextField(label="Cari...", on_change=search, prefix_icon=ft.icons.SEARCH)
        filter_buttons = ft.Row([ft.TextButton(t, on_click=lambda e: ganti_filter(e.control.text)) for t in ["Semua","Harian","Mingguan","Bulanan","Tahunan"]], scroll=True)
        list_view = ft.ListView(expand=True, spacing=5)
        btn_excel = ft.ElevatedButton("Export Excel", icon=ft.icons.TABLE_CHART, on_click=lambda e: export_file(e, "Excel"))
        btn_pdf = ft.ElevatedButton("Export PDF", icon=ft.icons.PICTURE_AS_PDF, on_click=lambda e: export_file(e, "PDF"))

        page.appbar = ft.AppBar(title=ft.Text("Buku Kas Sakha"), actions=[theme_btn, logout_btn])
        page.add(ft.Column([saldo_text, chart, ft.Row([btn_bayar, btn_terima]), search_bar, filter_buttons, ft.Row([btn_excel, btn_pdf]), ft.Divider(), list_view], expand=True))
        update_list()

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        show_register()
    else:
        show_login()

import os
if os.getenv("FLET_PLATFORM") == "web":
    ft.run(target=main)
else:
    ft.app(target=main)
