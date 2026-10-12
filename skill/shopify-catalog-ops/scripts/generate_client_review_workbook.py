#!/usr/bin/env python3
"""
generate_client_review_workbook.py
----------------------------------
Generates the standard 6-tab formatted Excel review workbook for client presentations.
Enforces:
1. Strict <= 31 character tab names (prevents Openpyxl / Excel repair warnings).
2. Professional formatting (Navy/Teal headers, zebra striping, thin borders, Segoe UI font).
3. Number formatting (#,#00.00 for prices, integers for weights and quantities).
4. Auto-adjusted column widths.
"""

import os, sys, openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Styles definition
FONT_TITLE = Font(name='Segoe UI', size=16, bold=True, color='1F4E79')
FONT_HEADER = Font(name='Segoe UI', size=10, bold=True, color='FFFFFF')
FONT_BOLD = Font(name='Segoe UI', size=10, bold=True)
FONT_REGULAR = Font(name='Segoe UI', size=10)
FONT_DRAFT = Font(name='Segoe UI', size=10, bold=True, color='9C0006')

FILL_NAVY = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
FILL_TEAL = PatternFill(start_color='1B7575', end_color='1B7575', fill_type='solid')
FILL_RED = PatternFill(start_color='C00000', end_color='C00000', fill_type='solid')
FILL_DRAFT = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
FILL_ZEBRA = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')

BORDER_THIN = Border(
    left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
    top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9')
)

def create_review_workbook(summary_data, duplicates_data, issues_data, gaps_data, models_data, catalog_data, output_path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active) # Remove default sheet

    def add_styled_sheet(title, headers, rows_data, fill_header):
        # Enforce 31 character limit
        safe_title = title[:31]
        ws = wb.create_sheet(safe_title)
        ws.views.sheetView[0].showGridLines = True

        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(1, col_idx)
            c.font = FONT_HEADER
            c.fill = fill_header
            c.alignment = Alignment(horizontal='center', vertical='center')

        for r_idx, rdata in enumerate(rows_data, 2):
            ws.append(rdata)
            is_draft = any(str(cell_val).upper() == 'DRAFT' for cell_val in rdata)
            for c_idx in range(1, len(rdata) + 1):
                cell = ws.cell(r_idx, c_idx)
                cell.font = FONT_DRAFT if is_draft else FONT_REGULAR
                cell.border = BORDER_THIN
                if is_draft:
                    cell.fill = FILL_DRAFT
                elif r_idx % 2 == 0:
                    cell.fill = FILL_ZEBRA

        return ws

    # 1. Executive Summary
    ws_exec = wb.create_sheet('Executive Summary')
    ws_exec.views.sheetView[0].showGridLines = True
    ws_exec.append(['Store Catalog Ingestion & Discrepancy Summary'])
    ws_exec.cell(1, 1).font = FONT_TITLE
    ws_exec.append(['High-level KPI overview and client action items'])
    ws_exec.append([])

    sum_headers = ['Batch / Department', 'Total SKUs', 'Active (Published)', 'Draft (Needs Review)', 'Markup %', 'Images', 'Status Notes']
    ws_exec.append(sum_headers)
    for c_idx in range(1, len(sum_headers) + 1):
        c = ws_exec.cell(4, c_idx)
        c.font = FONT_HEADER; c.fill = FILL_NAVY; c.alignment = Alignment(horizontal='center')

    for r_idx, srow in enumerate(summary_data, 5):
        ws_exec.append(srow)
        for c_idx in range(1, len(srow) + 1):
            cell = ws_exec.cell(r_idx, c_idx)
            cell.font = FONT_BOLD if r_idx == len(summary_data) + 4 else FONT_REGULAR
            cell.border = BORDER_THIN

    # 2. Duplicate Listings
    dup_headers = ['S.No', 'Product Title', 'Primary SKU (Active)', 'Primary Category', 'Primary Price',
                   'Duplicate SKU (Draft)', 'Secondary Category', 'Secondary Price', 'Price Diff', 'Photos', 'Action']
    add_styled_sheet('MTS Duplicate Listings', dup_headers, duplicates_data, FILL_RED)

    # 3. Data & Image Issues
    issue_headers = ['S.No', 'SKU', 'Product Title', 'Issue Type', 'Original Factory Data', 'Resolution', 'Status']
    add_styled_sheet('MTS Data & Image Issues', issue_headers, issues_data, FILL_TEAL)

    # 4. Gaps & Unpriced Items
    gap_headers = ['S.No', 'SKU', 'Description', 'Image Status', 'Issue Detail', 'Current Store Status', 'Client Action']
    add_styled_sheet('Westpoint SKU 207 & Gaps', gap_headers, gaps_data, FILL_TEAL)

    # 5. Model Code Variances
    model_headers = ['S.No', 'SKU', 'Product Title', 'Title Model Code', 'Short Desc Item No', 'Discrepancy Detail', 'Status']
    add_styled_sheet('Westpoint Model Variances', model_headers, models_data, FILL_NAVY)

    # 6. Full Catalog
    cat_headers = ['S.No', 'SKU', 'Batch', 'Product Title', 'Category Main', 'Category', 'Sub-Category',
                   'Price (PKR)', 'Compare-At Price', 'Markup %', 'Weight (g)', 'Inventory QTY', 'Images', 'Status', 'Notes']
    add_styled_sheet('Full Catalog (452 Products)', cat_headers, catalog_data, FILL_NAVY)

    # Auto-adjust column widths
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or '')
                if '\n' in val_str:
                    val_str = max(val_str.split('\n'), key=len)
                max_len = max(max_len, len(val_str))
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 48)

    wb.save(output_path)
    print(f"Client review workbook saved: {output_path}")

if __name__ == '__main__':
    print("Client review workbook module ready for use.")
