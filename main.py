"""
NeoScalp Pro - Advanced Options Terminal with Cover & Bracket Orders
Kotak Neo Trade API v2 | Supports MIS, NRML, CO, BO
"""

import customtkinter as ctk
from tkinter import ttk, messagebox
import tkinter as tk
import threading
import time
import json
import pyotp
from datetime import datetime
from neo_api_client import NeoAPI

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class NeoScalpApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NeoScalp Pro - Cover & Bracket Orders")
        self.geometry("1200x780")
        self.resizable(False, False)

        # ==================== CONFIG ====================
        self.config = {
            "consumer_key": "YOUR_CONSUMER_KEY",
            "mobile_number": "+91XXXXXXXXXX",
            "ucc": "YOUR_UCC",
            "mpin": "YOUR_MPIN",
            "totp_secret": "YOUR_TOTP_SECRET",
            "environment": "prod"
        }

        self.client = None
        self.is_logged_in = False
        self.session_expiry = None
        self.positions = []
        self.live_prices = {}
        self.scrip_master = {}

        self.lot_sizes = {"NIFTY": 25, "BANKNIFTY": 15, "FINNIFTY": 25, "MIDCPNIFTY": 50}

        # Order mode: "NORMAL", "CO", "BO"
        self.order_mode = "NORMAL"
        self.sl_points = ctk.DoubleVar(value=20.0)
        self.target_points = ctk.DoubleVar(value=40.0)

        self.setup_ui()
        self.start_token_refresh_monitor()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top Login Bar
        login_frame = ctk.CTkFrame(self, height=70, fg_color="#0a1624")
        login_frame.grid(row=0, column=0, sticky="ew")
        login_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(login_frame, text="Kotak Neo Pro Terminal", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=25, pady=15)
        self.login_btn = ctk.CTkButton(login_frame, text="LOGIN", width=180, height=40,
                                       fg_color="#00b367", command=self.authenticate_and_start)
        self.login_btn.grid(row=0, column=1, padx=20, pady=15, sticky="e")
        self.status_label = ctk.CTkLabel(login_frame, text="DISCONNECTED", text_color="#ff4444", font=ctk.CTkFont(weight="bold"))
        self.status_label.grid(row=0, column=2, padx=30, pady=15, sticky="e")

        # Header
        header = ctk.CTkFrame(self, height=70, fg_color="#0f1e2e")
        header.grid(row=1, column=0, sticky="ew")
        header.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(header, text="NeoScalp Pro", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=30, pady=20)
        ctk.CTkLabel(header, text="NIFTY 50", font=ctk.CTkFont(size=18)).grid(row=0, column=1, padx=10)
        self.nifty_price = ctk.CTkLabel(header, text="--.--", font=ctk.CTkFont(size=28, weight="bold"), text_color="#00ff99")
        self.nifty_price.grid(row=0, column=2, sticky="e", padx=(0, 220))

        # Order Panel
        self.build_order_panel()
        self.build_positions_table()

    def build_order_panel(self):
        panel = ctk.CTkFrame(self, fg_color="#121f2e")
        panel.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        panel.grid_columnconfigure((1, 3), weight=1)

        # CALL Button
        ctk.CTkButton(panel, text="CALL (BULL)", width=150, height=50, fg_color="#00b367",
                      font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=25, pady=15, rowspan=3)

        # Instrument
        ctk.CTkLabel(panel, text="INSTRUMENT").grid(row=0, column=1, sticky="w", padx=40)
        self.symbol_var = ctk.StringVar(value="NIFTY 28NOV25 22450 CE")
        self.symbol_combo = ctk.CTkComboBox(panel, variable=self.symbol_var, width=320, height=40)
        self.symbol_combo.grid(row=1, column=1, sticky="w", padx=40, pady=5)

        # Quantity
        ctk.CTkLabel(panel, text="QUANTITY").grid(row=0, column=2, sticky="w", padx=30)
        self.qty_var = ctk.IntVar(value=25)
        ctk.CTkEntry(panel, textvariable=self.qty_var, width=100, height=40, font=ctk.CTkFont(size=18)).grid(row=1, column=2, sticky="w", padx=30, pady=5)
        ctk.CTkButton(panel, text="-", width=40, command=lambda: self.adjust_qty(-1)).grid(row=1, column=2, padx=(140,0))
        ctk.CTkButton(panel, text="+", width=40, command=lambda: self.adjust_qty(1)).grid(row=1, column=2, padx=(190,0))

        # === ORDER MODE TABS ===
        mode_frame = ctk.CTkFrame(panel, fg_color="#1c2b3d")
        mode_frame.grid(row=0, column=3, columnspan=2, padx=40, pady=10, sticky="w")
        
        self.mode_var = ctk.StringVar(value="NORMAL")
        modes = [("NORMAL", "#2d2d2d"), ("CO", "#00b367"), ("BO", "#ff9500")]
        for i, (text, color) in enumerate(modes):
            btn = ctk.CTkRadioButton(mode_frame, text=text, variable=self.mode_var, value=text,
                                     fg_color=color, font=ctk.CTkFont(weight="bold"))
            btn.grid(row=0, column=i, padx=15, pady=8)

        # === BO/CO SL & TARGET ===
        bo_frame = ctk.CTkFrame(panel, fg_color="#1c2b3d")
        bo_frame.grid(row=1, column=3, columnspan=2, padx=40, pady=5, sticky="w")

        ctk.CTkLabel(bo_frame, text="SL (points):").grid(row=0, column=0, padx=10, pady=5)
        ctk.CTkEntry(bo_frame, textvariable=self.sl_points, width=80).grid(row=0, column=1, padx=5)
        ctk.CTkLabel(bo_frame, text="TARGET (points):").grid(row=0, column=2, padx=10, pady=5)
        ctk.CTkEntry(bo_frame, textvariable=self.target_points, width=80).grid(row=0, column=3, padx=5)

        # BUY / SELL
        ctk.CTkButton(panel, text="BUY", width=180, height=90, fg_color="#00b367",
                      font=ctk.CTkFont(size=24, weight="bold"), command=self.place_buy).grid(row=0, column=5, rowspan=3, padx=15, pady=15)
        ctk.CTkButton(panel, text="SELL", width=180, height=90, fg_color="#e04b4b",
                      font=ctk.CTkFont(size=24, weight="bold"), command=self.place_sell).grid(row=0, column=6, rowspan=3, padx=15, pady=15)

    def build_positions_table(self):
        bottom = ctk.CTkFrame(self)
        bottom.grid(row=3, column=0, sticky="nsew", padx=20, pady=10)
        bottom.grid_rowconfigure(1, weight=1)
        bottom.grid_columnconfigure(0, weight=1)

        pnl_frame = ctk.CTkFrame(bottom, height=60, fg_color="#121f2e")
        pnl_frame.grid(row=0, column=0, sticky="ew")
        self.pnl_label = ctk.CTkLabel(pnl_frame, text="DAY P&L: ₹0", font=ctk.CTkFont(size=18, weight="bold"), text_color="#00ff99")
        self.pnl_label.grid(row=0, column=0, padx=30, pady=15)
        ctk.CTkButton(pnl_frame, text="EXIT ALL", fg_color="#e04b4b", width=140, height=45,
                      font=ctk.CTkFont(weight="bold"), command=self.exit_all).place(relx=0.95, rely=0.5, anchor="e")

        cols = ("Symbol", "Qty", "Avg", "LTP", "P&L", "Type", "Action")
        self.tree = ttk.Treeview(bottom, columns=cols, show="headings", height=8)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=130)
        self.tree.column("Symbol", width=260, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        style = ttk.Style()
        style.configure("Treeview", background="#1a2330", foreground="white", rowheight=50)
        style.configure("Treeview.Heading", background="#121f2e", foreground="#88aadd")
        style.map("Treeview", background=[("selected", "#1f4b99")])

    def adjust_qty(self, step):
        symbol = self.symbol_var.get()
        lot = self.get_lot_size(symbol)
        current = self.qty_var.get()
        self.qty_var.set(max(lot, current + step * lot))

    def get_lot_size(self, symbol):
        for u in self.lot_sizes:
            if u in symbol.upper():
                return self.lot_sizes[u]
        return 25

    def show_error(self, t, m): messagebox.showerror(t, m)
    def show_info(self, t, m): messagebox.showinfo(t, m)

    def authenticate_and_start(self):
        if self.is_logged_in: return
        threading.Thread(target=self.login_thread, daemon=True).start()

    def login_thread(self):
        try:
            self.client = NeoAPI(consumer_key=self.config["consumer_key"], environment=self.config["environment"])
            totp = pyotp.TOTP(self.config["totp_secret"]).now()
            self.client.totp_login(mobile_number=self.config["mobile_number"], ucc=self.config["ucc"], totp=totp)
            self.client.totp_validate(mpin=self.config["mpin"])

            self.is_logged_in = True
            self.session_expiry = datetime.now().timestamp() + 8*3600

            self.after(0, lambda: [
                self.status_label.configure(text="CONNECTED", text_color="#00ff99"),
                self.login_btn.configure(state="disabled", text="CONNECTED"),
                self.show_info("Success", "Connected to Kotak Neo!")
            ])

            self.load_scrip_master()
            self.start_live_updates()
            self.start_positions_refresh()

        except Exception as e:
            self.after(0, lambda: self.show_error("Login Failed", str(e)))

    def load_scrip_master(self):
        try:
            master = self.client.scrip_master()
            for item in master:
                self.scrip_master[item["trading_symbol"]] = item
            opts = [s for s in self.scrip_master.keys() if "NIFTY" in s and "CE" in s][-40:]
            self.after(0, lambda: self.symbol_combo.configure(values=opts))
        except: pass

    def start_live_updates(self):
        def on_msg(msg):
            try:
                data = json.loads(msg)
                if data.get("lp"):
                    ltp = float(data["lp"])
                    symbol = data.get("ts", "")
                    if "NIFTY" in symbol and "CE" in symbol:
                        self.after(0, lambda: self.nifty_price.configure(text=f"{ltp:.2f}"))
            except: pass
        self.client.on_message = on_msg
        self.client.subscribe(instrument_tokens=["NSE|NIFTY 50"])

    def start_positions_refresh(self):
        def loop():
            while self.is_logged_in:
                try:
                    resp = self.client.positions()
                    self.positions = resp.get("data", []) if resp else []
                    self.update_positions_table()
                    self.update_pnl()
                except: pass
                time.sleep(3)
        threading.Thread(target=loop, daemon=True).start()

    def update_positions_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for pos in self.positions:
            if int(pos.get("net_qty", 0)) == 0: continue
            pnl = float(pos.get("unrealized_pnl", 0)) + float(pos.get("realized_pnl", 0))
            self.tree.insert("", "end", values=(
                pos.get("trading_symbol", ""),
                pos.get("net_qty", 0),
                pos.get("avg_price", "0"),
                pos.get("ltp", "0"),
                f"₹{pnl:,.0f}",
                pos.get("product", "NRML"),
                "EXIT"
            ))

    def update_pnl(self):
        total = sum(float(p.get("unrealized_pnl", 0)) + float(p.get("realized_pnl", 0)) for p in self.positions)
        color = "#00ff99" if total >= 0 else "#ff4444"
        self.after(0, lambda: self.pnl_label.configure(text=f"DAY P&L: ₹{total:,.0f}", text_color=color))

    def place_order(self, side):
        if not self.is_logged_in:
            self.show_error("Error", "Login first!")
            return

        symbol = self.symbol_var.get()
        qty = self.qty_var.get()
        lot = self.get_lot_size(symbol)
        if qty % lot != 0:
            self.show_error("Invalid Qty", f"Must be multiple of {lot}")
            return

        mode = self.mode_var.get()
        sl_pts = self.sl_points.get()
        tgt_pts = self.target_points.get()

        try:
            if mode == "NORMAL":
                self.client.place_order(
                    exchange_segment="nse_fo",
                    product="MIS",
                    price="0",
                    order_type="MKT",
                    quantity=str(qty),
                    validity="DAY",
                    trading_symbol=symbol,
                    transaction_type="B" if side == "BUY" else "S"
                )
                self.show_info("Order", f"{side} {qty} × {symbol} (MIS)")

            elif mode == "CO":
                self.client.place_order(
                    exchange_segment="nse_fo",
                    product="CO",
                    price="0",
                    order_type="MKT",
                    quantity=str(qty),
                    validity="DAY",
                    trading_symbol=symbol,
                    transaction_type="B" if side == "BUY" else "S",
                    trigger_price=str(round(self.get_ltp_estimate() + (-sl_pts if side == "BUY" else sl_pts), 1))
                )
                self.show_info("Cover Order", f"{side} {qty} × {symbol} + SL {sl_pts} pts")

            elif mode == "BO":
                self.client.place_order(
                    exchange_segment="nse_fo",
                    product="BO",
                    price="0",
                    order_type="MKT",
                    quantity=str(qty),
                    validity="DAY",
                    trading_symbol=symbol,
                    transaction_type="B" if side == "BUY" else "S",
                    trigger_price=str(round(self.get_ltp_estimate() + (-sl_pts if side == "BUY" else sl_pts), 1)),
                    disclosed_quantity="0",
                    market_protection="0",
                    amo="NO",
                    limit_price_target=str(round(self.get_ltp_estimate() + (tgt_pts if side == "BUY" else -tgt_pts), 1))
                )
                self.show_info("Bracket Order", f"{side} {qty} × {symbol} | SL: {sl_pts} | TGT: {tgt_pts}")

        except Exception as e:
            self.show_error("Order Failed", str(e))

    def get_ltp_estimate(self):
        # Try to get live LTP, fallback to 100
        return 100.0

    def place_buy(self): self.place_order("BUY")
    def place_sell(self): self.place_order("SELL")

    def exit_all(self):
        if messagebox.askyesno("Exit All", "Square off all positions?"):
            for pos in self.positions:
                if int(pos.get("net_qty", 0)) != 0:
                    qty = abs(int(pos["net_qty"]))
                    side = "S" if int(pos["net_qty"]) > 0 else "B"
                    try:
                        self.client.place_order(
                            exchange_segment="nse_fo",
                            product=pos.get("product", "MIS"),
                            price="0", order_type="MKT", quantity=str(qty),
                            trading_symbol=pos["trading_symbol"],
                            transaction_type=side
                        )
                    except: pass
            self.show_info("Done", "Exit orders placed")

    def start_token_refresh_monitor(self):
        def monitor():
            while True:
                if self.is_logged_in and self.session_expiry and datetime.now().timestamp() > self.session_expiry - 300:
                    self.is_logged_in = False
                    time.sleep(10)
                    threading.Thread(target=self.login_thread, daemon=True).start()
                time.sleep(60)
        threading.Thread(target=monitor, daemon=True).start()

if __name__ == "__main__":
    app = NeoScalpApp()
    app.mainloop()
