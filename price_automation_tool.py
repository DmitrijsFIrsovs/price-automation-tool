
import gspread
import time
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
import re

import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext

# ---------------- Configuration ----------------

ADMIN_URL = "YOUR_ADMIN_URL"

USERNAME = "YOUR_USERNAME"
PASSWORD = "YOUR_PASSWORD"

SPREADSHEET_NAME = "YOUR_SPREADSHEET"
WORKSHEET_NAME = "PRICE UPDATE"

CREDENTIALS_FILE = "credentials.json"

# ----------------------------------------------

CATEGORIES = {
    "LAPTOPS RENEW":  {"cols": {"code": 42, "rd": 44, "1a": 45, "varle": 46, "shop": 43}},
    "LAPTOPS NEW":    {"cols": {"code": 61, "rd": 63, "1a": 64, "varle": 65, "shop": 62}},
    "PC RENEW":       {"cols": {"code": 4,  "rd": 6,  "1a": 7,  "varle": 8,  "shop": 5 }},
    "PC NEW":         {"cols": {"code": 23, "rd": 25, "1a": 26, "varle": 27, "shop": 24}},
}


def parse_ranges(ranges_str):

    result = set()

    for part in ranges_str.split(","):

        match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", part)

        if match:

            start, end = int(match.group(1)), int(match.group(2))

            result.update(range(start, end + 1))

        else:

            if part.strip().isdigit():
                result.add(int(part.strip()))

    return sorted(result)


def check_versions():

    try:

        edge_ver = subprocess.run(["msedge", "--version"], capture_output=True, text=True)

        print(f"Microsoft Edge: {edge_ver.stdout.strip()}")

    except FileNotFoundError:

        print("Microsoft Edge was not found.")

    try:

        driver_ver = subprocess.run(["msedgedriver", "--version"], capture_output=True, text=True)

        print(f"Microsoft Edge WebDriver: {driver_ver.stdout.strip()}")

    except FileNotFoundError:

        print("Microsoft Edge WebDriver was not found.")


check_versions()


def start_driver():

    opts = Options()

    driver = webdriver.Edge(options=opts)

    wait = WebDriverWait(driver, 7)

    driver.get(ADMIN_URL)

    wait.until(EC.presence_of_element_located((By.NAME, "login")))

    driver.find_element(By.NAME, "login").send_keys(USERNAME)

    driver.find_element(By.NAME, "passw").send_keys(PASSWORD)

    driver.find_element(By.XPATH, "//input[@type='submit']").click()

    wait.until(EC.presence_of_element_located((By.NAME, "search_query")))

    return driver, wait


def main_workflow(category, ranges_str, output_widget, update_options):

    def log(msg):

        output_widget.config(state='normal')

        output_widget.insert(tk.END, msg + '\n')

        output_widget.see(tk.END)

        output_widget.config(state='disabled')

        output_widget.update_idletasks()

    try:

        log(f"Selected category: {category}")

        log(f"Selected rows: {ranges_str}")

        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']

        creds = ServiceAccountCredentials.from_json_keyfile_name(
            CREDENTIALS_FILE,
            scope
        )

        client = gspread.authorize(creds)

        sheet = client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)

        rows = sheet.get_all_values()

        col_code  = CATEGORIES[category]["cols"]["code"]
        col_rd    = CATEGORIES[category]["cols"]["rd"]
        col_1a    = CATEGORIES[category]["cols"]["1a"]
        col_varle = CATEGORIES[category]["cols"]["varle"]
        col_shop  = CATEGORIES[category]["cols"]["shop"]

        indices = parse_ranges(ranges_str)

        codes_and_prices = []

        for idx in indices:

            if idx - 1 >= len(rows):
                continue

            row = rows[idx - 1]

            row += [''] * (max(col_code, col_rd, col_1a, col_varle, col_shop) + 1 - len(row))

            code        = row[col_code].strip()
            price_rd    = row[col_rd].strip()
            price_1a    = row[col_1a].strip()
            price_varle = row[col_varle].strip()
            price_shop  = row[col_shop].strip()

            if code:

                codes_and_prices.append((code, price_rd, price_1a, price_varle, price_shop))

        log("Products to update:")

        log(str(codes_and_prices))

        driver, wait = start_driver()

        log("Processing products:")

        for code, price_rd, price_1a, price_varle, price_shop in codes_and_prices:

            log(f"Processing: {code} -> RD: {price_rd}, 1A: {price_1a}, VARLE: {price_varle}, SHOP: {price_shop}")

            try:

                

                wait.until(EC.presence_of_element_located((By.NAME, "search_query")))

                search_field = driver.find_element(By.NAME, "search_query")

                search_field.clear()

                search_field.send_keys(code)

                driver.find_element(By.NAME, "q").click()

                time.sleep(1.5)

                rows_web = driver.find_elements(By.XPATH, "//tr[td]")

                found = False

                for row_web in rows_web:

                    tds = row_web.find_elements(By.TAG_NAME, "td")

                    if not tds or len(tds) < 3:
                        continue

                    code_td = tds[1]

                    if code_td.text.strip() == code:

                        name_td = tds[2]

                        links = name_td.find_elements(By.TAG_NAME, "a")

                        for link in links:

                            href = link.get_attribute("href")

                            if href and "edit_product.php" in href and code in href:

                                link.click()

                                found = True
                                break

                    if found:
                        break

                if not found:

                    log(f"Product {code} was not found.")

                    continue

                time.sleep(1.5)

                price_inputs = driver.find_elements(By.NAME, "product_rd_price")

                visible_inputs = [i for i in price_inputs if i.is_displayed()]

                if visible_inputs:

                    price_input = visible_inputs[0]

                else:

                    accordion_btn = wait.until(EC.element_to_be_clickable((By.ID, "price_options_table_accordion_btn")))

                    accordion_btn.click()

                    time.sleep(1)

                    price_input = wait.until(EC.visibility_of_element_located((By.NAME, "product_rd_price")))

                price_1a_input = driver.find_element(By.NAME, "product_1a_price")

                price_varle_input = driver.find_element(By.NAME, "product_varle_price")

                try:
                    shop_input = driver.find_element(By.NAME, "product_end_price")
                except Exception:
                    shop_input = driver.find_element(By.ID, "red")

                current_rd = price_input.get_attribute('value').replace(',', '.').strip()
                current_1a = price_1a_input.get_attribute('value').replace(',', '.').strip()
                current_varle = price_varle_input.get_attribute('value').replace(',', '.').strip()
                current_shop = shop_input.get_attribute('value').replace(',', '.').strip()

                need_update = False

                if update_options["rd"] and price_rd:
                    if current_rd != str(price_rd):
                        price_input.clear()
                        price_input.send_keys(str(price_rd))
                        need_update = True

                if update_options["1a"] and price_1a:
                    if current_1a != str(price_1a):
                        price_1a_input.clear()
                        price_1a_input.send_keys(str(price_1a))
                        need_update = True

                if update_options["varle"] and price_varle:
                    if current_varle != str(price_varle):
                        price_varle_input.clear()
                        price_varle_input.send_keys(str(price_varle))
                        need_update = True

                if update_options["shop"] and price_shop:
                    if current_shop != str(price_shop):
                        shop_input.clear()
                        shop_input.send_keys(str(price_shop))
                        need_update = True

                if not need_update:

                    log(f" {code}: Prices are already up to date. Skipping.")

                    continue

                save_button = wait.until(EC.element_to_be_clickable((
                    By.XPATH, "//input[@type='button' and contains(@value, 'Запомнить')]"
                )))

                save_button.click()

                time.sleep(2)

            except Exception as e:

                log(f"Error while processing {code}: {e}")

        log("Done!")

        driver.quit()

    except Exception as e:

        log(f"Critical error: {e}")


def start_callback():

    category = cat_var.get()

    ranges_str = range_entry.get()

    update_options = {
        "rd": rd_var.get(),
        "1a": a1_var.get(),
        "varle": varle_var.get(),
        "shop": shop_var.get()
    }

    output_text.config(state='normal')
    output_text.delete('1.0', tk.END)
    output_text.config(state='disabled')

    root.after(100, main_workflow, category, ranges_str, output_text, update_options)


# ---------------- GUI ----------------

root = tk.Tk()

root.title('Price Automation Tool')

tk.Label(root, text='Category').grid(row=0, column=0)

cat_var = tk.StringVar(value=list(CATEGORIES.keys())[0])

cat_combo = ttk.Combobox(root, textvariable=cat_var, values=list(CATEGORIES.keys()), state="readonly")

cat_combo.grid(row=0, column=1)

tk.Label(root, text="Row Range").grid(row=1, column=0)

range_entry = tk.Entry(root)

range_entry.insert(0, "2-10")

range_entry.grid(row=1, column=1)

tk.Label(root, text="Update Prices").grid(row=2, column=0)

rd_var = tk.BooleanVar(value=True)
a1_var = tk.BooleanVar(value=True)
varle_var = tk.BooleanVar(value=True)
shop_var = tk.BooleanVar(value=True)

tk.Checkbutton(root, text="RD", variable=rd_var).grid(row=3, column=0)
tk.Checkbutton(root, text="1A", variable=a1_var).grid(row=3, column=1)
tk.Checkbutton(root, text="VARLE", variable=varle_var).grid(row=4, column=0)
tk.Checkbutton(root, text="SHOP", variable=shop_var).grid(row=4, column=1)

start_btn = tk.Button(root, text='Start', command=start_callback)

start_btn.grid(row=5, column=0)

exit_btn = tk.Button(root, text='Exit', command=root.destroy)

exit_btn.grid(row=5, column=1)

output_text = scrolledtext.ScrolledText(root, width=100, height=30, state='disabled')

output_text.grid(row=6, column=0, columnspan=2)

root.mainloop()
